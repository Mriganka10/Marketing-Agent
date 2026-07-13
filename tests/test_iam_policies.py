from deploy.iam_policies import ssm_parameter_read_policy


def test_ssm_parameter_policy_is_limited_to_production_path():
    policy = ssm_parameter_read_policy(
        region="ap-south-1",
        account_id="123456789012",
        parameter_path="/marketing-agent/prod/",
        kms_key_arn="arn:aws:kms:ap-south-1:123456789012:key/example",
    )

    ssm_statement, kms_statement = policy["Statement"]
    assert ssm_statement == {
        "Sid": "ReadMarketingAgentRuntimeParameters",
        "Effect": "Allow",
        "Action": "ssm:GetParametersByPath",
        "Resource": (
            "arn:aws:ssm:ap-south-1:123456789012:"
            "parameter/marketing-agent/prod/*"
        ),
    }
    assert kms_statement["Action"] == "kms:Decrypt"
    assert kms_statement["Resource"] == "arn:aws:kms:ap-south-1:123456789012:key/example"
    assert kms_statement["Condition"] == {
        "StringEquals": {"kms:ViaService": "ssm.ap-south-1.amazonaws.com"}
    }


def test_ssm_parameter_policy_normalizes_relative_path():
    policy = ssm_parameter_read_policy(
        region="us-east-1",
        account_id="123456789012",
        parameter_path="marketing-agent/prod",
    )

    statement = policy["Statement"][0]
    assert statement["Resource"].endswith("parameter/marketing-agent/prod/*")
