from typing import Annotated, Literal

from pydantic import BaseModel, Field


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
    email_verification_code_alphabet: Annotated[str, Field(min_length=1)] = (
        "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"  # 去除：数字 0、大写 I、大写 O、小写 l
    )
    jwt_es256_private_key: str
    jwt_es256_public_key: str
    access_token_lifespan: float = 2592000.0  # 30 天


class EmailDomainRestrictionInfo(BaseModel):
    restrict_email_domains: Literal["no", "blacklist", "whitelist"]
    restricted_email_domains: list[str]


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
