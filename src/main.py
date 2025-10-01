import datetime
import random
from contextlib import asynccontextmanager
from typing import Annotated

import pyotp
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.requests import Request
from pydantic import EmailStr, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from .config import get_config
from .models import Config, EmailDomainRestrictionInfo
from .sql import (
    Account,
    Base,
    EmailVerificationCode,
)

engine: AsyncEngine = None
session_maker: async_sessionmaker = None

config: Config = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, session_maker, config
    config = get_config()
    engine = create_async_engine(config.db_conn_scheme)
    session_maker = async_sessionmaker(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


async def validated_email(email: Annotated[EmailStr, Body(embed=True)]) -> str:
    if config.restrict_email_domains == "no":
        return email
    domain = email.split("@")[-1]
    if config.restrict_email_domains == "blacklist":
        if domain in config.restricted_email_domains:
            raise HTTPException(400, detail="邮箱域名处于黑名单中")
    if config.restrict_email_domains == "whitelist":
        if domain not in config.restricted_email_domains:
            raise HTTPException(400, detail="邮箱域名不处于白名单中")
    return email


@app.get("/email/domain_restriction_info", response_model=EmailDomainRestrictionInfo)
async def email_domain_restriction_info():
    return EmailDomainRestrictionInfo(
        restrict_email_domains=config.restrict_email_domains,
        restricted_email_domains=list(config.restricted_email_domains),
    )


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
    "/email/send_verification_code", responses={400: {"description": "请求被拒绝"}}
)
@limiter.limit("10/hour")
async def email_send_verification_code(
    request: Request, email: Annotated[str, Depends(validated_email)]
):
    code: str = "".join(random.choices(config.email_verification_code_alphabet, k=6))
    print(f"生成邮件验证码：{email}：{code}")  # TODO
    code_item = EmailVerificationCode(
        email=email,
        code=code,
        expire=datetime.datetime.now().timestamp()
        + config.email_verification_code_lifespan,
    )
    async with session_maker() as session:
        exist = await session.get(EmailVerificationCode, email)
        if exist is not None:
            await session.delete(exist)
        session.add(code_item)
        await session.commit()


@app.post("/account/register", responses={400: {"description": "请求被拒绝"}})
@limiter.limit("10/hour")
async def register_account(
    request: Request,
    email: Annotated[str, Depends(validated_email)],
    verify_code: Annotated[str, Field(min_length=6, max_length=6), Body(embed=True)],
):
    async with session_maker() as session:
        if (
            await session.execute(select(Account).where(Account.email == email))
        ).scalar_one_or_none() is not None:
            raise HTTPException(400, detail="此账户已存在")

        if not await validate_email_and_consume_code(email, verify_code):
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
