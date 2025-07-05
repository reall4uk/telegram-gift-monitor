#!/usr/bin/env python3
"""
Authentication Router
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import jwt
import os
from datetime import datetime, timedelta

from auth import AuthService

router = APIRouter()
security = HTTPBearer()
auth_service = AuthService()

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this")
JWT_ALGORITHM = "HS256"


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    telegram_id: Optional[int] = None


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def create_access_token(data: dict):
    """Create access token"""
    expire = datetime.utcnow() + timedelta(days=30)
    data.update({"exp": expire})
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/register")
async def register(request: RegisterRequest):
    """Register new user"""
    # Simple registration logic
    hashed_password = auth_service.hash_password(request.password)
    
    # In production, save to database
    access_token = create_access_token({"sub": request.username})
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.post("/login")
async def login(request: LoginRequest):
    """Login user"""
    # In production, verify against database
    access_token = create_access_token({"sub": request.username})
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }