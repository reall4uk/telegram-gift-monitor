#!/usr/bin/env python3
"""
Licenses Router
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from auth_router import verify_token

router = APIRouter()


class LicenseRequest(BaseModel):
    license_type: str = "basic"


@router.post("/generate")
async def generate_license(request: LicenseRequest, user=Depends(verify_token)):
    """Generate new license"""
    return {
        "license_key": "TGMP-XXXX-XXXX-XXXX-XXXX",
        "type": request.license_type,
        "status": "generated"
    }


@router.get("/check/{license_key}")
async def check_license(license_key: str):
    """Check license status"""
    return {
        "license_key": license_key,
        "valid": True,
        "type": "basic"
    }