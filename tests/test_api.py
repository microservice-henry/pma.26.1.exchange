import json
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response


def simular_resposta(json_data: dict, status_code: int = 200):
    resp = MagicMock(spec=Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def test_status_sem_cache(client):
    with patch("main.cache_conn", new=AsyncMock(return_value=None)):
        r = client.get("/exchanges/health-check")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "cache": "unavailable"}


def test_status_com_cache(client):
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    with patch("main.cache_conn", new=AsyncMock(return_value=mock_redis)):
        r = client.get("/exchanges/health-check")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "cache": "ok"}


def test_sem_autenticacao(client):
    r = client.get("/exchanges/USD/BRL")
    assert r.status_code == 403


def test_token_invalido(client):
    r = client.get("/exchanges/USD/BRL", headers={"Authorization": "Bearer invalido"})
    assert r.status_code == 401


def test_moeda_invalida(client, token):
    r = client.get(
        "/exchanges/USD/BRL123456",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_moeda_com_caractere_especial(client, token):
    r = client.get(
        "/exchanges/US$/BRL",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_cotacao_retornada_com_sucesso(client, token, dados_api):
    mock_resp = simular_resposta(dados_api)

    with patch("main.cache_conn", new=AsyncMock(return_value=None)), \
         patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        r = client.get(
            "/exchanges/USD/BRL",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["sell"] == 5.74
    assert body["buy"] == 5.73
    assert body["id-account"] == "acc-123"
    assert body["cached"] is False


def test_par_nao_encontrado(client, token):
    mock_resp = simular_resposta({}, status_code=404)

    with patch("main.cache_conn", new=AsyncMock(return_value=None)), \
         patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        r = client.get(
            "/exchanges/USD/XYZ",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 404


def test_retorno_do_cache(client, token):
    payload_cache = json.dumps(
        {"sell": 5.74, "buy": 5.73, "date": "2024-04-22 09:00:00", "cached": False}
    )

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=payload_cache)

    with patch("main.cache_conn", new=AsyncMock(return_value=mock_redis)):
        r = client.get(
            "/exchanges/USD/BRL",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["cached"] is True
    assert body["sell"] == 5.74


def test_timeout_da_api_externa(client, token):
    with patch("main.cache_conn", new=AsyncMock(return_value=None)), \
         patch(
             "httpx.AsyncClient.get",
             new=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
         ):
        r = client.get(
            "/exchanges/USD/BRL",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 502
