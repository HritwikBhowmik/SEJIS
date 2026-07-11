
import os
import bcrypt
from datetime import datetime, timedelta, timezone
from jose import jwt
from dotenv import load_dotenv

load_dotenv()

# Configuration constants
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24*60  # hour * minute


def hash_password(password: str) -> str:
    """
    Hashes a plain text password natively using the modern bcrypt package.
    """
    # Convert the plain text string into binary bytes
    password_bytes = password.encode('utf-8')
    
    # Generate a secure cryptographic salt
    salt = bcrypt.gensalt()
    
    # Hash the password and decode the binary hash string back to a UTF-8 string for DB storage
    hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_password_bytes.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain text password against a stored bcrypt hash string.
    """
    # Convert both fields into binary byte format for cryptographic comparison
    plain_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    
    # Securely check if they match (safely prevents timing attacks)
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": str(user_id), "exp": expire}
    return jwt.encode(to_encode, str(SECRET_KEY), algorithm=ALGORITHM)