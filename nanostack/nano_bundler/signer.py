"""
APK Signer — generates a debug keystore if needed and signs the APK.

Uses the Java `keytool` and `apksigner` utilities.  apksigner.jar must
be present at <package_root>/bin/apksigner.jar (bundled with Nano-Stack).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


_KEYSTORE_DIR  = Path.home() / ".nanostack"
_KEYSTORE_PATH = _KEYSTORE_DIR / "debug.keystore"
_KEY_ALIAS     = "androiddebugkey"
_STORE_PASS    = "android"
_KEY_PASS      = "android"

# Path to bundled apksigner JAR (relative to this file's package root)
_BIN_DIR = Path(__file__).parent.parent / "bin"
_APKSIGNER_JAR = _BIN_DIR / "apksigner.jar"


class SignerError(Exception):
    pass


def sign(apk_path: str) -> str:
    """
    Sign apk_path with the debug keystore.
    Creates the keystore if it does not already exist.
    Returns the path to the signed APK (same as input, signed in-place).
    """
    _ensure_keystore()
    _sign_apk(Path(apk_path))
    return apk_path


def _ensure_keystore() -> None:
    """Generate the debug keystore if it does not exist."""
    if _KEYSTORE_PATH.exists():
        return

    _KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)

    if not shutil.which("keytool"):
        raise SignerError(
            "keytool not found. Please install a JDK and ensure it is in your PATH."
        )

    cmd = [
        "keytool",
        "-genkey", "-v",
        "-keystore", str(_KEYSTORE_PATH),
        "-alias", _KEY_ALIAS,
        "-keyalg", "RSA",
        "-keysize", "2048",
        "-validity", "10000",
        "-storepass", _STORE_PASS,
        "-keypass", _KEY_PASS,
        "-dname", "CN=Android Debug,O=Android,C=US",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SignerError(
            f"keytool failed:\n{result.stderr}"
        )


def _sign_apk(apk_path: Path) -> None:
    """Sign the APK using apksigner.jar."""
    if not apk_path.exists():
        raise SignerError(f"APK not found: {apk_path}")

    if not _APKSIGNER_JAR.exists():
        raise SignerError(
            f"apksigner.jar not found at {_APKSIGNER_JAR}. "
            "Please reinstall nanostack or download the bin/ directory."
        )

    if not shutil.which("java"):
        raise SignerError(
            "java not found. Please install a JRE and ensure it is in your PATH."
        )

    cmd = [
        "java", "-jar", str(_APKSIGNER_JAR),
        "sign",
        "--ks", str(_KEYSTORE_PATH),
        "--ks-key-alias", _KEY_ALIAS,
        "--ks-pass", f"pass:{_STORE_PASS}",
        "--key-pass", f"pass:{_KEY_PASS}",
        "--out", str(apk_path),
        str(apk_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SignerError(f"apksigner failed:\n{result.stderr}")
