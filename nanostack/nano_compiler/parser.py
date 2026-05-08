"""
NanoCode Parser — converts a token list into an Abstract Syntax Tree (AST).

The AST is a plain Python dict/list structure mirroring the nested
structure of the .nano source file.  The emitter later serialises this
to logic.json.

Grammar (simplified):
  file       ::= app_block? (screen_block | script_block)*
  app_block  ::= 'app' ':' NEWLINE INDENT property* DEDENT
  screen     ::= 'screen' ':' NAME NEWLINE INDENT component* DEDENT
  component  ::= (text | input | button | list | image | link | script_ref)
  script     ::= 'script' ':' NAME NEWLINE INDENT 'steps' ':' NEWLINE INDENT step* DEDENT DEDENT
  step       ::= '-' action
  action     ::= navigate | call | store | show_toast | run_script | if_block | …
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .lexer import Token


class ParseError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(message)
        self.line = line


# ── Parser ────────────────────────────────────────────────────────────────────

class Parser:
    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._pos = 0

    # ── token stream helpers ──────────────────────────────────────────────────

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, ttype: str, tvalue: Any = None) -> Token:
        tok = self._peek()
        if tok.type != ttype:
            raise ParseError(
                f"Expected {ttype}{f'={tvalue!r}' if tvalue else ''}, "
                f"got {tok.type}={tok.value!r}",
                tok.line,
            )
        if tvalue is not None and tok.value != tvalue:
            raise ParseError(
                f"Expected {ttype}={tvalue!r}, got {tok.value!r}", tok.line
            )
        return self._advance()

    def _skip_newlines(self) -> None:
        while self._peek().type == "NEWLINE":
            self._advance()

    def _at_end(self) -> bool:
        return self._peek().type == "EOF"

    def _match(self, ttype: str, tvalue: Any = None) -> bool:
        tok = self._peek()
        if tok.type != ttype:
            return False
        if tvalue is not None and tok.value != tvalue:
            return False
        return True

    def _consume_if(self, ttype: str, tvalue: Any = None) -> Optional[Token]:
        if self._match(ttype, tvalue):
            return self._advance()
        return None

    # ── public ────────────────────────────────────────────────────────────────

    def parse(self) -> Dict:
        """Return the top-level AST dict."""
        ast: Dict[str, Any] = {
            "app": {},
            "screens": [],
            "scripts": [],
        }

        self._skip_newlines()

        while not self._at_end():
            self._skip_newlines()
            if self._at_end():
                break

            tok = self._peek()

            if tok.type in ("KEYWORD", "PROPERTY") and tok.value == "app":
                ast["app"] = self._parse_app()
            elif tok.type == "KEYWORD" and tok.value == "screen":
                ast["screens"].append(self._parse_screen())
            elif tok.type == "KEYWORD" and tok.value == "script":
                ast["scripts"].append(self._parse_script())
            else:
                self._advance()  # skip unexpected token

        return ast

    # ── app block ─────────────────────────────────────────────────────────────

    def _parse_app(self) -> Dict:
        self._expect("KEYWORD", "app")          # consume 'app'
        self._consume_if("NEWLINE")
        self._skip_newlines()

        app: Dict[str, Any] = {}

        if not self._match("INDENT"):
            return app
        self._advance()  # consume INDENT

        while not self._match("DEDENT") and not self._at_end():
            self._skip_newlines()
            if self._match("DEDENT") or self._at_end():
                break

            tok = self._peek()

            if tok.type == "PROPERTY" and tok.value == "permissions":
                self._advance()
                self._consume_if("NEWLINE")
                app["permissions"] = self._parse_list_block()
            elif tok.type in ("KEYWORD", "PROPERTY"):
                key = self._advance().value
                val = self._parse_value()
                app[key] = val
                self._consume_if("NEWLINE")
            else:
                self._advance()

        self._consume_if("DEDENT")
        return app

    # ── screen block ──────────────────────────────────────────────────────────

    def _parse_screen(self) -> Dict:
        self._expect("KEYWORD", "screen")
        name = self._expect("VALUE").value
        self._consume_if("NEWLINE")
        self._skip_newlines()

        screen: Dict[str, Any] = {
            "type": "screen",
            "name": name,
            "components": [],
        }

        if not self._match("INDENT"):
            return screen
        self._advance()

        while not self._match("DEDENT") and not self._at_end():
            self._skip_newlines()
            if self._match("DEDENT") or self._at_end():
                break

            tok = self._peek()

            if tok.type == "PROPERTY" and tok.value == "background":
                self._advance()
                screen["background"] = self._parse_value()
                self._consume_if("NEWLINE")
            elif tok.type == "KEYWORD" and tok.value == "script":
                # inline script inside screen
                script = self._parse_script()
                screen.setdefault("scripts", []).append(script)
            elif tok.type == "KEYWORD" and tok.value in (
                "text", "input", "button", "list", "image", "link", "service"
            ):
                screen["components"].append(self._parse_component())
            else:
                self._advance()

        self._consume_if("DEDENT")
        return screen

    # ── component dispatch ────────────────────────────────────────────────────

    def _parse_component(self) -> Dict:
        tok = self._peek()
        ctype = tok.value
        self._advance()
        self._consume_if("NEWLINE")
        self._skip_newlines()

        comp: Dict[str, Any] = {"type": ctype}

        if not self._match("INDENT"):
            return comp
        self._advance()

        while not self._match("DEDENT") and not self._at_end():
            self._skip_newlines()
            if self._match("DEDENT") or self._at_end():
                break

            tok = self._peek()

            if tok.type in ("KEYWORD", "PROPERTY"):
                key = tok.value
                self._advance()

                if key in ("on_click", "on_tap", "on_success", "on_fail",
                           "on_cancel", "on_connect", "on_device_found"):
                    self._consume_if("NEWLINE")
                    comp[key] = self._parse_action_list()

                elif key == "item_template":
                    self._consume_if("NEWLINE")
                    comp["item_template"] = self._parse_item_template()

                elif key == "steps":
                    self._consume_if("NEWLINE")
                    comp["steps"] = self._parse_action_list()

                elif key == "navigate":
                    val = self._parse_value()
                    comp[key] = val
                    self._consume_if("NEWLINE")

                else:
                    val = self._parse_value()
                    # normalise type → input_type to avoid shadowing component type
                    if key == "type" and ctype == "input":
                        comp["input_type"] = val
                    else:
                        comp[key] = val
                    self._consume_if("NEWLINE")
            else:
                self._advance()

        self._consume_if("DEDENT")
        return comp

    # ── script block ──────────────────────────────────────────────────────────

    def _parse_script(self) -> Dict:
        self._expect("KEYWORD", "script")
        name = self._expect("VALUE").value
        self._consume_if("NEWLINE")
        self._skip_newlines()

        script: Dict[str, Any] = {"type": "script", "name": name, "steps": []}

        if not self._match("INDENT"):
            return script
        self._advance()

        while not self._match("DEDENT") and not self._at_end():
            self._skip_newlines()
            if self._match("DEDENT") or self._at_end():
                break

            tok = self._peek()

            if tok.type == "PROPERTY" and tok.value == "steps":
                self._advance()
                self._consume_if("NEWLINE")
                script["steps"] = self._parse_action_list()
            else:
                self._advance()

        self._consume_if("DEDENT")
        return script

    # ── action list ───────────────────────────────────────────────────────────

    def _parse_action_list(self) -> List[Dict]:
        """Parse a YAML-style list of action steps (each begins with '- ')."""
        actions: List[Dict] = []

        self._skip_newlines()
        if not self._match("INDENT"):
            return actions
        self._advance()

        while not self._match("DEDENT") and not self._at_end():
            self._skip_newlines()
            if self._match("DEDENT") or self._at_end():
                break

            tok = self._peek()

            # Each action line was tokenised as:  PROPERTY/KEYWORD VALUE NEWLINE
            if tok.type in ("KEYWORD", "PROPERTY"):
                action_name = tok.value
                self._advance()

                if action_name == "if":
                    actions.append(self._parse_if_action())
                    continue

                # Peek at what follows
                val = None
                if not self._match("NEWLINE") and self._peek().type == "VALUE":
                    val = self._parse_value()

                action = self._build_action(action_name, val)

                # handle on_success / on_fail / on_cancel inline callbacks
                self._consume_if("NEWLINE")
                self._skip_newlines()
                inline = self._parse_inline_callbacks()
                action.update(inline)

                actions.append(action)

            elif tok.type == "VALUE":
                # bare value in list (uncommon)
                actions.append({"action": "raw", "value": tok.value})
                self._advance()
                self._consume_if("NEWLINE")
            else:
                self._advance()

        self._consume_if("DEDENT")
        return actions

    def _build_action(self, name: str, val: Any) -> Dict:
        """Turn an action keyword + value into a normalised action dict."""
        if name == "navigate":
            return {"action": "navigate", "target": val}
        if name == "show_toast":
            return {"action": "show_toast", "message": val}
        if name == "run_script":
            return {"action": "run_script", "script": val}
        if name == "store":
            # 'store: varname = value'  or  'store: varname'
            if isinstance(val, str) and "=" in val:
                parts = val.split("=", 1)
                return {"action": "store", "variable": parts[0].strip(), "value": parts[1].strip()}
            return {"action": "store", "variable": val}
        if name == "validate":
            fields = val if isinstance(val, list) else ([val] if val else [])
            return {"action": "validate", "fields": fields}
        if name == "call":
            return {"action": "call", "method": val}
        if name == "update":
            return {"action": "update", "target": val}
        if name == "set":
            return {"action": "set", "value": val}
        return {"action": name, "value": val}

    def _parse_inline_callbacks(self) -> Dict:
        """Parse optional on_success / on_fail / on_cancel blocks after an action."""
        callbacks: Dict[str, Any] = {}
        callback_keys = {"on_success", "on_fail", "on_cancel", "on_connect", "on_device_found"}

        while self._match("INDENT"):
            self._advance()
            self._skip_newlines()
            while not self._match("DEDENT") and not self._at_end():
                self._skip_newlines()
                if self._match("DEDENT") or self._at_end():
                    break
                tok = self._peek()
                if tok.type == "PROPERTY" and tok.value in callback_keys:
                    key = tok.value
                    self._advance()
                    self._consume_if("NEWLINE")
                    callbacks[key] = self._parse_action_list()
                else:
                    self._advance()
            self._consume_if("DEDENT")
            break
        return callbacks

    def _parse_if_action(self) -> Dict:
        """Parse if/then/else construct inside a steps list."""
        # condition value follows 'if' keyword
        condition = None
        if self._peek().type == "VALUE":
            condition = self._parse_value()
        self._consume_if("NEWLINE")
        self._skip_newlines()

        then_steps: List[Dict] = []
        else_steps: List[Dict] = []

        if self._match("INDENT"):
            self._advance()
            while not self._match("DEDENT") and not self._at_end():
                self._skip_newlines()
                if self._match("DEDENT") or self._at_end():
                    break
                tok = self._peek()
                if tok.type == "PROPERTY" and tok.value == "then":
                    self._advance()
                    self._consume_if("NEWLINE")
                    then_steps = self._parse_action_list()
                elif tok.type == "PROPERTY" and tok.value == "else":
                    self._advance()
                    self._consume_if("NEWLINE")
                    else_steps = self._parse_action_list()
                else:
                    self._advance()
            self._consume_if("DEDENT")

        node: Dict[str, Any] = {"action": "if", "condition": condition, "then": then_steps}
        if else_steps:
            node["else"] = else_steps
        return node

    # ── item_template block ───────────────────────────────────────────────────

    def _parse_item_template(self) -> Dict:
        template: Dict[str, Any] = {}
        self._skip_newlines()

        if not self._match("INDENT"):
            return template
        self._advance()

        while not self._match("DEDENT") and not self._at_end():
            self._skip_newlines()
            if self._match("DEDENT") or self._at_end():
                break
            tok = self._peek()
            if tok.type in ("KEYWORD", "PROPERTY"):
                key = tok.value
                self._advance()
                if key in ("on_tap", "on_click"):
                    self._consume_if("NEWLINE")
                    template[key] = self._parse_action_list()
                else:
                    val = self._parse_value()
                    template[key] = val
                    self._consume_if("NEWLINE")
            else:
                self._advance()

        self._consume_if("DEDENT")
        return template

    # ── list block (permissions etc.) ─────────────────────────────────────────

    def _parse_list_block(self) -> List[str]:
        items: List[str] = []
        self._skip_newlines()

        if not self._match("INDENT"):
            return items
        self._advance()

        while not self._match("DEDENT") and not self._at_end():
            self._skip_newlines()
            if self._match("DEDENT") or self._at_end():
                break
            tok = self._peek()
            if tok.type == "VALUE":
                items.append(str(tok.value))
                self._advance()
            self._consume_if("NEWLINE")

        self._consume_if("DEDENT")
        return items

    # ── value parsing ─────────────────────────────────────────────────────────

    def _parse_value(self) -> Any:
        tok = self._peek()
        if tok.type == "VALUE":
            self._advance()
            return tok.value
        # If the next token is a keyword being used as a value (e.g. align: center)
        if tok.type in ("KEYWORD", "PROPERTY"):
            self._advance()
            return tok.value
        return None


# ── convenience function ──────────────────────────────────────────────────────

def parse(tokens) -> Dict:
    """Parse a token list and return the AST dict."""
    return Parser(tokens).parse()
