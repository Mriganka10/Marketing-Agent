from __future__ import annotations


def ssm_parameter_read_policy(
    *,
    region: str,
    account_id: str,
    parameter_path: str,
    kms_key_arn: str = "*",
) -> dict[str, object]:
    """Build least-privilege runtime access for one SSM parameter hierarchy."""

    normalized_path = f"/{parameter_path.strip().strip('/')}"
    parameter_arn = f"arn:aws:ssm:{region}:{account_id}:parameter{normalized_path}"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ReadMarketingAgentRuntimeParameters",
                "Effect": "Allow",
                "Action": "ssm:GetParametersByPath",
                "Resource": [parameter_arn, f"{parameter_arn}/*"],
            },
            {
                "Sid": "DecryptMarketingAgentSecureStrings",
                "Effect": "Allow",
                "Action": "kms:Decrypt",
                "Resource": kms_key_arn,
                "Condition": {
                    "StringEquals": {"kms:ViaService": f"ssm.{region}.amazonaws.com"}
                },
            },
        ],
    }
