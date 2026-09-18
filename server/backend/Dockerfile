FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

COPY backend/entrypoint.sh /entrypoint.sh

# altera as permissões do arquivo entrypoint.sh para torná-lo executável
RUN chmod +x /entrypoint.sh

# expõe a porta 8000 para permitir o acesso externo (para a internet) à aplicação Flask
EXPOSE 8000

# executa o script de entrada para iniciar a aplicação Flask e migrações do banco de dados
CMD ["/entrypoint.sh"]
