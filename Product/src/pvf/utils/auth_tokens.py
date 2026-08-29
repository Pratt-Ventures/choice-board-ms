from datetime import datetime, timedelta, timezone
from ..config.pvf_config_settings import pvf_settings as settings
from jose import jwt

# adapting jwt process from: https://www.freecodecamp.org/news/how-to-add-jwt-authentication-in-fastapi/
#    and sample full code at: https://replit.com/@abdadeel/FastAPIwithJWTauth


def _create_access_token(id_value: any, *, expires_delta_secs: int = None) -> str:
    expires_delta = datetime.now(timezone.utc) + timedelta(seconds=expires_delta_secs)
    to_encode = {"exp": expires_delta, "sub": str(id_value)}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)
    return encoded_jwt

def create_access_token(user_id: int, *, expires_delta_secs: int = None) -> str:
    return _create_access_token(user_id, expires_delta_secs=expires_delta_secs) if expires_delta_secs is not None else _create_access_token(user_id, expires_delta_secs=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)