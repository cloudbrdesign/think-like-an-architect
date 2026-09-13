#!/usr/bin/env python3
"""Think Like an Architect — repository boundary check (Python standard library only).

Usage:  python3 tools/boundary_check.py [--config .tla/boundary.json] [--root .]
Exit:   0 = no violations · 1 = violations found · 2 = configuration or usage error

mode "education"  (free education repository): refuses commercial markers, the commercial canary pattern, commercial
                  paths, references to the commercial repository, submodules, workflows that check out other
                  repositories or use secrets other than GITHUB_TOKEN, unknown top-level entries, local filesystem
                  paths, obvious secrets and broken relative Markdown links.
mode "commercial" (private repository): requires the commercial marker header and a valid canary, and refuses
                  automation that references the education repository, local filesystem paths and obvious secrets.

Sensitive marker strings are assembled at runtime so this file never contains them literally and can scan itself.
"""
import argparse
import json
import os
import re
import subprocess
import sys

MARKER = "TLA-" + "COMMERCIAL"
SPDX_MARKER = "LicenseRef-" + "TLA-Commercial"
CANARY_RE = re.compile("tla-canary-" + "[0-9a-f]{32}")
EDU_NAME = "think-like-an-" + "architect"
PROD_NAME = EDU_NAME + "-production"
EDU_REF_RE = re.compile(re.escape(EDU_NAME) + "(?!-production)")
LOCAL_PATH_RE = re.compile(r"(/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\|/private/(?:var|tmp)/)")
SECRET_RES = (
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
)
WORKFLOW_REPO_RE = re.compile(r"^\s*repository\s*:", re.M)
WORKFLOW_SECRET_RE = re.compile(r"secrets\.(?!GITHUB_TOKEN\b)[A-Za-z_][A-Za-z0-9_]*")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def list_files(root):
    """Tracked files when root is a Git work tree; otherwise every file below root (used by fixture tests)."""
    if os.path.isdir(os.path.join(root, ".git")):
        try:
            out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True).stdout
            return sorted(f for f in out.decode("utf-8").split("\0") if f)
        except (OSError, subprocess.CalledProcessError):
            pass
    found = []
    for directory, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            found.append(os.path.relpath(os.path.join(directory, name), root).replace(os.sep, "/"))
    return sorted(found)


def read_text(path):
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def _under(path, prefixes):
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in prefixes)


def scan(root, cfg):
    mode = cfg.get("mode")
    if mode not in ("education", "commercial"):
        raise ValueError("config 'mode' must be 'education' or 'commercial'")
    violations = []
    files = list_files(root)
    fileset = set(files)

    for required in cfg.get("required_files", []):
        if required not in fileset:
            violations.append(f"required file missing: {required}")

    for pattern in cfg.get("forbidden_path_patterns", []):
        rx = re.compile(pattern)
        violations += [f"forbidden path: {f}" for f in files if rx.search(f)]

    if mode == "education":
        allowed = set(cfg.get("allowed_top_level", []))
        allowed_patterns = [re.compile(p) for p in cfg.get("allowed_top_level_patterns", [])]
        for top in sorted({f.split("/")[0] for f in files}):
            if top not in allowed and not any(p.search(top) for p in allowed_patterns):
                violations.append(f"top-level entry not allowlisted: {top}")

    for rel in files:
        text = read_text(os.path.join(root, rel))
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if LOCAL_PATH_RE.search(line):
                violations.append(f"{rel}:{number}: local filesystem path")
            for name, rx in SECRET_RES:
                if rx.search(line):
                    violations.append(f"{rel}:{number}: possible secret ({name})")

        if mode == "education":
            if MARKER in text or SPDX_MARKER in text:
                violations.append(f"{rel}: commercial marker present")
            if CANARY_RE.search(text):
                violations.append(f"{rel}: commercial canary token present")
            if PROD_NAME in text:
                violations.append(f"{rel}: reference to the commercial repository")
            if rel.startswith(".github/workflows/"):
                if WORKFLOW_REPO_RE.search(text):
                    violations.append(f"{rel}: workflow checks out another repository")
                for match in WORKFLOW_SECRET_RE.finditer(text):
                    violations.append(f"{rel}: workflow uses {match.group(0)}")
        else:
            if _under(rel, cfg.get("marker_required", [])) and MARKER not in "\n".join(text.splitlines()[:5]):
                violations.append(f"{rel}: commercial marker header missing")
            if _under(rel, cfg.get("automation_paths", [])) and EDU_REF_RE.search(text):
                violations.append(f"{rel}: automation references the education repository")

        if rel.endswith(".md"):
            for target in LINK_RE.findall(text):
                if re.match(r"^(?:https?:|mailto:|#)", target):
                    continue
                path = target.split("#", 1)[0]
                if not path:
                    continue
                resolved = os.path.normpath(os.path.join(os.path.dirname(rel), path)).replace(os.sep, "/")
                if resolved not in fileset and not any(f.startswith(resolved.rstrip("/") + "/") for f in files):
                    violations.append(f"{rel}: broken relative link -> {target}")

    if mode == "commercial":
        canary = cfg.get("canary_file", ".tla-commercial-canary")
        content = read_text(os.path.join(root, canary)) if canary in fileset else None
        if not content or not CANARY_RE.search(content):
            violations.append(f"canary missing or malformed: {canary}")

    return violations


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=".tla/boundary.json")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    try:
        with open(os.path.join(args.root, args.config), encoding="utf-8") as handle:
            cfg = json.load(handle)
        violations = scan(args.root, cfg)
    except (OSError, ValueError) as error:
        print(f"CONFIGURATION ERROR: {error}")
        return 2
    for violation in violations:
        print(f"VIOLATION  {violation}")
    print(f"boundary check ({cfg['mode']}): {'PASS' if not violations else 'FAIL'} — {len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
