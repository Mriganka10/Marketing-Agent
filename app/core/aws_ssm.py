from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SsmLoadResult:
    enabled: bool
    parameter_path: str
    region: str
    values: dict[str, str] = field(default_factory=dict)

    @property
    def parameter_count(self) -> int:
        return len(self.values)


def load_runtime_ssm() -> SsmLoadResult:
    """Load application settings from SSM without exporting decrypted values to the process."""

    enabled = _as_bool(os.getenv("SSM_ENABLED"), default=False)
    path = _normalize_path(os.getenv("SSM_PARAMETER_PATH", "/marketing-agent/prod"))
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-south-1"
    if not enabled:
        return SsmLoadResult(enabled=False, parameter_path=path, region=region)

    fail_fast = _as_bool(os.getenv("SSM_FAIL_FAST"), default=True)
    try:
        client = boto3.client(
            "ssm",
            region_name=region,
            config=Config(
                connect_timeout=2,
                read_timeout=5,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        values: dict[str, str] = {}
        next_token: str | None = None
        while True:
            request: dict[str, object] = {
                "Path": path,
                "Recursive": True,
                "WithDecryption": True,
                "MaxResults": 10,
            }
            if next_token:
                request["NextToken"] = next_token
            response = client.get_parameters_by_path(**request)
            for parameter in response.get("Parameters", []):
                name = str(parameter.get("Name") or "")
                value = parameter.get("Value")
                setting_name = _setting_name(name, path)
                if setting_name and value is not None:
                    values[setting_name] = str(value)
            next_token = response.get("NextToken")
            if not next_token:
                break
        required = {
            re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
            for name in os.getenv(
                "SSM_REQUIRED_PARAMETERS", "database-url,secret-key"
            ).split(",")
            if name.strip()
        }
        missing = sorted(name for name in required if not values.get(name, "").strip())
        if missing:
            raise RuntimeError(
                f"Required SSM parameters are missing or empty under {path}: {', '.join(missing)}."
            )
        logger.info("Loaded %s application settings from SSM path %s.", len(values), path)
        return SsmLoadResult(enabled=True, parameter_path=path, region=region, values=values)
    except Exception as exc:
        if fail_fast:
            raise RuntimeError(
                f"Runtime SSM loading failed for {path} in {region}; application startup aborted."
            ) from exc
        logger.warning(
            "Runtime SSM loading failed for %s in %s; using local/environment settings because "
            "SSM_FAIL_FAST is false.",
            path,
            region,
        )
        return SsmLoadResult(enabled=True, parameter_path=path, region=region)


def _setting_name(parameter_name: str, path: str) -> str | None:
    prefix = f"{path}/"
    if not parameter_name.startswith(prefix):
        return None
    relative_name = parameter_name[len(prefix) :].strip("/")
    if not relative_name:
        return None
    return re.sub(r"[^a-z0-9]+", "_", relative_name.lower()).strip("_") or None


def _normalize_path(value: str) -> str:
    normalized = f"/{value.strip().strip('/')}"
    return normalized if normalized != "/" else "/marketing-agent/prod"


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
