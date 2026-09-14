#!/usr/bin/env python3
"""Public commit metadata check (Python standard library only).

Keeps unexpected provenance metadata out of the public history:
  identity  commits are authored and committed by the publisher identity in the configuration; its commit email is the
            publisher's GitHub noreply address. A platform committer (for example GitHub) is accepted on merge commits.
  trailers  no forbidden trailers (co-author, generated-with, generated-by, assisted-by, *-Session).
  lines     no attribution lines such as "Generated with …" and no co-author attribution in any form.
The same message rules apply to pull request titles and bodies passed through environment variables.

Usage:  python3 tools/commit_metadata_check.py [--config .tla/commit_metadata.json] [--repo .] [--range REVISIONS]
                                              [--pr-text-env NAME[,NAME…]]
Exit:   0 = no findings · 1 = findings · 2 = configuration or usage error
"""
import argparse
import json
import os
import re
import subprocess
import sys

ZERO_SHA = "0" * 40
TRAILER_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9-]*)\s*:\s*\S")


def load_config(path):
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    publisher = config.get("publisher", {})
    if config.get("schema") != "commit-metadata/1" or not publisher.get("name") or not publisher.get("github_login") \
            or not isinstance(publisher.get("github_user_id"), int):
        raise ValueError(f"invalid configuration: {path}")
    config["line_patterns"] = [re.compile(p) for p in config.get("forbidden_line_patterns", [])]
    return config


def publisher_email(config):
    publisher = config["publisher"]
    return f"{publisher['github_user_id']}+{publisher['github_login']}@users.noreply.github.com"


def message_findings(text, config):
    """Findings for one commit message, pull request title or pull request body."""
    findings = []
    keys = {key.lower() for key in config.get("forbidden_trailer_keys", [])}
    suffixes = tuple(suffix.lower() for suffix in config.get("forbidden_trailer_key_suffixes", []))
    for number, line in enumerate(text.splitlines(), 1):
        match = TRAILER_RE.match(line)
        if match and (match.group(1).lower() in keys or (suffixes and match.group(1).lower().endswith(suffixes))):
            findings.append(f"line {number}: forbidden trailer '{match.group(1)}'")
            continue
        if any(rx.search(line) for rx in config["line_patterns"]):
            findings.append(f"line {number}: forbidden attribution text")
    return findings


def identity_findings(role, name, email, is_merge, config):
    if name == config["publisher"]["name"] and email == publisher_email(config):
        return []
    if role == "committer" and is_merge and any(name == c["name"] and email == c["email"]
                                                for c in config.get("platform_merge_committers", [])):
        return []
    domain = email.rsplit("@", 1)[-1] if "@" in email else "no domain"
    detail = "name" if email == publisher_email(config) else f"email (@{domain})"
    return [f"unexpected {role} {detail}"]


def normalise_range(revisions):
    """A push that creates a branch reports an all-zero 'before' commit: check everything reachable instead."""
    if revisions.startswith(ZERO_SHA + ".."):
        return revisions[len(ZERO_SHA) + 2:]
    return revisions


def read_commits(repo, revisions):
    fmt = "%H%x1f%P%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%B%x1e"
    proc = subprocess.run(["git", "-C", repo, "log", f"--format={fmt}", normalise_range(revisions), "--"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "git log failed")
    commits = []
    for record in proc.stdout.split("\x1e"):
        record = record.lstrip("\n")
        if record:
            sha, parents, author_name, author_email, committer_name, committer_email, message = record.split("\x1f", 6)
            commits.append({"sha": sha, "is_merge": len(parents.split()) > 1, "author": (author_name, author_email),
                            "committer": (committer_name, committer_email), "message": message})
    return commits


def commit_findings(commit, config):
    findings = []
    for role in ("author", "committer"):
        findings += identity_findings(role, *commit[role], commit["is_merge"], config)
    findings += message_findings(commit["message"], config)
    return [f"{commit['sha'][:7]}: {finding}" for finding in findings]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Public commit metadata check")
    parser.add_argument("--config", default=".tla/commit_metadata.json")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--range", default="HEAD", help="git revision range, for example BASE..HEAD")
    parser.add_argument("--pr-text-env", default="", help="comma-separated environment variable names to check")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        commits = read_commits(args.repo, args.range)
    except (OSError, ValueError, json.JSONDecodeError, re.error) as error:
        print(f"commit metadata: ERROR — {error}")
        return 2
    findings = []
    for commit in commits:
        findings += commit_findings(commit, config)
    for name in filter(None, (n.strip() for n in args.pr_text_env.split(","))):
        findings += [f"pull request {name}: {f}" for f in message_findings(os.environ.get(name, ""), config)]
    for finding in findings:
        print(finding)
    verdict = "PASS" if not findings else f"FAIL — {len(findings)} finding(s)"
    print(f"commit metadata: {verdict} · {len(commits)} commit(s) checked")
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
