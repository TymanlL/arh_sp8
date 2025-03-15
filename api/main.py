from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import jwt
import requests
import json
import os
import time
import logging
from datetime import datetime, timedelta
import random
from typing import Dict, List, Any, Optional

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reports_api")

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

# Получаем URL Keycloak из переменных окружения или используем значение по умолчанию
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")

# Список возможных URL для Keycloak для отказоустойчивости
KEYCLOAK_URL_ALTERNATIVES = [
    KEYCLOAK_URL,
    "http://localhost:8080",
    "http://host.docker.internal:8080"
]

# Кеш для публичных ключей
jwks_cache = None
jwks_cache_time = None

# Простое декодирование JWT без проверки
def decode_token_without_verification(token):
    """Декодируем JWT без проверки подписи просто для получения информации из полезной нагрузки"""
    # Разделяем JWT на части
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    
    # Декодируем полезную нагрузку (часть 2)
    padding = '=' * (4 - len(parts[1]) % 4)
    payload_json = parts[1] + padding
    
    try:
        import base64
        decoded = base64.b64decode(payload_json.replace('-', '+').replace('_', '/'))
        payload = json.loads(decoded)
        return payload
    except Exception as e:
        raise ValueError(f"Error decoding JWT payload: {str(e)}")

async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Валидация JWT токена"""
    token = credentials.credentials
    
    try:
        # В упрощенной версии просто декодируем токен без проверки подписи
        # В реальном приложении нужно обязательно проверять подпись!
        payload = decode_token_without_verification(token)
        
        # Проверяем срок действия токена
        exp = payload.get('exp')
        if exp is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing expiration claim"
            )
        
        if exp < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
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
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error validating token: {str(e)}"
        )

def check_prothetic_user_role(payload: Dict[str, Any] = Depends(validate_token)):
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
    return {"message": "BionicPRO Reports API", "status": "healthy"}

@app.get("/health")
def health_check():
    """Эндпоинт для проверки здоровья сервиса"""
    return {"status": "healthy"}

@app.get("/reports")
async def get_report(payload: Dict[str, Any] = Depends(check_prothetic_user_role)):
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