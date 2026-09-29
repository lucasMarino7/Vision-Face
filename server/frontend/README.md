# Frontend Vision Face

Interface React/Vite para o monitoramento da câmera e gerenciamento dos cadastros da API Flask.

## Executar

Em desenvolvimento, inicie o backend Flask em `http://localhost:8000` e execute:

```sh
npm install
npm run dev
```

O Vite encaminha `/api` para o backend. Para alterar o destino local, defina `BACKEND_PROXY_TARGET` antes de iniciar o Vite. Pelo Docker Compose, a interface fica em `http://localhost:3000` (ou na porta definida por `FRONTEND_PORT`).

## WebSocket e WebRTC

O endereço WebSocket da Raspberry pode ser informado no painel ou pela variável de build `RASPBERRY_WS_URL`. O serviço Raspberry precisa aceitar a conexão WebSocket do navegador e retransmitir sinalização WebRTC. O navegador espera uma oferta iniciada pela Raspberry e responde com `answer`; candidatos ICE são enviados/recebidos como `ice-candidate`.

Mensagens JSON esperadas no mesmo WebSocket:

```json
{"type":"offer","sdp":{"type":"offer","sdp":"..."}}
{"type":"ice-candidate","candidate":{"candidate":"...","sdpMid":"0","sdpMLineIndex":0}}
{"type":"status","camera_online":true}
{"type":"detection","person":{"name":"Nome","date_birth":"1990-01-01","age":36,"wanted":false,"reason":null,"embedding":[0.1]},"box":{"x":120,"y":60,"width":180,"height":220}}
```

Para uma pessoa não reconhecida, envie `person.recognized: false` (ou `person_id: null`). Os boxes podem usar coordenadas em pixels da imagem original ou valores normalizados entre 0 e 1. O vetor enviado em eventos de detecção é exibido apenas nos dados recebidos; o cadastro de embeddings usa os endpoints CRUD Flask e exige 512 valores. A aplicação desenha os boxes no canvas sobre o vídeo WebRTC.

O repositório ainda não contém servidor de sinalização ou cliente WebSocket implementado na Raspberry. Portanto, a interface de gerenciamento via REST está pronta, mas o feed ao vivo depende de um endpoint WebSocket compatível com o protocolo acima.
