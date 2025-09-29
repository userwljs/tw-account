import datetime
from typing import Annotated, Literal

import pyotp
from fastapi import FastAPI, HTTPException
from fastapi.requests import Request
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select
import random
from .sql import Account, Base, EmailVerificationCode, engine, the_session_maker
from .config import get_config

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
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


def validate_email_and_consume_code(email: str, request_code: str) -> bool:
    with the_session_maker() as session:
        code = session.get(EmailVerificationCode, email)
        if code is None:
            return False
        if code.expire < datetime.datetime.now().timestamp():
            session.delete(code)
            session.commit()
            return False
        if request_code != code.code:
            return False

        session.delete(code)
        session.commit()
        return True


@app.post(
    "/send_email_verification_code", responses={400: {"description": "请求被拒绝"}}
)
@limiter.limit("10/hour")
def send_email_verification_code(request: Request, email: Email):
    email_string = email.to_string()
    code: str = "".join(random.choices(EMAIL_VERIFICATION_CODE_ALPHABET, k=6))
    print(f"生成邮件验证码：{email_string}：{code}")  # TODO
    code_item = EmailVerificationCode(
        email=email_string,
        code=code,
        expire=datetime.datetime.now().timestamp()
        + get_config().email_verification_code_lifespan,
    )
    with the_session_maker() as session:
        exist = session.get(EmailVerificationCode, email_string)
        if exist is not None:
            session.delete(exist)
        session.add(code_item)
        session.commit()


@app.post("/account/register", responses={400: {"description": "请求被拒绝"}})
@limiter.limit("10/hour")
def register_account(request: Request, account: AccountRegistration):
    with the_session_maker() as session:
        email: str = account.email.to_string()
        if (
            session.execute(
                select(Account).where(Account.email == email)
            ).scalar_one_or_none()
            is not None
        ):
            raise HTTPException(400, detail="此账户已存在")

        if not validate_email_and_consume_code(email, account.verify_code):
            raise HTTPException(400, detail="验证码错误")

        new_account = Account(
            email=email, totp_secret=pyotp.random_base32(), status="NORMAL"
        )

        session.add(new_account)

        session.commit()


def main():
    Base.metadata.create_all(engine)

    import uvicorn

    uvicorn.run(app, port=8080)


if __name__ == "__main__":
    main()
