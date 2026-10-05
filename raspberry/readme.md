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

### Sincronização dos dados

Na pasta `raspberry/src`, copie `.env.example` para `.env` e configure `API_URL` com o endereço do backend incluindo `/api/`, por exemplo `http://servidor:8000/api/`. `SYNC_INTERVAL_SECONDS` define o intervalo de consulta e, por padrão, é 30 segundos.

Instale as dependências de `raspberry/src/requirements.txt` no ambiente virtual e execute `main.py` a partir de `raspberry/src`. A sincronização usa as rotas `/sync/status` e `/sync/delta`; pessoas são consultadas por ID e embeddings pela rota `/embedding/`. O avanço da versão é salvo no SQLite para retomar após reinicializações. O Chroma e o arquivo SQLite persistem em `raspberry/src/data`.

O reconhecimento usa a câmera CSI via Picamera2 e o pacote de modelos `buffalo_l` do InsightFace (o nome é a letra “l”, como no exemplo de teste; `buffalo_1` não é um pacote padrão do InsightFace). O parâmetro `det_size=(640, 640)` define o tamanho da entrada do detector: InsightFace redimensiona o frame inteiro para essa entrada, não seleciona um recorte de 640×640 pixels da câmera. A Raspberry envia `analysis_area` com a box que cobre o frame inteiro, as dimensões originais e o tamanho de entrada do modelo. Também envia `face_detections` a cada frame analisado, incluindo uma box para cada rosto encontrado, mesmo que não seja reconhecido. O frontend desenha a área analisada com borda tracejada ciano e as boxes dos rostos por cima. O WebSocket escuta em `0.0.0.0:8765` por padrão. Na interface, informe `ws://<IP-DA-RASPBERRY>:8765` no campo de conexão; opcionalmente, configure `VITE_RASPBERRY_WS_URL` no frontend. O frontend reconecta automaticamente. Ao conectar, a Raspberry envia uma oferta WebRTC `{ "type": "offer", "sdp": { "type": "offer", "sdp": "..." } }`; o frontend responde com `answer` e candidatos `ice-candidate` pelo mesmo WebSocket. O vídeo usa os mesmos frames capturados para reconhecimento, com envio limitado a 20 FPS. Eventos de reconhecimento são enviados separadamente como `detection` e mantêm os dados da pessoa e a box. O estado da câmera é enviado como `{ "type": "status", "camera_online": true }`. Ajuste `FACE_MATCH_DISTANCE_THRESHOLD` apenas após avaliar embeddings reais; o valor padrão depende da métrica da coleção Chroma (cosine: `0.4`, L2: `0.9`).

Para depuração, cada rosto detectado gera um log com o resultado do reconhecimento, nome quando reconhecido, score/distância e uma prévia da embedding. Defina `FACE_LOG_FULL_EMBEDDING=true` no `.env` para registrar o vetor completo; isso gera logs volumosos e expõe dados biométricos. O score cosine (`1 - distance`) indica similaridade e não é uma probabilidade calibrada de acerto.
