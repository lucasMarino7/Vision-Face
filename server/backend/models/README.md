Qualquer a atualização das models como:

- Criação/ exclusão de uma tabela
- Adição / exclusão de uma coluna de uma tabela

Para o migrate funcionar precisa primeiro rodar o docker do servidor que contem os serviços do postgress e do backend/flask, só depois pode fazer o migrate pois o alembic precisa acessa o banco de dados
Deve ser feito no terminal local (no mesmo caminho de 'flask run', sendo na pasta 'backend') o comando para criar uma nova versão no alembic da base de dados atualizada: `flask db migrate -m "descricao da alteracao"`.
Após isso bastar fazer um novo commit para o github que contem o repo desse projeto para que o coolify rode o docker compose novamente em que no docker compose contem `flask db upgrade` para atualizar o banco de dados apenas se haver uma versão mais recente em migrations
