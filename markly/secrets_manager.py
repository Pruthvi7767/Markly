"""Secrets manager using pyrage (age) encryption.

Secrets are stored in ~/.markly/secrets.age.
Identity (private key) is stored in ~/.markly/identity.txt.
"""
import os
import json
from pathlib import Path
from typing import Dict, Optional
import pyrage

MARKLY_DIR = Path.home() / ".markly"
IDENTITY_FILE = MARKLY_DIR / "identity.txt"
SECRETS_FILE = MARKLY_DIR / "secrets.age"

_SECRETS_CACHE: Optional[Dict[str, str]] = None

def _get_or_create_identity() -> pyrage.x25519.Identity:
    """Load the existing x25519 identity or create a new one."""
    MARKLY_DIR.mkdir(parents=True, exist_ok=True)
    if IDENTITY_FILE.exists():
        with open(IDENTITY_FILE, "r", encoding="utf-8") as f:
            identity_str = f.read().strip()
            return pyrage.x25519.Identity.from_str(identity_str)
    
    # Generate new identity
    identity = pyrage.x25519.Identity.generate()
    
    # Save identity with restricted permissions (Windows doesn't support chmod 600 natively easily in Python without win32api, 
    # but we do standard file write; in a production multi-user unix system, we'd chmod 600)
    with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
        f.write(str(identity))
        
    # Attempt to secure file on POSIX
    if os.name == "posix":
        os.chmod(IDENTITY_FILE, 0o600)
        
    return identity

def save_secrets(secrets: Dict[str, str]) -> None:
    """Encrypt and save secrets to disk."""
    identity = _get_or_create_identity()
    public_key = identity.to_public()
    
    plaintext = json.dumps(secrets).encode("utf-8")
    ciphertext = pyrage.encrypt(plaintext, [public_key])
    
    with open(SECRETS_FILE, "wb") as f:
        f.write(ciphertext)
        
    if os.name == "posix":
        os.chmod(SECRETS_FILE, 0o600)
        
    # Update cache
    global _SECRETS_CACHE
    _SECRETS_CACHE = secrets

def load_secrets() -> Dict[str, str]:
    """Load and decrypt secrets from disk. Uses in-memory cache if already loaded."""
    global _SECRETS_CACHE
    if _SECRETS_CACHE is not None:
        return _SECRETS_CACHE
        
    if not SECRETS_FILE.exists() or not IDENTITY_FILE.exists():
        _SECRETS_CACHE = {}
        return _SECRETS_CACHE
        
    identity = _get_or_create_identity()
    with open(SECRETS_FILE, "rb") as f:
        ciphertext = f.read()
        
    try:
        plaintext = pyrage.decrypt(ciphertext, [identity])
        _SECRETS_CACHE = json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        # If decryption fails (corrupted or wrong key), start fresh but don't crash loudly yet
        # Returning empty dict means user will have to setup again.
        _SECRETS_CACHE = {}
        
    return _SECRETS_CACHE

def get_secret(key: str) -> Optional[str]:
    """Retrieve a specific secret without ever logging it."""
    secrets = load_secrets()
    return secrets.get(key)

def is_setup_complete() -> bool:
    """Check if the user has completed the setup wizard."""
    return SECRETS_FILE.exists() and IDENTITY_FILE.exists()
