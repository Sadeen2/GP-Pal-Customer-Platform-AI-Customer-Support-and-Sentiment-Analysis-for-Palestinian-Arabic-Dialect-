import hashlib
import jwt
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import User
from app.schemas.message import UserRegister, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = "change-this-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/register", response_model=UserResponse)
def register_user(request: UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == request.email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    allowed_roles = ["super_admin", "manager", "agent"]

    if request.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = User(
        name=request.name,
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login")
def login_user(request: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.password_hash != hash_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    access_token = create_access_token({
        "user_id": user.id,
        "email": user.email,
        "role": user.role
    })

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active
        }
    }