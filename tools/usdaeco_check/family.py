"""Validate release trains and compare available sibling library manifests."""
import json
from pathlib import Path
import re

from packaging.specifiers import SpecifierSet
from packaging.version import Version
from .contracts import KINDS, VERSION, require, ranges, repository_name
from .plugins import read_json
from .report import Result

FAMILY_KINDS = KINDS | {"meta"}


def validate_family(document, *, sibling_root=None, inventory=False):
    """Validate a train, or an explicit inventory reporting seeds and range drift."""
    try:
        data = read_json(document) if isinstance(document, (str, Path)) else document
        require(isinstance(data, dict), "family must be an object")
        require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", data.get("train", ""))), "invalid train identifier")
        repos = data.get("repos")
        require(isinstance(repos, list) and bool(repos), "repos must be a nonempty list")
        names, libraries = {}, {}
        for index, repo in enumerate(repos):
            require(isinstance(repo, dict), "repository entries must be objects")
            require(set(("name", "kind", "library", "tag", "requires", "example", "enclave")) <= repo.keys(), "repository entry lacks a required field")
            name = repo["name"]
            repository_name(name, f"repos[{index}].name")
            require(name not in names, "duplicate repository: " + name)
            require(repo["kind"] in FAMILY_KINDS, "invalid repository kind")
            require(repo["tag"] is None or isinstance(repo["tag"], str) and bool(re.fullmatch("v" + VERSION, repo["tag"])), "tag must be an exact release or null for an unreleased seed")
            ranges(repo["requires"])
            library = repo["library"]
            require(library is None or isinstance(library, str) and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", library)), "library must be an identifier or null")
            if library:
                require(library not in libraries, "duplicate library: " + library)
                libraries[library] = repo
            names[name] = repo
            example = repo["example"]
            if example is not None:
                require(isinstance(example, dict), "example must be an object or null")
                require(bool(re.fullmatch("v" + VERSION, example.get("datacentre", ""))), "example must pin a data-centre release")
                require(bool(re.fullmatch(r"[a-z][a-z0-9-]*", example.get("variant", ""))), "example needs a variant")
            enclave = repo["enclave"]
            if enclave is not None:
                require(isinstance(enclave, str) and bool(enclave) and not Path(enclave).is_absolute() and ".." not in Path(enclave).parts, "enclave must be a relative artifact path")
        targets = names | libraries
        active, done = set(), set()
        def visit(repo):
            name = repo["name"]
            require(name not in active, "family dependency cycle")
            if name in done:
                return
            active.add(name)
            for dependency in repo["requires"]:
                require(dependency in targets, "required library/repository absent: " + dependency)
                visit(targets[dependency])
            active.remove(name)
            done.add(name)
        for repo in repos:
            visit(repo)
        # An inventory preserves the actual released ranges during migrations;
        # it must never claim these releases form a compatible train.
        drift = []
        seeds = [repo["name"] for repo in repos if repo["tag"] is None]
        for repo in repos:
            for dependency, constraint in repo["requires"].items():
                require(dependency in targets, "required library/repository absent: " + dependency)
                if repo["tag"] is None:
                    continue
                tag = targets[dependency]["tag"]
                if tag is None or Version(tag[1:]) not in SpecifierSet(constraint):
                    drift.append(f"{repo['name']} requires {dependency} {constraint} (inventory: {tag or 'unreleased'})")
            if repo["example"]:
                dc = names.get("usdaeco-datacentre")
                require(dc is not None and dc["tag"] == repo["example"]["datacentre"], "example data-centre pin differs from train")
        require(inventory or not (seeds or drift),
                f"not a compatible release train: {len(seeds)} unreleased seeds; {len(drift)} incompatible requirements"
                + ("; " + "; ".join(drift) if drift else ""))
        compared, missing, absent = 0, 0, 0
        if sibling_root is not None:
            root = Path(sibling_root)
            for repo in repos:
                checkout = root / repo["name"]
                if not checkout.is_dir():
                    absent += 1
                    continue
                path = checkout / "library.json"
                if not path.is_file():
                    missing += 1
                    continue
                metadata = read_json(path)
                require(metadata.get("name") == (repo["library"] or repo["name"]), repo["name"] + ": library name differs")
                if repo["tag"] is not None:
                    require(metadata.get("version") == repo["tag"][1:], repo["name"] + ": version differs from tag")
                require(metadata.get("requires") == repo["requires"], repo["name"] + ": requirements differ")
                if "kind" in metadata:
                    require(metadata["kind"] == repo["kind"], repo["name"] + ": kind differs")
                compared += 1
        detail = f"{len(repos)} repositories, {len(libraries)} libraries; {compared} sibling manifests compared"
        detail += f"; {missing} legacy manifests unavailable; {absent} checkouts absent"
        if sibling_root is None:
            detail += "; sibling comparison not requested"
        if inventory:
            detail += f"; inventory only: {len(seeds)} unreleased seeds; {len(drift)} incompatible requirements; compatibility not proven"
            if drift:
                detail += "; " + "; ".join(drift)
        return Result("family manifest", True, detail)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        return Result("family manifest", False, str(exc))
