from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.middleware.cors import CORSMiddleware
import jwt
from jwt import PyJWKClient
import os
from datetime import datetime, timedelta
import random
import json
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

# Настройка OAuth2
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"http://localhost:8080/realms/reports-realm/protocol/openid-connect/auth",
    tokenUrl=f"http://localhost:8080/realms/reports-realm/protocol/openid-connect/token"
)

# URL для получения публичных ключей для проверки JWT
JWKS_URL = "http://localhost:8080/realms/reports-realm/protocol/openid-connect/certs"
jwks_client = PyJWKClient(JWKS_URL)

# Функция для проверки JWT токена и извлечения информации о пользователе
async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    try:
        # Получаем ключ для проверки подписи
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Проверяем токен
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience="reports-frontend",  # Должен соответствовать clientId
            options={"verify_signature": True, "verify_aud": False, "verify_exp": True}
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
    except jwt.JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error validating token: {str(e)}"
        )

# Проверка наличия роли prothetic_user
def check_prothetic_user_role(user: Dict[str, Any]) -> Dict[str, Any]:
    realm_access = user.get("realm_access", {})
    roles = realm_access.get("roles", [])
    
    if "prothetic_user" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You need the 'prothetic_user' role to access this resource"
        )
    
    return user

# Генерация данных для отчета
def generate_report_data(user_id: str) -> Dict[str, Any]:
    # Получаем текущую дату
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
async def get_report(current_user: Dict[str, Any] = Depends(check_prothetic_user_role)):
    # Получаем ID пользователя из JWT токена
    user_id = current_user.get("sub")
    username = current_user.get("preferred_username", "unknown")
    
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