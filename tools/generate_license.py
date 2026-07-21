#!/usr/bin/env python3
"""
generate_license.py — Admin tool for generating RSA-signed license files.

Usage:
  First-time setup (generate RSA key pair):
    python generate_license.py --setup

  Generate a license:
    python generate_license.py \\
        --customer "ISRA VISION GmbH" \\
        --expiry "2027-12-31" \\
        --machine-id "a1b2c3d4..." \\
        --output license.lic

  Generate an unlocked license (any machine):
    python generate_license.py \\
        --customer "Demo User" \\
        --expiry "2026-12-31" \\
        --output demo.lic

  Show machine ID of this computer:
    python generate_license.py --show-machine-id
"""

import argparse
import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
except ImportError:
    print("ERROR: 'cryptography' package is required.")
    print("Install it with: pip install cryptography")
    sys.exit(1)

KEYS_DIR = Path(__file__).parent / "keys"
PRIVATE_KEY_PATH = KEYS_DIR / "private_key.pem"
PUBLIC_KEY_PATH = KEYS_DIR / "public_key.pem"
LICENSE_SEPARATOR = "\n---SIGNATURE---\n"


def setup_keys():
    """Generate a new RSA key pair."""
    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    if PRIVATE_KEY_PATH.exists():
        answer = input(
            f"Keys already exist at {KEYS_DIR}/. Overwrite? (y/N): "
        ).strip().lower()
        if answer != "y":
            print("Aborted.")
            return

    print("Generating 2048-bit RSA key pair...")

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Save private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    PRIVATE_KEY_PATH.write_bytes(private_pem)
    print(f"Private key saved: {PRIVATE_KEY_PATH}")

    # Save public key
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    PUBLIC_KEY_PATH.write_bytes(public_pem)
    print(f"Public key saved:  {PUBLIC_KEY_PATH}")

    print()
    print("=" * 60)
    print("IMPORTANT: Copy the public key below into")
    print("backend/app/core/license.py → PUBLIC_KEY_PEM")
    print("=" * 60)
    print()
    print(public_pem.decode())
    print("=" * 60)
    print()
    print("NEVER share the private key! Keep it safe.")


def get_machine_id():
    """Get machine ID of this computer."""
    raw = ""
    try:
        if platform.system() == "Windows":
            raw = subprocess.check_output(
                "wmic csproduct get uuid", shell=True,
                stderr=subprocess.DEVNULL,
            ).decode().strip().split("\n")[-1].strip()
        elif platform.system() == "Darwin":
            output = subprocess.check_output(
                "ioreg -rd1 -c IOPlatformExpertDevice",
                shell=True, stderr=subprocess.DEVNULL,
            ).decode()
            for line in output.split("\n"):
                if "IOPlatformUUID" in line:
                    raw = line.split("=")[-1].strip().strip('"')
                    break
        else:
            machine_id_path = Path("/etc/machine-id")
            if machine_id_path.exists():
                raw = machine_id_path.read_text().strip()
    except Exception:
        raw = platform.node()

    if not raw:
        raw = platform.node()
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def generate_license(
    customer: str,
    expiry: str,
    machine_id: str = "ANY",
    email: str = "",
    license_type: str = "enterprise",
    features: list = None,
    output_path: str = "license.lic",
):
    """Generate a signed license file."""
    if not PRIVATE_KEY_PATH.exists():
        print("ERROR: No private key found. Run --setup first.")
        sys.exit(1)

    # Validate expiry date
    try:
        datetime.fromisoformat(expiry)
    except ValueError:
        print(f"ERROR: Invalid expiry date format: {expiry}")
        print("Use ISO format: YYYY-MM-DD")
        sys.exit(1)

    if features is None:
        features = ["chat", "vision", "ocr"]

    # Build payload
    payload = {
        "customer": customer,
        "email": email,
        "license_type": license_type,
        "machine_id": machine_id,
        "expiry_date": expiry,
        "features": features,
        "issued_date": datetime.now().strftime("%Y-%m-%d"),
        "issued_by": "ISRA License Server",
    }

    payload_str = json.dumps(payload, indent=2)

    # Load private key and sign
    private_key = serialization.load_pem_private_key(
        PRIVATE_KEY_PATH.read_bytes(),
        password=None,
    )

    signature = private_key.sign(
        payload_str.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    signature_b64 = base64.b64encode(signature).decode()

    # Write license file
    license_content = payload_str + LICENSE_SEPARATOR + signature_b64

    output = Path(output_path)
    output.write_text(license_content, encoding="utf-8")

    print(f"License generated: {output.resolve()}")
    print(f"  Customer:   {customer}")
    print(f"  Expiry:     {expiry}")
    print(f"  Machine:    {machine_id}")
    print(f"  Type:       {license_type}")
    print(f"  Features:   {', '.join(features)}")


def main():
    parser = argparse.ArgumentParser(
        description="ISRA Chatbot License Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--setup", action="store_true",
        help="Generate RSA key pair (first-time setup)",
    )
    parser.add_argument(
        "--show-machine-id", action="store_true",
        help="Show this computer's machine ID",
    )
    parser.add_argument("--customer", help="Customer name")
    parser.add_argument("--expiry", help="Expiry date (YYYY-MM-DD)")
    parser.add_argument(
        "--machine-id", default="ANY",
        help="Machine ID to lock to (default: ANY = works on all machines)",
    )
    parser.add_argument("--email", default="", help="Customer email")
    parser.add_argument(
        "--license-type", default="enterprise",
        choices=["standard", "enterprise", "trial"],
        help="License type (default: enterprise)",
    )
    parser.add_argument(
        "--features", default="chat,vision,ocr",
        help="Comma-separated feature list (default: chat,vision,ocr)",
    )
    parser.add_argument(
        "--output", "-o", default="license.lic",
        help="Output file path (default: license.lic)",
    )

    args = parser.parse_args()

    if args.setup:
        setup_keys()
        return

    if args.show_machine_id:
        print(f"Machine ID: {get_machine_id()}")
        return

    if not args.customer or not args.expiry:
        print("ERROR: --customer and --expiry are required.")
        print("Run with --help for usage information.")
        sys.exit(1)

    features = [f.strip() for f in args.features.split(",")]

    generate_license(
        customer=args.customer,
        expiry=args.expiry,
        machine_id=args.machine_id,
        email=args.email,
        license_type=args.license_type,
        features=features,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
