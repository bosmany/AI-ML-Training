#!/usr/bin/env bash
# Reference/manual demo of the k8s/ manifests on a real kind cluster: create cluster -> build image
# -> load it into the cluster -> apply manifests -> real rolling update -> real rollback -> cleanup.
#
# This script is NOT part of the pytest-graded contract. It needs `kind` and a real cluster, neither
# of which is available in the sandbox this lab was built in (creating a kind cluster needs
# privileges - nested containers/cgroups/iptables - that this sandbox intentionally does not grant).
# It IS written to be correct and runnable as-is by a human on a normal machine with Docker + kind +
# kubectl installed. Run it from the lab root: `bash scripts/kind_demo.sh`.
#
# What "real rolling update" and "real rollback" mean here: this script builds TWO images from the
# SAME solution/assets Dockerfile - v1 as-is, and v2 with one visible line changed (the app version
# string) - so the rollout you watch is an actual different container replacing the old one, not a
# no-op re-apply.

set -euo pipefail

CLUSTER_NAME="mlops-demo"
NAMESPACE="default"
IMAGE_NAME="mlops-real-container-deploy"
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' is required but not on PATH." >&2; exit 1; }
}

echo "==> Checking prerequisites (docker, kind, kubectl)"
require docker
require kind
require kubectl

echo "==> [1/8] Creating kind cluster '${CLUSTER_NAME}' (skips if it already exists)"
if ! kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  kind create cluster --name "${CLUSTER_NAME}"
else
  echo "    cluster already exists, reusing it"
fi
kubectl config use-context "kind-${CLUSTER_NAME}"

echo "==> [2/8] Building image v1 from solution/assets"
docker build -t "${IMAGE_NAME}:v1" "${LAB_DIR}/solution/assets"

echo "==> [3/8] Building image v2 (visibly different: bumped app version, same model)"
V2_DIR="$(mktemp -d)"
trap 'rm -rf "${V2_DIR}"' EXIT
cp -r "${LAB_DIR}/solution/assets/." "${V2_DIR}/"
sed -i 's/version="1.0.0"/version="2.0.0"/' "${V2_DIR}/app/main.py"
docker build -t "${IMAGE_NAME}:v2" "${V2_DIR}"

echo "==> [4/8] Loading both images into the kind cluster's node (no registry needed)"
kind load docker-image "${IMAGE_NAME}:v1" --name "${CLUSTER_NAME}"
kind load docker-image "${IMAGE_NAME}:v2" --name "${CLUSTER_NAME}"

echo "==> [5/8] Applying k8s manifests (Deployment pinned to v1, Service)"
sed "s#image: .*#image: ${IMAGE_NAME}:v1#" "${LAB_DIR}/k8s/deployment.yaml" | kubectl apply -f -
kubectl apply -f "${LAB_DIR}/k8s/service.yaml"
kubectl rollout status deployment/iris-model-server -n "${NAMESPACE}" --timeout=120s

echo "==> [6/8] Verifying v1 is actually reachable through the Service (port-forward + curl)"
kubectl port-forward svc/iris-model-server 18080:80 -n "${NAMESPACE}" >/tmp/kind_demo_portforward.log 2>&1 &
PF_PID=$!
sleep 3
curl -sf http://127.0.0.1:18080/health && echo
kill "${PF_PID}" 2>/dev/null || true
wait "${PF_PID}" 2>/dev/null || true

echo "==> [7/8] Real rolling update: v1 -> v2"
kubectl set image deployment/iris-model-server iris-model-server="${IMAGE_NAME}:v2" -n "${NAMESPACE}"
kubectl rollout status deployment/iris-model-server -n "${NAMESPACE}" --timeout=120s
kubectl rollout history deployment/iris-model-server -n "${NAMESPACE}"

echo "==> [8/8] Real rollback: undo back to v1, and prove it"
kubectl rollout undo deployment/iris-model-server -n "${NAMESPACE}"
kubectl rollout status deployment/iris-model-server -n "${NAMESPACE}" --timeout=120s
kubectl get deployment iris-model-server -n "${NAMESPACE}" \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'

cat <<'EOF'

Demo complete. To tear everything down:
  kind delete cluster --name mlops-demo
  docker image rm mlops-real-container-deploy:v1 mlops-real-container-deploy:v2
EOF
