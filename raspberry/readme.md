### Configurações:

- Modelo da raspberry: raspberry pi 5 8gb
- Modelo do sistema operacional: Raspberry Pi OS (64-bit)
- Habiitado SSH
- Configurado hostname para ser utilizado na conexão ssh: pi5
- Configurado usuário admin com username: lucas, e uma senha
- Configurado credenciais do wifi para ser utilizado na conexão SSH durante etapas de desenvolvimento, e também utilizado para comunicação com o servidor

### Etapas de teste:

- Após instalar o OS na raspberry, conectei via SSH com meu computado através do VS code utilizando a extensão "Remote SSH" da microsoft:
  - ssh "username"@"hostname".local -> ssh lucas@pi5.local
  - E logo em seguida tive que inserir a senha configurada para o usuário "lucas"
- Após conexão SSH estabelecida, atualizei o software da raspberry:
  - sudo apt update
  - sudo apt full-upgrade
- Depois criei uma pasta Projetos em /home/lucas/ na raspberry através do SSH
- Logo após isso fiz com git clone deste projeto para minha raspberry conseguir acessar o código atualizado no github e também para minha raspberry conseguir adicionar novos commit ao repositório no github quando estiver em desenvolvimento.
- crie um ambiente virtual na raspberry com:  python3 -m venv raspberry/.venv --system-site-
packages
- logo após, dentro da venv fiz update do pip: pip install --upgrade pip
