"""
NanoCode Lexer — converts .nano source text into a flat token list.

Token types:
  KEYWORD   — top-level or block-level reserved word
  PROPERTY  — property key inside a block
  VALUE     — scalar value (string, number, bool, colour, variable, list)
  INDENT    — indentation increase
  DEDENT    — indentation decrease
  NEWLINE   — logical end-of-line (after non-empty content)
  EOF       — end of file
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

# ── Token definition ──────────────────────────────────────────────────────────

TOP_LEVEL_KEYWORDS = {
    "app", "screen", "text", "input", "button", "list",
    "image", "link", "service", "script",
}

PROPERTY_KEYWORDS = {
    "name", "version", "background", "value", "size", "bold", "align",
    "color", "hint", "type", "id", "label", "source", "on_click", "on_tap",
    "navigate", "call", "validate", "store", "show_toast", "update",
    "run_script", "item_template", "subtext", "icon", "empty_text",
    "permissions", "on_success", "on_fail", "on_cancel", "on_connect",
    "on_device_found", "action", "prompt", "duration", "data", "ssid",
    "password", "if", "then", "else", "steps", "set", "italic", "padding",
    "margin", "width", "height", "on_tap",
}

ALL_KEYWORDS = TOP_LEVEL_KEYWORDS | PROPERTY_KEYWORDS

# Regex patterns (compiled once)
_RE_INDENT   = re.compile(r'^( *)')
_RE_COMMENT  = re.compile(r'^\s*#')
_RE_BLANK    = re.compile(r'^\s*$')
_RE_DSTRING  = re.compile(r'"((?:[^"\\]|\\.)*)"')
_RE_SSTRING  = re.compile(r"'((?:[^'\\]|\\.)*)'")
_RE_HEX      = re.compile(r'#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?(?=\s|$|,|\])')
_RE_FLOAT    = re.compile(r'-?\d+\.\d+')
_RE_INT      = re.compile(r'-?\d+')
_RE_BOOL     = re.compile(r'\b(true|false)\b')
_RE_IDENT    = re.compile(r'[\w][\w.\-]*')
_RE_VAR      = re.compile(r'\$[\w][\w.\-]*')
_RE_LIST_VAL = re.compile(r'\[([^\]]*)\]')


@dataclass
class Token:
    type: str
    value: object
    line: int

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r}, line={self.line})"


class LexerError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(message)
        self.line = line


# ── Lexer ─────────────────────────────────────────────────────────────────────

class Lexer:
    def __init__(self, source: str):
        self._lines = source.splitlines()
        self._tokens: List[Token] = []
        self._indent_stack: List[int] = [0]

    # ── public ────────────────────────────────────────────────────────────────

    def tokenise(self) -> List[Token]:
        for lineno, raw in enumerate(self._lines, start=1):
            self._process_line(raw, lineno)

        # close any remaining open indents at EOF
        while self._indent_stack[-1] > 0:
            self._indent_stack.pop()
            self._tokens.append(Token("DEDENT", None, len(self._lines)))

        self._tokens.append(Token("EOF", None, len(self._lines)))
        return self._tokens

    # ── private ───────────────────────────────────────────────────────────────

    def _process_line(self, raw: str, lineno: int) -> None:
        if _RE_BLANK.match(raw) or _RE_COMMENT.match(raw):
            return

        # Measure indentation
        indent_match = _RE_INDENT.match(raw)
        current_indent = len(indent_match.group(1))
        stripped = raw.strip()

        # Emit INDENT / DEDENT
        prev_indent = self._indent_stack[-1]
        if current_indent > prev_indent:
            self._indent_stack.append(current_indent)
            self._tokens.append(Token("INDENT", current_indent, lineno))
        elif current_indent < prev_indent:
            while self._indent_stack[-1] > current_indent:
                self._indent_stack.pop()
                self._tokens.append(Token("DEDENT", None, lineno))
            if self._indent_stack[-1] != current_indent:
                raise LexerError(
                    f"Inconsistent indentation (got {current_indent} spaces, "
                    f"expected one of {self._indent_stack})",
                    lineno,
                )

        # Tokenise the content of this line
        self._tokenise_line(stripped, lineno)

    def _tokenise_line(self, text: str, lineno: int) -> None:
        """
        A line has one of these shapes:
          keyword: Value        →  KEYWORD  VALUE
          keyword:              →  KEYWORD
          - action: target      →  PROPERTY VALUE  (list item)
          - keyword             →  VALUE           (bare list item)
        """
        # Strip leading list-item marker
        list_item = False
        if text.startswith("- "):
            list_item = True
            text = text[2:].strip()
        elif text == "-":
            list_item = True
            text = ""

        if not text:
            return

        # Split on first colon that is not inside quotes
        key, sep, rest = self._split_key_value(text)
        rest = rest.strip() if rest else ""

        key_lower = key.strip().lower()

        if sep:
            # We have a key: value pair
            tok_type = "KEYWORD" if key_lower in TOP_LEVEL_KEYWORDS else "PROPERTY"
            self._tokens.append(Token(tok_type, key_lower, lineno))
            if rest:
                self._emit_value(rest, lineno)
        else:
            # No colon — bare word or bare value
            if key_lower in ALL_KEYWORDS:
                self._tokens.append(Token("KEYWORD", key_lower, lineno))
            else:
                self._emit_value(key.strip(), lineno)

        self._tokens.append(Token("NEWLINE", None, lineno))

    def _split_key_value(self, text: str):
        """Split 'key: value' respecting quoted strings. Returns (key, sep, rest)."""
        in_sq = in_dq = False
        for i, ch in enumerate(text):
            if ch == '"' and not in_sq:
                in_dq = not in_dq
            elif ch == "'" and not in_dq:
                in_sq = not in_sq
            elif ch == ":" and not in_sq and not in_dq:
                return text[:i], ":", text[i+1:]
        return text, "", ""

    def _emit_value(self, text: str, lineno: int) -> None:
        """Parse a raw value string and emit the appropriate VALUE token."""
        text = text.strip()
        if not text:
            return

        # Inline list  [a, b, c]
        m = _RE_LIST_VAL.match(text)
        if m:
            items = [item.strip().strip('"').strip("'")
                     for item in m.group(1).split(",") if item.strip()]
            self._tokens.append(Token("VALUE", items, lineno))
            return

        # Double-quoted string
        m = _RE_DSTRING.match(text)
        if m:
            self._tokens.append(Token("VALUE", m.group(1), lineno))
            return

        # Single-quoted string
        m = _RE_SSTRING.match(text)
        if m:
            self._tokens.append(Token("VALUE", m.group(1), lineno))
            return

        # Hex colour (must come before bare ident since it starts with #)
        m = _RE_HEX.match(text)
        if m:
            self._tokens.append(Token("VALUE", m.group(0), lineno))
            return

        # Boolean
        m = _RE_BOOL.fullmatch(text)
        if m:
            self._tokens.append(Token("VALUE", text == "true", lineno))
            return

        # Float
        m = _RE_FLOAT.fullmatch(text)
        if m:
            self._tokens.append(Token("VALUE", float(text), lineno))
            return

        # Integer
        m = _RE_INT.fullmatch(text)
        if m:
            self._tokens.append(Token("VALUE", int(text), lineno))
            return

        # Dollar-sign variable
        m = _RE_VAR.match(text)
        if m and m.end() == len(text):
            self._tokens.append(Token("VALUE", text, lineno))
            return

        # Keyword used as a bare value (e.g. `align: center`)
        lower = text.lower()
        if lower in ALL_KEYWORDS:
            self._tokens.append(Token("VALUE", lower, lineno))
            return

        # Bare identifier / anything else
        self._tokens.append(Token("VALUE", text, lineno))


# ── convenience function ──────────────────────────────────────────────────────

def lex(source: str) -> List[Token]:
    """Lex a NanoCode source string and return the token list."""
    return Lexer(source).tokenise()
