"""
Bundler — orchestrates the full APK build pipeline:
  1. Inject logic.json into runner.apk
  2. Update AndroidManifest.xml with app metadata and permissions
  3. Sign the APK with the debug keystore

Prints timestamped progress for each step.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

from .injector import inject, InjectorError
from .manifest import update as update_manifest, ManifestError
from .signer import sign, SignerError

_GREEN = "\033[92m"
_RED   = "\033[91m"
_RESET = "\033[0m"


class BundlerError(Exception):
    pass


def bundle(
    runner_apk_path: str,
    logic_json_path: str,
    package_id: str,
    app_name: str,
    version_name: str,
    output_dir: str = "build",
) -> str:
    """
    Full APK pipeline.

    runner_apk_path  — path to the pre-built Universal Runner APK
    logic_json_path  — path to the compiled logic.json
    package_id       — Android package ID (com.company.appname)
    app_name         — human-readable name shown on device
    version_name     — version string (e.g. "1.0")
    output_dir       — directory where final APK will be written

    Returns the path to the signed output APK.
    """
    total_start = time.perf_counter()

    # Derive output APK name from app_name
    safe_name = "".join(c if c.isalnum() else "_" for c in app_name)
    output_apk = os.path.join(output_dir, f"{safe_name}.apk")
    os.makedirs(output_dir, exist_ok=True)

    # ── Read services_required from logic.json ────────────────────────────────
    try:
        with open(logic_json_path, encoding="utf-8") as fh:
            logic = json.load(fh)
        services_required = logic.get("services_required", [])
    except (OSError, json.JSONDecodeError) as exc:
        raise BundlerError(f"Cannot read logic.json: {exc}")

    # ── Step 1: Inject ────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    print("[1/3] Injecting logic into runner APK...", end="  ", flush=True)
    try:
        injected_apk = inject(runner_apk_path, logic_json_path, output_apk)
    except InjectorError as exc:
        print(f"\n{_RED}✗{_RESET} Injection failed: {exc}")
        raise BundlerError(str(exc))
    t1 = time.perf_counter()
    print(f"{_GREEN}✓{_RESET}  ({t1 - t0:.1f}s)")

    # ── Step 2: Patch manifest ────────────────────────────────────────────────
    t0 = time.perf_counter()
    print("[2/3] Updating app manifest and permissions...", end=" ", flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix="nanostack_manifest_") as tmpdir:
            # Unzip the injected APK
            with zipfile.ZipFile(injected_apk, "r") as zf:
                zf.extractall(tmpdir)

            update_manifest(
                apk_dir=tmpdir,
                package_id=package_id,
                app_name=app_name,
                version_name=version_name,
                services_required=services_required,
            )

            # Re-zip back
            tmp_out = injected_apk + ".manifest_patched.apk"
            import zipfile as zfmod
            with zfmod.ZipFile(tmp_out, "w", compression=zfmod.ZIP_DEFLATED) as zout:
                for fpath in sorted(Path(tmpdir).rglob("*")):
                    if fpath.is_file():
                        arcname = fpath.relative_to(tmpdir)
                        zout.write(fpath, arcname)

            shutil.move(tmp_out, injected_apk)

    except ManifestError as exc:
        print(f"\n{_RED}✗{_RESET} Manifest update failed: {exc}")
        raise BundlerError(str(exc))
    t1 = time.perf_counter()
    print(f"{_GREEN}✓{_RESET}  ({t1 - t0:.1f}s)")

    # ── Step 3: Sign ──────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    print("[3/3] Signing APK...", end="                          ", flush=True)
    try:
        signed_apk = sign(injected_apk)
    except SignerError as exc:
        print(f"\n{_RED}✗{_RESET} Signing failed: {exc}")
        raise BundlerError(str(exc))
    t1 = time.perf_counter()
    print(f"{_GREEN}✓{_RESET}  ({t1 - t0:.1f}s)")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_elapsed = time.perf_counter() - total_start
    apk_size = os.path.getsize(signed_apk)
    size_str = _human_size(apk_size)
    print(f"\nBuild complete in {total_elapsed:.1f} seconds")
    print(f"Output: {signed_apk} ({size_str})")

    return signed_apk


def _human_size(byte_count: int) -> str:
    if byte_count < 1024:
        return f"{byte_count} B"
    if byte_count < 1024 ** 2:
        return f"{byte_count / 1024:.1f} KB"
    return f"{byte_count / (1024**2):.1f} MB"
