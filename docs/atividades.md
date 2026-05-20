# Atividades Realizadas

Esta página documenta as atividades práticas realizadas ao longo da disciplina.

---

## Atividade 1 — Criação do Microsserviço FastAPI com Autenticação JWT

**Descrição:**
Criação do microsserviço de câmbio utilizando FastAPI, com autenticação via token JWT. O serviço expõe o endpoint `GET /exchanges/{from}/{to}` e valida o token Bearer em cada requisição, extraindo o `id-account` do payload para incluir na resposta.

**Código:**
```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import os

app = FastAPI(title="Exchange API")
security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def get_current_account_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        account_id: str = payload.get("sub")
        if account_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
        return account_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


@app.get("/exchanges/{from_currency}/{to_currency}")
async def get_exchange(
    from_currency: str,
    to_currency: str,
    account_id: str = Depends(get_current_account_id),
):
    ...
```

**Resultado:**
O serviço passou a exigir um JWT válido em todas as requisições. Sem o token, a resposta é `401 Unauthorized`.

---

## Atividade 2 — Integração com a AwesomeAPI e Containerização com Docker

**Descrição:**
Integração do microsserviço com a [AwesomeAPI](https://economia.awesomeapi.com.br) para obter cotações em tempo real. O serviço realiza uma chamada HTTP assíncrona com `httpx` e retorna as taxas de venda (`ask`) e compra (`bid`). Em seguida, o projeto foi containerizado com Docker e orquestrado via Docker Compose.

**Código:**
```python
import httpx

@app.get("/exchanges/{from_currency}/{to_currency}")
async def get_exchange(from_currency: str, to_currency: str, ...):
    pair = f"{from_currency.upper()}-{to_currency.upper()}"
    url = f"https://economia.awesomeapi.com.br/json/last/{pair}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10.0)

    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Currency pair not found")

    data = response.json()
    key = pair.replace("-", "")
    rate = data[key]

    return {
        "sell": float(rate["ask"]),
        "buy": float(rate["bid"]),
        "date": rate["create_date"],
        "id-account": account_id,
    }
```

**Dockerfile:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Resultado:**
O serviço pode ser iniciado com `docker compose up` e responde corretamente a cotações como `USD-BRL`, `EUR-BRL` e `BTC-BRL`.

---

## Atividade 3 — Implementação de Cache com Redis

**Descrição:**
Adição de uma camada de cache utilizando Redis para reduzir a latência e o número de chamadas à AwesomeAPI. O cache armazena as cotações com TTL de 60 segundos por par de moedas. A implementação inclui fallback gracioso: se o Redis estiver indisponível, o serviço continua funcionando normalmente, consultando a API externa diretamente.

**Código:**
```python
import redis.asyncio as aioredis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CACHE_TTL = 60

redis_client: aioredis.Redis | None = None

async def get_redis():
    global redis_client
    if redis_client is None:
        try:
            redis_client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            await redis_client.ping()
        except Exception:
            redis_client = None
    return redis_client


@app.get("/exchanges/{from_currency}/{to_currency}")
async def get_exchange(from_currency: str, to_currency: str, ...):
    pair = f"{from_currency.upper()}-{to_currency.upper()}"
    cache_key = f"exchange:rate:{pair}"

    r = await get_redis()
    if r:
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)

    # Consulta a API externa somente se não há cache
    rate = await fetch_from_api(pair)
    response_data = {"sell": rate["sell"], "buy": rate["buy"], ..., "cached": False}

    if r:
        await r.setex(cache_key, CACHE_TTL, json.dumps(response_data))

    return response_data
```

**Resultado:**
Requisições repetidas para o mesmo par de moedas dentro de 60 segundos são respondidas diretamente do Redis, reduzindo significativamente a latência e a carga sobre a AwesomeAPI.
