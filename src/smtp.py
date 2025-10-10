import asyncio
from collections import deque
from contextlib import asynccontextmanager
from email.message import EmailMessage
from typing import Optional

from aiosmtplib import SMTP
from aiosmtplib.typing import Default


class SMTPClientFactory:
    """SMTP 客户端工厂，用于创建独立的客户端实例"""

    def __init__(
        self,
        hostname: str,
        use_tls: bool,
        port: int = 0,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.hostname = hostname
        self.port = Default.token if port is None or port == 0 else port
        self.use_tls = use_tls
        self.username = username
        self.password = password

    @asynccontextmanager
    async def get_client(self):
        """获取一个独立的SMTP客户端上下文"""
        smtp = SMTP()
        try:
            await smtp.connect(
                hostname=self.hostname, port=self.port, use_tls=self.use_tls
            )
            if self.username is not None:
                await smtp.login(self.username, self.password)
            yield smtp
        finally:
            await smtp.quit()


class SMTPConnectionPool:
    def __init__(self, factory: SMTPClientFactory, max_size: int = 10):
        self.factory = factory
        self.max_size = max_size
        self.pool = deque()
        self.size = 0
        self.lock = asyncio.Lock()

    @asynccontextmanager
    async def get_connection(self):
        async with self.lock:
            smtp: SMTP = None
            if len(self.pool) > 0:
                smtp = self.pool.popleft()
            if (smtp is None and self.size < self.max_size) or (
                smtp is not None and not smtp.is_connected
            ):
                smtp = SMTP()
                await smtp.connect(
                    hostname=self.factory.hostname,
                    port=self.factory.port,
                    use_tls=self.factory.use_tls,
                )
                if self.factory.username is not None:
                    await smtp.login(self.factory.username, self.factory.password)
                self.size += 1
            else:
                # 等待连接可用或创建新连接
                smtp = SMTP()
                await smtp.connect(
                    hostname=self.factory.hostname,
                    port=self.factory.port,
                    use_tls=self.factory.use_tls,
                )
                if self.factory.username:
                    await smtp.login(self.factory.username, self.factory.password)

        try:
            yield smtp
        finally:
            async with self.lock:
                if len(self.pool) < self.max_size:
                    self.pool.append(smtp)
                else:
                    await smtp.quit()
                    self.size -= 1


async def send_message(pool: SMTPConnectionPool, message: EmailMessage):
    async with pool.get_connection() as conn:
        await conn.send_message(message)
