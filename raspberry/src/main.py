# FEITO
# criar models com sqlalchemy
# criar tabela intermédiaria (outbox_peron) para lidar com a dupla escrita somente ocorrida quando uma pessoa for deletada, para que o chromaDB não fique com dados órfãos
# criar tabela de versionamento (sync_change) para operação feita com a api 'delta', seja armazenado a versão nesta tabela (não será usado a rota 'full', apenas será usada a rota 'delta' para sincronização incremental)

# FEITO
# criar chromaDB
# em seu metados irá armazenar o id da pessoa, o id da embedding e o angulo do rosto

# FEITO
# criar rotas para acesso da api

# FEITO
# criar código com thread para fazer sincronização dos dados assincrona
# lidar com dupla escrita no chromaDB e no banco de dados relacional quando houver a deleção de uma pessoa
# a theread irá ser rodada a cada 30 segundos, irá verificar se deve fazer sincronização da tabela de pessoas no sqlite e depois a sincronização das embeddings no chromaDB e depois alterações na tabela de outbox_person

# FEITO
# criar código para fazer o reconhecimento facial
# criar mutex para evitar conflitos de acesso simultaneo ao sqlite e chromaDB
# criar dicionário para armazenar na memória todas as pessoas, sendo que a chave será o id da pessoa, dessa forma não será necessário ficar acessando o sqlite a cada frame
# quando houver alguma alteração no banco de dados relacional, atualizar o dicionário em memória e o chromaDB

# FEITO
# criar código para envio dos dados via websockets
# criar código para stream via webrtc

import logging
import os
from threading import Event, Thread

from database import init_database
from recognition.runner import run_recognition_loop
from sync import run_sync_loop
from ws_server import DetectionWebSocketServer


def _configured_port() -> int:
    try:
        port = int(os.getenv("WEBSOCKET_PORT", "8765"))
        if not 0 < port < 65536:
            raise ValueError
        return port
    except ValueError:
        logging.error("Invalid WEBSOCKET_PORT; using default port 8765.")
        return 8765


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
    )

    init_database()
    stop_event = Event()
    sync_thread = Thread(
        target=run_sync_loop,
        args=(stop_event,),
        kwargs={
            "interval_seconds": float(os.getenv("SYNC_INTERVAL_SECONDS", "30"))
        },
        name="backend-sync",
        daemon=True,
    )
    sync_thread.start()
    websocket_server = DetectionWebSocketServer(
        host=os.getenv("WEBSOCKET_HOST", "0.0.0.0"),
        port=_configured_port(),
    )

    try:
        while not stop_event.is_set():
            try:
                run_recognition_loop(stop_event, websocket_server)
            except Exception:
                logging.exception("Recognition service failed; restarting in 5 seconds.")
                stop_event.wait(5)
    except KeyboardInterrupt:
        logging.info("Shutdown requested.")
    finally:
        stop_event.set()
        sync_thread.join()