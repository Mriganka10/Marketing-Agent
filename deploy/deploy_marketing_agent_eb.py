from __future__ import annotations

import json
import time
import urllib.request
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "ap-south-1"
ACCOUNT_ID = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
APP_NAME = "marketing-agent-eb-app"
ENV_NAME = "marketing-agent-eb-prod"
CNAME_PREFIX = "marketing-agent-prod"
PUBLIC_BASE_URL = "https://agenticgrowthlabs.com"
VERSION_LABEL = f"release-{int(time.time())}"
EB_BUCKET = f"marketing-agent-eb-source-{ACCOUNT_ID}-{REGION}"
EB_EC2_SG_NAME = "marketing-agent-eb-prod-ec2-sg"
EB_SERVICE_ROLE = "marketing-agent-eb-service-role"
EB_EC2_ROLE = "marketing-agent-eb-ec2-role"
EB_INSTANCE_PROFILE = "marketing-agent-eb-ec2-profile"
RDS_SG_ID = "sg-0cd2ce77bb239265f"
SSM_PATH = "/marketing-agent/prod"
SOLUTION_STACK = "64bit Amazon Linux 2023 v4.13.3 running Docker"
SOURCE_ZIP = Path("deploy/marketing-agent-eb-source.zip")
S3_KEY = f"versions/{VERSION_LABEL}.zip"
LEGACY_RUNTIME_ENV = {
    "SECRET_KEY",
    "API_KEY",
    "DATABASE_URL",
    "OPENAI_ENABLED",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_REASONING_EFFORT",
    "OPENAI_EMBEDDING_MODEL",
    "GA4_MEASUREMENT_ID",
    "GA4_PROPERTY_ID",
    "GOOGLE_SEARCH_CONSOLE_SITE_URL",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "DATAFORSEO_ENABLED",
    "DATAFORSEO_LOGIN",
    "DATAFORSEO_PASSWORD",
    "GOOGLE_ADS_ENABLED",
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
    "GOOGLE_ADS_CUSTOMER_ID",
    "GOOGLE_ADS_API_VERSION",
    "S3_BUCKET",
}


def tags(name: str) -> list[dict[str, str]]:
    return [
        {"Key": "Name", "Value": name},
        {"Key": "Project", "Value": "Marketing-Agent"},
        {"Key": "Environment", "Value": "production"},
        {"Key": "ManagedBy", "Value": "codex"},
    ]


def eb_tags() -> list[dict[str, str]]:
    return [
        {"Key": "Project", "Value": "Marketing-Agent"},
        {"Key": "Environment", "Value": "production"},
        {"Key": "ManagedBy", "Value": "codex"},
    ]


def client(service: str):
    return boto3.client(service, region_name=REGION)


def get_default_vpc_and_subnet() -> tuple[str, list[str]]:
    ec2 = client("ec2")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        raise RuntimeError("No default VPC found")
    vpc_id = vpcs[0]["VpcId"]
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    return vpc_id, [s["SubnetId"] for s in sorted(subnets, key=lambda s: s["AvailabilityZone"])]


