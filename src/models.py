import uuid
from typing import Annotated, Literal, Optional, Self

from pydantic import BaseModel, Field, model_validator


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
    access_token_lifespan: float = 900.0  # 15 分钟
    refresh_token_lifespan: float = 2592000.0  # 30 天
    smtp_host: str
    smtp_port: int = 0
    smtp_use_tls: bool
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    email_verification_code_from_email: str  # 邮件验证码的发件人邮箱
    email_verification_code_from_name: Optional[str] = None  # 邮件验证码的发件人名称


class EmailDomainRestrictionInfo(BaseModel):
    restrict_email_domains: Literal["no", "blacklist", "whitelist"]
    restricted_email_domains: list[str]


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class AccountInfo(BaseModel):
    id: str
    email: str


class RefreshTokenInRequest(BaseModel):
    refresh_token: Annotated[str, Field(min_length=101, max_length=101)]

    @model_validator(mode="after")
    def check_format(self) -> Self:
        if self.refresh_token.count(".") != 1:
            raise ValueError()
        if self.refresh_token.index(".") != 36:
            raise ValueError()
        (lookup_id, token) = self.refresh_token.split(".")
        uuid.UUID(lookup_id)

        return self
