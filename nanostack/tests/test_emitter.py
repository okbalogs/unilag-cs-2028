"""Tests for nano_compiler.emitter"""

import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from nano_compiler.lexer import lex
from nano_compiler.parser import parse
from nano_compiler.emitter import emit, emit_string, Emitter


# ── helpers ───────────────────────────────────────────────────────────────────

def compile_to_dict(source: str, dev: bool = False) -> dict:
    ast = parse(lex(source))
    return json.loads(emit_string(ast, dev=dev))


LOGIN_SOURCE = """\
app:
  name: LoginApp
  version: 1.0

screen: LoginScreen
  background: "#FFFFFF"

  text:
    value: "Welcome Back"
    size: 28
    bold: true
    align: center
    color: "#111111"

  input:
    id: username_field
    hint: "Enter your email"
    type: email

  button:
    label: "Login"
    color: "#4A90E2"
    on_click:
      - validate: [username_field, password_field]
      - navigate: HomeScreen

screen: HomeScreen
  background: "#F5F5F5"

  text:
    value: "Logged In"
    size: 22
"""

BT_SOURCE = """\
app:
  name: BTApp
  version: 1.0

screen: ScanScreen
  background: "#121212"

  button:
    label: "Scan"
    color: "#00C853"
    on_click:
      - call: bluetooth.scan(duration=10)
"""

CAMERA_SOURCE = """\
app:
  name: CamApp
  version: 1.0

screen: Home
  background: "#000000"

  button:
    label: "Take Photo"
    color: "#4A90E2"
    on_click:
      - call: camera.capture_photo()
      - call: storage.save($last_photo)
"""

SCRIPT_SOURCE = """\
app:
  name: ScriptApp
  version: 1.0

screen: Main
  background: "#FFFFFF"

  button:
    label: "Run"
    on_click:
      - run_script: my_script

  script: my_script
    steps:
      - show_toast: "Running!"
      - navigate: Main
"""


# ── 1. Valid JSON output ──────────────────────────────────────────────────────

def test_output_is_valid_json():
    ast = parse(lex(LOGIN_SOURCE))
    raw = emit_string(ast)
    parsed = json.loads(raw)  # must not raise
    assert isinstance(parsed, dict)


# ── 2. entry_screen is first screen ──────────────────────────────────────────

def test_entry_screen_is_first_screen():
    data = compile_to_dict(LOGIN_SOURCE)
    assert data["app"]["entry_screen"] == "LoginScreen"


def test_entry_screen_second_source():
    source = (
        "app:\n  name: X\n  version: 1.0\n"
        "screen: Alpha\n  text:\n    value: A\n"
        "screen: Beta\n  text:\n    value: B\n"
    )
    data = compile_to_dict(source)
    assert data["app"]["entry_screen"] == "Alpha"


# ── 3. services_required ──────────────────────────────────────────────────────

def test_services_required_bluetooth():
    data = compile_to_dict(BT_SOURCE)
    assert "bluetooth" in data["services_required"]


def test_services_required_camera_and_storage():
    data = compile_to_dict(CAMERA_SOURCE)
    assert "camera" in data["services_required"]
    assert "storage" in data["services_required"]


def test_services_required_empty_for_simple_app():
    simple = (
        "app:\n  name: A\n  version: 1.0\n"
        "screen: Home\n  text:\n    value: Hi\n"
    )
    data = compile_to_dict(simple)
    assert data["services_required"] == []


# ── 4. All screens present ────────────────────────────────────────────────────

def test_all_screens_in_output():
    data = compile_to_dict(LOGIN_SOURCE)
    screen_names = [s["name"] for s in data["screens"]]
    assert "LoginScreen" in screen_names
    assert "HomeScreen" in screen_names


def test_screen_components_present():
    data = compile_to_dict(LOGIN_SOURCE)
    login = next(s for s in data["screens"] if s["name"] == "LoginScreen")
    component_types = [c["type"] for c in login["components"]]
    assert "text" in component_types
    assert "input" in component_types
    assert "button" in component_types


# ── 5. on_click action arrays ─────────────────────────────────────────────────

def test_on_click_serialised():
    data = compile_to_dict(LOGIN_SOURCE)
    login = next(s for s in data["screens"] if s["name"] == "LoginScreen")
    btn = next(c for c in login["components"] if c["type"] == "button")
    assert "on_click" in btn
    assert isinstance(btn["on_click"], list)
    assert len(btn["on_click"]) >= 1


def test_navigate_action_in_on_click():
    data = compile_to_dict(LOGIN_SOURCE)
    login = next(s for s in data["screens"] if s["name"] == "LoginScreen")
    btn = next(c for c in login["components"] if c["type"] == "button")
    nav = next((a for a in btn["on_click"] if a["action"] == "navigate"), None)
    assert nav is not None
    assert nav["target"] == "HomeScreen"


# ── 6. Dev mode pretty-printing ───────────────────────────────────────────────

def test_dev_mode_pretty_printed():
    ast = parse(lex(LOGIN_SOURCE))
    output = emit_string(ast, dev=True)
    assert "\n" in output
    assert "  " in output  # indentation present


def test_production_mode_minified():
    ast = parse(lex(LOGIN_SOURCE))
    output = emit_string(ast, dev=False)
    assert "\n" not in output.strip() or output.count("\n") == 0


# ── 7. App name and version ───────────────────────────────────────────────────

def test_app_name_in_output():
    data = compile_to_dict(LOGIN_SOURCE)
    assert data["app"]["name"] == "LoginApp"


def test_app_version_in_output():
    data = compile_to_dict(LOGIN_SOURCE)
    assert data["app"]["version"] == "1.0"


# ── 8. Script blocks in output ────────────────────────────────────────────────

def test_script_in_scripts_array():
    data = compile_to_dict(SCRIPT_SOURCE)
    assert isinstance(data["scripts"], list)
    assert len(data["scripts"]) >= 1


def test_script_steps_serialised():
    data = compile_to_dict(SCRIPT_SOURCE)
    script = next(
        (s for s in data["scripts"] if s["name"] == "my_script"), None
    )
    assert script is not None
    assert isinstance(script["steps"], list)
    assert len(script["steps"]) == 2


# ── 9. File write ─────────────────────────────────────────────────────────────

def test_emit_writes_file():
    ast = parse(lex(LOGIN_SOURCE))
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "logic.json")
        byte_count = emit(ast, out_path)
        assert os.path.exists(out_path)
        assert byte_count > 0
        with open(out_path) as fh:
            data = json.load(fh)
        assert data["app"]["name"] == "LoginApp"
