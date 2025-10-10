from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import get_config, global_share, limiter, set_session_maker
from .routes import account, email
from .smtp import SMTPClientFactory, SMTPConnectionPool
from .sql import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    engine = create_async_engine(config.db_conn_scheme)
    session_maker = async_sessionmaker(engine)
    set_session_maker(session_maker)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    smtp_client_factory = SMTPClientFactory(
        hostname=config.smtp_host,
        use_tls=config.smtp_use_tls,
        port=config.smtp_port,
        username=config.smtp_username,
        password=config.smtp_password,
    )
    global_share.smtp_conn_pool = SMTPConnectionPool(smtp_client_factory)
    global_share.background_tasks = set()
    yield


app = FastAPI(lifespan=lifespan, root_path="/api")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(account.router)
app.include_router(email.router)
