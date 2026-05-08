"""
NanoCode Emitter — converts the validated AST to logic.json.

The output JSON is what the Android Universal Runner reads at runtime to
build its UI and wire up behaviour without any Java compilation.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Set


# Services that need Android permission entries in the manifest.
_SERVICE_METHODS: Set[str] = {
    "bluetooth", "wifi", "biometric", "camera",
    "gps", "nfc", "storage", "notifications", "accelerometer",
}


class Emitter:
    def __init__(self, ast: Dict, dev: bool = False):
        self._ast = ast
        self._dev = dev          # pretty-print when True
        self._services: Set[str] = set()

    # ── public ────────────────────────────────────────────────────────────────

    def emit(self, output_path: str) -> int:
        """
        Emit logic.json to output_path.
        Returns the number of bytes written.
        """
        payload = self._build_payload()
        content = self._serialise(payload)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(content)

        return len(content.encode("utf-8"))

    def emit_string(self) -> str:
        """Return the serialised JSON as a string (used by tests)."""
        return self._serialise(self._build_payload())

    # ── payload construction ──────────────────────────────────────────────────

    def _build_payload(self) -> Dict:
        app_meta = self._ast.get("app", {})
        screens_ast = self._ast.get("screens", [])
        scripts_ast = self._ast.get("scripts", [])

        # Determine entry screen (first screen defined)
        entry_screen = screens_ast[0]["name"] if screens_ast else ""

        screens_out = [self._emit_screen(s) for s in screens_ast]
        scripts_out = [self._emit_script(s) for s in scripts_ast]

        # Collect inline scripts declared inside screens
        for s in screens_ast:
            for scr in s.get("scripts", []):
                scripts_out.append(self._emit_script(scr))

        payload: Dict[str, Any] = {
            "app": {
                "name": app_meta.get("name", ""),
                "version": str(app_meta.get("version", "1.0")),
                "entry_screen": entry_screen,
            },
            "screens": screens_out,
            "scripts": scripts_out,
            "services_required": sorted(self._services),
        }

        return payload

    # ── screen ────────────────────────────────────────────────────────────────

    def _emit_screen(self, screen: Dict) -> Dict:
        out: Dict[str, Any] = {"name": screen["name"]}

        if "background" in screen:
            out["background"] = screen["background"]

        out["components"] = [
            self._emit_component(c) for c in screen.get("components", [])
        ]

        return out

    # ── component ─────────────────────────────────────────────────────────────

    def _emit_component(self, comp: Dict) -> Dict:
        ctype = comp.get("type", "unknown")
        out: Dict[str, Any] = {"type": ctype}

        # Copy all scalar properties, skipping internal/meta keys
        _skip = {"type", "_line", "on_click", "on_tap", "on_success",
                  "on_fail", "on_cancel", "on_connect", "on_device_found",
                  "item_template", "steps"}

        for key, val in comp.items():
            if key not in _skip:
                out[key] = val

        # Emit event handlers
        for event_key in ("on_click", "on_tap", "on_success", "on_fail",
                          "on_cancel", "on_connect", "on_device_found"):
            if event_key in comp:
                out[event_key] = self._emit_actions(comp[event_key])

        # Emit item_template for list components
        if "item_template" in comp:
            out["item_template"] = self._emit_item_template(comp["item_template"])

        # Emit steps for script-like components
        if "steps" in comp:
            out["steps"] = self._emit_actions(comp["steps"])

        return out

    # ── actions ───────────────────────────────────────────────────────────────

    def _emit_actions(self, actions: List[Dict]) -> List[Dict]:
        return [self._emit_action(a) for a in actions]

    def _emit_action(self, action: Dict) -> Dict:
        atype = action.get("action", "")
        out: Dict[str, Any] = {"action": atype}

        if atype == "navigate":
            out["target"] = action.get("target", "")

        elif atype == "show_toast":
            out["message"] = action.get("message", "")

        elif atype == "run_script":
            out["script"] = action.get("script", "")

        elif atype == "store":
            out["variable"] = action.get("variable", "")
            if "value" in action:
                out["value"] = action["value"]

        elif atype == "validate":
            out["fields"] = action.get("fields", [])

        elif atype == "call":
            method: str = action.get("method", "")
            out["method"] = method
            # track which service is used
            service = method.split(".")[0]
            if service in _SERVICE_METHODS:
                self._services.add(service)

        elif atype == "if":
            out["condition"] = action.get("condition", "")
            out["then"] = self._emit_actions(action.get("then", []))
            if "else" in action:
                out["else"] = self._emit_actions(action.get("else", []))

        elif atype == "update":
            out["target"] = action.get("target", "")

        elif atype == "set":
            out["value"] = action.get("value", "")

        else:
            # pass-through for unknown / raw actions
            for k, v in action.items():
                if k != "action":
                    out[k] = v

        # propagate inline callbacks (on_success, on_fail, etc.)
        for cb in ("on_success", "on_fail", "on_cancel", "on_connect", "on_device_found"):
            if cb in action:
                out[cb] = self._emit_actions(action[cb])

        return out

    # ── item_template ─────────────────────────────────────────────────────────

    def _emit_item_template(self, tmpl: Dict) -> Dict:
        out: Dict[str, Any] = {}
        _event_keys = {"on_tap", "on_click"}
        for key, val in tmpl.items():
            if key in _event_keys:
                out[key] = self._emit_actions(val)
            else:
                out[key] = val
        return out

    # ── script ────────────────────────────────────────────────────────────────

    def _emit_script(self, script: Dict) -> Dict:
        return {
            "name": script.get("name", ""),
            "steps": self._emit_actions(script.get("steps", [])),
        }

    # ── serialisation ─────────────────────────────────────────────────────────

    def _serialise(self, payload: Dict) -> str:
        if self._dev:
            return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


# ── convenience function ──────────────────────────────────────────────────────

def emit(ast: Dict, output_path: str = "logic.json", dev: bool = False) -> int:
    """Emit logic.json to output_path. Returns bytes written."""
    return Emitter(ast, dev=dev).emit(output_path)


def emit_string(ast: Dict, dev: bool = False) -> str:
    """Return logic.json content as a string (useful for tests)."""
    return Emitter(ast, dev=dev).emit_string()
