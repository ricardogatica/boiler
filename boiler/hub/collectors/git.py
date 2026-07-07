"""Estado git de un proyecto: rama, sin commitear, ahead/behind, último commit, diff."""
import subprocess
from typing import Dict, List, Optional


def _git(path: str, *args: str, timeout: int = 5) -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "-C", path] + list(args),
            capture_output=True, text=True, timeout=timeout,
        )
        if out.returncode != 0:
            return None
        return out.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return None


def commit_base(remote: Optional[str]) -> Optional[str]:
    """URL web base para enlazar commits según el host del remoto.

    git@bitbucket.org:org/repo.git  → https://bitbucket.org/org/repo/commits/
    https://github.com/org/repo.git → https://github.com/org/repo/commit/
    """
    if not remote:
        return None
    url = remote.strip()
    if url.startswith("git@"):
        # git@host:org/repo(.git) → https://host/org/repo
        host_path = url[len("git@"):].replace(":", "/", 1)
        url = "https://" + host_path
    if url.endswith(".git"):
        url = url[:-4]
    if not url.startswith("http"):
        return None
    if "bitbucket.org" in url:
        return url + "/commits/"
    if "github.com" in url:
        return url + "/commit/"
    if "gitlab" in url:
        return url + "/-/commit/"
    return None


def collect(path: str) -> Dict:
    inside = _git(path, "rev-parse", "--is-inside-work-tree")
    if inside != "true":
        return {"is_repo": False}

    # El repo debe ser DEL proyecto: si el toplevel está más arriba (repo padre
    # o del workspace), el proyecto no tiene git propio.
    import os
    toplevel = _git(path, "rev-parse", "--show-toplevel")
    if not toplevel or os.path.realpath(toplevel) != os.path.realpath(path):
        return {"is_repo": False, "parent_repo": toplevel}

    branch = _git(path, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    porcelain = _git(path, "status", "--porcelain") or ""
    dirty_files = [l for l in porcelain.splitlines() if l.strip()]

    ahead = behind = None
    lr = _git(path, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    if lr:
        parts = lr.split()
        if len(parts) == 2:
            behind, ahead = int(parts[0]), int(parts[1])

    last = _git(path, "log", "-1", "--format=%h|%ct|%cr|%s")
    last_commit = None
    if last and "|" in last:
        h, ts, when, subject = last.split("|", 3)
        last_commit = {"hash": h, "ts": int(ts), "when": when, "subject": subject}

    shortstat = _git(path, "diff", "--shortstat") or ""

    remote = _git(path, "remote", "get-url", "origin")

    return {
        "is_repo": True,
        "branch": branch,
        "dirty": len(dirty_files),
        "dirty_files": dirty_files[:50],
        "ahead": ahead,
        "behind": behind,
        "has_upstream": lr is not None,
        "last_commit": last_commit,
        "diff_shortstat": shortstat,
        "remote": remote,
        "commit_base": commit_base(remote),
    }


def recent_log(path: str, n: int = 10) -> List[Dict]:
    out = _git(path, "log", "-%d" % n, "--format=%h|%cr|%an|%s")
    commits = []
    for line in (out or "").splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({"hash": parts[0], "when": parts[1], "author": parts[2], "subject": parts[3]})
    return commits


def diff_stat(path: str) -> str:
    return _git(path, "diff", "--stat", timeout=10) or ""
