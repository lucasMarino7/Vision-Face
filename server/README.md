# Vision Face server

## Containers

1. Copie `.env.example` para `.env` e substitua as senhas de exemplo.
2. Execute `docker compose up --build` a partir deste diretório.
3. A interface Flask estará em `http://localhost:8000/` e a verificação da API em `http://localhost:8000/api/health`.

O serviço `backend` executa as migrations antes de iniciar o Gunicorn. O PostgreSQL usa a imagem com pgvector e persiste os dados no volume `postgres_data`.

Para interromper os serviços, use `docker compose down`. Para também apagar o banco local, use `docker compose down -v`.
