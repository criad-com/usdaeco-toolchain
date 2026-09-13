#!/usr/bin/env python3
"""Generate the family index from an explicit train and repository source cards."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from publish import git
from usdaeco_check.family import validate_family
from usdaeco_check.licences import detect_licence
from usdaeco_check.publication import text_findings
from usdaeco_check.report import Result
from usdaeco_check.structure import PUBLIC_GITHUB_ORG

SOURCE_FILES = ("library.json", "README.md", "docs/usecase.md", "LICENSE")
EXAMPLE_FILES = ("examples/datacentre/README.md", "examples/roundtrip/README.md", "examples/README.md",
                 "template/examples/datacentre/README.md", "docs/static-export.md")


def paragraph(document, heading):
    match = re.search(r"(?ms)^## " + re.escape(heading) + r"\s*\n(.*?)(?=^## |\Z)", document)
    if not match:
        return ""
    blocks = match.group(1).strip().split("\n\n")
    return " ".join(blocks[0].split())


def plain(text):
    text = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_]", "", text)
    return text.replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")


def collect(family_path, repos):
    family = json.loads(Path(family_path).read_text())
    validated = validate_family(family, inventory=True)
    if not validated:
        raise ValueError(validated.detail)
    family["repos"] = [entry for entry in family["repos"] if entry["kind"] != "meta"]
    cards = []
    for entry in family["repos"]:
        name, tag = entry["name"], entry["tag"]
        root = Path(repos) / name
        source = {}
        revision = None
        if tag:
            revision = git("rev-parse", "--verify", "refs/tags/" + tag + "^{commit}", cwd=root).decode().strip()
            paths = set(git("ls-tree", "-rz", "--name-only", revision, cwd=root).decode().strip("\0").split("\0"))
            def read(path):
                return git("show", revision + ":" + path, cwd=root).decode() if path in paths else ""
        else:
            paths = {p for p in SOURCE_FILES + EXAMPLE_FILES if (root / p).is_file()}
            if (root / "dist").is_dir():
                paths.add("dist/")
            def read(path):
                return (root / path).read_text() if path in paths else ""
        for path in SOURCE_FILES:
            source[path] = read(path)
        if not source["library.json"]:
            heading = re.search(r"(?m)^# .+?\s[—–-]\s(.+)$", source["README.md"])
            cards.append({"name": name, "available": False, "commit": revision,
                          "purpose": heading.group(1) if heading else "Source card unavailable",
                          "reason": "Tagged library manifest missing" if tag else "Source card unavailable"})
            continue
        metadata = json.loads(source["library.json"])
        if tag and metadata.get("version") != tag[1:]:
            raise ValueError(name + ": tag and manifest version differ")
        if metadata.get("kind", entry["kind"]) != entry["kind"]:
            raise ValueError(name + ": kind differs from train")
        if metadata["name"] != (entry["library"] or name):
            raise ValueError(name + ": library name differs from train")
        # Older trains can contain range drift; show it as recorded evidence.
        readme, usecase = source["README.md"], source["docs/usecase.md"]
        h1 = re.search(r"(?m)^# .+?\s[—–-]\s(.+)$", readme)
        purpose = h1.group(1) if h1 else paragraph(usecase, "1 The problem") or paragraph(readme, "Use case")
        status = paragraph(usecase, "9 Status") or paragraph(readme, "Status") or "No status recorded"
        # Keep the whole first paragraph: truncation can hide a failure or NOT RUN.
        examples = [p for p in EXAMPLE_FILES if p in paths]
        if not examples and any(p.startswith("dist/") for p in paths):
            examples = ["dist"]
        licence = detect_licence(source["LICENSE"])
        if licence is None or metadata.get("licence", licence) != licence:
            raise ValueError(name + ": licence verification failed")
        fields = ("name", "version", "kind", "tier", "requires", "licence", "namespaces", "classPrefixes")
        card = {"name": name, "available": True, "commit": revision,
                "library": {k: v for k, v in metadata.items() if k in fields}, "purpose": purpose, "status": status,
                "example": examples[0] if examples else None, "licence": licence,
                "source_sha256": {p: hashlib.sha256(t.encode()).hexdigest() for p, t in source.items() if t}}
        if text_findings(json.dumps(card), "card.json"):
            raise ValueError(name + ": public source card contains private text")
        cards.append(card)
    return {"format": 1, "family": family, "cards": cards}


def render(snapshot):
    family = snapshot["family"]
    cards = {r["name"]: r for r in snapshot["cards"]}
    lines = ["# usdAeco family — the repository index", "",
             f"Release inventory `{family['train']}`. Generated from the train and each available repository's",
             "library manifest, README and use-case status. Versions below belong to this inventory;",
             "they do not claim to be the newest releases or a compatible release train.", "",
             "| Repository | Purpose | Kind | Version | Example | Licence | Recorded status |",
             "|---|---|---|---|---|---|---|"]
    for entry in family["repos"]:
        name, tag = entry["name"], entry["tag"]
        card = cards[name]
        if card.get("private"):
            continue
        elif not card.get("available"):
            values = [name, plain(card["purpose"]), entry["kind"], tag or "Unreleased in train", "—", "Not verified", "NOT RUN: " + card["reason"]]
        else:
            ref = tag or "main"
            url = f"https://github.com/{PUBLIC_GITHUB_ORG}/" + name + "/tree/" + ref
            version = tag or "Unreleased in train (checkout " + card["library"]["version"] + ")"
            example = f"[Example]({url}/{card['example']})" if card["example"] else "Not recorded"
            values = [f"[{name}]({url})", plain(card["purpose"]), entry["kind"], version, example, card["licence"], plain(card["status"])]
        lines.append("| " + " | ".join(values) + " |")
    lines += ["", "Statuses quote the source release's first status paragraph; checks were not rerun to generate this index.",
              "An untagged entry is never evidence of a released example. Public links describe intended mirror locations;",
              "their availability is not proven by this document. The private metadata repository has no public link.", "",
              "See [contribution rules](../../CONTRIBUTING.md), [publication commands](../publishing.md),",
              f"[source cards](index.json) and the [board's static export contract](https://github.com/{PUBLIC_GITHUB_ORG}/usdaeco-board/blob/v0.1.2/docs/static-export.md).", ""]
    return "\n".join(lines)


def fresh_check(output, *, family=None, repos=None):
    try:
        output = Path(output)
        snapshot = json.loads(output.with_name("index.json").read_text())
        if (family is None) != (repos is None):
            raise ValueError("source freshness needs both family and repos")
        if family is not None and collect(family, repos) != snapshot:
            raise ValueError("source cards differ; regenerate the family README")
        if output.read_text() != render(snapshot):
            raise ValueError("family README is stale; regenerate it")
        mode = "live tagged sources" if family is not None else "committed source cards"
        return Result("family README fresh", True, f"{len(snapshot['cards'])} rows; {mode}")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return Result("family README fresh", False, str(exc))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", help="explicit family.json owned by the release gate")
    parser.add_argument("--repos", help="directory of repository checkouts; tags are read without checking out")
    parser.add_argument("--output", default="docs/family/README.md")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    from usdaeco_check import Report
    report = Report()
    print("== stage: family README", flush=True)
    if args.check:
        report.add(fresh_check(args.output, family=args.family, repos=args.repos))
    else:
        if not args.family or not args.repos:
            parser.error("generation needs --family and --repos")
        snapshot = collect(args.family, args.repos)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.with_name("index.json").write_text(json.dumps(snapshot, indent=2) + "\n")
        output.write_text(render(snapshot))
        report.add(fresh_check(output, family=args.family, repos=args.repos))
    return report.finish()


if __name__ == "__main__":
    raise SystemExit(main())
