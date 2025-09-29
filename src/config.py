import os
from typing import Optional, Literal

import platformdirs
from pydantic import BaseModel


class Config(BaseModel):
    db_conn_scheme: str
    email_verification_code_lifespan: float = 300.0
    restrict_email_domains: Literal["no", "blacklist", "whitelist"] = "whitelist"
    restricted_email_domains: set[str] = {
        "qq.com",
        "163.com",
        "126.com",
        "gmail.com",
        "outlook.com",
    }


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is not None:
        return _config
    reload_config()
    return _config


def reload_config():
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
