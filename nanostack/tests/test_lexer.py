"""Tests for nano_compiler.lexer"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from nano_compiler.lexer import lex, Token


# ── helpers ───────────────────────────────────────────────────────────────────

def token_types(source: str):
    return [t.type for t in lex(source)]


def token_values(source: str):
    return [t.value for t in lex(source)]


def find_tokens(source: str, ttype: str):
    return [t for t in lex(source) if t.type == ttype]


# ── 1. KEYWORD tokens ─────────────────────────────────────────────────────────

def test_keyword_screen():
    tokens = lex("screen: LoginScreen")
    kw = [t for t in tokens if t.type == "KEYWORD"]
    assert any(t.value == "screen" for t in kw)


def test_keyword_app():
    tokens = lex("app:")
    assert any(t.type == "KEYWORD" and t.value == "app" for t in tokens)


def test_keyword_button():
    tokens = lex("button:")
    assert any(t.type == "KEYWORD" and t.value == "button" for t in tokens)


def test_all_top_level_keywords():
    from nano_compiler.lexer import TOP_LEVEL_KEYWORDS
    for kw in TOP_LEVEL_KEYWORDS:
        tokens = lex(f"{kw}:")
        assert any(t.type == "KEYWORD" and t.value == kw for t in tokens), (
            f"Expected KEYWORD token for '{kw}'"
        )


# ── 2. String VALUE tokens ────────────────────────────────────────────────────

def test_double_quoted_string():
    tokens = lex('value: "Hello World"')
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value == "Hello World" for t in vals)


def test_single_quoted_string():
    tokens = lex("value: 'Hello World'")
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value == "Hello World" for t in vals)


def test_string_with_spaces():
    tokens = lex('label: "Get Started Now"')
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value == "Get Started Now" for t in vals)


# ── 3. Numeric VALUE tokens ───────────────────────────────────────────────────

def test_integer_value():
    tokens = lex("size: 28")
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value == 28 for t in vals)


def test_float_value():
    tokens = lex("version: 1.0")
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value == 1.0 for t in vals)


def test_negative_integer():
    tokens = lex("margin: -10")
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value == -10 for t in vals)


# ── 4. Boolean VALUE tokens ───────────────────────────────────────────────────

def test_boolean_true():
    tokens = lex("bold: true")
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value is True for t in vals)


def test_boolean_false():
    tokens = lex("bold: false")
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value is False for t in vals)


# ── 5. Hex colour VALUE tokens ────────────────────────────────────────────────

def test_hex_colour_rrggbb():
    tokens = lex('color: "#4A90E2"')
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value == "#4A90E2" for t in vals)


def test_hex_colour_rgb():
    tokens = lex('background: "#FFF"')
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value == "#FFF" for t in vals)


# ── 6. INDENT / DEDENT tokens ─────────────────────────────────────────────────

def test_indent_generated_on_nested_block():
    source = "screen: Home\n  text:"
    types = token_types(source)
    assert "INDENT" in types


def test_dedent_generated_on_dedent():
    source = "screen: Home\n  text:\n    value: Hi\nscreen: Other"
    types = token_types(source)
    assert "DEDENT" in types


def test_indent_dedent_balanced():
    source = (
        "screen: Home\n"
        "  text:\n"
        "    value: Hello\n"
        "  button:\n"
        "    label: Go\n"
    )
    tokens = lex(source)
    indents = sum(1 for t in tokens if t.type == "INDENT")
    dedents = sum(1 for t in tokens if t.type == "DEDENT")
    assert indents == dedents


# ── 7. Comments ───────────────────────────────────────────────────────────────

def test_comment_line_ignored():
    source = "# This is a comment\nscreen: Home"
    tokens = lex(source)
    values = [t.value for t in tokens]
    assert "This is a comment" not in values


def test_inline_comment_not_supported_but_line_produces_tokens():
    source = "screen: Home"
    tokens = lex(source)
    assert any(t.value == "screen" for t in tokens)


# ── 8. Dollar-sign variables ──────────────────────────────────────────────────

def test_dollar_variable():
    tokens = lex("text: $device.name")
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any(t.value == "$device.name" for t in vals)


def test_dollar_variable_complex():
    tokens = lex("source: $active_device.mac_address")
    vals = [t for t in tokens if t.type == "VALUE"]
    assert any("$active_device.mac_address" == t.value for t in vals)


# ── 9. Inline lists ───────────────────────────────────────────────────────────

def test_inline_list():
    tokens = lex("validate: [username_field, password_field]")
    vals = [t for t in tokens if t.type == "VALUE"]
    list_vals = [t for t in vals if isinstance(t.value, list)]
    assert list_vals, "Expected a list VALUE token"
    assert "username_field" in list_vals[0].value
    assert "password_field" in list_vals[0].value


def test_inline_list_single_item():
    tokens = lex("validate: [reset_email]")
    vals = [t for t in tokens if t.type == "VALUE"]
    list_vals = [t for t in vals if isinstance(t.value, list)]
    assert list_vals
    assert "reset_email" in list_vals[0].value


# ── 10. EOF token ─────────────────────────────────────────────────────────────

def test_eof_is_last_token():
    tokens = lex("screen: Home")
    assert tokens[-1].type == "EOF"


def test_eof_on_empty_source():
    tokens = lex("")
    assert tokens[-1].type == "EOF"
    assert len(tokens) == 1


# ── 11. Line numbers ──────────────────────────────────────────────────────────

def test_line_numbers_correct():
    source = "app:\n  name: TestApp\n  version: 1.0"
    tokens = lex(source)
    keyword_tokens = [t for t in tokens if t.type in ("KEYWORD", "PROPERTY")]
    assert keyword_tokens[0].line == 1   # app
    assert keyword_tokens[1].line == 2   # name
    assert keyword_tokens[2].line == 3   # version
