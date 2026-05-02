"""boto3-driven ECS Fargate deployer for the GASLIT Sentinel (Teammate 1).

Invoked by ``gaslit/deploy/deploy_sentinel_aws.sh``. Splits the AWS control
plane calls into small subcommands so the bash script can sequence them
alongside the docker build / push steps:

    python deploy_sentinel_aws.py ensure-ecr
    python deploy_sentinel_aws.py ecr-login           # prints password to stdout
    python deploy_sentinel_aws.py deploy-ecs --image <uri>

Why boto3 and not ``aws`` CLI?
  The homebrew ``awscli`` install on this box is broken against Python 3.14
  / system libexpat (see README troubleshooting). ``botocore[crt]`` in the
  project venv works reliably.

Idempotent: re-running after a successful deploy results in "no change" or
a rolling update to the newest task definition revision.
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("deploy")
logging.basicConfig(level=logging.INFO, format="[deploy] %(message)s")


# ─── AWS helpers ────────────────────────────────────────────────────
def _session() -> boto3.Session:
    return boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE"),
        region_name=os.environ.get("AWS_REGION", "eu-west-2"),
    )


def _region() -> str:
    return os.environ.get("AWS_REGION", "eu-west-2")


def _account_id() -> str:
    return os.environ["AWS_ACCOUNT_ID"]


# ─── ECR ────────────────────────────────────────────────────────────
def ensure_ecr(repo: str) -> str:
    ecr = _session().client("ecr")
    try:
        resp = ecr.describe_repositories(repositoryNames=[repo])
        uri = resp["repositories"][0]["repositoryUri"]
        log.info("ECR repo %s already exists (%s)", repo, uri)
        return uri
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "RepositoryNotFoundException":
            raise
    resp = ecr.create_repository(
        repositoryName=repo,
        imageScanningConfiguration={"scanOnPush": True},
        encryptionConfiguration={"encryptionType": "AES256"},
        tags=[{"Key": "project", "Value": "gaslit"}],
    )
    uri = resp["repository"]["repositoryUri"]
    log.info("created ECR repo %s (%s)", repo, uri)
    return uri


def ecr_login_password() -> str:
    ecr = _session().client("ecr")
    resp = ecr.get_authorization_token()
    token = resp["authorizationData"][0]["authorizationToken"]
    decoded = base64.b64decode(token).decode("utf-8")
    _, password = decoded.split(":", 1)
    return password


# ─── IAM ────────────────────────────────────────────────────────────
TASK_EXEC_ROLE_NAME = "gaslit-sentinel-task-exec"


TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
}


EXEC_POLICY_ARN = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"


def ensure_task_exec_role() -> str:
    iam = _session().client("iam")
    try:
        resp = iam.get_role(RoleName=TASK_EXEC_ROLE_NAME)
        log.info("task exec role %s already exists", TASK_EXEC_ROLE_NAME)
        return resp["Role"]["Arn"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchEntity":
            raise
    resp = iam.create_role(
        RoleName=TASK_EXEC_ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(TRUST_POLICY),
        Description="GASLIT Sentinel ECS task execution role",
        Tags=[{"Key": "project", "Value": "gaslit"}],
    )
    iam.attach_role_policy(RoleName=TASK_EXEC_ROLE_NAME, PolicyArn=EXEC_POLICY_ARN)
    log.info("created task exec role %s", TASK_EXEC_ROLE_NAME)
    return resp["Role"]["Arn"]


# ─── CloudWatch Logs ────────────────────────────────────────────────
def ensure_log_group(name: str) -> None:
    logs = _session().client("logs")
    try:
        logs.create_log_group(logGroupName=name)
        log.info("created log group %s", name)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceAlreadyExistsException":
            raise
        log.info("log group %s already exists", name)
    logs.put_retention_policy(logGroupName=name, retentionInDays=7)


# ─── ECS ────────────────────────────────────────────────────────────
def ensure_cluster(name: str) -> str:
    ecs = _session().client("ecs")
    resp = ecs.describe_clusters(clusters=[name])
    clusters = [c for c in resp.get("clusters", []) if c["status"] == "ACTIVE"]
    if clusters:
        log.info("cluster %s already ACTIVE", name)
        return clusters[0]["clusterArn"]
    create = ecs.create_cluster(
        clusterName=name,
        capacityProviders=["FARGATE", "FARGATE_SPOT"],
        tags=[{"key": "project", "value": "gaslit"}],
    )
    log.info("created cluster %s", name)
    return create["cluster"]["clusterArn"]


def _default_vpc_networking() -> dict:
    """Return ``{subnets, security_groups}`` from the default VPC."""
    ec2 = _session().client("ec2")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    if not vpcs["Vpcs"]:
        raise RuntimeError(
            "no default VPC in this account/region — create one or supply "
            "VPC_SUBNETS / VPC_SECURITY_GROUPS env vars"
        )
    vpc_id = vpcs["Vpcs"][0]["VpcId"]
    subnet_resp = ec2.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )
    subnets = [s["SubnetId"] for s in subnet_resp["Subnets"]]
    sg_resp = ec2.describe_security_groups(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "group-name", "Values": ["default"]},
        ],
    )
    sgs = [g["GroupId"] for g in sg_resp["SecurityGroups"]]
    return {"subnets": subnets, "security_groups": sgs}


SECRET_PASSTHROUGH_ENVS = (
    "MONGODB_URI",
    "NVIDIA_API_KEY",
    "ANTHROPIC_API_KEY",
    "HMAC_SECRET",
    "VOYAGE_API_KEY",
    "LANGSMITH_API_KEY",
    "ECS_CLUSTER",
    "ECS_SERVICE",
    "ECS_TASK_FAMILY",
)

PLAIN_ENVS = (
    "NEMOTRON_MODEL",
    "NEMOTRON_BASE_URL",
    "MONGODB_DB_NAME",
    "MONGODB_APP_NAME",
    "AWS_REGION",
    "SENTINEL_LOG_LEVEL",
)


def _build_container_env() -> list[dict]:
    env: list[dict] = []
    for name in PLAIN_ENVS + SECRET_PASSTHROUGH_ENVS:
        val = os.environ.get(name)
        if val:
            env.append({"name": name, "value": val})
    # Always force SENTINEL_MODE=local inside the ECS task: the container IS
    # the Sentinel; don't loop back into boto3 stop/start.
    env.append({"name": "SENTINEL_MODE", "value": "local"})
    return env


def register_task_definition(image: str, task_exec_role_arn: str,
                             family: str, log_group: str) -> str:
    ecs = _session().client("ecs")
    container = {
        "name": "sentinel",
        "image": image,
        "essential": True,
        "environment": _build_container_env(),
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": log_group,
                "awslogs-region": _region(),
                "awslogs-stream-prefix": "sentinel",
            },
        },
    }
    resp = ecs.register_task_definition(
        family=family,
        networkMode="awsvpc",
        requiresCompatibilities=["FARGATE"],
        cpu="512",
        memory="1024",
        executionRoleArn=task_exec_role_arn,
        taskRoleArn=task_exec_role_arn,
        containerDefinitions=[container],
        tags=[{"key": "project", "value": "gaslit"}],
    )
    arn = resp["taskDefinition"]["taskDefinitionArn"]
    log.info("registered task def %s", arn)
    return arn


def ensure_service(cluster: str, service: str, task_def_arn: str) -> None:
    ecs = _session().client("ecs")
    desc = ecs.describe_services(cluster=cluster, services=[service])
    existing = [s for s in desc.get("services", []) if s["status"] != "INACTIVE"]
    net = _default_vpc_networking()
    network_config = {
        "awsvpcConfiguration": {
            "subnets": net["subnets"],
            "securityGroups": net["security_groups"],
            "assignPublicIp": "ENABLED",
        },
    }
    if existing:
        log.info("service %s exists — updating task def + desiredCount=1", service)
        ecs.update_service(
            cluster=cluster,
            service=service,
            desiredCount=1,
            taskDefinition=task_def_arn,
            networkConfiguration=network_config,
            forceNewDeployment=True,
        )
        return
    log.info("creating service %s", service)
    ecs.create_service(
        cluster=cluster,
        serviceName=service,
        taskDefinition=task_def_arn,
        desiredCount=1,
        launchType="FARGATE",
        networkConfiguration=network_config,
        tags=[{"key": "project", "value": "gaslit"}],
    )


# ─── CLI ────────────────────────────────────────────────────────────
def cmd_ensure_ecr(_args) -> int:
    repo = os.environ["ECR_REPOSITORY"]
    uri = ensure_ecr(repo)
    print(uri)
    return 0


def cmd_ecr_login(_args) -> int:
    pw = ecr_login_password()
    sys.stdout.write(pw)
    return 0


def cmd_deploy_ecs(args) -> int:
    cluster = os.environ["ECS_CLUSTER"]
    service = os.environ["ECS_SERVICE"]
    family = os.environ["ECS_TASK_FAMILY"]
    log_group = f"/ecs/{family}"
    image = args.image or f"{_account_id()}.dkr.ecr.{_region()}.amazonaws.com/{os.environ['ECR_REPOSITORY']}:latest"

    ensure_cluster(cluster)
    ensure_log_group(log_group)
    role_arn = ensure_task_exec_role()
    task_arn = register_task_definition(image, role_arn, family, log_group)
    ensure_service(cluster, service, task_arn)
    log.info("deploy complete — image=%s task=%s", image, task_arn)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ensure-ecr").set_defaults(fn=cmd_ensure_ecr)
    sub.add_parser("ecr-login").set_defaults(fn=cmd_ecr_login)
    d = sub.add_parser("deploy-ecs")
    d.add_argument("--image", help="Full ECR image URI to deploy")
    d.set_defaults(fn=cmd_deploy_ecs)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
