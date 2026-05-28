# Exchange API

???+ info inline end "Edição"

    2026.1

## Equipe

1. Henry Idesis
1. Nathan Benaion
1. Kauã Makiyama

!!! tip "Repositório"

    [github.com/microservice-henry/pma.26.1.exchange](https://github.com/microservice-henry/pma.26.1.exchange){:target='_blank'}

---

## Entregas

- [x] Roteiro 1 — Criação do microsserviço FastAPI com JWT
- [x] Roteiro 2 — Integração com AwesomeAPI e containerização Docker
- [x] Roteiro 3 — Cache com Redis e endpoint de health-check
- [x] Roteiro 4 — Testes automatizados e deploy via GitHub Actions
- [x] Apresentação em vídeo

---

## Arquitetura

A Exchange API faz parte de uma plataforma de microsserviços. Toda requisição entra pelo **Gateway**, que valida o JWT e injeta o `id-account` no header antes de encaminhar ao serviço de câmbio.

``` mermaid
flowchart LR
    C([Cliente]) -->|JWT| G[Gateway]
    G -->|valida| A[Auth Service]
    G -->|id-account| E[Exchange API]
    E -->|cache hit/miss| R[(Redis)]
    E -->|cotação| AW([AwesomeAPI])

    style E fill:#4051b5,color:#fff
    style R fill:#d32f2f,color:#fff
    style G fill:#00796b,color:#fff
```

### Fluxo de uma Requisição

``` mermaid
sequenceDiagram
    participant C as Cliente
    participant G as Gateway
    participant E as Exchange API
    participant R as Redis
    participant A as AwesomeAPI

    C->>G: GET /exchanges/USD/BRL (Bearer JWT)
    G->>E: GET /exchanges/USD/BRL (id-account header)
    E->>R: GET exchange:rate:USD-BRL
    alt cache hit (TTL 60s)
        R-->>E: cotação em cache
    else cache miss
        E->>A: GET /json/last/USD-BRL
        A-->>E: { bid, ask, create_date }
        E->>R: SET exchange:rate:USD-BRL (TTL 60s)
    end
    E-->>G: { sell, buy, date, id-account }
    G-->>C: { sell, buy, date, id-account }
```

---

## Exemplo de Código

=== "Endpoint principal"

    ``` { .python .copy title="main.py" linenums="1" }
    @app.get("/exchanges/{from_currency}/{to_currency}")
    async def cotacao(
        from_currency: str,
        to_currency: str,
        account_id: str = Depends(validar_token),
    ):
        if not CURRENCY_PATTERN.match(from_currency) or not CURRENCY_PATTERN.match(to_currency):
            raise HTTPException(status_code=422, detail="Invalid currency code.")

        par = f"{from_currency.upper()}-{to_currency.upper()}"
        cache_key = f"exchange:rate:{par}"

        r = await cache_conn()
        if r:
            cached = await r.get(cache_key)
            if cached:
                data = json.loads(cached)
                data["id-account"] = account_id
                data["cached"] = True
                return data

        url = f"https://economia.awesomeapi.com.br/json/last/{par}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)  # (1)!

        taxa = response.json()[par.replace("-", "")]
        resultado = {"sell": float(taxa["ask"]), "buy": float(taxa["bid"]), ...}

        if r:
            await r.setex(cache_key, CACHE_TTL, json.dumps(resultado))  # (2)!

        return {**resultado, "id-account": account_id}
    ```

    1. Timeout de 10 segundos para evitar que uma API lenta trave o serviço indefinidamente.
    2. Armazena a cotação no Redis com TTL de 60 segundos, eliminando chamadas redundantes à AwesomeAPI.

=== "Docker Compose"

    ``` { .yaml .copy title="compose.yaml" }
    services:
      exchange:
        build: .
        ports:
          - "8000:8000"
        environment:
          - JWT_SECRET=${JWT_SECRET}
          - JWT_ALGORITHM=${JWT_ALGORITHM:-HS256}
          - REDIS_HOST=redis
          - REDIS_PORT=6379
        depends_on:
          - redis

      redis:
        image: redis:7-alpine
        ports:
          - "6379:6379"
    ```

---

## Vídeo de Apresentação

[https://youtu.be/zGQpPKkvC_w](https://youtu.be/zGQpPKkvC_w){:target='_blank'}

---

## Referências

- [FastAPI](https://fastapi.tiangolo.com/){:target='_blank'}
- [AwesomeAPI — Documentação](https://docs.awesomeapi.com.br/){:target='_blank'}
- [Redis — Documentação](https://redis.io/docs/){:target='_blank'}
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/reference/){:target='_blank'}
- [python-jose](https://python-jose.readthedocs.io/){:target='_blank'}
