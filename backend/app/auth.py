from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import get_session
from .models import User
from .schemas import TokenPayload

settings = get_settings()

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

MAX_PASSWORD_LENGTH = 32


def hash_password(password: str) -> str:
    if len(password) > MAX_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"密码长度需在8-{MAX_PASSWORD_LENGTH}个字符之间",
        )
    try:
        return pwd_context.hash(password)
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=400,
            detail=f"密码长度需在8-{MAX_PASSWORD_LENGTH}个字符之间",
        ) from exc


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(subject: str, expires_delta: int = None) -> str:
    expire_minutes = expires_delta or settings.access_token_expire_minutes
    expire = datetime.utcnow() + timedelta(minutes=expire_minutes)
    to_encode = {"sub": subject, "exp": expire}
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValueError) as exc:  # pragma: no cover - security
        raise credentials_exception from exc

    statement = select(User).where(User.email == token_data.sub)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception
    return user
