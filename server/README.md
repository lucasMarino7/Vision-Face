# Vision Face server

## Containers

1. Inicie o Docker Desktop e aguarde o engine ficar pronto.
2. No diretório `server`, copie `.env.example` para `.env`. Os valores do exemplo funcionam para desenvolvimento local; troque as senhas/segredos antes de qualquer implantação.
3. Execute `docker compose up --build -d`.
4. Acompanhe a inicialização com `docker compose ps` e `docker compose logs -f postgres backend frontend`. O backend aguarda o Postgres/Redis, aplica as migrations e só então fica saudável; o frontend aguarda a API.
5. Abra `http://localhost:3000/`. A API fica em `http://localhost:8000/` e sua documentação em `http://localhost:8000/api/docs`.

No `.env`, `DATABASE_URL` deve usar o nome de serviço `postgres` como host, não `localhost`, porque o Flask roda dentro da rede Docker. O `ENV=production` deste exemplo faz o Flask usar `DATABASE_URL`; `REDIS_HOST=redis` usa o nome do serviço Redis. Se as portas locais 3000, 8000 ou 5432 já estiverem ocupadas, altere `FRONTEND_PORT` ou `BACKEND_PORT` no `.env` (a porta 5432 do Postgres pode ser alterada em `docker-compose.yml`).

Para confirmar que a API consegue consultar o banco, use `Invoke-RestMethod http://localhost:8000/api/person/` no PowerShell; a resposta inicial esperada é uma lista JSON, possivelmente vazia. Os dados do Postgres persistem no volume `postgres_data`: `docker compose down` preserva os dados; `docker compose down -v` apaga o banco local.

O serviço `backend` executa as migrations antes de iniciar o Gunicorn. O PostgreSQL usa a imagem com pgvector e persiste os dados no volume `postgres_data`.

O feed de câmera requer um endpoint WebSocket da Raspberry com sinalização WebRTC compatível. Configure `RASPBERRY_WS_URL` para definir um endereço inicial ou informe o endereço no painel. O protocolo de mensagens está documentado em `frontend/README.md`.

Para interromper os serviços, use `docker compose down`. Para também apagar o banco local, use `docker compose down -v`.
