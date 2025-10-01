from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select

from ..config import limiter, make_session
from ..sql import Account
from .email import allowed_email, verify_email_and_consume_code

router = APIRouter(prefix="/account")


@router.post("/register", responses={400: {"description": "请求被拒绝"}})
@limiter.limit("10/hour")
async def register_account(
    request: Request,
    email: Annotated[str, Depends(allowed_email)],
    verify_code: Annotated[str, Field(min_length=6, max_length=6), Body(embed=True)],
):
    async with make_session() as session:
        if (
            await session.execute(select(Account).where(Account.email == email))
        ).scalar_one_or_none() is not None:
            raise HTTPException(400, detail="此账户已存在")

        if not await verify_email_and_consume_code(email, verify_code):
            raise HTTPException(400, detail="验证码错误")

        new_account = Account(email=email, status="NORMAL")

        session.add(new_account)

        await session.commit()
