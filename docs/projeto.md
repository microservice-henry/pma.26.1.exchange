# Documentação do Projeto

## Descrição

A **Exchange API** é um microsserviço REST implementado em **Python** com **FastAPI** que expõe endpoints para consulta de taxas de câmbio em tempo real entre duas moedas. O serviço busca as cotações na [AwesomeAPI](https://docs.awesomeapi.com.br/){:target='_blank'}, armazena os resultados em **Redis** por 60 segundos (com fallback gracioso se o Redis estiver indisponível) e exige autenticação via token JWT para acesso ao endpoint principal.

---

## Tecnologias

| Tecnologia | Versão | Finalidade |
|---|---|---|
| Python | 3.12 | Linguagem principal |
| FastAPI | 0.115.0 | Framework web / REST |
| Uvicorn | 0.32.0 | Servidor ASGI |
| httpx | ≥ 0.28.1 | Requisições HTTP assíncronas |
| python-jose | 3.3.0 | Validação de tokens JWT |
| redis | ≥ 5.0.0 | Cache de cotações (TTL 60s) |
| Docker | — | Containerização |
| AwesomeAPI | — | Provedor externo de cotações |

---

## Endpoints

### `GET /exchanges/health-check`

Verifica se o serviço está operacional e se o Redis está acessível.

**Autenticação:** Nenhuma (endpoint público)

**Exemplo de resposta (200 OK):**

``` json
{
    "status": "ok",
    "cache": "ok"
}
```

| Campo | Valores possíveis |
|---|---|
| `status` | `"ok"` |
| `cache` | `"ok"` \| `"unavailable"` |

---

### `GET /exchanges/{from}/{to}`

Retorna a taxa de câmbio atual entre duas moedas. As cotações são servidas do cache Redis quando disponíveis (TTL de 60 segundos), reduzindo a latência e a dependência da API externa.

**Autenticação:** Bearer Token (JWT)

**Parâmetros de rota:**

| Parâmetro | Tipo | Restrição | Exemplo |
|---|---|---|---|
| `from` | string | 3–5 letras (A-Z) | `USD` |
| `to` | string | 3–5 letras (A-Z) | `BRL` |

**Exemplo de requisição:**

``` shell
curl -X GET "http://localhost:8000/exchanges/USD/BRL" \
     -H "Authorization: Bearer <token>"
```

**Exemplo de resposta (200 OK):**

``` json
{
    "sell": 5.74,
    "buy": 5.73,
    "date": "2024-04-22 09:00:00",
    "id-account": "0195ae95-5be7-7dd3-b35d-7a7d87c404fb",
    "cached": false
}
```

**Códigos de erro:**

| Código | Descrição |
|---|---|
| 401 | Token JWT inválido ou ausente |
| 404 | Par de moedas não encontrado na AwesomeAPI |
| 422 | Código de moeda com formato inválido (ex: `US$`, `BRL1234`) |
| 502 | Timeout na chamada à AwesomeAPI (> 10s) |

---

## Código Fonte

``` { .python .copy title="main.py" linenums="1" }
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import httpx
import redis.asyncio as aioredis
import json
import os
import re

app = FastAPI(title="Exchange API")
security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CACHE_TTL = 60

CURRENCY_PATTERN = re.compile(r"^[A-Za-z]{3,5}$")

_cache: aioredis.Redis | None = None


async def cache_conn() -> aioredis.Redis | None:
    global _cache
    if _cache is None:
        try:
            _cache = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            await _cache.ping()
        except Exception:
            _cache = None
    return _cache


def validar_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        account_id: str = payload.get("sub")
        if account_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return account_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@app.get("/exchanges/health-check")
async def status_check():
    cache_status = "unavailable"
    r = await cache_conn()
    if r:
        try:
            await r.ping()
            cache_status = "ok"
        except Exception:
            cache_status = "unavailable"
    return {"status": "ok", "cache": cache_status}


@app.get("/exchanges/{from_currency}/{to_currency}")
async def cotacao(
    from_currency: str,
    to_currency: str,
    account_id: str = Depends(validar_token),
):
    if not CURRENCY_PATTERN.match(from_currency) or not CURRENCY_PATTERN.match(to_currency):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid currency code. Use 3-5 letter codes (e.g. USD, BRL, EUR).",
        )

    par = f"{from_currency.upper()}-{to_currency.upper()}"
    cache_key = f"exchange:rate:{par}"

    r = await cache_conn()
    if r:
        try:
            cached = await r.get(cache_key)
            if cached:
                data = json.loads(cached)
                data["id-account"] = account_id
                data["cached"] = True
                return data
        except Exception:
            pass

    url = f"https://economia.awesomeapi.com.br/json/last/{par}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
        except httpx.TimeoutException:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Exchange API timeout")

    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency pair not found")

    data = response.json()
    chave = par.replace("-", "")

    if chave not in data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency pair not found")

    taxa = data[chave]
    armazenavel = {
        "sell": float(taxa["ask"]),
        "buy": float(taxa["bid"]),
        "date": taxa["create_date"],
        "cached": False,
    }

    if r:
        try:
            await r.setex(cache_key, CACHE_TTL, json.dumps(armazenavel))
        except Exception:
            pass

    return {**armazenavel, "id-account": account_id}
```

---

## Como Executar

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/){:target='_blank'} e [Docker Compose](https://docs.docker.com/compose/){:target='_blank'}
- Arquivo `.env` baseado no `.env.example`

### Com Docker Compose

``` shell
docker compose up --build
```

O serviço estará disponível em `http://localhost:8000`.

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `JWT_SECRET` | `secret` | Chave secreta para validação do JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo do JWT |
| `REDIS_HOST` | `localhost` | Host do Redis |
| `REDIS_PORT` | `6379` | Porta do Redis |

!!! warning "Atenção"

    Em produção, nunca utilize os valores padrão de `JWT_SECRET`. Utilize uma chave segura e aleatória.

### Documentação Interativa

Após subir o serviço, acesse `http://localhost:8000/docs` para a interface Swagger automática gerada pelo FastAPI.

---

## Testes

A suite de testes cobre os principais cenários do serviço, incluindo autenticação, validação de entrada, cache hit/miss e timeout.

``` shell
python -m pytest tests/ -v
```

| Teste | Cenário |
|---|---|
| `test_status_sem_cache` | Health-check sem Redis disponível |
| `test_status_com_cache` | Health-check com Redis ativo |
| `test_sem_autenticacao` | Requisição sem token → 403 |
| `test_token_invalido` | Token JWT corrompido → 401 |
| `test_moeda_invalida` | Código de moeda com formato errado → 422 |
| `test_cotacao_retornada_com_sucesso` | Fluxo normal sem cache → 200 |
| `test_retorno_do_cache` | Cotação servida do Redis → 200 cached |
| `test_timeout_da_api_externa` | AwesomeAPI não responde → 502 |
