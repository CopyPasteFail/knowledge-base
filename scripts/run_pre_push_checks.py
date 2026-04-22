from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def run_check(command: list[str]) -> None:
    printable = " ".join(command)
    print(f"$ {printable}", flush=True)
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def main() -> int:
    run_check([sys.executable, "tools/process_html.py"])
    run_check(["git", "diff", "--exit-code", "--", "docs", "assets"])
    run_check([sys.executable, "-m", "ruff", "check", "tools"])
    run_check([sys.executable, "-m", "compileall", "-q", "tools"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
