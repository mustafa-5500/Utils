"""
Dev Log Generator for the Building-Lore Linking Plugin project.

If today's dev log does not exist yet, this script creates it from
`dev-log-template.md`, auto-filling the date, the link to the previous
entry, and the developer's name (from git). Placeholders that must be
written by hand (Comments/Goals/Actions) are replaced with short tips to
help developers who are not used to keeping a dev log.

If today's dev log already exists, the script just opens it, adding the
current developer to the Developer list first if they are not on it yet.

Can be run as `dev-log` from the repository root or any subfolder once
Utils/dev-log-generator is added to your PATH (dev-log.cmd for Windows,
dev-log for POSIX shells), or directly with `python generate_dev_log.py`.

Usage:
    dev-log [--date YYYY-MM-DD] [--developer "Name"] [--no-open]

Example:
    dev-log
    dev-log --date 2026-08-20
"""

import argparse
import getpass
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

DEV_LOG_DIR_NAME = Path("Development-Notes") / "Development-Log"
TEMPLATE_PATH = Path(__file__).resolve().parent / "dev-log-template.md"


def find_dev_log_root(start: Path) -> Path:
    """Walk up from `start` to find the repo's Development-Notes/Development-Log folder."""
    for candidate in (start, *start.parents):
        dev_log_dir = candidate / DEV_LOG_DIR_NAME
        if dev_log_dir.is_dir():
            return dev_log_dir
    raise SystemExit(
        f"Could not find '{DEV_LOG_DIR_NAME}' above {start}. "
        "Run dev-log from within the plugin repository."
    )


COMMENTS_TIP = (
    "_New to dev logs? Use this section to explain your thought process - "
    "decisions made, tradeoffs, or context that isn't obvious from the code. "
    "Future developers (including future you) will thank you._"
)
GOALS_TIP = (
    "_Longer-term objective(s) this work is building toward. These can span "
    "multiple days - leave them in place until complete._"
)
ACTIONS_TIP = (
    "_Concrete step(s) you're taking today toward the goal(s) above. Add one "
    "bullet per action, and cross items out with `~~like this~~` once done._"
)


def get_developer_name(repo_dir: Path) -> str:
    """Resolve the current developer's name from git, falling back to the OS user."""
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        name = result.stdout.strip()
        if name:
            return name
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return getpass.getuser()


def find_previous_entry(dev_log_root: Path, target_date: date):
    """Find the most recent existing dev-log.md dated before target_date."""
    candidates = []
    for path in dev_log_root.glob("*/*/*/dev-log.md"):
        year, month, day, _ = path.relative_to(dev_log_root).parts
        try:
            entry_date = date(int(year), int(month), int(day))
        except ValueError:
            continue
        if entry_date < target_date:
            candidates.append((entry_date, path))
    if not candidates:
        return None
    return max(candidates, key=lambda c: c[0])


def build_log_content(dev_log_root: Path, target_date: date, developer: str) -> str:
    """Fill in dev-log-template.md for a new entry."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")

    previous = find_previous_entry(dev_log_root, target_date)
    day_dir = day_dir_for(dev_log_root, target_date)
    if previous:
        prev_date, prev_path = previous
        rel_path = os.path.relpath(prev_path, day_dir).replace(os.sep, "/")
        previous_entry_text = f"[{prev_date.isoformat()}]({rel_path})"
    else:
        previous_entry_text = "None (this is the first entry)"

    replacements = {
        "{date the log corresponds to}": target_date.isoformat(),
        "{The date of the previous dev-log, with the relative path to that dev-log from this file}": previous_entry_text,
        "{name of the developer corresponding to this log, get from git information, add multiple developers if multiple run the dev-log script.}": developer,
        "{add any comments to explain development thoughts/actions/plans}": COMMENTS_TIP,
        "{add any overall goals to be completed}": GOALS_TIP,
        "{add any actions being done}": ACTIONS_TIP,
    }
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def day_dir_for(dev_log_root: Path, target_date: date) -> Path:
    return dev_log_root / f"{target_date.year:04d}" / f"{target_date.month:02d}" / f"{target_date.day:02d}"


def ensure_developer_listed(content: str, developer: str) -> str:
    """Add developer to the Developer bullet list if they aren't already on it."""
    lines = content.splitlines(keepends=True)
    try:
        header_index = next(i for i, line in enumerate(lines) if line.strip() == "**Developer:**")
    except StopIteration:
        return content

    block_end = header_index + 1
    while block_end < len(lines) and lines[block_end].strip().startswith("- "):
        block_end += 1

    block = lines[header_index + 1:block_end]
    if any(developer.lower() in line.lower() for line in block):
        return content

    lines.insert(block_end, f"    - {developer}\n")
    return "".join(lines)


def open_in_editor(path: Path) -> None:
    try:
        subprocess.run(["code", "-r", str(path)], check=True)
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)])
    else:
        subprocess.run(["xdg-open", str(path)])


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or open today's dev log.")
    parser.add_argument("--date", help="Date for the log entry (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--developer", help="Developer name. Defaults to git config user.name.")
    parser.add_argument("--no-open", action="store_true", help="Don't open the log after creating/updating it.")
    args = parser.parse_args()

    dev_log_root = find_dev_log_root(Path.cwd())
    repo_root = dev_log_root.parent.parent
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    developer = args.developer or get_developer_name(repo_root)
    log_dir = day_dir_for(dev_log_root, target_date)
    log_path = log_dir / "dev-log.md"

    if log_path.exists():
        content = log_path.read_text(encoding="utf-8")
        updated = ensure_developer_listed(content, developer)
        if updated != content:
            log_path.write_text(updated, encoding="utf-8")
            print(f"Added {developer} to the Developer list in {log_path}")
        else:
            print(f"Dev log already exists: {log_path}")
    else:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path.write_text(build_log_content(dev_log_root, target_date, developer), encoding="utf-8")
        print(f"Created dev log: {log_path}")

    if not args.no_open:
        open_in_editor(log_path)


if __name__ == "__main__":
    main()
