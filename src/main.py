import datetime
from typing import Annotated, Literal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine
import pyotp
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from fastapi.requests import Request
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select
import random
from .sql import (
    Account,
    Base,
    EmailVerificationCode,
)
from .config import get_config

engine: AsyncEngine = None
session_maker: async_sessionmaker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, session_maker
    engine = create_async_engine(get_config().db_conn_scheme)
    session_maker = async_sessionmaker(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

EMAIL_VERIFICATION_CODE_ALPHABET = (
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
)
# 去除：数字 0、大写 I、大写 O、小写 l


class Email(BaseModel):
    email_prefix: Annotated[str, Field(min_length=1, max_length=64)]
    email_domain: Literal[
        "qq.com", "163.com", "126.com", "gmail.com", "outlook.com"
    ]  # Annotated[str, Field(min_length=3, max_length=64)]

    def to_string(self) -> str:
        return f"{self.email_prefix}@{self.email_domain}"


class AccountRegistration(BaseModel):
    email: Email
    verify_code: Annotated[str, Field(min_length=6, max_length=6)]


async def validate_email_and_consume_code(email: str, request_code: str) -> bool:
    async with session_maker() as session:
        code = await session.get(EmailVerificationCode, email)
        if code is None:
            return False
        if code.expire < datetime.datetime.now().timestamp():
            await session.delete(code)
            await session.commit()
            return False
        if request_code != code.code:
            return False

        await session.delete(code)
        await session.commit()
        return True


@app.post(
    "/send_email_verification_code", responses={400: {"description": "请求被拒绝"}}
)
@limiter.limit("10/hour")
async def send_email_verification_code(request: Request, email: Email):
    email_string = email.to_string()
    code: str = "".join(random.choices(EMAIL_VERIFICATION_CODE_ALPHABET, k=6))
    print(f"生成邮件验证码：{email_string}：{code}")  # TODO
    code_item = EmailVerificationCode(
        email=email_string,
        code=code,
        expire=datetime.datetime.now().timestamp()
        + get_config().email_verification_code_lifespan,
    )
    async with session_maker() as session:
        exist = await session.get(EmailVerificationCode, email_string)
        if exist is not None:
            await session.delete(exist)
        session.add(code_item)
        await session.commit()


@app.post("/account/register", responses={400: {"description": "请求被拒绝"}})
@limiter.limit("10/hour")
async def register_account(request: Request, account: AccountRegistration):
    async with session_maker() as session:
        email: str = account.email.to_string()
        if (
            await session.execute(select(Account).where(Account.email == email))
        ).scalar_one_or_none() is not None:
            raise HTTPException(400, detail="此账户已存在")

        if not await validate_email_and_consume_code(email, account.verify_code):
            raise HTTPException(400, detail="验证码错误")

        new_account = Account(
            email=email, totp_secret=pyotp.random_base32(), status="NORMAL"
        )

        session.add(new_account)

        await session.commit()


def main():
    import uvicorn

    uvicorn.run(app, port=8080)


if __name__ == "__main__":
    main()
