from fastapi import FastAPI, Depends, HTTPException, Query, status
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
            _cache = aioredis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
            )
            await _cache.ping()
        except Exception:
            _cache = None
    return _cache


def validar_token(
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


@app.get("/exchange")
async def cotacao_interna(
    from_: str = Query(alias="from"),
    to: str = Query(),
):
    """Internal endpoint for service-to-service calls (no auth required)."""
    if not CURRENCY_PATTERN.match(from_) or not CURRENCY_PATTERN.match(to):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid currency code. Use 3-5 letter codes (e.g. USD, BRL, EUR).",
        )

    par = f"{from_.upper()}-{to.upper()}"
    cache_key = f"exchange:rate:{par}"

    r = await cache_conn()
    if r:
        try:
            cached = await r.get(cache_key)
            if cached:
                data = json.loads(cached)
                return {"rate": data["sell"]}
        except Exception:
            pass

    url = f"https://economia.awesomeapi.com.br/json/last/{par}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Exchange API timeout",
            )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Currency pair not found"
        )

    data = response.json()
    chave = par.replace("-", "")

    if chave not in data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Currency pair not found"
        )

    taxa = data[chave]
    sell = float(taxa["ask"])

    armazenavel = {
        "sell": sell,
        "buy": float(taxa["bid"]),
        "date": taxa["create_date"],
        "cached": False,
    }

    if r:
        try:
            await r.setex(cache_key, CACHE_TTL, json.dumps(armazenavel))
        except Exception:
            pass

    return {"rate": sell}


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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Exchange API timeout",
            )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Currency pair not found"
        )

    data = response.json()
    chave = par.replace("-", "")

    if chave not in data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Currency pair not found"
        )

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
