"""Tests for nano_compiler.parser"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from nano_compiler.lexer import lex
from nano_compiler.parser import parse


# ── helpers ───────────────────────────────────────────────────────────────────

def compile_ast(source: str):
    return parse(lex(source))


# ── 1. Screen node with name and background ───────────────────────────────────

def test_screen_name():
    ast = compile_ast("screen: LoginScreen\n  background: \"#FFFFFF\"")
    assert len(ast["screens"]) == 1
    assert ast["screens"][0]["name"] == "LoginScreen"


def test_screen_background():
    ast = compile_ast("screen: LoginScreen\n  background: \"#FFFFFF\"")
    assert ast["screens"][0]["background"] == "#FFFFFF"


def test_screen_type_field():
    ast = compile_ast("screen: Home\n  background: \"#000\"")
    assert ast["screens"][0]["type"] == "screen"


# ── 2. Text component ─────────────────────────────────────────────────────────

def test_text_component_value():
    source = (
        "screen: Home\n"
        "  text:\n"
        "    value: \"Hello\"\n"
        "    size: 28\n"
        "    bold: true\n"
        "    align: center\n"
        "    color: \"#111111\"\n"
    )
    ast = compile_ast(source)
    comps = ast["screens"][0]["components"]
    text = next(c for c in comps if c["type"] == "text")
    assert text["value"] == "Hello"
    assert text["size"] == 28
    assert text["bold"] is True
    assert text["align"] == "center"
    assert text["color"] == "#111111"


# ── 3. Button with on_click action list ───────────────────────────────────────

def test_button_with_on_click():
    source = (
        "screen: Home\n"
        "  button:\n"
        "    label: \"Go\"\n"
        "    on_click:\n"
        "      - navigate: OtherScreen\n"
    )
    ast = compile_ast(source)
    comps = ast["screens"][0]["components"]
    btn = next(c for c in comps if c["type"] == "button")
    assert btn["label"] == "Go"
    assert "on_click" in btn
    assert len(btn["on_click"]) == 1


# ── 4. Navigate action ────────────────────────────────────────────────────────

def test_navigate_action_target():
    source = (
        "screen: A\n"
        "  button:\n"
        "    label: \"Go\"\n"
        "    on_click:\n"
        "      - navigate: B\n"
    )
    ast = compile_ast(source)
    action = ast["screens"][0]["components"][0]["on_click"][0]
    assert action["action"] == "navigate"
    assert action["target"] == "B"


# ── 5. List component with item_template ──────────────────────────────────────

def test_list_component():
    source = (
        "screen: S\n"
        "  list:\n"
        "    id: device_list\n"
        "    source: found_devices\n"
        "    empty_text: \"None\"\n"
        "    item_template:\n"
        "      text: $device.name\n"
        "      subtext: $device.mac_address\n"
        "      icon: bluetooth\n"
    )
    ast = compile_ast(source)
    lst = ast["screens"][0]["components"][0]
    assert lst["type"] == "list"
    assert lst["source"] == "found_devices"
    assert "item_template" in lst
    tmpl = lst["item_template"]
    assert tmpl["text"] == "$device.name"
    assert tmpl["icon"] == "bluetooth"


# ── 6. Service block on_success / on_fail ────────────────────────────────────

def test_button_on_success_on_fail():
    source = (
        "screen: Home\n"
        "  button:\n"
        "    label: \"Photo\"\n"
        "    on_click:\n"
        "      - call: camera.capture_photo()\n"
        "      - on_success:\n"
        "          - navigate: Preview\n"
        "      - on_fail:\n"
        "          - show_toast: \"Error\"\n"
    )
    ast = compile_ast(source)
    btn = ast["screens"][0]["components"][0]
    actions = btn["on_click"]
    call_action = next(a for a in actions if a.get("action") == "call")
    assert call_action["method"] == "camera.capture_photo()"


# ── 7. Script block ───────────────────────────────────────────────────────────

def test_script_block_parsed():
    source = (
        "screen: S\n"
        "  script: my_script\n"
        "    steps:\n"
        "      - show_toast: \"Hello\"\n"
        "      - navigate: OtherScreen\n"
    )
    ast = compile_ast(source)
    screen = ast["screens"][0]
    scripts = screen.get("scripts", [])
    assert len(scripts) == 1
    assert scripts[0]["name"] == "my_script"
    assert len(scripts[0]["steps"]) == 2


# ── 8. if/then/else logic ─────────────────────────────────────────────────────

def test_if_then_else():
    source = (
        "screen: S\n"
        "  script: check\n"
        "    steps:\n"
        "      - if: condition_met\n"
        "          then:\n"
        "            - navigate: SuccessScreen\n"
        "          else:\n"
        "            - show_toast: \"Failed\"\n"
    )
    ast = compile_ast(source)
    scripts = ast["screens"][0].get("scripts", [])
    if_step = scripts[0]["steps"][0]
    assert if_step["action"] == "if"
    assert len(if_step["then"]) == 1
    assert if_step["then"][0]["action"] == "navigate"
    assert len(if_step["else"]) == 1
    assert if_step["else"][0]["action"] == "show_toast"


# ── 9. Multiple screens ───────────────────────────────────────────────────────

def test_multiple_screens():
    source = (
        "screen: A\n"
        "  text:\n"
        "    value: \"A\"\n"
        "screen: B\n"
        "  text:\n"
        "    value: \"B\"\n"
        "screen: C\n"
        "  text:\n"
        "    value: \"C\"\n"
    )
    ast = compile_ast(source)
    assert len(ast["screens"]) == 3
    names = [s["name"] for s in ast["screens"]]
    assert names == ["A", "B", "C"]


# ── 10. App metadata block ────────────────────────────────────────────────────

def test_app_metadata():
    source = (
        "app:\n"
        "  name: MyApp\n"
        "  version: 2.0\n"
        "screen: Home\n"
        "  text:\n"
        "    value: \"Hi\"\n"
    )
    ast = compile_ast(source)
    assert ast["app"]["name"] == "MyApp"
    assert ast["app"]["version"] == 2.0


def test_app_permissions():
    source = (
        "app:\n"
        "  name: BT\n"
        "  version: 1.0\n"
        "  permissions:\n"
        "    - bluetooth\n"
        "    - camera\n"
    )
    ast = compile_ast(source)
    perms = ast["app"].get("permissions", [])
    assert "bluetooth" in perms
    assert "camera" in perms
