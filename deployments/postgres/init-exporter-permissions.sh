#!/bin/bash
set -e

if psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'pg_monitor'" | grep -q 1; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d "$POSTRES_DB" <<-EOSQL
      GRANT pg_monitor TO $POSTGRES_USER;
      CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
EOSQL

else
  echo "Avertissement : Le rôle pg_monitor n'existe pas ou la base de données n'est pas accessible."
fi