from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import get_config, limiter, set_session_maker
from .routes import account, email
from .sql import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    engine = create_async_engine(config.db_conn_scheme)
    session_maker = async_sessionmaker(engine)
    set_session_maker(session_maker)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan, root_path=get_config().root_path)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(account.router)
app.include_router(email.router)
