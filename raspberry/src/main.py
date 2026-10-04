# criar models com sqlalchemy
# criar tabela intermédiaria (outbox_peron) para lidar com a dupla escrita somente ocorrida quando uma pessoa for deletada, para que o chromaDB não fique com dados órfãos
# criar tabela de versionamento (sync_change) para operação feita com a api 'delta', seja armazenado a versão nesta tabela (não será usado a rota 'full', apenas será usada a rota 'delta' para sincronização incremental)

# criar chromaDB
# em seu metados irá armazenar o id da pessoa, o id da embedding e o angulo do rosto

# criar rotas para acesso da api

# criar código com thread para fazer sincronização dos dados assincrona
# lidar com dupla escrita no chromaDB e no banco de dados relacional quando houver a deleção de uma pessoa
# a theread irá ser rodada a cada 30 segundos, irá verificar se deve fazer sincronização da tabela de pessoas no sqlite e depois a sincronização das embeddings no chromaDB e depois alterações na tabela de outbox_person

# criar código para fazer o reconhecimento facial
# criar mutex para evitar conflitos de acesso simultaneo ao sqlite e chromaDB
# criar dicionário para armazenar na memória todas as pessoas, sendo que a chave será o id da pessoa, dessa forma não será necessário ficar acessando o sqlite a cada frame
# quando houver alguma alteração no banco de dados relacional, atualizar o dicionário em memória e o chromaDB

# criar código para envio dos dados via websockets
# criar código para stream via webrtc
