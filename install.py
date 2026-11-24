import json
import os
import platform
import subprocess
import sys
from pathlib import Path


def get_claude_config_path() -> Path:
    """Resolve Claude Desktop configuration file path across operating systems."""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            appdata = str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def main():
    project_root = Path(__file__).resolve().parent
    print("=" * 60)
    print("  TikTok Scraper MCP — 1-Click Automated Setup")
    print(f"  Target directory: {project_root}")
    print("=" * 60)

    # 1. Setup Virtual Environment
    venv_dir = project_root / "venv"
    if not venv_dir.exists():
        print("\n[1/4] Creating Python virtual environment (venv)...")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    else:
        print("\n[1/4] Existing virtual environment found.")

    # Determine venv python binary
    if platform.system() == "Windows":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if not venv_python.exists():
        print(f"ERROR: Virtual environment python binary not found at {venv_python}")
        sys.exit(1)

    # 2. Install Dependencies
    print("\n[2/4] Installing dependencies from requirements.txt...")
    req_file = project_root / "requirements.txt"
    subprocess.check_call([
        str(venv_python), "-m", "pip", "install", "-r", str(req_file), "--quiet"
    ])

    # 3. Install Playwright Headless Chromium Shell
    print("\n[3/4] Installing Playwright Chromium headless shell...")
    try:
        subprocess.check_call([
            str(venv_python), "-m", "playwright", "install", "chromium-headless-shell"
        ])
    except Exception as exc:
        print(f"Playwright shell install note: {exc}. Retrying with full chromium...")
        subprocess.check_call([
            str(venv_python), "-m", "playwright", "install", "chromium"
        ])

    # 4. Configure Claude Desktop & Claude Code MCP
    print("\n[4/4] Registering 'content-scrapper' MCP Server...")
    config_path = get_claude_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_data = {}
    if config_path.exists():
        try:
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            config_data = {}

    mcp_servers = config_data.setdefault("mcpServers", {})

    server_script = project_root / "server.py"
    # Clean up old key if present
    mcp_servers.pop("tiktok-scraper", None)
    mcp_servers["content-scrapper"] = {
        "command": str(venv_python),
        "args": [str(server_script)],
    }

    config_path.write_text(json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated Claude Desktop config: {config_path}")

    # Also register to Claude Code CLI if available
    try:
        subprocess.run(
            ["claude", "mcp", "add", "-s", "user", "content-scrapper", str(venv_python), str(server_script)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("Registered 'content-scrapper' to Claude Code user scope.")
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("  [SUCCESS] 'content-scrapper' MCP is successfully installed!")
    print(f"  Name:   content-scrapper")
    print(f"  Server: {server_script}")
    print(f"  Python: {venv_python}")
    print("  Action required: Restart Claude Desktop app to activate.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
