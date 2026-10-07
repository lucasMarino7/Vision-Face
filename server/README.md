# Vision Face — servidor

Backend Flask, banco PostgreSQL (pgvector), Redis e painel React. A documentação completa (arquitetura, variáveis de ambiente e passo a passo do Docker) está no [README da raiz](../README.md#7-rodando-o-servidor-com-docker-passo-a-passo).

Resumo:

1. Na **raiz do repositório** (não nesta pasta), copie `.env.example` para `.env` e troque senhas e segredos.
2. Execute `docker compose up --build -d` na raiz.
3. Painel em `http://localhost:3000`, API em `http://localhost:8000/api/` e Swagger em `http://localhost:8000/api/docs`.
4. `docker compose down` para parar (mantém o banco); `docker compose down -v` também apaga o banco local.

O container do backend aplica as migrations antes de iniciar o Gunicorn. O feed da câmera vem direto da Raspberry (veja [raspberry/readme.md](../raspberry/readme.md)).
