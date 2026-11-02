#!/usr/bin/env bash
# Cria o cluster Kind e o banco com Terraform, faz o deploy da API com a imagem informada e testa.
# Uso: bash infra/scripts/deploy-kind-ci.sh postech-api:<tag>
set -euo pipefail

IMAGE="${1:?informe a imagem, ex.: postech-api:abc123}"
KIND_DIR=infra/terraform/environments/local-kind
DB_DIR=infra/terraform/environments/local-postgres
NODE=postech-iac-control-plane
PORT=18000

echo "== Cluster Kind (Terraform local-kind)"
terraform -chdir="$KIND_DIR" init -input=false
terraform -chdir="$KIND_DIR" apply -auto-approve -input=false
KUBECONFIG="$(terraform -chdir="$KIND_DIR" output -raw kubeconfig_path)"
export KUBECONFIG
kubectl get nodes

echo "== Banco de dados (Terraform local-postgres)"
terraform -chdir="$DB_DIR" init -input=false
terraform -chdir="$DB_DIR" apply -auto-approve -input=false
kubectl rollout status statefulset/postech-db -n postech --timeout=180s

echo "== Imagem $IMAGE no nó do Kind"
# O Kind não enxerga as imagens do Docker do host; importa direto no containerd do nó.
docker tag "$IMAGE" postech-api:ci
docker save postech-api:ci | docker exec -i "$NODE" ctr --namespace=k8s.io images import -

echo "== Manifestos da API (k8s/overlays/ci)"
kubectl apply -k k8s/overlays/ci
kubectl rollout status deployment/postech-api -n postech --timeout=300s
kubectl get pods,svc,hpa,configmap,secret -n postech

echo "== Testes de fumaça"
kubectl port-forward service/postech-api "$PORT:8000" -n postech >/dev/null 2>&1 &
PF_PID=$!
trap 'kill "$PF_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  curl -fsS "http://localhost:$PORT/api/health/" >/dev/null 2>&1 && break
  sleep 2
done

status() {
  curl -s -o /dev/null -w '%{http_code}' "$@"
}

esperar() {
  local nome=$1 esperado=$2 obtido=$3
  if [ "$obtido" != "$esperado" ]; then
    echo "FALHOU: $nome (esperado $esperado, veio $obtido)"
    exit 1
  fi
  echo "ok: $nome ($obtido)"
}

BASE="http://localhost:$PORT"
WEBHOOK_TOKEN="$(terraform -chdir="$DB_DIR" output -raw webhook_token)"

esperar "health" 200 "$(status "$BASE/api/health/")"
esperar "login" 200 "$(status -X POST "$BASE/api/token/" -H 'Content-Type: application/json' \
  -d '{"username": "atendente", "password": "oficina123"}')"
esperar "webhook sem token" 403 "$(status -X POST "$BASE/api/webhooks/orcamento/" \
  -H 'Content-Type: application/json' -d '{}')"
# Token aceito chega na validação do corpo.
esperar "webhook com token do Secret" 400 "$(status -X POST "$BASE/api/webhooks/orcamento/" \
  -H 'Content-Type: application/json' -H "X-Webhook-Token: $WEBHOOK_TOKEN" -d '{}')"

MIGRACOES="$(kubectl exec -n postech postech-db-0 -- \
  psql -U postech_user -d postech -tAc 'select count(*) from django_migrations')"
if [ "${MIGRACOES:-0}" -lt 1 ]; then
  echo "FALHOU: nenhuma migration aplicada no PostgreSQL do cluster"
  exit 1
fi
echo "ok: API usando o PostgreSQL do cluster ($MIGRACOES migrations)"
