"""Stable skeleton vocabulary and pin validation, without importing USD."""
import re
from packaging.specifiers import SpecifierSet
from packaging.version import Version

KINDS = {"library", "usecase", "integration", "data", "gate", "board"}
TIERS = {"core", "section", "kind", "record", "sector", "organization", "project", "toolchain", "integration", "data", "gate", "board"}
README_HEADINGS = ["Use case", "The schema on an index card", "The example", "Build and check", "Family", "Layout", "Status", "Licence"]
USECASE_HEADINGS = ["1 The problem", "2 The data as it arrives", "3 The model in USD", "4 Workflow", "5 Validation", "6 The example on the demo data centre", "7 Trade-offs and alternatives", "8 Out of scope and open questions", "9 Status"]
VERSION = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?"
RANGE = re.compile(r"\s*(?:>=|<=|>|<|~=)\s*\d+(?:\.\d+){1,2}(?:-[0-9A-Za-z.-]+)?(?:\s*,\s*(?:>=|<=|>|<|~=)\s*\d+(?:\.\d+){1,2}(?:-[0-9A-Za-z.-]+)?)*\s*")
KIT_UPSTREAM_REPOS = ("usdSolid", "usdSolidOcct", "hdOcct", "aeco-toolchain", "OpenUSD")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def repository_name(repo, entry):
    """The shared dependency-pin and family-inventory repository vocabulary."""
    require(isinstance(repo, str) and (repo in KIT_UPSTREAM_REPOS or bool(re.fullmatch(
        r"(?:[a-z][a-z0-9-]*|usdAeco(?:[A-Z][A-Za-z0-9]*)?)", repo))),
        f"{entry}: invalid repository name {repo!r}; expected a lowercase "
        "slug [a-z][a-z0-9-]* (including usdaeco-*), usdAeco or usdAeco<X>, "
        "or a declared kit/upstream name: " + ", ".join(KIT_UPSTREAM_REPOS))


def ranges(values):
    require(isinstance(values, dict), "requires must be an object")
    for name, value in values.items():
        require(isinstance(name, str) and bool(name), "empty dependency name")
        require(isinstance(value, str) and bool(RANGE.fullmatch(value)), f"{name}: requires a range, never an exact lock")
        SpecifierSet(value)


def pin_version(pin):
    ref = pin.get("ref", "")
    require(isinstance(ref, str), "ref must be a string")
    if re.fullmatch("v" + VERSION, ref):
        return Version(ref[1:])
    require(bool(re.fullmatch(r"[0-9a-f]{40}", ref)), "ref must be an exact release tag or full revision")
    if pin.get("library") is None and "version" not in pin:
        return None
    require(bool(re.fullmatch(VERSION, pin.get("version", ""))), "schema revision pins need a version")
    return Version(pin["version"])


def fixture_inputs(document):
    """Select explicitly declared flake inputs; other fixture evidence is opaque."""
    fixtures = document.get("fixtures", {})
    require(isinstance(fixtures, dict), "fixtures must be an object")
    inputs = {}
    for key, fixture in fixtures.items():
        if isinstance(fixture, dict) and "flakeInput" in fixture:
            require(isinstance(fixture["flakeInput"], bool), f"{key}: flakeInput must be a boolean")
            if fixture["flakeInput"]:
                inputs[key] = fixture
    return inputs


def pins(document, requires):
    repos = document.get("repos")
    require(isinstance(repos, dict), "dependencies.json needs a repos object")
    fixtures = fixture_inputs(document)
    require(not (repos.keys() & fixtures.keys()), "fixture input names must be distinct from direct pins")
    for key, pin in fixtures.items():
        repository_name(pin.get("repo", ""), key)
        pin_version(pin)
        require(pin.get("library") is None or isinstance(pin["library"], str),
                f"{key}: invalid fixture library")
        require(isinstance(pin.get("reason"), str) and bool(pin["reason"].strip()),
                f"{key}: fixture needs a nonblank reason")
    libraries = {}
    for key, pin in repos.items():
        require(isinstance(pin, dict), f"{key}: pin must be an object")
        repository_name(pin.get("repo", ""), key)
        version = pin_version(pin)
        library = pin.get("library")
        if library is not None:
            require(isinstance(library, str) and library not in libraries, "duplicate or invalid pinned library")
            libraries[library] = version
    for name, constraint in requires.items():
        require(name in libraries, f"{name}: missing pin")
        require(libraries[name] in SpecifierSet(constraint), f"{name}: pin outside declared range")
    return repos
