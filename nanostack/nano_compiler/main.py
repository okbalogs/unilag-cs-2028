"""
NanoCode Compiler — main entry point.

Usage:
  python main.py app.nano
  python main.py app.nano --output build/logic.json
  python main.py app.nano --dev
  python main.py app.nano --check-only
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running as `python nano_compiler/main.py` from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nano_compiler.lexer import lex, LexerError
from nano_compiler.parser import parse, ParseError
from nano_compiler.validator import validate
from nano_compiler.emitter import emit

# ANSI colour codes (degrade gracefully on Windows without colorama)
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"


def _ok(msg: str) -> None:
    print(f"{_GREEN}✓{_RESET} {msg}")


def _fail(msg: str) -> None:
    print(f"{_RED}✗{_RESET} {msg}", file=sys.stderr)


def _count_components(screens: list) -> int:
    total = 0
    for screen in screens:
        total += len(screen.get("components", []))
    return total


def compile_file(
    source_path: str,
    output_path: str = "logic.json",
    dev: bool = False,
    check_only: bool = False,
) -> bool:
    """
    Full compilation pipeline.
    Returns True on success, False on any error.
    """
    # 1. Read source
    try:
        with open(source_path, "r", encoding="utf-8") as fh:
            source = fh.read()
    except FileNotFoundError:
        _fail(f"File not found: {source_path}")
        return False
    except OSError as exc:
        _fail(f"Cannot read '{source_path}': {exc}")
        return False

    # 2. Lex
    try:
        tokens = lex(source)
    except LexerError as exc:
        _fail(f"Lexer error on line {exc.line}: {exc}")
        return False

    token_count = len(tokens)
    _ok(f"Lexed {token_count} tokens")

    # 3. Parse
    try:
        ast = parse(tokens)
    except ParseError as exc:
        _fail(f"Parse error on line {exc.line}: {exc}")
        return False

    screens = ast.get("screens", [])
    scripts = ast.get("scripts", [])
    component_count = _count_components(screens)
    _ok(
        f"Parsed {len(screens)} screen{'s' if len(screens) != 1 else ''}, "
        f"{component_count} component{'s' if component_count != 1 else ''}"
    )

    # 4. Validate
    errors = validate(ast)
    if errors:
        for err in errors:
            line_info = f"line {err['line']}: " if err.get("line") else ""
            _fail(f"Error on {line_info}{err['message']}")
        print(
            f"\n{_RED}Build failed with {len(errors)} "
            f"error{'s' if len(errors) != 1 else ''}.{_RESET}",
            file=sys.stderr,
        )
        return False

    _ok("Validation passed")

    if check_only:
        print("Check complete — no errors found.")
        return True

    # 5. Emit
    try:
        byte_count = emit(ast, output_path, dev=dev)
    except OSError as exc:
        _fail(f"Cannot write '{output_path}': {exc}")
        return False

    size_str = _human_size(byte_count)
    _ok(f"Emitted {output_path} ({size_str})")

    return True


def _human_size(byte_count: int) -> str:
    if byte_count < 1024:
        return f"{byte_count} B"
    kb = byte_count / 1024
    return f"{kb:.1f} KB"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nano-compile",
        description="NanoCode → logic.json compiler",
    )
    parser.add_argument("source", help="Path to the .nano source file")
    parser.add_argument(
        "--output", "-o",
        default="logic.json",
        help="Output path for logic.json (default: logic.json)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Emit pretty-printed JSON (development mode)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Lex, parse, and validate only — do not write output",
    )

    args = parser.parse_args()

    success = compile_file(
        source_path=args.source,
        output_path=args.output,
        dev=args.dev,
        check_only=args.check_only,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
