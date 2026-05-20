import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from jose import jwt

import main as app_module
from main import app

JWT_SECRET = "testsecret"
JWT_ALGORITHM = "HS256"


def gerar_jwt(account_id: str = "acc-123") -> str:
    return jwt.encode({"sub": account_id}, JWT_SECRET, algorithm=JWT_ALGORITHM)


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("JWT_ALGORITHM", JWT_ALGORITHM)
    monkeypatch.setattr(app_module, "JWT_SECRET", JWT_SECRET)
    monkeypatch.setattr(app_module, "JWT_ALGORITHM", JWT_ALGORITHM)


@pytest.fixture(autouse=True)
def limpar_cache(monkeypatch):
    monkeypatch.setattr(app_module, "_cache", None)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def token():
    return gerar_jwt()


@pytest.fixture()
def dados_api():
    return {
        "USDBRL": {
            "ask": "5.74",
            "bid": "5.73",
            "create_date": "2024-04-22 09:00:00",
        }
    }
