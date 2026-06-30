from __future__ import annotations

import ast
import json
from typing import Any


def coerce_text(value: Any, fallback: str = "") -> str:
    parsed = _parse_structured_string(value)
    if isinstance(parsed, dict):
        return _dict_to_text(parsed, fallback)
    if isinstance(parsed, list):
        parts = [coerce_text(item) for item in parsed]
        return _clean_text(" ".join(part for part in parts if part), fallback)
    if parsed is None:
        return fallback
    return _clean_text(str(parsed), fallback)


def normalize_sections(value: Any, fallback: list[dict[str, str]]) -> list[dict[str, str]]:
    parsed = _parse_structured_string(value)
    if not isinstance(parsed, list):
        parsed = fallback

    sections: list[dict[str, str]] = []
    for item in parsed:
        if isinstance(item, dict):
            heading = coerce_text(
                item.get("heading") or item.get("title") or item.get("name"),
                "Section",
            )
            body = coerce_text(item.get("body") or item.get("copy") or item.get("content"), "")
        else:
            heading = "Section"
            body = coerce_text(item, "")
        if body:
            sections.append({"heading": heading, "body": body})

    return sections or fallback


def normalize_seo(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_structured_string(value)
    return parsed if isinstance(parsed, dict) else fallback


def _parse_structured_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped or stripped[0] not in "{[":
        return value

    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(stripped)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
    return value


def _dict_to_text(value: dict[str, Any], fallback: str) -> str:
    primary = (
        value.get("body")
        or value.get("copy")
        or value.get("content")
        or value.get("description")
        or value.get("text")
    )
    heading = value.get("heading") or value.get("title")
    cta = value.get("cta")

    parts = [coerce_text(item) for item in (heading, primary, cta) if item]
    return _clean_text(" ".join(parts), fallback)


def _clean_text(value: str, fallback: str) -> str:
    cleaned = " ".join(value.replace("\\n", " ").split())
    return cleaned or fallback

