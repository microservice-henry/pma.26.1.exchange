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
