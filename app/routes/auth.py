import os
import hashlib
import secrets
import string
import jwt
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import User, Admin
from app.schemas.message import (
    UserRegister, UserLogin, UserResponse,
    UserUpdate, UserPasswordChange,
    AdminRegister, AdminLogin, AdminResponse, AgentAvailabilityUpdate
)
from app.security import get_current_user, require_roles
from app.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Refusing to start with a hardcoded fallback secret."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours so sessions last longer

LEGACY_SHA256_LENGTH = 64
# bcrypt silently ignores bytes beyond 72, so cap the input ourselves.
BCRYPT_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:BCRYPT_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def _is_legacy_sha256_hash(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == LEGACY_SHA256_LENGTH
        and all(c in "0123456789abcdef" for c in value.lower())
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Old accounts were created with unsalted sha256. Verify against that
    format too, so existing users are not locked out, and migrate them
    to bcrypt transparently on next successful login.
    """
    if _is_legacy_sha256_hash(stored_hash):
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash

    try:
        truncated = password.encode("utf-8")[:BCRYPT_MAX_PASSWORD_BYTES]
        return bcrypt.checkpw(truncated, stored_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def generate_random_password(length: int = 12) -> str:
    """Generate a secure random password suggestion."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "is_available": bool(getattr(user, "is_available", True)),
        "max_active_conversations": getattr(user, "max_active_conversations", 5),
        "last_seen_at": user.last_seen_at.isoformat() if getattr(user, "last_seen_at", None) else None,
        "last_assigned_at": user.last_assigned_at.isoformat() if getattr(user, "last_assigned_at", None) else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def admin_to_dict(admin: Admin) -> dict:
    user = admin.user
    return {
        "id": admin.id,
        "user_id": admin.user_id,
        "name": user.name if user else None,
        "email": user.email if user else None,
        "phone": admin.phone,
        "role": user.role if user else None,
        "is_active": bool(admin.is_active and (user.is_active if user else False)),
        "created_at": admin.created_at.isoformat() if admin.created_at else None,
    }


# ─────────────────────────────────────────────
# Public routes
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# Admin public setup/login routes
# ─────────────────────────────────────────────

@router.post("/admin/register", response_model=AdminResponse)
@limiter.limit("5/minute")
def register_admin(request: Request, payload: AdminRegister, db: Session = Depends(get_db)):
    """
    Create an admin account with a short request body:
    name, email, password, phone, role.
    """
    allowed_admin_roles = ["super_admin", "manager"]
    if payload.role not in allowed_admin_roles:
        raise HTTPException(status_code=400, detail="Admin role must be super_admin or manager")

    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )

    db.add(user)
    db.flush()

    admin = Admin(
        user_id=user.id,
        phone=payload.phone,
        department=None,
        permissions=[],
        is_active=True,
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)

    return admin_to_dict(admin)


@router.post("/admin/login")
@limiter.limit("10/minute")
def login_admin(request: Request, payload: AdminLogin, db: Session = Depends(get_db)):
    """Login for admin/manager accounts only."""
    user = db.query(User).filter(User.email == payload.email).first()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.role not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="This account is not an admin account")

    admin = db.query(Admin).filter(Admin.user_id == user.id).first()
    if admin is None:
        raise HTTPException(status_code=403, detail="Admin profile not found")

    if not user.is_active or not admin.is_active:
        raise HTTPException(status_code=403, detail="Admin account is inactive")

    user.last_seen_at = datetime.utcnow()

    # Transparently upgrade legacy sha256 hashes to bcrypt on successful login.
    if _is_legacy_sha256_hash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        db.commit()

    access_token = create_access_token({
        "user_id": user.id,
        "admin_id": admin.id,
        "email": user.email,
        "role": user.role,
        "is_admin": True,
    })

    return {
        "message": "Admin login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "admin": admin_to_dict(admin),
    }


@router.get("/admins")
def list_admins(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin"]))
):
    """List admin profiles. Super admin only."""
    admins = db.query(Admin).join(User).order_by(Admin.created_at.desc()).all()
    return {
        "count": len(admins),
        "admins": [admin_to_dict(a) for a in admins],
    }

