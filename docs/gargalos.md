# Gargalos Implementados

Esta página descreve os gargalos identificados e as soluções implementadas no projeto.

!!! info
    O enunciado exige ao menos **2 gargalos por integrante** — 6 no total para este time de 3 pessoas.

---

## Gargalo 1 — Autenticação JWT

**Integrante responsável:** Hnery Idesis

**Problema identificado:**
Sem autenticação, qualquer cliente poderia consultar taxas de câmbio livremente, expondo o serviço a abusos e consumo irrestrito de recursos.

**Solução implementada:**
Validação de token JWT em todas as requisições via `HTTPBearer`. O `id-account` do usuário autenticado é extraído do campo `sub` do payload e retornado na resposta.

```python
def validar_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        account_id: str = payload.get("sub")
        if account_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return account_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
```

**Impacto:** Garante que apenas usuários autenticados pela plataforma possam consumir o serviço, protegendo contra acesso não autorizado.

---

## Gargalo 2 — Dependência de API Externa (Timeout)

**Integrante responsável:** Nathan Benaion

**Problema identificado:**
O serviço depende integralmente da AwesomeAPI. Se a API externa estiver lenta ou indisponível, a requisição do usuário falha ou trava indefinidamente, degradando toda a plataforma.

**Solução implementada:**
Definição de timeout de 10 segundos na requisição HTTP. Caso a API externa não responda no prazo, o erro é tratado e uma resposta adequada (`502 Bad Gateway`) é retornada ao cliente.

```python
async with httpx.AsyncClient() as client:
    try:
        response = await client.get(url, timeout=10.0)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Exchange API timeout"
        )
```

**Impacto:** Evita que o serviço trave indefinidamente aguardando resposta de terceiros, liberando threads para outras requisições.

---

## Gargalo 3 — Cache com Redis (Alta Latência em Requisições Repetidas)

**Integrante responsável:** Kauã Makiyama

**Problema identificado:**
Cada requisição ao endpoint de câmbio realizava uma chamada HTTP à AwesomeAPI, mesmo para o mesmo par de moedas consultado repetidamente em curto intervalo de tempo. Isso causava alta latência desnecessária e sobrecarga na API externa.

**Solução implementada:**
Camada de cache com Redis armazenando as cotações por 60 segundos (TTL). A implementação inclui fallback gracioso: se o Redis estiver indisponível, o serviço continua funcionando normalmente.

```python
import redis.asyncio as aioredis
import json

CACHE_TTL = 60

async def buscar_cache(r: aioredis.Redis, cache_key: str):
    cached = await r.get(cache_key)
    if cached:
        return json.loads(cached)
    return None

async def salvar_cache(r: aioredis.Redis, cache_key: str, data: dict):
    await r.setex(cache_key, CACHE_TTL, json.dumps(data))
```

**Impacto:** Requisições repetidas dentro de 60 segundos são respondidas diretamente do Redis, reduzindo latência e eliminando chamadas redundantes à API externa.

---

## Gargalo 4 — Validação de Entrada (Par de Moedas Inválido)

**Integrante responsável:** Nathan Benaion

**Problema identificado:**
Sem validação prévia, o serviço encaminhava qualquer string como par de moedas para a AwesomeAPI, gerando erros confusos e requisições desnecessárias para pares claramente inválidos (ex: `/exchanges/abc123/xyz!@#`).

**Solução implementada:**
Validação com regex antes de consultar a API externa, garantindo que ambas as moedas sejam strings alfabéticas de 3 a 5 caracteres.

```python
import re

CURRENCY_PATTERN = re.compile(r"^[A-Za-z]{3,5}$")

@app.get("/exchanges/{from_currency}/{to_currency}")
async def cotacao(from_currency: str, to_currency: str, ...):
    if not CURRENCY_PATTERN.match(from_currency) or not CURRENCY_PATTERN.match(to_currency):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid currency code. Use 3-5 letter codes (e.g. USD, BRL, EUR)."
        )
    ...
```

**Impacto:** Requisições com entradas malformadas são rejeitadas imediatamente com `422`, sem custo de chamada à API externa e com mensagem de erro clara para o cliente.

---

## Gargalo 5 — Observabilidade: Endpoint de Status

**Integrante responsável:** Hnery Idesis

**Problema identificado:**
Sem um endpoint de saúde, o orquestrador (Kubernetes, Docker Compose) não consegue verificar se o serviço está operacional. Uma instância travada ou em estado inconsistente continuaria recebendo tráfego.

**Solução implementada:**
Endpoint público `GET /exchanges/health-check` que retorna o status do serviço e a disponibilidade do cache Redis, permitindo que orquestradores e load balancers tomem decisões de roteamento.

```python
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
```

**Impacto:** Permite que Kubernetes e Docker realizem liveness/readiness probes, removendo automaticamente instâncias não saudáveis do pool de tráfego.

---

## Gargalo 6 — Degradação Graciosa do Cache (Fallback)

**Integrante responsável:** Kauã Makiyama

**Problema identificado:**
Uma implementação de cache que falha junto com o Redis deixaria o serviço completamente fora do ar sempre que o Redis ficasse indisponível, acoplando a disponibilidade do microsserviço à do cache.

**Solução implementada:**
O cliente Redis é inicializado com tratamento de exceção. Se a conexão falhar (na inicialização ou em qualquer operação), o serviço continua operando sem cache, consultando a API externa diretamente.

```python
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


r = await cache_conn()
if r:
    try:
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
```

**Impacto:** O serviço mantém 100% de disponibilidade mesmo quando o Redis está indisponível, degradando graciosamente para consultas diretas à API externa.
