#!/usr/bin/env bash
# Резервная копия: дамп БД + data/demo/. Использование: ./scripts/backup.sh [каталог]
set -euo pipefail
OUT="${1:-backups/$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-linesight}" "${POSTGRES_DB:-linesight}" > "$OUT/db.sql"
if [ -d data/demo ]; then cp -r data/demo "$OUT/demo"; fi
echo "Резервная копия: $OUT"
