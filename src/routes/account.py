import datetime
import secrets
import uuid
from typing import Annotated

import jwt
from email_validator import EmailNotValidError
from email_validator.validate_email import validate_email
from fastapi import (
    APIRouter,
    Body,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config, limiter, make_session
from ..models import AccountInfo, RefreshTokenInRequest, Token
from ..sql import Account, RefreshToken
from .email import allowed_email, verify_email_and_consume_code

router = APIRouter(prefix="/account")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="account/login")


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


async def create_access_token(account_id: str) -> str:
    config = get_config()
    to_encode = {
        "sub": str(account_id),
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=config.access_token_lifespan),
    }
    encoded_jwt = jwt.encode(to_encode, config.jwt_es256_private_key, algorithm="ES256")
    return encoded_jwt


async def create_refresh_token(
    owner_id: uuid.UUID, expire: float, session: AsyncSession
) -> str:
    token_in_db = RefreshToken(
        token=secrets.token_hex(32), owner_id=owner_id, expire=expire
    )
    session.add(token_in_db)
    await session.commit()
    return f"{token_in_db.lookup_id}.{token_in_db.token}"


async def set_refresh_token(response: Response, token_str: str):
    response.set_cookie(
        "refresh_token",
        token_str,
        secure=True,
        httponly=True,
        samesite="strict",
    )


async def rotate_refresh_token(
    response: Response, refresh_token_in_db: RefreshToken, session: AsyncSession
):
    """轮换刷新令牌。

    :param response: FastAPI Response
    :param refresh_token_in_db: 待轮换的 SQLAlchemy ORM RefreshToken 对象
    :param session: 获取待轮换对象的 AsyncSession"""
    refresh_token_in_db.lookup_id = uuid.uuid4()
    refresh_token_in_db.token = secrets.token_hex(32)
    await session.commit()
    await set_refresh_token(
        response, f"{str(refresh_token_in_db.lookup_id)}.{refresh_token_in_db.token}"
    )


@router.post("/login")
@limiter.limit("10/hour")
async def login(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    EMAIL_OR_VERIFICATION_CODE_WRONG = "邮箱或验证码错误"

    try:
        email = validate_email(form_data.username).email
    except EmailNotValidError:
        raise HTTPException(400, detail="无效的邮箱地址")
    await allowed_email(email)  # 检查邮箱域名是否允许
    async with make_session() as session:
        account = (
            await session.execute(select(Account).where(Account.email == email))
        ).scalar_one_or_none()
        if account is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, detail=EMAIL_OR_VERIFICATION_CODE_WRONG
            )
        if not await verify_email_and_consume_code(email, form_data.password):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, detail=EMAIL_OR_VERIFICATION_CODE_WRONG
            )

        encoded_jwt = await create_access_token(account.id)

        refresh_token = await create_refresh_token(
            account.id,
            datetime.datetime.now().timestamp() + get_config().refresh_token_lifespan,
            session,
        )

        await set_refresh_token(response, refresh_token)

        return Token(access_token=encoded_jwt)


@router.post("/refresh")
async def refresh_access_token(
    response: Response, refresh_token: Annotated[RefreshTokenInRequest, Cookie()]
) -> Token:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    (lookup_id, request_token) = refresh_token.refresh_token.split(".")
    async with make_session() as session:
        target_token = await session.get(RefreshToken, lookup_id)
        if (target_token is None) or (
            not secrets.compare_digest(request_token, target_token.token)
        ):
            raise credentials_exception
        if target_token.expire < datetime.datetime.now().timestamp():
            session.delete(target_token)
            await session.commit()
            raise credentials_exception
        await rotate_refresh_token(response, target_token, session)
        return Token(access_token=create_access_token(target_token.owner_id))


async def get_current_account(token: Annotated[str, Depends(oauth2_scheme)]):
    config = get_config()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.jwt_es256_public_key, algorithms="ES256")
        id: str = payload.get("sub")
        async with make_session() as session:
            account = await session.get(Account, id)
            if account is None:
                raise credentials_exception
            if account.status != "NORMAL":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="账户状态异常",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return account
    except jwt.InvalidTokenError:
        raise credentials_exception


@router.get("/me/info")
async def my_info(
    account: Annotated[Account, Depends(get_current_account)],
) -> AccountInfo:
    return AccountInfo(id=str(account.id), email=account.email)
