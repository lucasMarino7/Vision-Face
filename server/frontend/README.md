# Frontend Vision Face

Interface React/Vite para o monitoramento da câmera e gerenciamento dos cadastros da API Flask.

## Executar

Em desenvolvimento, inicie o backend Flask em `http://localhost:8000` e execute:

```sh
npm install
npm run dev
```

O Vite encaminha `/api` para `http://localhost:<BACKEND_PORT>` (lido do `.env` da raiz; padrão 8000). Pelo Docker Compose, a interface fica em `http://localhost:3000` (ou na porta definida por `FRONTEND_PORT`).

## WebSocket e WebRTC

O endereço WebSocket da Raspberry pode ser informado no painel ou pela variável de build `RASPBERRY_WS_URL` (lida do `.env` da raiz). O navegador conecta direto na Raspberry: ela envia uma oferta WebRTC, o navegador responde com `answer` e os candidatos ICE trafegam como `ice-candidate`.

O formato das mensagens (`offer`, `ice-candidate`, `status` com FPS e sincronização, `faces`) está documentado na [seção 10 do README da raiz](../../README.md#10-referência-da-api-e-do-websocket). O painel mostra apenas os rostos presentes no frame atual (mensagem `faces`) e desenha as caixas no canvas sobre o vídeo.

Datas são exibidas e digitadas no formato brasileiro `dd/mm/aaaa`; a API continua usando ISO (`aaaa-mm-dd`).
