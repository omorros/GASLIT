#!/usr/bin/env bash
# GASLIT — deploy the Sentinel to AWS ECS Fargate in eu-west-2 (Teammate 1).
#
# Idempotent end-to-end pipeline:
#   1. docker build -f gaslit/deploy/Dockerfile.sentinel
#   2. ECR login + push to ${ECR_REPOSITORY} (creates the repo if missing)
#   3. Register ECS task definition ${ECS_TASK_FAMILY}
#   4. Ensure ECS cluster ${ECS_CLUSTER} exists
#   5. Ensure ECS service ${ECS_SERVICE} exists; update to latest task def
#
# Requires (in .env):
#   MONGODB_URI, NVIDIA_API_KEY, ANTHROPIC_API_KEY, HMAC_SECRET
#   AWS_REGION=eu-west-2, AWS_PROFILE, AWS_ACCOUNT_ID,
#   ECR_REPOSITORY, ECS_CLUSTER, ECS_SERVICE, ECS_TASK_FAMILY
#
# The heavy lifting (ECR + ECS API calls) is done via boto3 in a Python
# helper — the macOS homebrew awscli is known flaky on this box (libexpat
# symbol mismatch against system python). boto3 in .venv works fine.
#
# Usage:
#   gaslit/deploy/deploy_sentinel_aws.sh
#   gaslit/deploy/deploy_sentinel_aws.sh --skip-build   # reuse existing local ${ECR_REPOSITORY}:${IMAGE_TAG} image only
#   gaslit/deploy/deploy_sentinel_aws.sh --tag v2       # custom image tag

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

SKIP_BUILD=0
IMAGE_TAG="latest"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-build) SKIP_BUILD=1 ;;
        --tag) shift; IMAGE_TAG="$1" ;;
        -h|--help)
            sed -n '2,25p' "$0"
            exit 0
            ;;
        *) echo "unknown flag: $1" >&2; exit 2 ;;
    esac
    shift
done

if [ -f "$REPO_ROOT/.env" ]; then
    # shellcheck disable=SC1091
    set -a; source "$REPO_ROOT/.env"; set +a
fi

: "${AWS_REGION:=eu-west-2}"
: "${AWS_PROFILE:?AWS_PROFILE env var required (expected in .env)}"
: "${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID env var required (expected in .env)}"
: "${ECR_REPOSITORY:?ECR_REPOSITORY env var required}"
: "${ECS_CLUSTER:?ECS_CLUSTER env var required}"
: "${ECS_SERVICE:?ECS_SERVICE env var required}"
: "${ECS_TASK_FAMILY:?ECS_TASK_FAMILY env var required}"
: "${MONGODB_URI:?MONGODB_URI env var required}"
: "${NVIDIA_API_KEY:?NVIDIA_API_KEY env var required}"
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY env var required}"

IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG}"

# ─── 0. Activate venv (boto3 + docker-credential helpers) ─────────────
if [ -d "$REPO_ROOT/.venv" ]; then
    # shellcheck source=/dev/null
    source "$REPO_ROOT/.venv/bin/activate"
fi
export DYLD_LIBRARY_PATH="${DYLD_LIBRARY_PATH:-/opt/homebrew/opt/expat/lib}"
export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/opt/expat/lib}"

PY_HELPER="$REPO_ROOT/gaslit/deploy/deploy_sentinel_aws.py"

# ─── 1. Build image ───────────────────────────────────────────────────
if [ "$SKIP_BUILD" = "0" ]; then
    echo "[deploy] building Sentinel image (platform linux/amd64)"
    docker buildx build \
        --platform linux/amd64 \
        --load \
        -f "$REPO_ROOT/gaslit/deploy/Dockerfile.sentinel" \
        -t "${ECR_REPOSITORY}:${IMAGE_TAG}" \
        "$REPO_ROOT"
else
    echo "[deploy] skipping docker build (--skip-build)"
    if ! docker image inspect "${ECR_REPOSITORY}:${IMAGE_TAG}" >/dev/null 2>&1; then
        echo "[deploy] ERROR: no local Docker image '${ECR_REPOSITORY}:${IMAGE_TAG}'." >&2
        echo "[deploy] Run WITHOUT --skip-build once to build, or docker pull your last pushed tag from ECR." >&2
        exit 1
    fi
fi

# ─── 2. Ensure ECR repo + login + push ────────────────────────────────
echo "[deploy] ensuring ECR repository ${ECR_REPOSITORY}"
python "$PY_HELPER" ensure-ecr

echo "[deploy] logging docker into ECR"
python "$PY_HELPER" ecr-login | \
    docker login \
        --username AWS \
        --password-stdin \
        "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "[deploy] tagging + pushing ${IMAGE_URI}"
docker tag "${ECR_REPOSITORY}:${IMAGE_TAG}" "${IMAGE_URI}"
docker push "${IMAGE_URI}"

# ─── 3. Register / update ECS cluster + task def + service ────────────
echo "[deploy] provisioning ECS cluster + task definition + service"
python "$PY_HELPER" deploy-ecs --image "${IMAGE_URI}"

echo "[deploy] done → ${IMAGE_URI} live on ${ECS_CLUSTER}/${ECS_SERVICE}"
echo "[deploy] tail logs:  aws logs tail /ecs/${ECS_TASK_FAMILY} --follow --region ${AWS_REGION} --profile ${AWS_PROFILE}"
