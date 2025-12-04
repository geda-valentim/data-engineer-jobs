#!/bin/bash
# Build skills catalog: converte YAML para JSON e cria zip para Glue

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SKILLS_DIR="$PROJECT_ROOT/src/skills_detection"
CONFIG_DIR="$SKILLS_DIR/config"
OUTPUT_DIR="$PROJECT_ROOT/infra/modules/ingestion"

echo "📋 Converting skills catalog to JSON..."
python3 -c "
import yaml, json, pathlib
p = pathlib.Path('$CONFIG_DIR/skills_catalog.yaml')
out = p.with_suffix('.json')
out.write_text(json.dumps(yaml.safe_load(p.read_text()), indent=2))
print('  ✓', out)
"

echo "📦 Creating skills_detection.zip for Glue..."
cd "$PROJECT_ROOT/src"
zip -rq skills_detection.zip skills_detection/ \
    -x "*.pyc" \
    -x "*__pycache__*" \
    -x "*.yaml"
mv skills_detection.zip "$OUTPUT_DIR/"
echo "  ✓ $OUTPUT_DIR/skills_detection.zip"
