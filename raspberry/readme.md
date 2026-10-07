# Vision Face na Raspberry Pi — guia completo

Este guia leva você de uma Raspberry Pi 5 **nova, ainda na caixa**, até o reconhecimento facial rodando e enviando vídeo e dados para o painel web. Tudo é feito por **SSH**, sem precisar de monitor, teclado ou mouse na Raspberry.

Para entender o projeto como um todo (servidor, painel, arquitetura), leia primeiro o [README da raiz](../README.md).

## Sumário

1. [Lista de materiais](#1-lista-de-materiais)
2. [O que a Raspberry faz neste projeto](#2-o-que-a-raspberry-faz-neste-projeto)
3. [Montagem do hardware (câmera)](#3-montagem-do-hardware-câmera)
4. [Instalando o Raspberry Pi OS 64 bits no cartão microSD](#4-instalando-o-raspberry-pi-os-64-bits-no-cartão-microsd)
5. [Primeiro boot e conexão por SSH](#5-primeiro-boot-e-conexão-por-ssh)
6. [Atualizando o sistema (apt)](#6-atualizando-o-sistema-apt)
7. [Testando a câmera](#7-testando-a-câmera)
8. [Baixando o projeto e preparando o Python](#8-baixando-o-projeto-e-preparando-o-python)
9. [Configurando o `.env`](#9-configurando-o-env)
10. [Rodando o projeto](#10-rodando-o-projeto)
11. [Conectando o painel à Raspberry](#11-conectando-o-painel-à-raspberry)
12. [Iniciar automaticamente no boot (systemd)](#12-iniciar-automaticamente-no-boot-systemd)
13. [Desenvolvendo pelo VS Code (Remote SSH)](#13-desenvolvendo-pelo-vs-code-remote-ssh)
14. [Estrutura do código](#14-estrutura-do-código)
15. [Ajustes do reconhecimento](#15-ajustes-do-reconhecimento)
16. [Problemas comuns](#16-problemas-comuns)

---

## 1. Lista de materiais

### Utilizados neste projeto

| Item | Observação |
| --- | --- |
| **Raspberry Pi 5 — 8 GB de RAM** | O reconhecimento facial roda na CPU; os 8 GB dão folga para o modelo InsightFace, o ChromaDB e o vídeo. |
| **Câmera 5 MP v1.3 (sensor OV5647)** | Câmera CSI com cabo flat de 15 pinos. |
| **Cabo adaptador flat para a Raspberry Pi 5** | A Pi 5 usa conectores de câmera menores (22 pinos, passo de 0,5 mm). O cabo adaptador converte do conector de 15 pinos da câmera para o de 22 pinos da Pi 5. |
| **Fonte oficial 27 W (USB-C, 5,1 V / 5 A)** | A Pi 5 precisa de 5 A para entregar potência total. Fontes mais fracas causam avisos de subtensão e instabilidade. |

### Itens complementares necessários

| Item | Observação |
| --- | --- |
| **Cartão microSD (mínimo 32 GB, classe A1/A2) e leitor** | O sistema, o modelo de IA (~300 MB), o ChromaDB e o SQLite ficam no cartão. |
| **Rede Wi-Fi** (ou cabo de rede) | A Raspberry e o computador do operador precisam estar na mesma rede. |

### Recomendados (opcionais)

- Case com refrigeração ou o Active Cooler oficial: o reconhecimento mantém a CPU em carga contínua.
- Suporte/tripé para fixar a câmera.

---

## 2. O que a Raspberry faz neste projeto

- Captura vídeo da câmera CSI (Picamera2).
- Detecta rostos e gera embeddings com o InsightFace (`buffalo_l`), na CPU.
- Compara cada embedding com o ChromaDB local para reconhecer pessoas.
- **Sincroniza** o cadastro de pessoas e embeddings com o servidor a cada 30 s (por padrão), usando a API do backend.
- Atua como **servidor WebSocket + WebRTC** (porta `8765`): o navegador conecta direto nela para receber o vídeo, os rostos, o FPS e o estado da sincronização.

---

## 3. Montagem do hardware (câmera)

> **Faça sempre com a Raspberry desligada e sem a fonte conectada.**

A Raspberry Pi 5 tem **dois** conectores de câmera/display, ao lado das portas micro-HDMI, identificados como **CAM/DISP 0** e **CAM/DISP 1**. Este projeto usa o **CAM/DISP 0**.

1. **Prepare o cabo adaptador.** Uma ponta do cabo tem o conector largo (15 pinos, para a câmera) e a outra o conector estreito (22 pinos, para a Pi 5).
2. **Conecte na câmera (lado de 15 pinos):**
   - Levante com cuidado a trava plástica do conector da câmera (ela sobe poucos milímetros).
   - Insira o cabo reto até o fundo e empurre a trava de volta para baixo para prendê-lo.
3. **Conecte na Raspberry Pi 5 (lado de 22 pinos), no CAM/DISP 0:**
   - Levante a trava do conector. Ela é pequena; levante pelas bordas, sem forçar.
   - Insira o cabo reto até o fundo e baixe a trava.
4. **Verifique:** o cabo deve estar reto, sem inclinação, e preso pelas duas travas. Os contatos metálicos do cabo precisam estar voltados para os contatos do conector. Se a câmera não for detectada na [etapa 7](#7-testando-a-câmera), desligue e inverta o lado do cabo, porque essa é a causa mais comum.
5. Não toque no sensor e não remova a película protetora da lente antes de usar. Mantenha a câmera fixa e estável.

A fonte de 27 W só deve ser ligada depois que o sistema estiver gravado no cartão ([etapa 4](#4-instalando-o-raspberry-pi-os-64-bits-no-cartão-microsd)).

---

## 4. Instalando o Raspberry Pi OS 64 bits no cartão microSD

Faça isto no **seu computador**, usando o **Raspberry Pi Imager**.

1. Baixe e instale o **Raspberry Pi Imager**: <https://www.raspberrypi.com/software/>
2. Insira o cartão microSD no computador (o conteúdo dele será apagado).
3. Abra o Imager e escolha:
   - **Dispositivo:** Raspberry Pi 5
   - **Sistema operacional:** *Raspberry Pi OS (64-bit)*. Este projeto usa a versão de 64 bits. A versão Lite (sem desktop) também funciona e é suficiente, já que tudo é feito por SSH.
   - **Armazenamento:** o seu cartão microSD
4. Clique em **Próximo** e depois em **Editar configurações** (personalização do SO). Configure:
   - **Nome do host:** `pi5` (a Raspberry ficará acessível como `pi5.local`)
   - **Nome de usuário e senha:** por exemplo, usuário `lucas` e uma senha forte. Anote os dois.
   - **Wi-Fi:** SSID e senha da sua rede, e o **país do Wi-Fi: BR**. Será a rede usada para o SSH e também para falar com o servidor.
   - **Localização:** fuso horário `America/Sao_Paulo` e teclado `br`.
   - Na aba **Serviços**: marque **Ativar SSH** e escolha **Usar autenticação por senha**.
5. Salve, confirme e clique em **Gravar**. Aguarde a gravação e a verificação.
6. Remova o cartão com segurança e coloque-o no slot microSD da Raspberry Pi (parte de baixo da placa).

---

## 5. Primeiro boot e conexão por SSH

1. Com a câmera já encaixada ([etapa 3](#3-montagem-do-hardware-câmera)) e o cartão inserido, conecte a **fonte de 27 W** na porta USB-C da Raspberry.
2. Aguarde 1 a 3 minutos. O primeiro boot é mais demorado porque o sistema aplica as configurações e conecta ao Wi-Fi.
3. No **seu computador** (na mesma rede Wi-Fi), abra um terminal (PowerShell no Windows, Terminal no macOS/Linux; o cliente `ssh` já vem instalado):

   ```bash
   ssh lucas@pi5.local
   ```

   Substitua `lucas` pelo usuário que você criou e `pi5` pelo hostname escolhido.
4. Na primeira conexão, o SSH pergunta se confia no host. Digite `yes`. Depois informe a senha (ela não aparece enquanto você digita).
5. Quando aparecer o prompt `lucas@pi5:~ $`, você está dentro da Raspberry.

**Se `pi5.local` não for encontrado** (acontece em algumas redes e em versões antigas do Windows): descubra o IP da Raspberry na lista de dispositivos conectados do seu roteador e use `ssh lucas@192.168.x.x`.

**Recomendado:** no roteador, reserve um **IP fixo** para a Raspberry (reserva de DHCP). Assim o endereço do WebSocket que você coloca no painel não muda.

---

## 6. Atualizando o sistema (apt)

Ainda dentro do SSH:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

A conexão SSH cai durante o reinício. Espere cerca de 1 minuto e conecte de novo com `ssh lucas@pi5.local`.

Instale também as ferramentas usadas pelo projeto:

```bash
sudo apt install -y git python3-venv python3-pip python3-picamera2 build-essential python3-dev cmake
```

- `git`: baixar e atualizar o projeto.
- `python3-venv`: criar o ambiente virtual.
- `python3-picamera2`: biblioteca da câmera (vem instalada na versão com desktop; na Lite é necessário instalar).
- `build-essential`, `python3-dev`, `cmake`: compilação de algumas dependências Python (o InsightFace compila extensões na instalação).

---

## 7. Testando a câmera

A câmera OV5647 (v1.3) é detectada automaticamente no Raspberry Pi OS, sem editar nenhum arquivo de configuração.

```bash
rpicam-hello --list-cameras
```

Deve listar uma câmera `ov5647`. Para tirar uma foto de teste:

```bash
rpicam-still -o teste.jpg
```

Se aparecer `no cameras available`:

1. Desligue (`sudo poweroff`), retire a fonte e confira o encaixe do cabo nos dois lados e se ele está no conector **CAM/DISP 0**.
2. Inverta o lado do cabo no conector e tente de novo.
3. Confirme que o cabo adaptador é o de 15 pinos para 22 pinos, próprio para a Pi 5.

---

## 8. Baixando o projeto e preparando o Python

```bash
mkdir -p ~/Projetos
cd ~/Projetos
git clone <URL_DO_REPOSITORIO> Vision-Face
cd Vision-Face
```

Crie o ambiente virtual **com acesso aos pacotes do sistema** (`--system-site-packages`). Isso é necessário para o Python enxergar o `picamera2`, instalado via `apt`:

```bash
python3 -m venv raspberry/.venv --system-site-packages
source raspberry/.venv/bin/activate
pip install --upgrade pip
```

O prompt passa a mostrar `(.venv)`. Sempre que abrir um novo SSH, ative de novo com `source ~/Projetos/Vision-Face/raspberry/.venv/bin/activate`.

Instale as dependências:

```bash
pip install -r raspberry/src/requirements.txt
```

> O `requirements.txt` é um congelamento de todo o ambiente da Raspberry do desenvolvedor, incluindo pacotes que vêm do `apt` (como `python-apt`, `dbus-python`, `PyQt5`, `pycups`). Se o `pip` falhar em algum desses, instale apenas o que o projeto realmente usa, com as versões do arquivo:
>
> ```bash
> pip install insightface==2.0 onnxruntime==1.30.0 chromadb==1.5.9 aiortc==1.15.0 av==14.2.0 \
>   websockets==17.2 SQLAlchemy==2.1.3 requests==2.32.3 python-dotenv==1.2.4 \
>   numpy==2.2.4 opencv-python==5.0.0.93
> ```

A instalação pode levar vários minutos na Raspberry.

---

## 9. Configurando o `.env`

O `main.py` lê o arquivo `.env` na **raiz do repositório** (`~/Projetos/Vision-Face/.env`), o mesmo usado pelo servidor.

```bash
cd ~/Projetos/Vision-Face
cp .env.example .env
nano .env
```

O que a Raspberry usa (o resto do arquivo é do servidor e pode ficar como está):

| Variável | O que colocar |
| --- | --- |
| `API_URL` | **Obrigatória.** Endereço do backend visto pela Raspberry, **terminando em `/api`**. Ex.: `http://192.168.15.50:8000/api`, onde `192.168.15.50` é o IP do computador/servidor onde o Docker roda. |
| `SYNC_INTERVAL_SECONDS` | Intervalo da sincronização, em segundos (padrão 30). |
| `WEBSOCKET_HOST` / `WEBSOCKET_PORT` | Onde o WebSocket escuta (padrão `0.0.0.0` e `8765`). |
| `INSIGHTFACE_MODEL` | Modelo (padrão `buffalo_l`, com a letra "l"). |
| `FACE_MIN_DETECTION_SCORE` | Score mínimo do detector (padrão 0.5). |
| `FACE_MATCH_DISTANCE_THRESHOLD` | Distância máxima para reconhecer. Vazio usa o padrão (0.4). |
| `FACE_LOG_FULL_EMBEDDING` | `false`. Deixe assim: `true` gera logs enormes e expõe dados biométricos. |

Salve no `nano` com `Ctrl+O`, `Enter`, e saia com `Ctrl+X`.

**Antes de continuar, confirme que a Raspberry alcança o servidor** (o Docker do servidor precisa estar rodando — veja a [seção 7 do README principal](../README.md#7-rodando-o-servidor-com-docker-passo-a-passo)):

```bash
curl http://192.168.15.50:8000/api/sync/status
```

Deve responder um JSON como `{"latest_snapshot_version": 0}`. Se não responder, verifique o IP, a porta e o firewall do computador do servidor (porta 8000).

---

## 10. Rodando o projeto

```bash
cd ~/Projetos/Vision-Face/raspberry/src
source ../.venv/bin/activate
python main.py
```

Na **primeira execução**, o InsightFace baixa o modelo `buffalo_l` (cerca de 300 MB) para `~/.insightface`. É preciso ter internet nessa etapa, que pode levar alguns minutos.

O que você deve ver nos logs:

```
Frontend WebSocket listening on 0.0.0.0:8765.
Wi-Fi connected (wlan0, SSID MinhaRede).
WebSocket address: ws://192.168.15.103:8765
Starting backend synchronization every 30.0 seconds.
Loading InsightFace model buffalo_l.
Face recognition loop started.
```

A linha `WebSocket address: ws://...` é o endereço que você usa no painel. Quando um rosto é detectado, o log mostra se foi reconhecido, a distância e uma prévia da embedding.

Para parar: `Ctrl+C`.

**Teste rápido só da câmera (opcional):** `python ../tests/camera_test.py` tira uma foto `testeCam.jpg` usando o Picamera2.

**Dados locais:** o SQLite e o ChromaDB ficam em `raspberry/src/data/`. Para forçar uma ressincronização do zero, pare o programa e apague `raspberry/src/data/vision_face.db` e a pasta `raspberry/src/data/chroma/`; na próxima execução tudo é baixado do servidor de novo. Apague **os dois juntos**, nunca só um.

---

## 11. Conectando o painel à Raspberry

1. Com o servidor Docker rodando, abra o painel em `http://IP_DO_SERVIDOR:3000` (ou `http://localhost:3000`).
2. No campo **Endpoint da Raspberry**, informe o endereço do log (`ws://192.168.15.103:8765`) ou, para que ele já venha preenchido, defina `RASPBERRY_WS_URL` no `.env` do servidor e refaça o build do frontend: `docker compose up -d --build frontend`.
3. Clique em **Conectar**. Você deve ver o vídeo, o FPS e o indicador "Dispositivo conectado".

O navegador conecta **diretamente na Raspberry**, então o computador que abre o painel precisa estar na mesma rede dela (ou ter rota até ela).

---

## 12. Iniciar automaticamente no boot (systemd)

Para o reconhecimento subir sozinho quando a Raspberry ligar:

```bash
sudo nano /etc/systemd/system/vision-face.service
```

Conteúdo (ajuste `lucas` e o caminho se for diferente):

```ini
[Unit]
Description=Vision Face - reconhecimento facial
After=network-online.target
Wants=network-online.target

[Service]
User=lucas
WorkingDirectory=/home/lucas/Projetos/Vision-Face/raspberry/src
ExecStart=/home/lucas/Projetos/Vision-Face/raspberry/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Ative e inicie:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vision-face
```

Comandos úteis:

```bash
sudo systemctl status vision-face        # estado
journalctl -u vision-face -f             # logs em tempo real
sudo systemctl restart vision-face       # reiniciar após atualizar o código
sudo systemctl stop vision-face          # parar (necessário antes de rodar manualmente)
```

---

## 13. Desenvolvendo pelo VS Code (Remote SSH)

Para editar o código direto na Raspberry:

1. No VS Code do seu computador, instale a extensão **Remote - SSH** (Microsoft).
2. `F1` → **Remote-SSH: Connect to Host…** → `lucas@pi5.local` e digite a senha.
3. Abra a pasta `/home/lucas/Projetos/Vision-Face`.

Fluxo de atualização do código:

```bash
cd ~/Projetos/Vision-Face
git pull
sudo systemctl restart vision-face    # se estiver usando o systemd
```

---

## 14. Estrutura do código

```
raspberry/src/
├── main.py              # ponto de entrada: sync (thread) + monitor de rede (thread) + reconhecimento
├── ws_server.py         # servidor WebSocket e sinalização WebRTC para o navegador
├── network_monitor.py   # registra no log o estado do Wi-Fi e o endereço ws://IP:porta
├── recognition/
│   ├── camera.py        # captura via Picamera2 (1280x720, RGB888)
│   ├── face_engine.py   # InsightFace: detecção + embedding normalizada
│   ├── runner.py        # loop principal: captura → reconhece → envia pelo WebSocket
│   └── video_track.py   # track de vídeo WebRTC (até 20 FPS) com o último frame
├── sync/                # sincronização por delta com o backend + estado exposto ao painel
├── database/            # SQLite, ChromaDB e cache de pessoas em RAM
└── requirements.txt
```

---

## 15. Ajustes do reconhecimento

- **Modelo:** `buffalo_l` (nome com a letra "l"; `buffalo_1` não existe). O `det_size=(640, 640)` é a resolução de entrada do detector: o frame inteiro é redimensionado para ela, não é um recorte da imagem.
- **Distância de cosseno:** o ChromaDB usa a métrica de cosseno. Distância menor significa rosto mais parecido. O padrão aceita até `0.4`. Ajuste `FACE_MATCH_DISTANCE_THRESHOLD` somente depois de avaliar embeddings reais: valores maiores reconhecem mais, mas aumentam o risco de confundir pessoas.
- **Mais de um ângulo por pessoa:** cadastre embeddings de ângulos diferentes (frontal, diagonal) para melhorar a taxa de acerto.
- **FPS:** o valor enviado ao painel é o do laço completo (captura + reconhecimento), então mostra a lentidão real. O vídeo WebRTC é limitado a 20 FPS, mas o reconhecimento na CPU da Pi costuma rodar abaixo disso.
- O score cosseno (`1 − distância`) indica similaridade, não é uma probabilidade calibrada de acerto.

---

## 16. Problemas comuns

| Sintoma | Causa provável e solução |
| --- | --- |
| `ssh: Could not resolve hostname pi5.local` | Use o IP da Raspberry (veja no roteador). Confirme que computador e Raspberry estão na mesma rede. |
| `Permission denied` no SSH | Usuário ou senha diferentes dos definidos no Imager. Reconfigure regravando o cartão, se necessário. |
| Ícone de raio/aviso de subtensão | Fonte inadequada. Use a fonte de 27 W e um cabo USB-C de boa qualidade. |
| `no cameras available` | Cabo mal encaixado, invertido ou no conector errado (use o CAM/DISP 0). Desligue antes de mexer. |
| `ModuleNotFoundError: picamera2` | O ambiente virtual foi criado sem `--system-site-packages` ou o `python3-picamera2` não foi instalado. Recrie a venv com a flag e rode `sudo apt install python3-picamera2`. |
| `Camera startup failed` nos logs | A câmera está em uso por outro processo (`rpicam-*`, outra instância do `main.py` ou o serviço systemd). Pare o outro processo. |
| `API_URL must be configured` | O `.env` não está na raiz do repositório ou falta `API_URL`. |
| Log `Synchronization attempt ... failed` | A Raspberry não alcança o backend. Teste com `curl` (etapa 9) e confira o firewall do servidor. |
| Painel conecta mas o vídeo não aparece | Reconecte. Veja no log a mensagem de negociação do WebRTC. Computador e Raspberry precisam ter rota direta de rede. |
| `Wi-Fi is up but has no IPv4 address yet` | O DHCP ainda não entregou o IP; aguarde alguns segundos. |
| Raspberry esquenta e o FPS cai | Use cooler/case com ventilação. O reconhecimento mantém a CPU em carga contínua. |
