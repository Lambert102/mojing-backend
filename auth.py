"""认证与安全模块 —— JWT 创建/验证 + bcrypt 密码哈希 + get_current_user 依赖。"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models import User

# ─── 密码上下文 ─────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─── HTTP Bearer ───────────────────────────────────────

security_scheme = HTTPBearer(auto_error=False)


# ─── 密码工具 ───────────────────────────────────────────

def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希。"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希值是否匹配。"""
    return pwd_context.verify(plain_password, hashed_password)


# ─── JWT 工具 ──────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """生成 JWT access token。

    Args:
        data: 要编码到 token 中的数据（通常包含 user_id）。
        expires_delta: 过期时间增量，默认使用配置中的 7 天。

    Returns:
        编码后的 JWT 字符串。
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """解码并验证 JWT token。

    Args:
        token: JWT 字符串。

    Returns:
        解码后的 payload 字典，验证失败返回 None。
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


# ─── 依赖：当前用户 ─────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 Bearer token 中解析当前登录用户。

    Raises:
        HTTPException 401: 未提供 token 或 token 无效，或用户不存在。
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: Optional[int] = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证凭据中缺少用户标识",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user
