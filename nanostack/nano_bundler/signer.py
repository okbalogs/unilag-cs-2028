"""
APK Signer — generates a debug keystore if needed and signs the APK.

Primary:  apksigner.jar (bundled in bin/) — produces v2/v3 signatures.
Fallback: jarsigner   (bundled in JDK)   — produces v1 signatures,
          installable on Android 5.0+ (API 21+).

apksigner.jar is used when present; jarsigner is used automatically when
apksigner.jar has not yet been downloaded, so the full build pipeline works
locally without any extra downloads as long as a JDK is installed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


_KEYSTORE_DIR  = Path.home() / ".nanostack"
_KEYSTORE_PATH = _KEYSTORE_DIR / "debug.keystore"
_KEY_ALIAS     = "androiddebugkey"
_STORE_PASS    = "android"
_KEY_PASS      = "android"

_BIN_DIR       = Path(__file__).parent.parent / "bin"
_APKSIGNER_JAR = _BIN_DIR / "apksigner.jar"


class SignerError(Exception):
    pass


def sign(apk_path: str) -> str:
    """
    Sign apk_path with the debug keystore.
    Creates the keystore if it does not already exist.
    Returns the path to the signed APK (same path, signed in-place).
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
        raise SignerError(f"keytool failed:\n{result.stderr}")


def _sign_apk(apk_path: Path) -> None:
    """
    Sign the APK.  Uses apksigner.jar when available, falls back to jarsigner.
    """
    if not apk_path.exists():
        raise SignerError(f"APK not found: {apk_path}")

    if _APKSIGNER_JAR.exists():
        _sign_with_apksigner(apk_path)
    else:
        _sign_with_jarsigner(apk_path)


def _sign_with_apksigner(apk_path: Path) -> None:
    """Sign using the bundled apksigner.jar (v2/v3 signatures)."""
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


def _sign_with_jarsigner(apk_path: Path) -> None:
    """
    Sign using jarsigner (part of JDK) — v1 JAR signature.
    Produces APKs installable on Android 5.0+ (API 21+).
    Automatically used when apksigner.jar is not present in bin/.
    """
    if not shutil.which("jarsigner"):
        raise SignerError(
            "Neither apksigner.jar nor jarsigner is available.\n"
            "  • Place apksigner.jar in nanostack/bin/apksigner.jar, OR\n"
            "  • Ensure a JDK (not just JRE) is installed so jarsigner is on PATH."
        )

    cmd = [
        "jarsigner",
        "-verbose",
        "-sigalg",   "SHA256withRSA",
        "-digestalg", "SHA-256",
        "-keystore",  str(_KEYSTORE_PATH),
        "-storepass", _STORE_PASS,
        "-keypass",   _KEY_PASS,
        str(apk_path),
        _KEY_ALIAS,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SignerError(f"jarsigner failed:\n{result.stderr}")
