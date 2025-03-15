from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import jwt
from jwt.jwk import PyJWK
import requests
import json
from datetime import datetime, timedelta
import random
from typing import Dict, List, Any, Optional

app = FastAPI(title="BionicPRO Reports API")

# Настройка CORS для доступа с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Схема для получения Bearer токена
security = HTTPBearer()

# URL для получения публичных ключей Keycloak
KEYCLOAK_URL = "http://keycloak:8080"
REALM = "reports-realm"
JWKS_URL = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs"

# Кеш для публичных ключей
jwks_cache = None
jwks_cache_time = None

def get_jwks():
    """Получение и кеширование публичных ключей Keycloak"""
    global jwks_cache, jwks_cache_time
    
    # Если кеш устарел или отсутствует, обновляем его
    if jwks_cache is None or jwks_cache_time is None or (datetime.now() - jwks_cache_time).total_seconds() > 3600:
        try:
            response = requests.get(JWKS_URL)
            response.raise_for_status()
            jwks_cache = response.json()
            jwks_cache_time = datetime.now()
        except Exception as e:
            # Если не удалось получить ключи с Keycloak, пробуем публичный URL
            try:
                public_url = f"http://localhost:8080/realms/{REALM}/protocol/openid-connect/certs"
                response = requests.get(public_url)
                response.raise_for_status()
                jwks_cache = response.json()
                jwks_cache_time = datetime.now()
            except Exception as e2:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Could not fetch JWKS: {str(e2)}"
                )
    
    return jwks_cache

def get_signing_key(token):
    """Получение ключа для проверки подписи токена"""
    jwks = get_jwks()
    
    # Получаем заголовок токена без проверки подписи
    try:
        header = jwt.get_unverified_header(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token header: {str(e)}"
        )
    
    # Ищем ключ с соответствующим kid
    kid = header.get('kid')
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has no 'kid' header"
        )
    
    # Находим соответствующий ключ в JWKS
    for key in jwks.get('keys', []):
        if key.get('kid') == kid:
            return PyJWK(key)
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"No matching key found for kid: {kid}"
    )

async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Валидация JWT токена"""
    token = credentials.credentials
    
    try:
        # Получаем ключ для проверки подписи
        signing_key = get_signing_key(token)
        
        # Проверяем токен
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False}  # Отключаем проверку audience
        )
        
        # Проверяем наличие обязательных полей
        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject claim"
            )
            
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error validating token: {str(e)}"
        )

def check_prothetic_user_role(payload: Dict[str, Any]):
    """Проверка наличия роли prothetic_user"""
    realm_access = payload.get("realm_access", {})
    roles = realm_access.get("roles", [])
    
    if "prothetic_user" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You need the 'prothetic_user' role to access this resource"
        )
    
    return payload

def generate_report_data(user_id: str):
    """Генерация данных отчета"""
    now = datetime.now()
    
    # Генерируем данные за последние 30 дней
    days = []
    for i in range(30):
        date = now - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        
        # Генерируем случайные данные об использовании протеза
        data = {
            "date": date_str,
            "activeHours": round(random.uniform(1, 16), 1),
            "batteryDrain": round(random.uniform(5, 30), 1),
            "movements": {
                "grasp": random.randint(10, 200),
                "pinch": random.randint(5, 150),
                "wristRotation": random.randint(20, 300),
                "extension": random.randint(15, 180),
                "flexion": random.randint(25, 250)
            },
            "accuracyRate": round(random.uniform(70, 99), 1),
            "responseTime": round(random.uniform(50, 150), 0),
            "batteryChargeCycles": random.randint(0, 3),
            "errorCounts": random.randint(0, 10)
        }
        days.append(data)
    
    # Формируем итоговый отчет
    report = {
        "userId": user_id,
        "generatedAt": now.isoformat(),
        "reportPeriod": {
            "from": days[-1]["date"],
            "to": days[0]["date"]
        },
        "summary": {
            "totalActiveHours": round(sum(day["activeHours"] for day in days), 1),
            "avgDailyActiveHours": round(sum(day["activeHours"] for day in days) / len(days), 1),
            "totalMovements": sum(sum(movement for movement in day["movements"].values()) for day in days),
            "avgAccuracyRate": round(sum(day["accuracyRate"] for day in days) / len(days), 1),
            "avgResponseTime": round(sum(day["responseTime"] for day in days) / len(days), 0),
            "totalBatteryChargeCycles": sum(day["batteryChargeCycles"] for day in days),
            "totalErrors": sum(day["errorCounts"] for day in days),
        },
        "dailyStats": days
    }
    
    return report

@app.get("/")
def read_root():
    return {"message": "BionicPRO Reports API"}

@app.get("/reports")
async def get_report(payload: Dict[str, Any] = Depends(validate_token)):
    # Проверяем роль prothetic_user
    check_prothetic_user_role(payload)
    
    # Получаем ID пользователя из JWT токена
    user_id = payload.get("sub")
    username = payload.get("preferred_username", "unknown")
    
    # Генерируем отчет на основе ID пользователя
    report_data = generate_report_data(user_id)
    
    return {
        "username": username,
        "reportTitle": f"Отчет об использовании протеза ({username})",
        "reportData": report_data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)