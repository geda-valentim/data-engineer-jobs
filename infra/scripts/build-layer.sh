#!/bin/bash
set -e

# --- Checagem de dependências ---
if ! command -v zip >/dev/null 2>&1; then
  echo "❌ Dependência 'zip' não encontrada."
  echo "   Instale com, por exemplo (Ubuntu/WSL):"
  echo "   sudo apt-get update && sudo apt-get install -y zip"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LAYER_DIR="$PROJECT_ROOT/infra/layers/python-deps"
BUILD_DIR="$LAYER_DIR/python"

echo "🔨 Building Lambda Layer with Poetry (root pyproject)..."

# Limpa build anterior
rm -rf "$BUILD_DIR" "$LAYER_DIR/requirements.txt" "$LAYER_DIR/layer.zip"

mkdir -p "$BUILD_DIR"

# 👉 Exporta a partir do pyproject da RAIZ
cd "$PROJECT_ROOT"

if ! poetry export -f requirements.txt --output "$LAYER_DIR/requirements.txt" --without-hashes; then
  echo "⚠️  'poetry export' não disponível. Tentando instalar plugin poetry-plugin-export..."
  poetry self add poetry-plugin-export
  echo "🔁 Tentando de novo 'poetry export'..."
  poetry export -f requirements.txt --output "$LAYER_DIR/requirements.txt" --without-hashes
fi

# Volta pra pasta da layer
cd "$LAYER_DIR"

# Instala dependências na pasta python/
pip install -r requirements.txt --target "$BUILD_DIR" --upgrade

# Limpa lixo
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true

# Zipar a pasta python/ (estrutura correta pra Lambda)
zip -r layer.zip python -q

echo "✅ Layer criado: $LAYER_DIR/layer.zip"
echo "📦 Tamanho: $(du -h "$LAYER_DIR/layer.zip" | cut -f1)"
