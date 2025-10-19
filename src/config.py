import os
import sys
import tomllib
from asyncio import Task
from dataclasses import dataclass

import platformdirs
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import Config
from .smtp import SMTPConnectionPool

_config: Config = None
_session_maker: async_sessionmaker = None

limiter: Limiter = Limiter(key_func=get_remote_address)


@dataclass
class GlobalShare:
    smtp_conn_pool: SMTPConnectionPool = None
    background_tasks: set[Task] = None
    # 重要！
    # https://github.com/python/cpython/issues/91887
    # https://docs.python.org/zh-cn/3/library/asyncio-task.html#asyncio.create_task


global_share = GlobalShare()


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


def get_data_path():
    data_path = os.getenv(
        "TW_ACCOUNT_DATA_PATH", platformdirs.user_data_path("tw-account")
    )
    if not os.path.isdir(data_path):
        os.makedirs(data_path)
    return data_path


def _load_config():
    global _config
    data_path = get_data_path()
    config_file_path = os.path.join(data_path, "config.toml")
    if not os.path.isfile(config_file_path):
        raise NotImplementedError("设置向导")
    try:
        _config = Config(**tomllib.load(open(config_file_path, "rb")))
    except Exception as e:
        print(f"无法加载配置文件 “{config_file_path}”：{str(e)}")
        sys.exit(1)
