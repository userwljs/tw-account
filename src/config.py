import os

import platformdirs
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import Config

_config: Config = None
_session_maker: async_sessionmaker = None

limiter: Limiter = Limiter(key_func=get_remote_address)


def get_config() -> Config:
    global _config
    if _config is not None:
        return _config
    _load_config()
    return _config


def make_session() -> AsyncSession:
    return _session_maker()


def set_session_maker(session_maker: async_sessionmaker):
    global _session_maker
    _session_maker = session_maker


def _load_config():
    global _config
    data_path = os.getenv(
        "TW_ACCOUNT_DATA_PATH", platformdirs.user_data_path("tw-account")
    )
    if not os.path.isdir(data_path):
        os.makedirs(data_path)
    config_file_path = os.path.join(data_path, "config.json")
    if not os.path.isfile(config_file_path):
        raise NotImplementedError("设置向导")
    _config = Config.model_validate_json(open(config_file_path).read())
