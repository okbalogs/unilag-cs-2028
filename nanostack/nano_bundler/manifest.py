"""
Manifest Patcher — updates AndroidManifest.xml inside the unzipped APK.

Handles:
  - package attribute
  - android:label (app name)
  - android:versionName
  - Adding <uses-permission> entries for required services
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List


# ── Permission mappings ───────────────────────────────────────────────────────

SERVICE_PERMISSIONS = {
    "bluetooth": [
        "android.permission.BLUETOOTH",
        "android.permission.BLUETOOTH_SCAN",
        "android.permission.BLUETOOTH_CONNECT",
    ],
    "wifi": [
        "android.permission.ACCESS_WIFI_STATE",
        "android.permission.CHANGE_WIFI_STATE",
    ],
    "camera": [
        "android.permission.CAMERA",
    ],
    "gps": [
        "android.permission.ACCESS_FINE_LOCATION",
    ],
    "storage": [
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
    ],
    "notifications": [
        "android.permission.POST_NOTIFICATIONS",
    ],
    "nfc": [
        "android.permission.NFC",
    ],
    "biometric": [
        "android.permission.USE_BIOMETRIC",
        "android.permission.USE_FINGERPRINT",
    ],
    "accelerometer": [],  # no permission needed; sensor access is open
}


class ManifestError(Exception):
    pass


def update(
    apk_dir: str,
    package_id: str,
    app_name: str,
    version_name: str,
    services_required: List[str],
) -> None:
    """
    Patch AndroidManifest.xml inside apk_dir in-place.

    apk_dir      — path to the unzipped APK directory
    package_id   — e.g. com.yourname.myapp
    app_name     — human-readable app label
    version_name — e.g. "1.0"
    services_required — list of service names from logic.json
    """
    manifest_path = Path(apk_dir) / "AndroidManifest.xml"
    if not manifest_path.exists():
        raise ManifestError(f"AndroidManifest.xml not found at {manifest_path}")

    xml = manifest_path.read_text(encoding="utf-8")

    # Update package attribute
    xml = re.sub(
        r'(package\s*=\s*")[^"]*(")',
        lambda m: m.group(1) + package_id + m.group(2),
        xml,
    )

    # Update android:label
    xml = re.sub(
        r'(android:label\s*=\s*")[^"]*(")',
        lambda m: m.group(1) + app_name + m.group(2),
        xml,
    )

    # Update android:versionName
    xml = re.sub(
        r'(android:versionName\s*=\s*")[^"]*(")',
        lambda m: m.group(1) + version_name + m.group(2),
        xml,
    )

    # Collect required permissions
    required_perms: List[str] = []
    for service in services_required:
        required_perms.extend(SERVICE_PERMISSIONS.get(service, []))

    # Deduplicate while preserving order
    seen: set = set()
    unique_perms: List[str] = []
    for p in required_perms:
        if p not in seen:
            seen.add(p)
            unique_perms.append(p)

    # Build <uses-permission> XML lines
    perm_lines = "\n".join(
        f'    <uses-permission android:name="{p}" />'
        for p in unique_perms
    )

    # Remove any existing <uses-permission> tags to avoid duplication
    xml = re.sub(r'\s*<uses-permission[^/]*/>', '', xml)

    # Insert new permissions before </manifest>
    if perm_lines:
        xml = xml.replace("</manifest>", f"\n{perm_lines}\n</manifest>")

    manifest_path.write_text(xml, encoding="utf-8")