def ensure_bucket() -> None:
    s3 = client("s3")
    try:
        s3.head_bucket(Bucket=EB_BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=EB_BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
    s3.put_public_access_block(
        Bucket=EB_BUCKET,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    s3.put_bucket_encryption(
        Bucket=EB_BUCKET,
        ServerSideEncryptionConfiguration={"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]},
    )


def ensure_security_group(vpc_id: str) -> str:
    ec2 = client("ec2")
    groups = ec2.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": [EB_EC2_SG_NAME]}, {"Name": "vpc-id", "Values": [vpc_id]}]
    )["SecurityGroups"]
    if groups:
        sg_id = groups[0]["GroupId"]
    else:
        sg_id = ec2.create_security_group(
            GroupName=EB_EC2_SG_NAME,
            Description="Marketing Agent Elastic Beanstalk EC2 web access",
            VpcId=vpc_id,
        )["GroupId"]
        ec2.create_tags(Resources=[sg_id], Tags=tags(EB_EC2_SG_NAME))
    try:
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTP public access"}]}
            ],
        )
    except ClientError as exc:
        if exc.response["Error"].get("Code") != "InvalidPermission.Duplicate":
            raise
    try:
        ec2.authorize_security_group_ingress(
            GroupId=RDS_SG_ID,
            IpPermissions=[
                {"IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432, "UserIdGroupPairs": [{"GroupId": sg_id, "Description": "Marketing Agent EB EC2 only"}]}
            ],
        )
    except ClientError as exc:
        if exc.response["Error"].get("Code") != "InvalidPermission.Duplicate":
            raise
    return sg_id


def ensure_iam() -> None:
    iam = boto3.client("iam")
    eb_assume = {"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"elasticbeanstalk.amazonaws.com"},"Action":"sts:AssumeRole"}]}
    ec2_assume = {"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}
    try:
        iam.get_role(RoleName=EB_SERVICE_ROLE)
    except ClientError as exc:
        if exc.response["Error"].get("Code") != "NoSuchEntity":
            raise
        iam.create_role(RoleName=EB_SERVICE_ROLE, AssumeRolePolicyDocument=json.dumps(eb_assume), Tags=tags(EB_SERVICE_ROLE))
    for policy in [
        "arn:aws:iam::aws:policy/service-role/AWSElasticBeanstalkEnhancedHealth",
        "arn:aws:iam::aws:policy/AWSElasticBeanstalkManagedUpdatesCustomerRolePolicy",
    ]:
        iam.attach_role_policy(RoleName=EB_SERVICE_ROLE, PolicyArn=policy)
    try:
        iam.get_role(RoleName=EB_EC2_ROLE)
    except ClientError as exc:
        if exc.response["Error"].get("Code") != "NoSuchEntity":
            raise
        iam.create_role(RoleName=EB_EC2_ROLE, AssumeRolePolicyDocument=json.dumps(ec2_assume), Tags=tags(EB_EC2_ROLE))
    for policy in [
        "arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier",
        "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    ]:
        iam.attach_role_policy(RoleName=EB_EC2_ROLE, PolicyArn=policy)
    inline = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucket"],"Resource":[f"arn:aws:s3:::{EB_BUCKET}", f"arn:aws:s3:::{EB_BUCKET}/*", f"arn:aws:s3:::marketing-agent-prod-{ACCOUNT_ID}-{REGION}", f"arn:aws:s3:::marketing-agent-prod-{ACCOUNT_ID}-{REGION}/*"]},
            {
                "Effect": "Allow",
                "Action": ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
                "Resource": f"arn:aws:ssm:{REGION}:{ACCOUNT_ID}:parameter{SSM_PATH}/*",
            },
            {
                "Effect": "Allow",
                "Action": "kms:Decrypt",
                "Resource": "*",
                "Condition": {"StringEquals": {"kms:ViaService": f"ssm.{REGION}.amazonaws.com"}},
            },
        ],
    }
    iam.put_role_policy(RoleName=EB_EC2_ROLE, PolicyName="marketing-agent-eb-app-access", PolicyDocument=json.dumps(inline))
    try:
        iam.get_instance_profile(InstanceProfileName=EB_INSTANCE_PROFILE)
    except ClientError as exc:
        if exc.response["Error"].get("Code") != "NoSuchEntity":
            raise
        iam.create_instance_profile(InstanceProfileName=EB_INSTANCE_PROFILE, Tags=tags(EB_INSTANCE_PROFILE))
    try:
        iam.add_role_to_instance_profile(InstanceProfileName=EB_INSTANCE_PROFILE, RoleName=EB_EC2_ROLE)
    except ClientError as exc:
        if exc.response["Error"].get("Code") not in {"LimitExceeded", "EntityAlreadyExists"}:
            raise
    time.sleep(10)


def build_source_zip() -> None:
    SOURCE_ZIP.parent.mkdir(parents=True, exist_ok=True)
    include_roots = ["app", ".platform", "docs"]
    include_files = ["Dockerfile", "README.md", "pyproject.toml"]
    with zipfile.ZipFile(SOURCE_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root in include_roots:
            p = Path(root)
            if not p.exists():
                continue
            for file in p.rglob("*"):
                if file.is_file() and "__pycache__" not in file.parts:
                    zf.write(file, file.as_posix())
        for file in include_files:
            p = Path(file)
            if p.exists():
                zf.write(p, p.as_posix())


def upload_source() -> None:
    client("s3").upload_file(str(SOURCE_ZIP), EB_BUCKET, S3_KEY)


def ensure_app_and_version() -> None:
    eb = client("elasticbeanstalk")
    apps = eb.describe_applications(ApplicationNames=[APP_NAME]).get("Applications", [])
    if not apps:
        eb.create_application(ApplicationName=APP_NAME, Description="Marketing Agent Elastic Beanstalk app", Tags=eb_tags())
    try:
        eb.create_application_version(
            ApplicationName=APP_NAME,
            VersionLabel=VERSION_LABEL,
            SourceBundle={"S3Bucket": EB_BUCKET, "S3Key": S3_KEY},
            Process=True,
            Tags=eb_tags(),
        )
    except ClientError as exc:
        if exc.response["Error"].get("Code") != "InvalidParameterValue":
            raise


def existing_environment_values(eb) -> dict[str, str]:
    try:
        settings = eb.describe_configuration_settings(
            ApplicationName=APP_NAME,
            EnvironmentName=ENV_NAME,
        ).get("ConfigurationSettings", [])
    except ClientError:
        return {}
    if not settings:
        return {}
    return {
        option["OptionName"]: option.get("Value", "")
        for option in settings[0].get("OptionSettings", [])
        if option.get("Namespace") == "aws:elasticbeanstalk:application:environment"
    }


def option_settings(
    vpc_id: str,
    subnet_ids: list[str],
    ec2_sg: str,
) -> list[dict[str, str]]:
    env = {
        "APP_NAME": "Marketing Agent",
        "ENVIRONMENT": "production",
        "DATA_DIR": "/app/data",
        "PUBLIC_BASE_URL": PUBLIC_BASE_URL,
        "ALLOWED_ORIGINS": '["*"]',
        "AWS_REGION": REGION,
        "SSM_ENABLED": "true",
        "SSM_PARAMETER_PATH": SSM_PATH,
        "SSM_FAIL_FAST": "true",
        "SSM_REQUIRED_PARAMETERS": "database-url,secret-key",
    }
    settings = [
        {"Namespace":"aws:elasticbeanstalk:environment","OptionName":"EnvironmentType","Value":"SingleInstance"},
        {"Namespace":"aws:elasticbeanstalk:environment","OptionName":"ServiceRole","Value":EB_SERVICE_ROLE},
        {"Namespace":"aws:autoscaling:launchconfiguration","OptionName":"IamInstanceProfile","Value":EB_INSTANCE_PROFILE},
        {"Namespace":"aws:autoscaling:launchconfiguration","OptionName":"InstanceType","Value":"t3.micro"},
        {"Namespace":"aws:autoscaling:launchconfiguration","OptionName":"SecurityGroups","Value":ec2_sg},
        {"Namespace":"aws:ec2:vpc","OptionName":"VPCId","Value":vpc_id},
        {"Namespace":"aws:ec2:vpc","OptionName":"Subnets","Value":subnet_ids[0]},
        {"Namespace":"aws:ec2:vpc","OptionName":"AssociatePublicIpAddress","Value":"true"},
        {"Namespace":"aws:elasticbeanstalk:application:environment","OptionName":"PORT","Value":"8000"},
        {"Namespace":"aws:elasticbeanstalk:healthreporting:system","OptionName":"SystemType","Value":"enhanced"},
    ]
    for key, value in env.items():
        settings.append({"Namespace":"aws:elasticbeanstalk:application:environment","OptionName":key,"Value":value})
    return settings


def deploy_environment(vpc_id: str, subnet_ids: list[str], ec2_sg: str) -> dict:
    eb = client("elasticbeanstalk")
    envs = eb.describe_environments(ApplicationName=APP_NAME, EnvironmentNames=[ENV_NAME], IncludeDeleted=False).get("Environments", [])
    existing = existing_environment_values(eb) if envs else {}
    opts = option_settings(vpc_id, subnet_ids, ec2_sg)
    if envs:
        removals = [
            {
                "Namespace": "aws:elasticbeanstalk:application:environment",
                "OptionName": name,
            }
            for name in sorted(LEGACY_RUNTIME_ENV.intersection(existing))
        ]
        update = dict(
            EnvironmentName=ENV_NAME,
            VersionLabel=VERSION_LABEL,
            OptionSettings=opts,
        )
        if removals:
            update["OptionsToRemove"] = removals
        eb.update_environment(**update)
    else:
        eb.create_environment(
            ApplicationName=APP_NAME,
            EnvironmentName=ENV_NAME,
            CNAMEPrefix=CNAME_PREFIX,
            VersionLabel=VERSION_LABEL,
            SolutionStackName=SOLUTION_STACK,
            OptionSettings=opts,
            Tags=eb_tags(),
        )
    for _ in range(90):
        env = eb.describe_environments(ApplicationName=APP_NAME, EnvironmentNames=[ENV_NAME], IncludeDeleted=False)["Environments"][0]
        print(json.dumps({"status": env.get("Status"), "health": env.get("Health"), "url": env.get("CNAME")}, default=str))
        if env.get("Status") == "Ready" and env.get("Health") in {"Green", "Yellow", "Grey"}:
            return env
        if env.get("Status") == "Ready" and application_health_ok():
            return env
        time.sleep(30)
    raise RuntimeError("Elastic Beanstalk environment did not become ready in time")


def application_health_ok() -> bool:
    try:
        with urllib.request.urlopen(f"{PUBLIC_BASE_URL}/health", timeout=10) as response:
            status = response.status
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return False
    return status == 200 and payload.get("status") == "ok"


def main() -> None:
    vpc_id, subnet_ids = get_default_vpc_and_subnet()
    ensure_bucket()
    ensure_iam()
    ec2_sg = ensure_security_group(vpc_id)
    build_source_zip()
    upload_source()
    ensure_app_and_version()
    env = deploy_environment(vpc_id, subnet_ids, ec2_sg)
    out = {
        "region": REGION,
        "application": APP_NAME,
        "environment": ENV_NAME,
        "cname": env.get("CNAME"),
        "url": f"http://{env.get('CNAME')}",
        "version": VERSION_LABEL,
        "source_bucket": EB_BUCKET,
        "source_key": S3_KEY,
        "ec2_security_group": ec2_sg,
        "rds_security_group": RDS_SG_ID,
        "rds_instance": "marketing-agent-prod-postgres",
        "rds_endpoint": "marketing-agent-prod-postgres.c7yu6kk6ytyl.ap-south-1.rds.amazonaws.com",
        "app_s3_bucket": f"marketing-agent-prod-{ACCOUNT_ID}-{REGION}",
    }
    Path("deploy/marketing-agent-eb-output.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
