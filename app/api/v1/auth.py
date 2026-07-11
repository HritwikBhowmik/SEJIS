

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_async_db
from app.models.model import User
from app.schemas.user import UserRegister, UserLogin, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token

router = APIRouter()

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_candidate(
    payload: UserRegister, 
    db: AsyncSession = Depends(get_async_db)):
    """
    Asynchronously checks for existing credentials, hashes the password, 
    and saves the new candidate to the PostgreSQL database.
    """
    # Query the DB asynchronously to verify if email already exists
    result = await db.execute(select(User).where(User.email == payload.email))
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.")
        
    # Hash the raw user input password securely using bcrypt
    secure_password = hash_password(payload.password)
    
    # Instantiate the new user entry matching your SQLAlchemy model layout
    new_user = User(
        email=payload.email,
        hashed_password=secure_password,
        full_name=payload.full_name
    )
    
    # Add to transaction batch and commit asynchronously
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)  # Refreshes the instance to attach the generated UUID
    
    return {"message": "Registration successful.", "user_id": str(new_user.id)}


@router.post("/login", response_model=TokenResponse)
async def login_candidate(
    payload: UserLogin, 
    db: AsyncSession = Depends(get_async_db)):
    """
    Validates candidate credentials and generates an access token 
    to handle state authorization on subsequent secure endpoint calls.
    """
    # Fetch user instance matching the provided input email
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalars().first()
    
    # Guard Clause: Enforce a uniform exception if user isn't found
    invalid_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not user:
        raise invalid_credentials_exception
        
    # Check if the input password matches the stored bcrypt signature
    if not verify_password(payload.password, user.hashed_password):
        raise invalid_credentials_exception
        
    # Generate the cryptographically signed JWT token containing the user's UUID
    token = create_access_token(user_id=str(user.id))
    
    return {"access_token": token, "token_type": "bearer"}


