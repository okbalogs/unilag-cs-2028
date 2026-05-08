"""
NanoCode Validator — semantic checks on the AST before emission.

Returns a list of error dicts:
  {"line": int, "type": str, "message": str}

All checks are non-fatal individually; the full list is returned so the
user can fix everything in one pass.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set


_VALID_SERVICES: Set[str] = {
    "bluetooth", "wifi", "biometric", "camera", "gps",
    "nfc", "storage", "notifications", "accelerometer",
}

_HEX_RE = re.compile(r'^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$')


class Validator:
    def __init__(self, ast: Dict):
        self._ast = ast
        self._errors: List[Dict] = []

    # ── public ────────────────────────────────────────────────────────────────

    def validate(self) -> List[Dict]:
        self._errors = []

        self._check_app_block()
        screen_names = self._collect_screen_names()
        script_names = self._collect_script_names()
        self._check_screens(screen_names, script_names)
        self._check_scripts(screen_names, script_names)

        return self._errors

    # ── app block ─────────────────────────────────────────────────────────────

    def _check_app_block(self) -> None:
        app = self._ast.get("app", {})
        if not app.get("name"):
            self._err(0, "MISSING_APP_NAME", "app block is missing required 'name' property")
        if not app.get("version") and app.get("version") != 0:
            self._err(0, "MISSING_APP_VERSION", "app block is missing required 'version' property")

    # ── screen name collection ────────────────────────────────────────────────

    def _collect_screen_names(self) -> Set[str]:
        seen: Set[str] = set()
        for screen in self._ast.get("screens", []):
            name = screen.get("name", "")
            if name in seen:
                self._err(
                    0, "DUPLICATE_SCREEN",
                    f"duplicate screen name '{name}' — screen names must be unique",
                )
            seen.add(name)
        return seen

    def _collect_script_names(self) -> Set[str]:
        names: Set[str] = set()
        for script in self._ast.get("scripts", []):
            names.add(script.get("name", ""))
        # also collect inline scripts defined inside screens
        for screen in self._ast.get("screens", []):
            for scr in screen.get("scripts", []):
                names.add(scr.get("name", ""))
        return names

    # ── screen validation ─────────────────────────────────────────────────────

    def _check_screens(self, screen_names: Set[str], script_names: Set[str]) -> None:
        for screen in self._ast.get("screens", []):
            bg = screen.get("background")
            if bg is not None:
                self._validate_color(bg, 0, f"screen '{screen.get('name', '?')}'")

            for comp in screen.get("components", []):
                self._check_component(comp, screen_names, script_names)

    def _check_component(
        self, comp: Dict, screen_names: Set[str], script_names: Set[str]
    ) -> None:
        ctype = comp.get("type", "unknown")
        line = comp.get("_line", 0)

        if ctype == "button":
            if not comp.get("label"):
                self._err(line, "MISSING_LABEL", f"button is missing required 'label' property")
            color = comp.get("color")
            if color:
                self._validate_color(color, line, "button")

        elif ctype == "input":
            if not comp.get("id"):
                self._err(line, "MISSING_ID", "input is missing required 'id' property")

        elif ctype == "list":
            if not comp.get("source"):
                self._err(line, "MISSING_SOURCE", "list is missing required 'source' property")
            tmpl = comp.get("item_template")
            if tmpl:
                for key in ("on_tap", "on_click"):
                    for action in tmpl.get(key, []):
                        self._check_action(action, screen_names, script_names, line)

        elif ctype == "link":
            target = comp.get("navigate")
            if target and target not in screen_names:
                self._err(
                    line, "MISSING_SCREEN",
                    f"link navigates to '{target}' but no screen named '{target}' exists",
                )

        # validate on_click, on_tap, etc.
        for event_key in ("on_click", "on_tap", "on_success", "on_fail",
                          "on_cancel", "on_connect", "on_device_found"):
            for action in comp.get(event_key, []):
                self._check_action(action, screen_names, script_names, line)

    def _check_action(
        self,
        action: Dict,
        screen_names: Set[str],
        script_names: Set[str],
        line: int,
    ) -> None:
        atype = action.get("action", "")

        if atype == "navigate":
            target = action.get("target")
            if target and target not in screen_names:
                self._err(
                    line, "MISSING_SCREEN",
                    f"navigate points to '{target}' but no screen named '{target}' exists",
                )

        elif atype == "run_script":
            script = action.get("script")
            if script and script not in script_names:
                self._err(
                    line, "MISSING_SCRIPT",
                    f"run_script references '{script}' but no script named '{script}' exists",
                )

        elif atype == "store":
            var = action.get("variable", "")
            if not var:
                self._err(line, "EMPTY_STORE_VAR", "store action has an empty variable name")

        elif atype == "call":
            method = action.get("method", "")
            if method:
                service = method.split(".")[0]
                if service not in _VALID_SERVICES:
                    self._err(
                        line, "INVALID_SERVICE",
                        f"call references service '{service}' which is not one of: "
                        + ", ".join(sorted(_VALID_SERVICES)),
                    )

        elif atype == "if":
            for step in action.get("then", []):
                self._check_action(step, screen_names, script_names, line)
            for step in action.get("else", []):
                self._check_action(step, screen_names, script_names, line)

    # ── script validation ─────────────────────────────────────────────────────

    def _check_scripts(self, screen_names: Set[str], script_names: Set[str]) -> None:
        for script in self._ast.get("scripts", []):
            for step in script.get("steps", []):
                self._check_action(step, screen_names, script_names, 0)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _validate_color(self, value: Any, line: int, context: str) -> None:
        if isinstance(value, str) and value.startswith("#"):
            if not _HEX_RE.match(value):
                self._err(
                    line, "INVALID_COLOR",
                    f"color value '{value}' in {context} is not a valid hex color "
                    f"(use #RGB or #RRGGBB)",
                )

    def _err(self, line: int, etype: str, message: str) -> None:
        self._errors.append({"line": line, "type": etype, "message": message})


# ── convenience function ──────────────────────────────────────────────────────

def validate(ast: Dict) -> List[Dict]:
    """Validate an AST and return a list of error dicts."""
    return Validator(ast).validate()
