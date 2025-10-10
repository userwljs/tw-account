import asyncio
import datetime
import secrets
from email.message import EmailMessage
from email.utils import formataddr
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import EmailStr, Field

from ..config import get_config, global_share, limiter, make_session
from ..models import EmailDomainRestrictionInfo
from ..smtp import send_message
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


async def allowed_email(
    email: Annotated[EmailStr, Body(embed=True), Field(max_length=129)],
) -> str:
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


@router.post(
    "/send_verification_code",
    responses={400: {"description": "请求被拒绝"}},
    status_code=202,
)
@limiter.limit("10/hour")
async def email_send_verification_code(
    request: Request, email: Annotated[str, Depends(allowed_email)]
):
    config = get_config()

    code: str = "".join(
        secrets.choice(config.email_verification_code_alphabet) for i in range(6)
    )
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
    msg = EmailMessage()
    msg.set_content(
        f"您的邮件验证码为：{code}，请勿透露给他人，验证码 {config.email_verification_code_lifespan:.0f} 秒内有效。"
    )
    msg["Subject"] = "邮件验证码"
    msg["From"] = formataddr(
        (
            config.email_verification_code_from_name,
            config.email_verification_code_from_email,
        )
    )
    msg["To"] = email

    task = asyncio.create_task(send_message(global_share.smtp_conn_pool, msg))

    global_share.background_tasks.add(task)
    # 重要！
    # https://github.com/python/cpython/issues/91887
    # https://docs.python.org/zh-cn/3/library/asyncio-task.html#asyncio.create_task

    task.add_done_callback(global_share.background_tasks.discard)