@router.post("/register", response_model=UserResponse)
@limiter.limit("5/minute")
def register_user(request: Request, payload: UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == payload.email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Public self-registration can NEVER grant elevated roles.
    # Elevated roles (manager/super_admin) are only created through the
    # authenticated POST /auth/users endpoint below.
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="agent"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login")
@limiter.limit("10/minute")
def login_user(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Transparently upgrade legacy sha256 hashes to bcrypt on successful login.
    if _is_legacy_sha256_hash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        db.commit()

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    user.last_seen_at = datetime.utcnow()
    db.commit()

    access_token = create_access_token({
        "user_id": user.id,
        "email": user.email,
        "role": user.role
    })

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_to_dict(user)
    }


# ─────────────────────────────────────────────
# Token verification — used by frontend on refresh
# ─────────────────────────────────────────────

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Validate the current token and return user info. Frontend calls this on page load."""
    return user_to_dict(current_user)


@router.patch("/me/availability")
def update_my_availability(
    payload: AgentAvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Agent toggles whether they can receive automatic assignments."""
    if current_user.role != "agent":
        raise HTTPException(status_code=403, detail="Only agents can change availability")

    current_user.is_available = payload.is_available
    current_user.last_seen_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)

    return {
        "message": "Availability updated successfully",
        "user": user_to_dict(current_user),
    }


@router.get("/agents/available")
def list_available_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "manager"])),
):
    """Admins/managers can see which agents can receive auto-assigned chats."""
    agents = (
        db.query(User)
        .filter(User.role == "agent", User.is_active == True, User.is_available == True)
        .order_by(User.last_assigned_at.asc().nullsfirst(), User.id.asc())
        .all()
    )
    return {
        "count": len(agents),
        "agents": [user_to_dict(agent) for agent in agents],
    }


# ─────────────────────────────────────────────
# Users management (admin/manager only)
# ─────────────────────────────────────────────

@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "manager"]))
):
    """List all users. Admins and managers only."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {
        "count": len(users),
        "users": [user_to_dict(u) for u in users]
    }


@router.post("/users", response_model=UserResponse)
def create_user(
    request: UserRegister,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "manager"]))
):
    """Create a new user. Admins and managers only."""
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    allowed_roles = ["super_admin", "manager", "agent"]
    if request.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Invalid role")

    # Managers can only create agents, not other admins
    if current_user.role == "manager" and request.role in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Managers can only create agent accounts")

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


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    request: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "manager"]))
):
    """Update user name, role, or active status."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent managers from editing admins
    if current_user.role == "manager" and user.role in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Managers cannot edit admin accounts")

    if request.name is not None:
        user.name = request.name

    if request.role is not None:
        if current_user.role == "manager" and request.role in ["super_admin", "manager"]:
            raise HTTPException(status_code=403, detail="Managers cannot assign admin roles")
        user.role = request.role

    if request.is_active is not None:
        # Prevent deactivating yourself
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot change your own active status")
        user.is_active = request.is_active

    if request.is_available is not None:
        user.is_available = request.is_available

    if request.max_active_conversations is not None:
        if request.max_active_conversations < 1:
            raise HTTPException(status_code=400, detail="max_active_conversations must be at least 1")
        user.max_active_conversations = request.max_active_conversations

    db.commit()
    db.refresh(user)
    return user_to_dict(user)


@router.patch("/users/{user_id}/password")
def change_user_password(
    user_id: int,
    request: UserPasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "manager"]))
):
    """Change a user's password. Never requires the old password. Admins/managers only."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Managers cannot change admin passwords
    if current_user.role == "manager" and user.role in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Managers cannot change admin passwords")

    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user.password_hash = hash_password(request.new_password)
    db.commit()

    return {"message": "Password changed successfully", "user_id": user_id}


@router.get("/users/password-suggestion")
def get_password_suggestion(
    current_user: User = Depends(require_roles(["super_admin", "manager"]))
):
    """Returns a randomly generated secure password suggestion."""
    return {"suggested_password": generate_random_password(12)}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin"]))
):
    """Delete a user. Super admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    db.delete(user)
    db.commit()

    return {"message": "User deleted successfully", "deleted_user_id": user_id}