#!/bin/bash
set -e

ENVIRONMENT="${1:-dev}"  # dev por default
PROJECT_NAME="data-engineer-jobs"
REGION="us-east-1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="$SCRIPT_DIR/../secrets/secrets.env"

if [ ! -f "$SECRETS_FILE" ]; then
  echo "❌ Arquivo $SECRETS_FILE não encontrado."
  echo "   Copie secrets.env.example para secrets.env e preencha as chaves."
  exit 1
fi

echo "🔐 Carregando segredos de $SECRETS_FILE..."
set -a
source "$SECRETS_FILE"
set +a

echo "🚀 Enviando segredos para o SSM ($ENVIRONMENT)..."

aws ssm put-parameter \
  --name "/$PROJECT_NAME/$ENVIRONMENT/brightdata/api-key" \
  --type "SecureString" \
  --value "$BRIGHTDATA_API_KEY" \
  --overwrite \
  --region "$REGION"

# Exemplo pra outra API:
# aws ssm put-parameter \
#   --name "/$PROJECT_NAME/$ENVIRONMENT/another/api-key" \
#   --type "SecureString" \
#   --value "$ANOTHER_API_KEY" \
#   --overwrite \
#   --region "$REGION"

echo "✅ Segredos sincronizados com sucesso para $ENVIRONMENT."
