"""User-scoped directories for saves, backups, clock anchors, and logs."""

import os
from pathlib import Path


def user_data_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA nao esta definido; nao foi possivel preparar os dados locais.")
    root = Path(local_app_data) / "GuildIdleManager"
    checkout = Path(__file__).resolve().parents[2]
    if root.resolve() == checkout or checkout in root.resolve().parents:
        raise RuntimeError("O diretorio de dados nao pode ficar dentro da pasta do aplicativo.")
    return root


def user_log_directory() -> Path:
    path = user_data_directory() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
