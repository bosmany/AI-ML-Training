#!/usr/bin/env bash
# Manual, real end-to-end verification for a human who has `terraform` (and the `aws` CLI)
# installed - the automated pytest suite in tests/ cannot use either because this lab was
# built in a sandbox without the terraform binary, so it re-implements the create/verify
# steps directly with boto3 instead. This script exercises the REAL terraform/*.tf files.
#
# What it does, in order:
#   1. starts a real LocalStack container (community edition, pinned version)
#   2. terraform init / plan / apply against it
#   3. terraform show (prints real applied state)
#   4. verifies the bucket, role and Lambda with the real `aws` CLI against LocalStack
#   5. invokes the real Lambda and prints its real response
#   6. terraform destroy, then removes the container (runs even if a step above fails)
#
# Usage: ./scripts/manual_verify.sh
# Requires: docker, terraform >= 1.5, aws CLI v2 (only for the verification step - terraform
# itself does not need it).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="$(dirname "$HERE")"
TF_DIR="$LAB_DIR/terraform"
CONTAINER="tf-localstack-manual-verify-$$"
PORT="${LOCALSTACK_PORT:-4566}"
ENDPOINT="http://localhost:$PORT"

cleanup() {
  echo
  echo "--- tearing down ---"
  (cd "$TF_DIR" && terraform destroy -auto-approve -var "localstack_endpoint=$ENDPOINT") || true
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  rm -rf "$TF_DIR/.build" "$TF_DIR/.terraform" "$TF_DIR/.terraform.lock.hcl" \
         "$TF_DIR/terraform.tfstate" "$TF_DIR/terraform.tfstate.backup" "$TF_DIR/tfplan"
}
trap cleanup EXIT

command -v terraform >/dev/null || { echo "terraform not found on PATH" >&2; exit 1; }
command -v docker >/dev/null || { echo "docker not found on PATH" >&2; exit 1; }

echo "--- starting LocalStack (localstack/localstack:3.8.1) on port $PORT ---"
docker run -d --name "$CONTAINER" -p "$PORT:4566" \
  -e SERVICES=s3,iam,lambda,sts,logs \
  -v /var/run/docker.sock:/var/run/docker.sock \
  localstack/localstack:3.8.1

echo "--- waiting for LocalStack health ---"
for _ in $(seq 1 60); do
  if curl -fs "$ENDPOINT/_localstack/health" 2>/dev/null | grep -q '"s3": *"available"'; then
    echo "LocalStack is healthy."
    break
  fi
  sleep 1
done

echo "--- terraform init / plan / apply ---"
cd "$TF_DIR"
terraform init -input=false
terraform plan -out=tfplan -var "localstack_endpoint=$ENDPOINT"
terraform apply -auto-approve tfplan

echo "--- terraform show (real applied state) ---"
terraform show

BUCKET="$(terraform output -raw bucket_arn | sed 's#arn:aws:s3:::##')"
ROLE="$(terraform output -raw role_arn | sed 's#.*/##')"
FUNCTION="$(basename "$(terraform output -raw function_arn)")"

echo
echo "--- verifying with the real aws CLI against LocalStack ---"
aws --endpoint-url="$ENDPOINT" s3api get-bucket-versioning --bucket "$BUCKET"
aws --endpoint-url="$ENDPOINT" s3api get-bucket-encryption --bucket "$BUCKET"
aws --endpoint-url="$ENDPOINT" s3api get-public-access-block --bucket "$BUCKET"
aws --endpoint-url="$ENDPOINT" iam get-role --role-name "$ROLE"
aws --endpoint-url="$ENDPOINT" iam list-role-policies --role-name "$ROLE"

echo
echo "--- invoking the real Lambda ---"
aws --endpoint-url="$ENDPOINT" lambda invoke --function-name "$FUNCTION" \
  --payload '{"text":"hello from manual_verify.sh"}' \
  --cli-binary-format raw-in-base64-out /tmp/tf-localstack-invoke-response.json
cat /tmp/tf-localstack-invoke-response.json
echo
rm -f /tmp/tf-localstack-invoke-response.json

echo
echo "--- all checks passed; tearing down (terraform destroy + container removal) ---"
