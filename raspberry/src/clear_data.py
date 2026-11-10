"""CLI para limpar os bancos locais da Raspberry (ChromaDB e SQLite).

Os dados do servidor (PostgreSQL) não são tocados. Ao zerar o SQLite a versão
de sincronização volta para 0, então na próxima sincronização a Raspberry baixa
tudo de novo do servidor.

Uso (a partir de raspberry/src):
    python clear_data.py                  # mostra o que seria apagado e pergunta
    python clear_data.py --chroma         # só o ChromaDB (embeddings)
    python clear_data.py --sqlite         # só o SQLite (pessoas, outbox, versão do sync)
    python clear_data.py --all --yes      # os dois, sem perguntar
"""

import argparse
import subprocess
import sys

from sqlalchemy import delete, func, select

from database import init_database
from database.chroma import CHROMA_PATH, face_collection, chroma_lock
from database.database import DATABASE_PATH, SessionLocal
from database.models import Outbox, Person, SyncChange

SERVICE_NAME = "vision-face"
CHROMA_BATCH_SIZE = 500


def service_is_running() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", SERVICE_NAME],
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def count_sqlite() -> dict[str, int]:
    with SessionLocal() as session:
        return {
            "pessoas": session.scalar(select(func.count()).select_from(Person)) or 0,
            "outbox": session.scalar(select(func.count()).select_from(Outbox)) or 0,
            "versão de sync": session.scalar(select(func.count()).select_from(SyncChange)) or 0,
        }


def clear_sqlite() -> None:
    with SessionLocal() as session:
        session.execute(delete(Outbox))
        session.execute(delete(Person))
        session.execute(delete(SyncChange))
        session.commit()


def clear_chroma() -> int:
    with chroma_lock:
        ids = face_collection.get(include=[])["ids"]
        for start in range(0, len(ids), CHROMA_BATCH_SIZE):
            face_collection.delete(ids=ids[start:start + CHROMA_BATCH_SIZE])
    return len(ids)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Limpa os registros dos bancos locais da Raspberry."
    )
    parser.add_argument("--chroma", action="store_true", help="limpa só o ChromaDB")
    parser.add_argument("--sqlite", action="store_true", help="limpa só o SQLite")
    parser.add_argument("--all", action="store_true", help="limpa os dois (padrão)")
    parser.add_argument("-y", "--yes", action="store_true", help="não pede confirmação")
    parser.add_argument(
        "--force",
        action="store_true",
        help=f"roda mesmo com o serviço {SERVICE_NAME} ativo (não recomendado)",
    )
    args = parser.parse_args()

    do_chroma = args.chroma or args.all or not args.sqlite
    do_sqlite = args.sqlite or args.all or not args.chroma

    if service_is_running() and not args.force:
        print(
            f"O serviço '{SERVICE_NAME}' está rodando. Pare antes com:\n"
            f"  sudo systemctl stop {SERVICE_NAME}\n"
            "ou use --force (pode corromper os bancos)."
        )
        return 1

    init_database()

    print("Será apagado:")
    if do_chroma:
        print(f"  ChromaDB ({CHROMA_PATH}): {face_collection.count()} embeddings")
    if do_sqlite:
        counts = ", ".join(f"{name}: {value}" for name, value in count_sqlite().items())
        print(f"  SQLite ({DATABASE_PATH}): {counts}")
    if do_chroma != do_sqlite:
        print(
            "\nAtenção: limpar só um dos bancos deixa os dois fora de sincronia. "
            "O que foi apagado só volta se a versão de sync for zerada "
            "(use --sqlite junto com --chroma)."
        )
    print("Os dados do servidor não são alterados.")

    if not args.yes:
        if input("\nDigite 'apagar' para confirmar: ").strip().lower() != "apagar":
            print("Cancelado, nada foi apagado.")
            return 1

    if do_chroma:
        print(f"ChromaDB: {clear_chroma()} embeddings apagadas.")
    if do_sqlite:
        clear_sqlite()
        print("SQLite: registros apagados.")
    print("Pronto. Na próxima sincronização a Raspberry baixa tudo do servidor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
