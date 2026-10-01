#!/usr/bin/env python3
"""Commit and push approved context documents after Claude edits them."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SYNCED_DOCUMENTS = {
    "DESIGN.md": "design",
    "HANDOVER.md": "handover",
    "meta/ongoing-discussions.md": "ongoing discussions",
}


class SyncError(RuntimeError):
    """A context change could not be synchronized safely."""


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
        repo_root = repository_root()
        relative_path = edited_context_path(hook_input, repo_root)
        if relative_path is None or not has_changes(repo_root, relative_path):
            print(json.dumps({"suppressOutput": True}))
            return

        synchronize(repo_root, relative_path)
        print(json.dumps({"suppressOutput": True}))
    except (json.JSONDecodeError, OSError, SyncError) as error:
        report_failure(str(error))


def repository_root() -> Path:
    result = run_git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()).resolve()


def edited_context_path(hook_input: dict[str, object], repo_root: Path) -> str | None:
    tool_input = hook_input.get("tool_input")
    if not isinstance(tool_input, dict):
        return None

    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str):
        return None

    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate

    try:
        relative_path = candidate.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return None

    return relative_path if relative_path in SYNCED_DOCUMENTS else None


def has_changes(repo_root: Path, relative_path: str) -> bool:
    ensure_tracked(repo_root, relative_path)
    result = run_git(repo_root, "status", "--porcelain", "--", relative_path)
    return bool(result.stdout.strip())


def synchronize(repo_root: Path, relative_path: str) -> None:
    ensure_safe_repository_state(repo_root)
    label = SYNCED_DOCUMENTS[relative_path]
    run_git(
        repo_root,
        "commit",
        "--only",
        "-m",
        f"chore(context): sync {label}",
        "--",
        relative_path,
    )
    run_git(repo_root, "push")


def ensure_tracked(repo_root: Path, relative_path: str) -> None:
    run_git(repo_root, "ls-files", "--error-unmatch", "--", relative_path)


def ensure_safe_repository_state(repo_root: Path) -> None:
    branch = run_git(repo_root, "branch", "--show-current").stdout.strip()
    if not branch:
        raise SyncError("automatic context sync is disabled on a detached HEAD")

    conflicts = run_git(
        repo_root,
        "diff",
        "--name-only",
        "--diff-filter=U",
        allow_failure=True,
    ).stdout.strip()
    if conflicts:
        raise SyncError("automatic context sync is disabled while merge conflicts exist")

    run_git(repo_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")


def run_git(
    repo_root: Path,
    *arguments: str,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0 and not allow_failure:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise SyncError(f"`git {' '.join(arguments)}` failed: {detail}")
    return result


def report_failure(message: str) -> None:
    guidance = (
        "Automatic context synchronization failed. The local document was preserved. "
        f"Resolve the issue and commit/push it manually. Details: {message}"
    )
    print(
        json.dumps(
            {
                "systemMessage": guidance,
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": guidance,
                },
            }
        )
    )


if __name__ == "__main__":
    main()
