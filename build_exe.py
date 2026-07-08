"""Build DocuFind Local Windows executable with PyInstaller."""

from __future__ import annotations

import subprocess
import sys
import sysconfig
from pathlib import Path


def main() -> int:
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        print("PyInstaller/PySide6 build requires regular Python, not free-threaded Python.", file=sys.stderr)
        return 2

    spec_path = Path(__file__).resolve().parent / "DocuFindLocal.spec"
    command = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec_path)]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
