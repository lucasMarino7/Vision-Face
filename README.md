# Vision Face

Sistema de **reconhecimento facial em tempo real** com câmera em uma Raspberry Pi 5, cadastro centralizado de pessoas em um servidor e painel web de monitoramento.

A câmera fica na Raspberry. Ela detecta rostos, gera uma _embedding_ (vetor numérico de 512 valores que representa o rosto) e compara com as pessoas cadastradas. O resultado e o vídeo ao vivo vão direto para o navegador do operador. O cadastro de pessoas e embeddings fica no servidor, e a Raspberry mantém uma cópia local sincronizada para reconhecer rostos sem depender de internet a cada frame.

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Arquitetura](#2-arquitetura)
3. [Tecnologias](#3-tecnologias)
4. [Estrutura do repositório](#4-estrutura-do-repositório)
5. [Como o sistema funciona](#5-como-o-sistema-funciona)
6. [Conceitos do reconhecimento facial](#6-conceitos-do-reconhecimento-facial)
7. [Variáveis de ambiente](#7-variáveis-de-ambiente)
8. [Rodando o servidor com Docker](#8-rodando-o-servidor-com-docker)
9. [Rodando a Raspberry](#9-rodando-a-raspberry)
10. [Operação e manutenção da Raspberry](#10-operação-e-manutenção-da-raspberry)
11. [Usando o painel](#11-usando-o-painel)
12. [Referência da API e do WebSocket](#12-referência-da-api-e-do-websocket)
13. [Pendências de documentação](#13-pendências-de-documentação)

---

## 1. Visão geral

| Problema | Como o projeto resolve |
| --- | --- |
| Reconhecer rostos na câmera em tempo quase real, em hardware pequeno | A Raspberry Pi 5 roda detecção e reconhecimento localmente (InsightFace + ONNX Runtime, só CPU). |
| Não depender da internet/servidor a cada rosto | A Raspberry guarda uma cópia local das pessoas (SQLite) e dos vetores (ChromaDB) e compara localmente. |
| Cadastrar pessoas em um só lugar | O servidor (Flask + PostgreSQL com pgvector) é a fonte da verdade; a Raspberry sincroniza por **delta** (só o que mudou). |
| Ver a câmera e os rostos no navegador, sem plugin | A Raspberry transmite vídeo por **WebRTC** e envia dados por **WebSocket**; o painel React exibe tudo. |
| Cadastrar quem ainda não é conhecido | Rostos não reconhecidos aparecem no painel com o botão **Adicionar**, que atrela a embedding a uma pessoa existente ou nova. |

O painel mostra, em tempo real: vídeo da câmera com caixas nos rostos, FPS real da câmera, dados da pessoa reconhecida (nome, nascimento, idade, se é procurada e o motivo), embeddings de rostos desconhecidos e o horário da próxima sincronização da Raspberry.

---

## 2. Arquitetura

```
                 ┌──────────────────────── Servidor (Docker) ───────────────────────┐
                 │  PostgreSQL + pgvector  ◄──  Backend Flask (API REST, :8000)      │
                 │                                   ▲                               │
                 │                       nginx + painel React (:3000)                │
                 └───────────────────────────────────┬───────────────────────────────┘
                                 ▲                   │
          sincronização por delta│                   │ HTTP (cadastro: pessoas/embeddings)
              (HTTP, a cada 30 s)│                   ▼
┌──────────── Raspberry Pi 5 ────┴────────┐     ┌───────────────┐
│ Câmera CSI → InsightFace → ChromaDB     │     │   Navegador   │
│ SQLite + cache em RAM                   │────►│ (painel React)│
│ WebSocket + WebRTC (:8765)              │     └───────────────┘
└─────────────────────────────────────────┘   vídeo (WebRTC) + rostos/status (WebSocket)
```

- O **navegador conecta direto na Raspberry** para vídeo e dados, e no **servidor** para o cadastro.
- A **Raspberry conecta no servidor** apenas para sincronizar o cadastro.

### Por que sincronização por delta?

Cada alteração no backend (pessoa ou embedding inserida, alterada ou removida) gera um registro na tabela `sync_change` (tabela postgres) com um número de **versão** crescente. A Raspberry guarda a última versão aplicada e consulta `GET /api/sync/delta/<versão>`, recebendo só o que mudou depois dela. A exclusão de pessoa usa a tabela `outbox` (tabela sqlite da raspberry) para garantir que os vetores dela também saiam do ChromaDB, mesmo se houver falha no meio (evita **dupla escrita** inconsistente e dados órfãos).

### Distribuição em threads (Raspberry)

| Atividade | Onde roda | Função |
| --- | --- | --- |
| Loop de reconhecimento | Thread principal | Captura frame → detecta → reconhece → envia resultado. É sequencial: um frame por vez. |
| Sincronização (`backend-sync`) | Thread daemon | A cada 30 s (configurado por `SYNC_INTERVAL_SECONDS`)  consulta o servidor e atualiza SQLite, ChromaDB e cache em RAM (variavel em RAM da raspberry). |
| Monitor de rede (`network-monitor`) | Thread daemon | Loga o estado do Wi-Fi e o endereço `ws://IP:porta`. |
| Servidor WebSocket/WebRTC | Thread própria com event loop `asyncio` | Atende o navegador (sinalização, vídeo e mensagens) sem bloquear o reconhecimento. |

**Concorrência, não paralelismo de código Python:** as threads do projeto são `threading.Thread` do CPython, e o **GIL** (_Global Interpreter Lock_) permite que apenas uma thread execute bytecode Python por vez. Mesmo com 4 núcleos da raspberry pi 5, o código Python das threads (reconhecimento, sincronização, monitor de rede, WebSocket) é executado de forma **concorrente**: o interpretador alterna rapidamente entre elas, e elas progridem de forma intercalada, mas não simultânea. A divisão em threads vale pela **responsividade**, não por ganho de velocidade: enquanto uma thread espera (a rede da sincronização, o envio pelo WebSocket, o `sleep` do monitor de rede), o GIL é liberado e outra roda, então a sincronização e o WebSocket não travam o laço de reconhecimento.

O GIL é liberado durante operações de I/O e em chamadas a bibliotecas nativas. Por isso a inferência do InsightFace (ONNX Runtime) e as contas do NumPy podem usar vários núcleos por dentro, mas isso é paralelismo interno dessas bibliotecas, não das threads do projeto. Resumo:

| Parte | Natureza |
| --- | --- |
| Loop de reconhecimento: capturar → detectar → buscar → enviar, um frame por vez | **Sequencial** |
| Threads Python (reconhecimento, sync, rede, WebSocket) entre si | **Concorrente** (limitada pelo GIL) |
| Inferência dos modelos (ONNX Runtime) e cálculos nativos | Pode ocupar vários núcleos, fora do GIL |

Como o gargalo é a inferência na CPU e ela roda na thread do reconhecimento, o FPS é limitado por ela, e não pelo número de threads.

**Proteção dos dados compartilhados:** as threads compartilham dados, então o acesso é protegido por _locks_ (`chroma_lock` para o ChromaDB, `PERSON_CACHE_LOCK` para o cache de pessoas, lock do frame de vídeo e do estado de sincronização). Um dicionário em RAM (chave = id da pessoa) evita consultar o SQLite a cada frame.

**Parada:** `main.py` usa um `Event` compartilhado (`stop_event`) para encerrar as threads com `Ctrl+C`. Se o reconhecimento falhar com exceção, o loop reinicia sozinho após 5 s.

---

## 3. Tecnologias

### Raspberry Pi (`raspberry/`)

| Tecnologia | Função no projeto |
| --- | --- |
| **Raspberry Pi 5 (8 GB) + Pi OS 64 bits** | Hardware e sistema que rodam o reconhecimento localmente. |
| **Picamera2 / libcamera** | Captura os frames da câmera CSI. |
| **InsightFace (`buffalo_l`)** | Detecta rostos e gera a embedding de 512 valores de cada rosto. |
| **ONNX Runtime (CPU)** | Executa os modelos do InsightFace (sem GPU). |
| **ChromaDB** | Banco vetorial local. Busca o vetor cadastrado mais próximo (distância de cosseno). |
| **SQLite + SQLAlchemy** | Guarda pessoas, versão da sincronização e a fila `outbox` de exclusões. |
| **websockets** | Servidor WebSocket: envia rostos, status, FPS e estado da sincronização; troca a sinalização do WebRTC. |
| **aiortc + PyAV** | WebRTC: transmite o vídeo ao navegador (limitado a 20 FPS). |

### Servidor (`server/`)

| Tecnologia | Função no projeto |
| --- | --- |
| **Docker Compose** | Sobe Postgres, backend e frontend com um comando. |
| **Flask + Flask-RESTX** | API REST e documentação Swagger (`/api/docs`). |
| **Gunicorn** | Servidor de produção do Flask no container. |
| **PostgreSQL + pgvector** | Banco principal; a extensão guarda a embedding como coluna vetorial de 512 dimensões. |
| **SQLAlchemy + Flask-Migrate (Alembic)** | Modelos e migrations; o container aplica `flask db upgrade` ao iniciar. |
| **Marshmallow** | Serialização e validação dos dados da API. |
| **React 19 + Vite** | Painel web: monitoramento ao vivo e CRUD de pessoas e embeddings. |
| **nginx** | Serve o build do frontend e faz proxy de `/api/` para o backend (evita CORS). |
| **WebRTC / WebSocket (navegador)** | Recebe vídeo e dados direto da Raspberry. |

---

## 4. Estrutura do repositório

```
Vision-Face/
├── .env.example              # modelo de todas as variáveis de ambiente
├── docker-compose.yml        # postgres, backend, frontend
├── README.md                 # este arquivo
├── raspberry/
│   ├── readme.md                 # guia completo de montagem e execução
│   ├── vision-face.service       # serviço systemd: inicia o main.py no boot
│   ├── src/
│   │   ├── main.py               # ponto de entrada (sync, rede e reconhecimento)
│   │   ├── clear_data.py         # CLI para limpar ChromaDB e/ou SQLite locais
│   │   ├── ws_server.py          # WebSocket + WebRTC para o navegador
│   │   ├── network_monitor.py    # estado do Wi-Fi e endereço ws://IP:porta
│   │   ├── requirements.txt
│   │   ├── recognition/
│   │   │   ├── camera.py         # captura de frames (Picamera2)
│   │   │   ├── face_engine.py    # InsightFace: detecção e embeddings
│   │   │   ├── runner.py         # loop: reconhece, busca no ChromaDB, envia "faces"/"status"
│   │   │   └── video_track.py    # track de vídeo do WebRTC
│   │   ├── sync/__init__.py      # sincronização com o backend (delta + outbox)
│   │   ├── database/             # database.py (SQLite + cache RAM), chroma.py, models/
│   │   └── data/                 # gerado em execução: chroma/ e vision_face.db (fora do Git)
│   └── tests/                    # camera_test.py e test_capture_embeddings/
└── server/
    ├── README.md
    ├── postgres/init.sql         # habilita a extensão pgvector
    ├── backend/                  # API Flask
    │   ├── Dockerfile, entrypoint.sh   # aplica migrations e sobe o gunicorn
    │   ├── main.py, requirements.txt
    │   ├── server/               # app_factory, config, extensions, instance
    │   ├── apis/                 # person.py, embedding.py, sync.py (rotas /api/...)
    │   ├── models/ e schemas/    # person, embedding, sync_change
    │   ├── migrations/           # Alembic (versions/)
    │   └── web/                  # páginas server-side: auth/, home/, blog/
    └── frontend/                 # painel React/Vite (src/App.jsx, nginx.conf, Dockerfile)
```

---

## 5. Como o sistema funciona

### 5.1 Reconhecimento (na Raspberry)

1. `main.py` inicializa o SQLite, carrega as pessoas no cache em RAM e inicia a sincronização (thread), o monitor de rede (thread) e o loop de reconhecimento (thread principal).
2. O loop captura um frame da câmera e o entrega ao WebRTC (vídeo ao vivo).
3. O InsightFace detecta os rostos e gera, para cada um, a bounding box, o score de detecção e a embedding normalizada.
4. Rostos com score abaixo de `FACE_MIN_DETECTION_SCORE` são ignorados.
5. A embedding é buscada no ChromaDB (vizinho mais próximo, distância de cosseno). Se a distância for menor ou igual ao limite (`0.4` por padrão, ou `FACE_MATCH_DISTANCE_THRESHOLD`), o rosto é **reconhecido** e os dados da pessoa vêm do cache em RAM. Caso contrário, é **não reconhecido**.
6. A cada frame, a Raspberry envia pelo WebSocket a mensagem `faces` com todos os rostos do frame. A cada segundo, envia `status` com o FPS e o estado da sincronização.

### 5.2 Sincronização (Raspberry ← servidor)

A cada `SYNC_INTERVAL_SECONDS` (30 s por padrão):

1. Processa a fila `outbox` (exclusões pendentes no ChromaDB).
2. Consulta `GET /api/sync/status` para saber a versão mais recente do servidor.
3. Se a versão local for menor, chama `GET /api/sync/delta/<versão_local>`.
4. Aplica cada mudança em ordem: pessoas vão para o SQLite e o cache em RAM; embeddings vão para o ChromaDB (buscando os vetores em `GET /api/embedding/`). O ChromaDB guarda nos metadados o id da pessoa, o id da embedding, o ângulo do rosto e o modelo que a gerou.
5. Atualiza a versão local e agenda a próxima sincronização.

O painel mostra "Sincronizando…" ou "Próxima sync: HH:MM:SS (em Ns)", então depois de cadastrar uma pessoa ou embedding você sabe quando a Raspberry vai passar a reconhecê-la.

### 5.3 Cadastro a partir de um rosto desconhecido

1. Um rosto não reconhecido aparece no card **Rostos identificados** com sua embedding.
2. Clique em **Adicionar**. Escolha uma pessoa existente e o ângulo (ex.: `frontal`, `diagonal`), ou clique em **Cadastrar nova pessoa**.
3. Ao cadastrar a nova pessoa, a embedding é atrelada a ela automaticamente com o ângulo informado.
4. Na próxima sincronização, a Raspberry recebe a embedding e passa a reconhecer essa pessoa.

### 5.4 Passo a passo resumido de um frame

1. A Raspberry captura um array NumPy da câmera (matriz de pixels: altura × largura × 3 canais).
2. O frame é enviado ao navegador via WebRTC (uma conexão direta de vídeo; o WebSocket só troca a sinalização). O stream sempre usa o último frame capturado, a até 20 FPS, e não acumula fila.
3. O modelo de IA retorna, para cada face: embedding (512 dimensões), score de detecção e box (coordenadas).
4. A embedding é normalizada e comparada por cosseno com as cadastradas.
5. A cada segundo, FPS e estado da sincronização são enviados via WebSocket.

---

## 6. Conceitos do reconhecimento facial

### 6.1 Câmera

- Câmera de 5 MP (OV5647) com resolução máxima de 2592×1944, ligada a um conector CSI da Raspberry Pi 5.
- **Resolução em uso:** definida em `recognition/camera.py` (padrão do código atual: `640×480`, formato `RGB888`).
- Resoluções nativas do sensor (prefira-as; qualquer outra é redimensionada pela biblioteca e pode distorcer o frame):

  | Resolução | FPS |
  | --- | --- |
  | 2592×1944 | 1–15 |
  | 1920×1080 | 1–30 |
  | 1296×972 | 1–42 |
  | 1296×730 | 1–49 |
  | 640×480 | 42–60 |

- **Resolução menor** = menos CPU e mais FPS, mas pode falhar em rostos distantes (poucos pixels sobre a face).
- **Formato `RGB888`:** na prática o array vem em ordem BGR, que é o formato esperado pelo InsightFace.
- A resolução da câmera deve ficar próxima da área de detecção do InsightFace: o frame é redimensionado para ela, então resolução muito maior só gasta CPU à toa.
- A câmera também alimenta o vídeo do painel. O frame capturado é enviado como está, e as caixas dos rostos são desenhadas pelo painel por cima do vídeo.

### 6.2 Modelo de IA (InsightFace)

- Usa o módulo `FaceAnalysis` do InsightFace (que utiliza o ArcFace por baixo), com o pacote `buffalo_l`, que gera embeddings de 512 dimensões.
- **Área de detecção (`det_size`):** o frame é redimensionado para ela antes de entrar no detector (mantendo a proporção; o que sobra é preenchido). Aceita múltiplos de 32 (128, 320, 448, 640, 1280…). Áreas menores são bem mais rápidas, porém pior para rostos pequenos/distantes; áreas maiores fazem o contrário. O código atual usa `320×320` em `recognition/face_engine.py`.
- **Execução na CPU:** `ctx_id=-1` em `self._app.prepare(ctx_id=-1, det_size=...)` indica CPU; `0`, `1`, `2`… indicam o id de uma GPU. Hardware com GPU roda estes modelos muito mais rápido.
- **Só detecção e reconhecimento:** o `buffalo_l` contém 5 modelos, mas o projeto habilita apenas dois (`allowed_modules=["detection", "recognition"]`), economizando processamento:

  | Modelo | Função | Usado? |
  | --- | --- | --- |
  | `det_10g.onnx` | Detecção do rosto (bbox, score e pontos) | Sim |
  | `w600k_r50.onnx` | Gera a embedding de 512 números | Sim |
  | `1k3d68.onnx` | 68 pontos 3D do rosto | Não |
  | `2d106det.onnx` | 106 pontos 2D do rosto | Não |
  | `genderage.onnx` | Estimativa de gênero e idade | Não |

### 6.3 Normalização e similaridade

1. Calcula-se a **magnitude** (norma) do vetor: raiz da soma dos quadrados dos 512 valores.
2. Divide-se cada valor pela magnitude, resultando em um vetor de comprimento 1. A direção do vetor é preservada.
3. O que identifica o rosto é a **direção** do vetor, não o seu comprimento. Com comprimento 1, a comparação depende só do ângulo entre os vetores.
4. Compara-se pela **similaridade de cosseno**: resultado de −1 a 1, e quanto mais próximo de 1, mais parecidos (com vetores normalizados, equivale ao produto escalar). O ChromaDB trabalha com **distância** de cosseno (`1 − similaridade`): quanto **menor**, mais parecido.
5. Não há `softmax` nesse processo: a normalização não corrige erro de softmax, e a similaridade de cosseno não é uma probabilidade.

### 6.4 Seleção do modelo (`INSIGHTFACE_MODEL`)

As opções são `buffalo_l`, `buffalo_m`, `buffalo_s` e `buffalo_sc`, do maior para o menor. Na primeira vez que um modelo é selecionado, a Raspberry baixa o pacote para `~/.insightface/models/<modelo>`, então precisa de internet nesse momento. Depois, usa o arquivo local.

**Compatibilidade entre vetores:** todos os modelos geram 512 dimensões (treino WebFace600K), mas só são comparáveis entre modelos da mesma rede de reconhecimento:

| Grupo | Modelos | Rede de reconhecimento |
| --- | --- | --- |
| A | `buffalo_l`, `buffalo_m` | ResNet50 (`w600k_r50`) |
| B | `buffalo_s`, `buffalo_sc` | MobileFaceNet (`w600k_mbf`) |

Vetores de grupos diferentes ficam em espaços vetoriais distintos, e a similaridade por cosseno entre eles não tem significado. Por isso cada embedding é gravada no ChromaDB com o modelo e a família que a gerou, e a busca considera apenas vetores da mesma família do modelo em uso. **Ao trocar de grupo, as faces já cadastradas deixam de ser reconhecidas até que suas embeddings sejam geradas novamente com o novo modelo.**

---

## 7. Variáveis de ambiente

Existe **um único arquivo `.env`, na raiz do repositório**, usado pelo Docker Compose, backend, frontend (build) e Raspberry.

```bash
cp .env.example .env          # Linux/macOS/Raspberry
copy .env.example .env        # Windows (cmd)
```

O `.env` não vai para o Git. Variáveis já definidas no ambiente têm prioridade sobre o arquivo.

| Variável | Quem usa | Descrição |
| --- | --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Postgres, backend | Banco e credenciais. **Troque a senha.** |
| `POSTGRES_PORT` | Docker | Porta publicada em `127.0.0.1` para acessar o banco com pgAdmin (padrão 5432). |
| `DATABASE_URL` | Backend fora do Docker | URI do Postgres ao rodar o Flask localmente. No Docker o compose monta a URI com o host `postgres`. |
| `SECRET_KEY`, `SECURITY_PASSWORD_SALT` | Backend | Segredos do Flask. Use valores aleatórios longos. |
| `BACKEND_IP`, `BACKEND_PORT` | Backend, Docker | Interface e porta publicada da API (padrão `0.0.0.0` e `8000`). |
| `ENV` | Backend | `production` usa `DATABASE_URL` (Postgres). Qualquer outro valor usa SQLite local. |
| `FLASK_APP` | Backend | `main`. |
| `FRONTEND_PORT` | Docker | Porta publicada do painel (padrão `3000`). |
| `RASPBERRY_WS_URL` | Frontend (**build**) | `ws://IP_DA_RASP:8765`, já preenchido no painel. Lido no build; ao mudar, refaça o build do frontend. |
| `API_URL` | Raspberry | URL da API vista pela Raspberry, ex.: `http://IP_DO_SERVIDOR:8000/api`. |
| `SYNC_INTERVAL_SECONDS` | Raspberry | Intervalo entre sincronizações (padrão 30). |
| `WEBSOCKET_HOST`, `WEBSOCKET_PORT` | Raspberry | Onde o WebSocket escuta (padrão `0.0.0.0` e `8765`). |
| `INSIGHTFACE_MODEL` | Raspberry | Pacote de modelos (padrão `buffalo_l`, com a letra "l"). |
| `FACE_MIN_DETECTION_SCORE` | Raspberry | Score mínimo do detector, de 0 a 1 (padrão 0.5). |
| `FACE_MATCH_DISTANCE_THRESHOLD` | Raspberry | Distância máxima para reconhecer. Vazio usa o padrão (0.4). Menor = mais rigoroso. |
| `FACE_LOG_FULL_EMBEDDING` | Raspberry | `true` registra o vetor completo nos logs (volumoso e expõe dado biométrico). |

Dois endereços diferentes, não confunda:

- `API_URL` é o **servidor visto pela Raspberry**.
- `RASPBERRY_WS_URL` é a **Raspberry vista pelo navegador**.

---

## 8. Rodando o servidor com Docker

**Pré-requisitos:** Docker Desktop e Git.

1. **Clone o repositório**
   ```bash
   git clone <URL_DO_REPOSITORIO> Vision-Face
   cd Vision-Face
   ```
2. **Crie o `.env`** a partir do exemplo (veja a [seção 7](#7-variáveis-de-ambiente)):
   ```bash
   cp .env.example .env
   ```
3. **Edite o `.env`**:
   - Troque `POSTGRES_PASSWORD`.
   - Troque `SECRET_KEY` e `SECURITY_PASSWORD_SALT` por valores aleatórios.
   - Defina `RASPBERRY_WS_URL` com o IP da Raspberry, ex.: `ws://192.168.15.103:8765`.
   - Defina `API_URL` com o IP do computador onde o Docker roda, ex.: `http://192.168.15.50:8000/api` (usado pela Raspberry).
4. **Suba os containers**
   ```bash
   docker compose up --build -d
   ```
   Ordem de inicialização: o Postgres fica saudável, o backend aplica as migrations e inicia o Gunicorn, e só então o frontend sobe.
5. **Acesse**
   - Painel: <http://localhost:3000>
   - API: <http://localhost:8000/api/person/> (deve devolver uma lista JSON, possivelmente vazia)
   - Swagger: <http://localhost:8000/api/docs>

**Comandos úteis**

```bash
docker compose up                       # roda todos os serviços
docker compose up -d --build frontend   # refaz só o frontend; '-d' roda em segundo plano
docker compose logs -f frontend         # logs do nginx
docker compose down                     # para e remove tudo, mantendo o banco (volume preservado)
docker compose down -v                  # para e remove tudo, APAGANDO o banco (volume do Postgres)
```

**Portas ocupadas:** altere `FRONTEND_PORT` e `BACKEND_PORT` no `.env` e ajuste a porta em `API_URL`.

---

## 9. Rodando a Raspberry

O guia completo, da compra e montagem do hardware até a execução, está em **[raspberry/readme.md](raspberry/readme.md)**. Resumo:

1. Montar o hardware (Pi 5, câmera 5 MP v1.3 com cabo adaptador em um conector CSI — CAM0 ou CAM1 —, fonte de 5 V / 27 W).
2. Gravar o Pi OS 64 bits no microSD com o Pi Imager, com SSH e Wi-Fi configurados (a mesma rede do servidor).
3. Inserir o cartão e alimentar a placa.
4. Conectar por SSH, atualizar com `apt` e validar a câmera.
5. Clonar o projeto, criar o ambiente virtual e instalar as dependências.
6. Configurar o `.env` (principalmente `API_URL`) e rodar `python main.py`.

Ao subir, o log mostra o endereço para usar no painel, por exemplo `WebSocket address: ws://192.168.15.103:8765`.

**Acesso:**

- Pode-se usar monitor, teclado e mouse na Raspberry, ou SSH pela rede Wi-Fi configurada.
- Com SSH, use a extensão **Remote - SSH** do VS Code: nova conexão com `ssh usuario@pi5.local` e a senha definida na instalação do SO. Raspberry e computador devem estar na mesma rede.
- Para descobrir o IP da Raspberry: `hostname -I`.

---

## 10. Operação e manutenção da Raspberry

### 10.1 Desligar com segurança

Desligar com o `main.py` rodando pode **corromper o ChromaDB e o SQLite** caso haja escrita em andamento.

1. Pare o programa (`sudo systemctl stop vision-face` ou `Ctrl+C`).
2. Execute `sudo poweroff`.
3. Só desligue a fonte quando o LED da placa ficar **vermelho** (placa apenas alimentada, sem SO rodando).

### 10.2 Temperatura e energia

Em testes a 25 °C ambiente, a Raspberry chegou a **74 °C**. O seguro é até 80 °C; acima disso ela reduz o clock (throttling) para se proteger. Cuide da ventilação do ambiente.

```bash
watch -n 1 vcgencmd measure_temp   # temperatura a cada 1 s
vcgencmd get_throttled             # problemas desde o boot
htop                               # uso de CPU (4 cores) e RAM
```

`get_throttled` retorna um valor em que cada bit indica uma condição (os bits de histórico desde o boot aparecem como `0x5000X`):

| Valor | Significado |
| --- | --- |
| `0x0` | Nenhum problema. |
| `0x1` | Subtensão detectada: a fonte não entrega tensão/corrente suficiente. |
| `0x2` | Frequência da CPU limitada. |
| `0x4` | Redução de clock (throttling) em andamento. |
| `0x8` | Limite de temperatura atingido. |

Os valores se somam (por exemplo, `0x5` = subtensão + throttling).

### 10.3 Monitor de rede

`network_monitor.py` registra no log se o Wi-Fi conectou (interface em estado `up`), quedas de conexão e o IP da Raspberry no roteador, para formar o endereço do WebSocket.

### 10.4 Rodar sem perder o programa ao cair o SSH

Rodar o código direto em um terminal SSH o encerra se a conexão cair. Há duas opções:

**a) Serviço systemd (recomendado)** — inicia sozinho ao ligar a Raspberry:

```bash
sudo cp ~/Projetos/Vision-Face/raspberry/vision-face.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vision-face
```

Veja os comandos de gerenciamento em [raspberry/readme.md](raspberry/readme.md).

**b) tmux** — mantém a sessão viva em segundo plano:

```bash
sudo apt install tmux
tmux new -s vision          # abre a sessão "vision"
python src/main.py          # roda o programa dentro dela
# Ctrl+B e depois D: sai da sessão sem parar o programa
tmux attach -t vision       # volta à sessão
tmux ls                     # lista as sessões
tmux kill-session -t vision # encerra a sessão e o programa
# Ctrl+C dentro da sessão: apenas para o programa
```

### 10.5 Limpar os bancos locais (`clear_data.py`)

Com a venv da Raspberry, limpa ChromaDB e/ou SQLite locais (o servidor/PostgreSQL não é afetado; ao zerar o SQLite, a próxima sincronização baixa tudo de novo):

```bash
cd ~/Projetos/Vision-Face/raspberry/src
../.venv/bin/python clear_data.py              # os dois, pedindo confirmação
../.venv/bin/python clear_data.py --chroma     # só o ChromaDB (embeddings)
../.venv/bin/python clear_data.py --sqlite     # só o SQLite
../.venv/bin/python clear_data.py --all --yes  # os dois, sem perguntar
```

---

## 11. Usando o painel

Acesse <http://localhost:3000>.

**Visão ao vivo**

- Campo **Endpoint da Raspberry**: já vem com o valor de `RASPBERRY_WS_URL`. Clique em **Conectar** (o botão vira **Desconectar** enquanto conectado).
- O vídeo mostra caixas nos rostos (laranja = pessoa procurada, verde = demais rostos). O **FPS** real aparece no canto do vídeo e no rodapé.
- O card **Rostos identificados** lista só os rostos presentes na câmera no momento. Para reconhecidos, mostra nome, nascimento, idade e alerta de procurado. Para desconhecidos, mostra a embedding e o botão **Adicionar**.
- No topo, o indicador de sincronização mostra quando a Raspberry sincroniza de novo.

**Pessoas cadastradas:** cadastro, edição e exclusão de pessoas e das suas embeddings. Datas no formato `dd/mm/aaaa`.

**Embeddings:** lista de todos os vetores cadastrados, com busca e edição.

---

## 12. Referência da API e do WebSocket

### API REST (`/api`)

| Método e rota | Descrição |
| --- | --- |
| `GET/POST /person/` | Lista e cria pessoas. |
| `GET/PUT/DELETE /person/<id>` | Consulta, altera e remove uma pessoa (e suas embeddings). |
| `GET /embedding/` | Lista todas as embeddings. |
| `GET/POST /embedding/<person_id>/embeddings` | Lista e cria embeddings de uma pessoa (vetor com exatamente 512 valores). |
| `PUT/DELETE /embedding/<person_id>/embeddings/<id>` | Altera e remove uma embedding. |
| `GET /sync/status` | Versão mais recente dos dados. |
| `GET /sync/delta/<versão>` | Mudanças ocorridas depois da versão informada. |

A documentação interativa completa fica em `/api/docs`.

### WebSocket da Raspberry (porta 8765)

Mensagens enviadas **pela Raspberry**:

```json
{"type":"offer","sdp":{"type":"offer","sdp":"..."}}
{"type":"ice-candidate","candidate":{"candidate":"...","sdpMid":"0","sdpMLineIndex":0}}
{"type":"status","camera_online":true,"fps":12.4,
 "sync":{"syncing":false,"backend_online":true,"last_sync_at":"2026-01-01T12:00:00+00:00",
         "next_sync_at":"2026-01-01T12:00:30+00:00","next_sync_in":18.2,"interval_seconds":30}}
{"type":"faces","frame_size":{"width":640,"height":480},"faces":[
  {"recognized":true,"person":{"id":1,"name":"Nome","date_birth":"1990-01-01","wanted":false,"reason":null},
   "embedding":[0.01,"... 512 valores"],"model":"buffalo_l",
   "box":{"x":120,"y":60,"width":180,"height":220},"distance":0.21,
   "similarity":79.0,"embedding_id":12,"angle":"diagonal"}
]}
```

Mensagens enviadas **pelo navegador**: `answer` (resposta WebRTC) e `ice-candidate`.

Para um rosto não reconhecido, `recognized` é `false` e `person` é `null`.

- `similarity`: similaridade de cosseno (`1 − distance`) em %, entre o rosto da câmera e a embedding cadastrada **mais próxima**. Indica confiança, mas **não é uma probabilidade calibrada de acerto**. Também é enviada para rostos não reconhecidos (melhor correspondência abaixo do limite).
- `embedding_id` e `angle`: embedding cadastrada que gerou o reconhecimento e o ângulo dela (`null` quando não reconhecido). O ângulo é gravado nos metadados do ChromaDB durante a sincronização; embeddings sincronizadas antes dessa versão não o têm na Raspberry, então o painel o busca pela API usando o `embedding_id`.

**Fluxo WebRTC:** o navegador abre o WebSocket, a Raspberry envia a `offer`, o navegador responde com `answer` e os dois trocam `ice-candidate`. O vídeo passa a fluir direto por WebRTC (usa o STUN público do Google para descobrir caminhos de rede).

---

## 13. Pendências de documentação

- Criar um fluxo (diagrama) mostrando o passo a passo do funcionamento do projeto.
