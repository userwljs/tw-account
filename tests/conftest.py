import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent)
)  # 将项目根插入到导入路径里

from src.models import Config


@pytest.fixture
def test_config(monkeypatch: pytest.MonkeyPatch):
    config_instance = Config(
        db_conn_scheme="sqlite+aiosqlite:///:memory:",
        jwt_es256_private_key="""-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIMTYj1pha3SgiQoblXDDVxrN7XBpqW+rQm/T6ukzVDscoAoGCCqGSM49
AwEHoUQDQgAE3LPffOhMvCyFXUIV6HFBA1yxUzMlMo5/ZpK82sZFOpUZWHTk84L3
VJljbtTHLOUVCSXxWdoWHtb7tmJcaaKDcA==""",
        jwt_es256_public_key="""-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE3LPffOhMvCyFXUIV6HFBA1yxUzMl
Mo5/ZpK82sZFOpUZWHTk84L3VJljbtTHLOUVCSXxWdoWHtb7tmJcaaKDcA==
-----END PUBLIC KEY-----""",
        email_verification_code_alphabet="T",
        smtp_host="::1",
        smtp_port=9901,
        smtp_use_tls=False,
        email_verification_code_from_email="noreply@example.com",
        restrict_email_domains="whitelist",
        restricted_email_domains=["example.com"],
    )

    def mock_get_config() -> Config:
        return config_instance

    monkeypatch.setattr("src.get_config", mock_get_config)
    monkeypatch.setattr("src.routes.email.get_config", mock_get_config)
    monkeypatch.setattr("src.routes.account.get_config", mock_get_config)

    return config_instance


@pytest.fixture
def test_client_with_config(test_config) -> Generator[tuple[TestClient, Config]]:
    from src import app

    with TestClient(app) as c:
        yield c, test_config
