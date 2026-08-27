#!/usr/bin/env bash
###############################################################################
# deploy.sh — One-command cloud deployment helper
# Usage: ./scripts/deploy.sh [dev|prod]
# Prerequisites: aws-cli, terraform, kubectl, docker, envsubst
###############################################################################

set -euo pipefail

ENVIRONMENT="${1:-dev}"
REGION="eu-west-2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

###############################################################################
# Pre-flight checks
###############################################################################
info "Pre-flight checks..."
for cmd in aws terraform kubectl docker envsubst; do
  command -v "$cmd" &>/dev/null || error "Missing required tool: $cmd"
done

aws sts get-caller-identity &>/dev/null || error "AWS credentials not configured"
success "Pre-flight checks passed"

###############################################################################
# 1. Provision infrastructure with Terraform
###############################################################################
info "Step 1/4: Provisioning AWS infrastructure (Terraform)..."
cd "$ROOT_DIR/cloud/terraform"

terraform init -backend-config="environments/${ENVIRONMENT}/backend.hcl" -input=false
terraform validate
terraform plan -var-file="environments/${ENVIRONMENT}/terraform.tfvars" -out=tfplan -input=false
terraform apply -auto-approve tfplan

# Capture outputs
CLUSTER_NAME=$(terraform output -raw cluster_name)
VIDEO_BUCKET=$(terraform output -raw video_bucket_name)
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
success "Infrastructure provisioned. Cluster: $CLUSTER_NAME | Bucket: $VIDEO_BUCKET"

###############################################################################
# 2. Build & push Docker images
###############################################################################
info "Step 2/4: Building and pushing Docker images..."

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

# Create ECR repos if they don't exist
for repo in hri-backend hri-frontend; do
  aws ecr describe-repositories --repository-names "$repo" --region "$REGION" 2>/dev/null || \
    aws ecr create-repository --repository-name "$repo" --region "$REGION" \
      --image-scanning-configuration scanOnPush=true \
      --encryption-configuration encryptionType=AES256
done

# Build & push backend
docker build -t "${ECR_REGISTRY}/hri-backend:${IMAGE_TAG}" "$ROOT_DIR/backend"
docker push "${ECR_REGISTRY}/hri-backend:${IMAGE_TAG}"
docker tag "${ECR_REGISTRY}/hri-backend:${IMAGE_TAG}" "${ECR_REGISTRY}/hri-backend:latest"
docker push "${ECR_REGISTRY}/hri-backend:latest"

# Build & push frontend
docker build \
  --build-arg "NEXT_PUBLIC_API_URL=https://${DOMAIN_NAME:-hri-platform.example.com}" \
  --build-arg "NEXT_PUBLIC_WS_URL=wss://${DOMAIN_NAME:-hri-platform.example.com}" \
  -t "${ECR_REGISTRY}/hri-frontend:${IMAGE_TAG}" "$ROOT_DIR/frontend"
docker push "${ECR_REGISTRY}/hri-frontend:${IMAGE_TAG}"
docker tag "${ECR_REGISTRY}/hri-frontend:${IMAGE_TAG}" "${ECR_REGISTRY}/hri-frontend:latest"
docker push "${ECR_REGISTRY}/hri-frontend:latest"
success "Images pushed to ECR"

###############################################################################
# 3. Configure kubectl & deploy to EKS
###############################################################################
info "Step 3/4: Deploying to EKS cluster..."
aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER_NAME"

# Substitute env vars in manifests
export ECR_REGISTRY IMAGE_TAG DOMAIN_NAME \
       ACM_CERTIFICATE_ARN WAF_ACL_ARN IAM_ROLE_ARN

envsubst < "$ROOT_DIR/cloud/kubernetes/base/platform.yaml"     | kubectl apply -f -
envsubst < "$ROOT_DIR/cloud/kubernetes/base/backend-deployment.yaml" | kubectl apply -f -

# Wait for rollout
kubectl rollout status deployment/hri-backend  -n hri-platform --timeout=300s
kubectl rollout status deployment/hri-frontend -n hri-platform --timeout=300s
success "Kubernetes deployment complete"

###############################################################################
# 4. Pull VLM model in Ollama pod
###############################################################################
info "Step 4/4: Ensuring VLM model is available in Ollama..."
OLLAMA_POD=$(kubectl get pods -n hri-platform -l app=hri-ollama \
             -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$OLLAMA_POD" ]; then
  kubectl exec -n hri-platform "$OLLAMA_POD" -- ollama pull llava:13b || \
    warn "Could not pull llava:13b — may already be present or pod not ready"
else
  warn "Ollama pod not yet running — model will be pulled on first use"
fi

###############################################################################
# Summary
###############################################################################
INGRESS_URL=$(kubectl get ingress hri-ingress -n hri-platform \
              -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅  HRI Platform deployed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Environment : ${CYAN}${ENVIRONMENT}${NC}"
echo -e "  Cluster     : ${CYAN}${CLUSTER_NAME}${NC}"
echo -e "  Image tag   : ${CYAN}${IMAGE_TAG}${NC}"
echo -e "  ALB URL     : ${CYAN}${INGRESS_URL}${NC}"
echo -e "  S3 Bucket   : ${CYAN}${VIDEO_BUCKET}${NC}"
echo -e "  Region      : ${CYAN}${REGION} (London — UK data residency)${NC}"
echo ""
echo -e "  Health check: curl https://${DOMAIN_NAME:-<domain>}/api/v1/health"
echo ""
