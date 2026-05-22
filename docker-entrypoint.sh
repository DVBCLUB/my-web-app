#!/bin/sh
set -eu

mkdir -p /tmp/fastrack

if [ ! -f "${ACCOUNTING_DB_PATH}" ] && [ -f /app/PythonApplication1/data/accounting.db ]; then
  cp /app/PythonApplication1/data/accounting.db "${ACCOUNTING_DB_PATH}"
fi

exec "$@"
