"""
nano — the Nano-Stack command-line interface.

Commands:
  nano new <AppName>   Create a new project folder with starter files
  nano check           Validate app.nano without building
  nano build           Compile and bundle a signed APK
  nano run             Install and launch the APK on a connected device
  nano clean           Delete the build/ folder
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import click
import yaml

# ── path resolution ──────────────────────────────────────────────────────────

# Allow running as `python nano_cli/nano.py` from the repo root
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from nano_compiler.lexer import lex, LexerError
from nano_compiler.parser import parse, ParseError
from nano_compiler.validator import validate
from nano_compiler.emitter import emit as emit_json

_GREEN = "\033[92m"
_RED   = "\033[91m"
_RESET = "\033[0m"

_RUNNER_APK    = _REPO_ROOT / "bin" / "runner.apk"
_STARTER_NANO  = _REPO_ROOT / "templates" / "starter.nano"

# ── starter templates ─────────────────────────────────────────────────────────

def _starter_nano(app_name: str) -> str:
    """Return the starter app.nano content, reading from the template file."""
    try:
        template = _STARTER_NANO.read_text(encoding="utf-8")
        return template.replace("{app_name}", app_name)
    except OSError:
        # Inline fallback if the package was installed without templates/
        return (
            f"app:\n  name: {app_name}\n  version: 1.0\n\n"
            f"screen: HomeScreen\n  background: \"#FFFFFF\"\n\n"
            f"  text:\n    value: \"Hello from {app_name}\"\n"
            f"    size: 26\n    bold: true\n    align: center\n    color: \"#111111\"\n\n"
            f"  button:\n    label: \"Get Started\"\n    color: \"#4A90E2\"\n"
            f"    on_click:\n      - show_toast: \"Welcome!\"\n"
        )


def _starter_config(app_name: str) -> dict:
    return {
        "app_name": app_name,
        "package_id": f"com.yourname.{app_name.lower()}",
        "version": "1.0",
        "icon": "assets/icon.png",
        "permissions": [],
    }


# ── CLI group ──────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """Nano-Stack — build Android apps without Java, Gradle or Android Studio."""
    pass


# ── nano new ──────────────────────────────────────────────────────────────────

@cli.command("new")
@click.argument("app_name")
def cmd_new(app_name: str):
    """Create a new Nano-Stack project."""
    project_dir = Path(app_name)

    if project_dir.exists():
        click.echo(
            f"{_RED}✗{_RESET} Directory '{app_name}' already exists.", err=True
        )
        sys.exit(1)

    project_dir.mkdir()
    (project_dir / "assets").mkdir()

    # app.nano
    (project_dir / "app.nano").write_text(
        _starter_nano(app_name), encoding="utf-8"
    )

    # nano.config
    (project_dir / "nano.config").write_text(
        yaml.dump(_starter_config(app_name), default_flow_style=False),
        encoding="utf-8",
    )

    click.echo(
        f"{_GREEN}✓{_RESET} Created project {app_name} — "
        f"open app.nano to start building"
    )


# ── nano check ────────────────────────────────────────────────────────────────

@cli.command("check")
def cmd_check():
    """Validate app.nano without building."""
    source_path = Path("app.nano")
    config_path = Path("nano.config")

    if not source_path.exists():
        click.echo(f"{_RED}✗{_RESET} app.nano not found in current directory.", err=True)
        sys.exit(1)

    config = _load_config(config_path)
    source = source_path.read_text(encoding="utf-8")

    try:
        tokens = lex(source)
    except LexerError as exc:
        click.echo(f"{_RED}✗{_RESET} Lexer error on line {exc.line}: {exc}", err=True)
        sys.exit(1)

    try:
        ast = parse(tokens)
    except ParseError as exc:
        click.echo(f"{_RED}✗{_RESET} Parse error on line {exc.line}: {exc}", err=True)
        sys.exit(1)

    errors = validate(ast)
    if errors:
        for err in errors:
            line_info = f"line {err['line']}: " if err.get("line") else ""
            click.echo(f"{_RED}✗{_RESET} Error on {line_info}{err['message']}", err=True)
        click.echo(
            f"\n{_RED}Check failed with {len(errors)} error(s).{_RESET}", err=True
        )
        sys.exit(1)

    screens = ast.get("screens", [])
    component_count = sum(len(s.get("components", [])) for s in screens)
    click.echo(f"{_GREEN}✓{_RESET} Lexed {len(tokens)} tokens")
    click.echo(
        f"{_GREEN}✓{_RESET} Parsed {len(screens)} screen(s), "
        f"{component_count} component(s)"
    )
    click.echo(f"{_GREEN}✓{_RESET} Validation passed — no errors found.")


# ── nano build ────────────────────────────────────────────────────────────────

@cli.command("build")
def cmd_build():
    """Compile app.nano and bundle a signed APK."""
    source_path = Path("app.nano")
    config_path = Path("nano.config")

    if not source_path.exists():
        click.echo(f"{_RED}✗{_RESET} app.nano not found.", err=True)
        sys.exit(1)

    config = _load_config(config_path)
    app_name    = config.get("app_name", "MyApp")
    package_id  = config.get("package_id", f"com.yourname.{app_name.lower()}")
    version     = str(config.get("version", "1.0"))

    source = source_path.read_text(encoding="utf-8")

    # ── Transpile ──────────────────────────────────────────────────────────
    click.echo("Compiling app.nano …")
    try:
        tokens = lex(source)
        ast    = parse(tokens)
    except (LexerError, ParseError) as exc:
        click.echo(f"{_RED}✗{_RESET} {exc}", err=True)
        sys.exit(1)

    errors = validate(ast)
    if errors:
        for err in errors:
            click.echo(f"{_RED}✗{_RESET} {err['message']}", err=True)
        sys.exit(1)

    build_dir = Path("build")
    build_dir.mkdir(exist_ok=True)
    logic_json_path = str(build_dir / "logic.json")
    emit_json(ast, logic_json_path, dev=False)

    screens = ast.get("screens", [])
    components = sum(len(s.get("components", [])) for s in screens)
    click.echo(
        f"{_GREEN}✓{_RESET} Compiled {len(screens)} screen(s), "
        f"{components} component(s) → logic.json"
    )

    # ── Bundle ─────────────────────────────────────────────────────────────
    if not _RUNNER_APK.exists():
        click.echo(
            f"\n{_RED}✗{_RESET} runner.apk not found at {_RUNNER_APK}\n"
            "  The Universal Runner APK is a pre-built binary that must be\n"
            "  present in the nanostack/bin/ directory.\n"
            "  Download it from: https://github.com/yourname/nanostack/releases",
            err=True,
        )
        click.echo(
            f"\n{_GREEN}✓{_RESET} logic.json generated successfully at {logic_json_path}\n"
            "  (APK bundling skipped — runner.apk missing)"
        )
        return

    try:
        from nano_bundler.bundler import bundle, BundlerError
        signed_apk = bundle(
            runner_apk_path=str(_RUNNER_APK),
            logic_json_path=logic_json_path,
            package_id=package_id,
            app_name=app_name,
            version_name=version,
            output_dir=str(build_dir),
        )
    except Exception as exc:
        click.echo(f"{_RED}✗{_RESET} Build failed: {exc}", err=True)
        sys.exit(1)


# ── nano run ──────────────────────────────────────────────────────────────────

@cli.command("run")
def cmd_run():
    """Install and launch the APK on a connected Android device."""
    config_path = Path("nano.config")
    config      = _load_config(config_path)
    app_name    = config.get("app_name", "MyApp")
    package_id  = config.get("package_id", f"com.yourname.{app_name.lower()}")

    safe_name = "".join(c if c.isalnum() else "_" for c in app_name)
    apk_path  = Path("build") / f"{safe_name}.apk"

    if not apk_path.exists():
        click.echo(
            f"{_RED}✗{_RESET} APK not found at {apk_path}. "
            "Run 'nano build' first.",
            err=True,
        )
        sys.exit(1)

    # Detect device
    try:
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=10
        )
    except FileNotFoundError:
        click.echo(
            f"{_RED}✗{_RESET} adb not found. "
            "Install Android Platform Tools and add adb to your PATH.",
            err=True,
        )
        sys.exit(1)

    lines = [l.strip() for l in result.stdout.splitlines()
             if l.strip() and "List of devices" not in l]
    devices = [l for l in lines if "\tdevice" in l]

    if not devices:
        click.echo(
            f"{_RED}✗{_RESET} No Android device detected.\n"
            "  1. Connect your device via USB\n"
            "  2. Enable Developer Options → USB Debugging\n"
            "  3. Run 'adb devices' to confirm it appears",
            err=True,
        )
        sys.exit(1)

    device_serial = devices[0].split("\t")[0]
    click.echo(f"Device found: {device_serial}")

    # Install APK
    click.echo(f"Installing {apk_path} …")
    install = subprocess.run(
        ["adb", "-s", device_serial, "install", "-r", str(apk_path)],
        capture_output=True, text=True,
    )
    if install.returncode != 0:
        click.echo(f"{_RED}✗{_RESET} Install failed:\n{install.stderr}", err=True)
        sys.exit(1)

    click.echo(f"{_GREEN}✓{_RESET} Installed successfully")

    # Launch app
    launch = subprocess.run(
        ["adb", "-s", device_serial, "shell", "monkey",
         "-p", package_id, "1"],
        capture_output=True, text=True,
    )
    if launch.returncode != 0:
        click.echo(
            f"{_RED}✗{_RESET} Could not launch app:\n{launch.stderr}", err=True
        )
        sys.exit(1)

    click.echo(f"{_GREEN}✓{_RESET} Launched {app_name} on {device_serial}")


# ── nano clean ────────────────────────────────────────────────────────────────

@cli.command("clean")
def cmd_clean():
    """Delete the build/ folder."""
    import shutil
    build_dir = Path("build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
        click.echo(f"{_GREEN}✓{_RESET} Build folder cleaned")
    else:
        click.echo("Nothing to clean (build/ does not exist)")


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    try:
        with open(config_path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
