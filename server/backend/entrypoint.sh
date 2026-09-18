#!/bin/sh
set -eu

echo "Aplicando migrations..."
# Executa as migrations do banco de dados usando Flask-Migrate, assim caso tenha uma nova versão de migration, o banco de dados será atualizado automaticamente
flask --app backend.main:app db upgrade

echo "Iniciando aplicação Flask..."
exec gunicorn --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-2}" "backend.main:app"
