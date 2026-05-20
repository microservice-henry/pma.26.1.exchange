# Documentação do Projeto

## Descrição

A Exchange API é um microsserviço REST implementado em **Python** com **FastAPI** que expõe um endpoint para consulta de taxas de câmbio em tempo real entre duas moedas. O serviço busca as cotações na [AwesomeAPI](https://docs.awesomeapi.com.br/) e exige que o usuário esteja autenticado via token JWT para consumir o endpoint.

---

## Tecnologias Utilizadas

| Tecnologia | Versão | Finalidade |
|---|---|---|
| Python | 3.12 | Linguagem principal |
| FastAPI | 0.115.0 | Framework web |
| Uvicorn | 0.32.0 | Servidor ASGI |
| httpx | ≥0.28.1 | Requisições HTTP assíncronas |
| python-jose | 3.3.0 | Validação de JWT |
| Docker | — | Containerização |
| AwesomeAPI | — | Provedor de cotações |

---

## Endpoint

### `GET /exchanges/{from}/{to}`

Retorna a taxa de câmbio atual entre duas moedas.

**Autenticação:** Bearer Token (JWT)

**Parâmetros de rota:**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `from` | string | Moeda de origem (ex: `USD`) |
| `to` | string | Moeda de destino (ex: `BRL`) |

**Exemplo de requisição:**
```
GET /exchanges/USD/BRL
Authorization: Bearer <token>
```

**Exemplo de resposta (200 OK):**
```json
{
    "sell": 5.72,
    "buy": 5.70,
    "date": "2021-09-01 14:23:42",
    "id-account": "0195ae95-5be7-7dd3-b35d-7a7d87c404fb"
}
```

**Erros possíveis:**

| Código | Descrição |
|---|---|
| 401 | Token inválido ou ausente |
| 404 | Par de moedas não encontrado |

---

## Código Fonte

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import httpx
import os

app = FastAPI(title="Exchange API")
security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def get_current_account_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        account_id: str = payload.get("sub")
        if account_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return account_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@app.get("/exchanges/{from_currency}/{to_currency}")
async def get_exchange(
    from_currency: str,
    to_currency: str,
    account_id: str = Depends(get_current_account_id),
):
    pair = f"{from_currency.upper()}-{to_currency.upper()}"
    url = f"https://economia.awesomeapi.com.br/json/last/{pair}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10.0)

    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency pair not found")

    data = response.json()
    key = pair.replace("-", "")

    if key not in data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency pair not found")

    rate = data[key]

    return {
        "sell": float(rate["ask"]),
        "buy": float(rate["bid"]),
        "date": rate["create_date"],
        "id-account": account_id,
    }
```

---

## Como Executar

### Com Docker

```bash
docker compose up --build
```

O serviço estará disponível em `http://localhost:8000`.

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `JWT_SECRET` | `secret` | Chave secreta para validação do JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo do JWT |

### Documentação interativa

Após subir o serviço, acesse `http://localhost:8000/docs` para a interface Swagger automática do FastAPI.
