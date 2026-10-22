"""Raise the plugin's patch version by one (0.1.0 -> 0.1.1, ... 0.1.99 -> 0.1.100) and stage the manifest.

Run by the pre-commit hook in githooks/ (enable it once per clone: `git config core.hooksPath githooks`), so each
commit carries a new version and `claude plugin update` sees the change. Set CLAUDE_BOARD_NO_BUMP=1 to skip
it for one commit (e.g. an amend that already bumped). Standard library only.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

MANIFEST: Path = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"
VERSION: re.Pattern[str] = re.compile(r'("version"\s*:\s*")(\d+)\.(\d+)\.(\d+)(")')


def bump(manifest_text: str) -> tuple[str, str]:
    """Return (the manifest text with its patch version raised by one, the new version); the rest is kept as is.

    Raises:
        ValueError: the manifest has no "version": "X.Y.Z".
    """
    match: re.Match[str] | None = VERSION.search(manifest_text)
    if match is None:
        raise ValueError('plugin.json has no "version": "X.Y.Z"')
    version: str = f"{match[2]}.{match[3]}.{int(match[4]) + 1}"
    return manifest_text[:match.start()] + match[1] + version + match[5] + manifest_text[match.end():], version


def main() -> int:
    """Bump and stage the manifest; returns the exit code (non-zero stops the commit)."""
    if os.environ.get("CLAUDE_BOARD_NO_BUMP"):
        return 0
    text: str = MANIFEST.read_text(encoding="utf-8")
    try:
        bumped: str
        version: str
        bumped, version = bump(text)
    except ValueError as error:
        print(f"bump_version: {error}", file=sys.stderr)
        return 1
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as manifest:
        manifest.write(bumped)
    subprocess.run(["git", "add", str(MANIFEST)], check=True)
    print(f"bump_version: version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
