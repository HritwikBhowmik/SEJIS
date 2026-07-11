
import os
import sys
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from dotenv import load_dotenv
from redis.asyncio import Redis, ConnectionPool
from typing import AsyncGenerator

from app.core.db import AsyncSessionFactory
from app.models.model import User

load_dotenv()


# This tells FastAPI to look for a token in the "Authorization" header
# tokenUrl points to your v1 login endpoint for Swagger UI documentation compatibility
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

# ---  REDIS CONFIGURATION ---
REDIS_URL = os.getenv("REDIS_URL")



class TokenData(BaseModel):
    """Pydantic model to validate the data inside the decoded payload"""
    user_id: Optional[str] | None = None


if not REDIS_URL:
    print('[!] REDIS_URL not found in .env!')
    sys.exit()

redis_pool = ConnectionPool.from_url(
    REDIS_URL, decode_responses=True, max_connections=20
)
print("Redis connection pool initialized.")


async def get_redis():
    """Dependency injection for REDIS"""
    if redis_pool is None:
        raise RuntimeError("Redis connection pool is unavailable.")
    
    async with Redis(connection_pool=redis_pool) as client:
        yield client

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator that yields an active, isolated async database session 
    for each request, ensuring clean context management and automatic rollback/closure.
    """
    
    async_session = AsyncSessionFactory()
    
    try:
        yield async_session
    except Exception:
        # If any database error occurs during execution, roll back the transaction
        await async_session.rollback()
        raise
    finally:
        await async_session.close()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_db)) -> User:
    """
    Dependency Injection function that intercepts requests, decodes the JWT token,
    verifies if the user exists in PostgreSQL, and injects the live User object.
    """
    # Define a generic 401 response for credential failure
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the token using your backend secret signature
        payload = jwt.decode(token, str(SECRET_KEY), algorithms=[ALGORITHM])
        
        # Extract the raw claim value first (it will be a string or None)
        user_id_str = payload.get("sub")
        
        # Correctly catch missing subjects before converting types
        if user_id_str is None:
            raise credentials_exception
            
        # Parse safely into your Pydantic data model
        token_data = TokenData(user_id=str(user_id_str))
        
    except (JWTError, ValueError) as e:
        # Debug tip: Printing the actual error string helps spot parsing vs cryptographic issues instantly!
        print(f"Token validation failed due to: {e}")
        raise credentials_exception
        
    # Query PostgreSQL using AsyncSession to verify the user exists
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalars().first()
    
    if user is None:
        print('user failed here')
        raise credentials_exception
        
    # Success! Inject the authenticated user object into the endpoint route
    return user




