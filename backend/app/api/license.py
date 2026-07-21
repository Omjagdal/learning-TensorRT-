"""
api/license.py — License management API endpoints.

Provides:
  - GET  /license/status     → current license status
  - GET  /license/machine-id → machine ID for activation
  - POST /license/activate   → upload/activate a .lic file
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.core.license import (
    get_machine_id,
    get_current_license,
    validate_license,
    save_license_file,
    set_current_license,
    get_license_path,
    LicenseError,
)

router = APIRouter(prefix="/license", tags=["License"])


class LicenseStatusResponse(BaseModel):
    status: str  # "valid", "expired", "invalid", "not_activated"
    message: str
    customer: str | None = None
    expiry_date: str | None = None
    days_remaining: int | None = None
    license_type: str | None = None
    features: list[str] | None = None
    machine_id: str | None = None


class MachineIdResponse(BaseModel):
    machine_id: str
    platform: str


class ActivateResponse(BaseModel):
    status: str
    message: str
    customer: str | None = None
    expiry_date: str | None = None


@router.get("/status", response_model=LicenseStatusResponse)
async def license_status():
    """Check current license status."""
    import platform as plat

    current = get_current_license()
    machine_id = get_machine_id()

    if current is None:
        # Try to validate from file
        try:
            info = validate_license()
            set_current_license(info)
            return LicenseStatusResponse(
                status="valid",
                message=f"License valid. {info.days_remaining} days remaining.",
                customer=info.customer,
                expiry_date=info.expiry_date,
                days_remaining=info.days_remaining,
                license_type=info.license_type,
                features=info.features,
                machine_id=machine_id,
            )
        except LicenseError as e:
            # Determine if it's expired vs not found
            msg = str(e)
            if "expired" in msg.lower():
                return LicenseStatusResponse(
                    status="expired",
                    message=msg,
                    machine_id=machine_id,
                )
            elif "not valid for this machine" in msg.lower():
                return LicenseStatusResponse(
                    status="invalid",
                    message=msg,
                    machine_id=machine_id,
                )
            else:
                return LicenseStatusResponse(
                    status="not_activated",
                    message=msg,
                    machine_id=machine_id,
                )

    return LicenseStatusResponse(
        status="valid",
        message=f"License valid. {current.days_remaining} days remaining.",
        customer=current.customer,
        expiry_date=current.expiry_date,
        days_remaining=current.days_remaining,
        license_type=current.license_type,
        features=current.features,
        machine_id=machine_id,
    )


@router.get("/machine-id", response_model=MachineIdResponse)
async def machine_id():
    """Get the machine ID for license activation."""
    import platform as plat

    return MachineIdResponse(
        machine_id=get_machine_id(),
        platform=plat.system(),
    )


@router.post("/activate", response_model=ActivateResponse)
async def activate_license(file: UploadFile = File(...)):
    """
    Activate a license by uploading a .lic file.
    The file is validated and saved to the standard location.
    """
    if not file.filename or not file.filename.endswith(".lic"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a valid .lic license file.",
        )

    # Read the file content
    content = await file.read()
    license_text = content.decode("utf-8")

    # Save to a temp location first for validation
    license_path = get_license_path()

    try:
        # Save the file
        save_license_file(license_text, license_path)

        # Validate it
        info = validate_license(license_path)

        # Set as current license
        set_current_license(info)

        return ActivateResponse(
            status="valid",
            message=f"License activated successfully! Valid until {info.expiry_date}.",
            customer=info.customer,
            expiry_date=info.expiry_date,
        )
    except LicenseError as e:
        # Remove invalid license file
        if license_path.exists():
            license_path.unlink()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if license_path.exists():
            license_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate license: {e}",
        )
