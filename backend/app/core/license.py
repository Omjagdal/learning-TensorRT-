"""
core/license.py — Offline RSA-signed license validation.

License files (.lic) contain a JSON payload + RSA signature.
The app ships with the public key to VERIFY signatures.
The admin keeps the private key to SIGN/generate licenses.

License file format:
    {JSON payload}
    ---SIGNATURE---
    {base64-encoded RSA signature}
"""

import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

# ── Embedded Public Key ──────────────────────────────────────────────────────
# This public key is used to VERIFY license signatures.
# The matching private key is kept by the admin in tools/keys/private_key.pem
# Replace this after running: python tools/generate_license.py --setup
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0placeholder0placeholder
0placeholder0placeholder0placeholder0placeholder0placeholder0placeholder
0placeholder0placeholder0placeholder0placeholder0placeholder0placeholder
0placeholder0placeholder0placeholder0placeholder0placeholder0placeholder
0placeholder0placeholder0placeholder0placeholder0placeholder0placeholder
AQAB
-----END PUBLIC KEY-----"""

LICENSE_SEPARATOR = "\n---SIGNATURE---\n"


class LicenseError(Exception):
    """Raised when license validation fails."""
    pass


class LicenseInfo:
    """Parsed and validated license data."""

    def __init__(self, data: dict):
        self.customer: str = data.get("customer", "Unknown")
        self.email: str = data.get("email", "")
        self.license_type: str = data.get("license_type", "standard")
        self.machine_id: str = data.get("machine_id", "ANY")
        self.expiry_date: str = data.get("expiry_date", "")
        self.features: list[str] = data.get("features", [])
        self.issued_date: str = data.get("issued_date", "")
        self.issued_by: str = data.get("issued_by", "")
        self._raw = data

    @property
    def is_expired(self) -> bool:
        if not self.expiry_date:
            return False
        try:
            expiry = datetime.fromisoformat(self.expiry_date)
            return datetime.now() > expiry
        except ValueError:
            return True

    @property
    def days_remaining(self) -> int:
        if not self.expiry_date:
            return 9999
        try:
            expiry = datetime.fromisoformat(self.expiry_date)
            delta = expiry - datetime.now()
            return max(0, delta.days)
        except ValueError:
            return 0

    def to_dict(self) -> dict:
        return {
            "customer": self.customer,
            "email": self.email,
            "license_type": self.license_type,
            "expiry_date": self.expiry_date,
            "days_remaining": self.days_remaining,
            "features": self.features,
            "issued_date": self.issued_date,
            "issued_by": self.issued_by,
            "is_expired": self.is_expired,
        }


def get_machine_id() -> str:
    """
    Generate a unique machine ID from hardware identifiers.
    Uses motherboard/system UUID for a stable fingerprint.
    """
    raw = ""
    try:
        if platform.system() == "Windows":
            # Windows: get system UUID via WMIC
            raw = subprocess.check_output(
                "wmic csproduct get uuid",
                shell=True,
                stderr=subprocess.DEVNULL,
            ).decode().strip().split("\n")[-1].strip()
        elif platform.system() == "Darwin":
            # macOS: get hardware UUID
            output = subprocess.check_output(
                "ioreg -rd1 -c IOPlatformExpertDevice",
                shell=True,
                stderr=subprocess.DEVNULL,
            ).decode()
            for line in output.split("\n"):
                if "IOPlatformUUID" in line:
                    raw = line.split("=")[-1].strip().strip('"')
                    break
        else:
            # Linux: read machine-id
            machine_id_path = Path("/etc/machine-id")
            if machine_id_path.exists():
                raw = machine_id_path.read_text().strip()
    except Exception as e:
        logger.warning(f"Could not read hardware UUID: {e}")

    if not raw:
        raw = platform.node()  # fallback to hostname

    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get_license_path() -> Path:
    """
    License file location:
    - Frozen (.exe): %LOCALAPPDATA%/IsraChatbot/license.lic
    - Dev mode: backend/license.lic
    """
    if getattr(sys, 'frozen', False):
        base = Path(os.environ.get('LOCALAPPDATA', '.')) / 'IsraChatbot'
        base.mkdir(parents=True, exist_ok=True)
        return base / "license.lic"
    return Path(__file__).parent.parent.parent / "license.lic"


def validate_license(license_path: Optional[Path] = None) -> LicenseInfo:
    """
    Validate a license file and return LicenseInfo if valid.
    Raises LicenseError if invalid, expired, or missing.
    """
    if license_path is None:
        license_path = get_license_path()

    if not license_path.exists():
        raise LicenseError(
            "No license file found. Please activate your license."
        )

    content = license_path.read_text(encoding="utf-8")

    # Split payload and signature
    if LICENSE_SEPARATOR not in content:
        raise LicenseError("Invalid license file format.")

    parts = content.split(LICENSE_SEPARATOR, 1)
    if len(parts) != 2:
        raise LicenseError("Invalid license file format.")

    payload_str = parts[0].strip()
    signature_b64 = parts[1].strip()

    # Parse JSON payload
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise LicenseError("License file contains invalid data.")

    # Verify RSA signature
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.exceptions import InvalidSignature

        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode())
        signature = base64.b64decode(signature_b64)

        public_key.verify(
            signature,
            payload_str.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature:
        raise LicenseError(
            "License signature verification failed. This license file is invalid."
        )
    except Exception as e:
        raise LicenseError(f"License verification error: {e}")

    # Build LicenseInfo
    info = LicenseInfo(payload)

    # Check expiry
    if info.is_expired:
        raise LicenseError(
            f"License expired on {info.expiry_date}. Please contact your administrator to renew."
        )

    # Check machine lock
    if info.machine_id and info.machine_id != "ANY":
        current_machine = get_machine_id()
        if info.machine_id != current_machine:
            raise LicenseError(
                f"This license is not valid for this machine.\n"
                f"License machine: {info.machine_id}\n"
                f"This machine:    {current_machine}"
            )

    logger.info(
        f"License valid — Customer: {info.customer}, "
        f"Expires: {info.expiry_date}, "
        f"Days remaining: {info.days_remaining}"
    )
    return info


def save_license_file(license_content: str, license_path: Optional[Path] = None) -> Path:
    """Save a license file to the standard location."""
    if license_path is None:
        license_path = get_license_path()
    license_path.parent.mkdir(parents=True, exist_ok=True)
    license_path.write_text(license_content, encoding="utf-8")
    logger.info(f"License file saved to: {license_path}")
    return license_path


# ── Global license state ─────────────────────────────────────────────────────
_current_license: Optional[LicenseInfo] = None


def get_current_license() -> Optional[LicenseInfo]:
    """Get the currently validated license (if any)."""
    return _current_license


def set_current_license(info: LicenseInfo):
    """Set the current license after validation."""
    global _current_license
    _current_license = info
