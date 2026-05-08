"""
Asset Injector — injects logic.json into a pre-built runner APK.

An APK is just a ZIP file, so we:
  1. Unzip runner.apk to a temp directory
  2. Copy logic.json into the assets/ folder
  3. Re-zip everything back to a new .apk

No Android tooling is required for this step.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path


class InjectorError(Exception):
    pass


def inject(
    runner_apk_path: str,
    logic_json_path: str,
    output_apk_path: str,
) -> str:
    """
    Inject logic_json_path into runner_apk_path and write the result to
    output_apk_path.  Returns output_apk_path.

    Raises InjectorError on any failure.
    """
    runner = Path(runner_apk_path)
    logic  = Path(logic_json_path)
    output = Path(output_apk_path)

    if not runner.exists():
        raise InjectorError(f"Runner APK not found: {runner}")
    if not logic.exists():
        raise InjectorError(f"logic.json not found: {logic}")

    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="nanostack_inject_") as tmpdir:
        tmp = Path(tmpdir)

        # Step 1 — unzip the runner APK
        _unzip(runner, tmp)

        # Step 2 — copy logic.json into assets/
        assets_dir = tmp / "assets"
        assets_dir.mkdir(exist_ok=True)
        shutil.copy2(logic, assets_dir / "logic.json")

        # Step 3 — re-zip into the output APK
        _rezip(tmp, output)

    return str(output)


def _unzip(apk_path: Path, dest_dir: Path) -> None:
    """Extract all entries from the APK ZIP into dest_dir."""
    with zipfile.ZipFile(apk_path, "r") as zf:
        zf.extractall(dest_dir)


def _rezip(src_dir: Path, output_path: Path) -> None:
    """Re-pack src_dir into a new ZIP/APK at output_path."""
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as zf:
        for file_path in sorted(src_dir.rglob("*")):
            if file_path.is_file():
                arcname = file_path.relative_to(src_dir)
                zf.write(file_path, arcname)
