#!/usr/bin/env python3
"""Prepare a tagged orphan tree and a report; push only when explicitly selected."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

from usdaeco_check.publication import inspect_tree, safe_name
from usdaeco_check.structure import PUBLIC_GITHUB_ORG


def git(*args, cwd=None, input=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="usdAeco", GIT_COMMITTER_NAME="usdAeco",
               GIT_AUTHOR_EMAIL="release@usdaeco.org", GIT_COMMITTER_EMAIL="release@usdaeco.org",
               GIT_AUTHOR_DATE="2000-01-01T00:00:00Z", GIT_COMMITTER_DATE="2000-01-01T00:00:00Z")
    result = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                             "-c", "init.templateDir=", *map(str, args)], cwd=cwd,
                            env=env, input=input, capture_output=True)
    if result.returncode:
        # Git diagnostics can contain source addresses, credentials or local paths.
        raise ValueError("git " + args[0] + " failed (exit " + str(result.returncode) + ")")
    return result.stdout


def excluded(name):
    parts = PurePosixPath(name).parts
    if any(p in {".git", ".work", "__pycache__", ".pytest_cache", ".venv"} or p.endswith(".egg-info") for p in parts):
        return True
    if len(parts) == 1 and (name in {"STEERING.md", "BLOCKED.md", "flake.lock"}):
        return True
    return parts[0] in {"out", "build", "result"} or parts[0].startswith("result-")


def prepare(source, tag, output, *, push=False, remote=None, patterns=()):
    try:
        for pattern in patterns:
            re.compile(pattern)
    except re.error:
        raise ValueError("invalid term pattern") from None
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", tag):
        raise ValueError("an exact version tag is required")
    if push and not remote:
        raise ValueError("--push requires an explicit --remote")
    if remote and not push:
        raise ValueError("--remote requires --push")
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("output must be a new directory")
    local = Path(source).expanduser()
    if local.exists():
        local = local.resolve()
        if output == local or local in output.parents:
            raise ValueError("output must be outside the source checkout")
        source = str(local)
    with tempfile.TemporaryDirectory(prefix="aeco-source-") as temporary:
        clone = Path(temporary) / "source"
        git("clone", "--quiet", "--no-checkout", "--no-local", "--depth", "1", "--branch", tag, "--", source, clone)
        revision = git("rev-parse", "--verify", "refs/tags/" + tag + "^{commit}", cwd=clone).decode().strip()
        tree = git("ls-tree", "-rz", "--full-tree", revision, cwd=clone).split(b"\0")
        metadata = json.loads(git("show", revision + ":library.json", cwd=clone))
        name = metadata.get("name", "")
        if metadata.get("kind") == "meta" or name == "usdaeco-meta":
            raise ValueError("private metadata repositories cannot be published")
        if metadata.get("version") != tag[1:]:
            raise ValueError("tag and library.json version differ")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", name) or safe_name(name, patterns) != name:
            raise ValueError("invalid public library name")
        output.mkdir(parents=True)
        destination = output / "tree"
        destination.mkdir()
        omitted, rejected = [], []
        for entry in tree:
            if not entry:
                continue
            attributes, raw_name = entry.split(b"\t", 1)
            mode, kind, oid = attributes.decode().split()
            relative = raw_name.decode("utf-8")
            parts = PurePosixPath(relative).parts
            if excluded(relative):
                omitted.append(safe_name(relative, patterns))
                continue
            if (mode not in {"100644", "100755", "120000"} or kind != "blob" or
                    any(p.casefold() in {"..", ".git"} for p in parts) or relative.startswith("/")):
                rejected.append({"path": safe_name(relative, patterns), "rule": "UnsupportedGitEntry"})
                continue
            file = destination / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            data = git("cat-file", "blob", oid, cwd=clone)
            if mode == "120000":
                file.symlink_to(data.decode("utf-8"))
            else:
                file.write_bytes(data)
                file.chmod(0o755 if mode == "100755" else 0o644)
        report = inspect_tree(destination, patterns=patterns)
        repository = "usdaeco-" + (name.removeprefix("usdAeco").lower() or "core") if name.startswith("usdAeco") else name
        report.update({"source_commit": revision, "tag": tag, "library": name,
                       "public_url": f"https://github.com/{PUBLIC_GITHUB_ORG}/{repository}",
                       "omitted": omitted, "mode": "push" if push else "report", "pushed": False})
        report["sweep"]["findings"].extend(rejected)
        report["ok"] = report["sweep"]["ok"] = not report["sweep"]["findings"]
        if report["ok"]:
            git("init", "--quiet", "--initial-branch=main", destination)
            # -f includes every reviewed file even when source ignore rules match.
            git("add", "--force", "--all", cwd=destination)
            git("commit", "--quiet", "-m", name + " " + tag + " public release", cwd=destination)
            git("tag", "-a", tag, "-m", name + " " + tag, cwd=destination)
            report["orphan_commit"] = git("rev-parse", "HEAD", cwd=destination).decode().strip()
            report["commit_count"] = int(git("rev-list", "--count", "HEAD", cwd=destination))
            assert report["commit_count"] == 1
        write_report(output, report)
        if push and report["ok"]:
            # One atomic update, no force, no remote creation or visibility change.
            git("push", "--atomic", "--", remote, "HEAD:refs/heads/main",
                "refs/tags/" + tag + ":refs/tags/" + tag, cwd=destination)
            report["pushed"] = True
            write_report(output, report)
        return report


def write_report(output, report):
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Publication report", "", f"Tag: `{report['tag']}`. Mode: {report['mode']}. Pushed: {report['pushed']}.", "",
             "| Library | Public URL |", "|---|---|",
             f"| {report['library']} | {report['public_url']} |", "",
             "Public URL is the intended destination; availability is not checked.", "",
             f"{report['file_count']} files, {report['bytes']} bytes; sweep {'PASS' if report['ok'] else 'FAIL'}.", "",
             "| Licence file | Licence |", "|---|---|"]
    lines += [f"| {r['path']} | {r['licence']} |" for r in report["licences"]]
    lines += ["", "| File | Bytes | SHA-256 |", "|---|---:|---|"]
    lines += [f"| {r['path']} | {r['bytes']} | {r['sha256']} |" for r in report["files"]]
    lines += ["", "Sweep findings: " + str(len(report["sweep"]["findings"])) + ".", ""]
    lines += [f"- {r['path']}:{r.get('line', 0)} {r['rule']}" for r in report["sweep"]["findings"]]
    lines += ["", "Omitted operational files: " + (", ".join(report["omitted"]) or "none") + ".", ""]
    (output / "report.md").write_text("\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--report", action="store_true", help="default; never push")
    modes.add_argument("--push", action="store_true", help="requires prior approval and an explicit remote")
    parser.add_argument("--remote")
    parser.add_argument("--term-pattern", action="append", default=[])
    args = parser.parse_args(argv)
    print("== stage: publication report", flush=True)
    try:
        report = prepare(args.source, args.tag, args.output, push=args.push, remote=args.remote, patterns=args.term_pattern)
    except (ValueError, OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        print("FAIL publication preparation: " + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__))
        print("1 checks, 1 failed, 0 not run")
        return 1
    print(f"{'PASS' if report['ok'] else 'FAIL'} publication: {report['file_count']} files, {report['bytes']} bytes, "
          f"{len(report['sweep']['findings'])} findings; pushed={report['pushed']}")
    print(f"1 checks, {0 if report['ok'] else 1} failed, 0 not run")
    return int(not report["ok"])


if __name__ == "__main__":
    raise SystemExit(main())
