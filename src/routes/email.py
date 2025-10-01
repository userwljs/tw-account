import datetime
import random
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import EmailStr

from ..config import get_config, limiter, make_session
from ..models import EmailDomainRestrictionInfo
from ..sql import EmailVerificationCode

router = APIRouter(prefix="/email")


async def verify_email_and_consume_code(email: str, request_code: str) -> bool:
    async with make_session() as session:
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


async def allowed_email(email: Annotated[EmailStr, Body(embed=True)]) -> str:
    config = get_config()

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


@router.get("/domain_restriction_info", response_model=EmailDomainRestrictionInfo)
async def email_domain_restriction_info():
    config = get_config()

    return EmailDomainRestrictionInfo(
        restrict_email_domains=config.restrict_email_domains,
        restricted_email_domains=list(config.restricted_email_domains),
    )


@router.post("/send_verification_code", responses={400: {"description": "请求被拒绝"}})
@limiter.limit("10/hour")
async def email_send_verification_code(
    request: Request, email: Annotated[str, Depends(allowed_email)]
):
    config = get_config()

    code: str = "".join(random.choices(config.email_verification_code_alphabet, k=6))
    print(f"生成邮件验证码：{email}：{code}")  # TODO
    code_item = EmailVerificationCode(
        email=email,
        code=code,
        expire=datetime.datetime.now().timestamp()
        + config.email_verification_code_lifespan,
    )
    async with make_session() as session:
        exist = await session.get(EmailVerificationCode, email)
        if exist is not None:
            await session.delete(exist)
        session.add(code_item)
        await session.commit()
