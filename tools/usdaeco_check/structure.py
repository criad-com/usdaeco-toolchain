"""The stable S01–S29 repository rules from docs/repo-conventions.md."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .contracts import KINDS, TIERS, VERSION, README_HEADINGS, USECASE_HEADINGS, require, ranges, pins, fixture_inputs
from .plugins import read_json, discover
from .report import Result
from .licences import check_licence, is_licence_file

RULES = {}
PUBLIC_GITHUB_ORG = "criad-com"
SCHEMA_RULES = set(range(6, 20))
IGNORED = {".git", ".venv", "__pycache__", ".pytest_cache", "out", "build", "dist", "pluginset"}
# Match sensitive terms without reproducing their spelling in repository text.
PRIVATE_TERMS = [r"cr[i]ad", r"fel[i]x", r"neu[f]eld", r"sj[w]s", r"gr[q]6a"]
TERM_PATTERNS = [r"\b(?:10|100|127)(?:\.\d{1,3}){3}\b", r"\b192\.168(?:\.\d{1,3}){2}\b",
                 r"\b172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}\b",
                 r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b",
                 r"/(?:Users|Volumes|home)/[^\s\"']+", r"\b[A-Z]:\\(?:Users|Projects)\\",
                 r"\b[\w.-]+\.(?:local|lan|internal|ts\.net)\b",
                 r"\b(?:mini|studio|npg)[-](?:one|two|three|\d+)\b", *PRIVATE_TERMS]


def public_org_text(text):
    """Exempt only the public org slug; retain adjacent and caller-defined terms."""
    # Preserve hostname syntax so private suffixes and single-label URLs match.
    return re.sub(r"(?<![\w-])" + re.escape(PUBLIC_GITHUB_ORG) + r"(?![\w-])",
                  "public-org", text)


def rule(number):
    def decorate(fn):
        RULES[number] = fn
        return fn
    return decorate


def _text(path):
    return path.read_text()


def _headings(path):
    return re.findall(r"(?m)^## (.+)$", _text(path))


def _owned_names(c, field, default):
    if field not in c.manifest:
        return default
    values = c.manifest[field]
    require(isinstance(values, list) and bool(values)
            and all(isinstance(value, str) and bool(value.strip()) for value in values),
            f"{field} must be a nonempty array of nonempty strings")
    return values


def _process(code, args, *, clean=False):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    if clean:
        for key in ("PXR_PLUGINPATH_NAME", "PXR_AR_DEFAULT_SEARCH_PATH"):
            env.pop(key, None)
    setup = f"import sys; sys.path.insert(0, {str(Path(__file__).resolve().parents[1])!r}); "
    return subprocess.run([sys.executable, "-c", setup + code, *args], env=env,
                          text=True, capture_output=True, timeout=90)


class Context:
    def __init__(self, root, deps, term_patterns):
        self.root = Path(root).resolve()
        try:
            self.manifest = read_json(self.root / "library.json")
        except (ValueError, OSError):
            self.manifest = {}
        self.name = self.manifest.get("name", "")
        self.kind = self.manifest.get("kind", "")
        self.schema = isinstance(self.name, str) and self.name.startswith("usdAeco")
        self.suffix = self.name.removeprefix("usdAeco") if self.schema else ""
        self.module = self.root / self.name
        self.validator_dir = self.root / (self.name + "Validators")
        self.keyword = "UsdAeco" + self.suffix + "Validators"
        self.example = self.root / "examples" / ("roundtrip" if self.kind == "integration" else "datacentre")
        self.story = self.kind in ("usecase", "integration")
        self.deps = [str(Path(d).resolve()) for d in deps]
        if not self.deps:
            candidate = os.environ.get("CORE_PLUGIN_DIR")
            if candidate:
                self.deps.append(str(Path(candidate).resolve()))
            else:
                for candidate in (self.root.parent / "usdaeco-core/plugins/usdAeco/resources",
                                  Path(__file__).resolve().parents[3] / "usdaeco-core/plugins/usdAeco/resources"):
                    if (candidate / "plugInfo.json").exists():
                        self.deps.append(str(candidate.resolve()))
                        break
            self.deps.extend(p for p in os.environ.get("PXR_PLUGINPATH_NAME", "").split(os.pathsep) if p)
        self.term_patterns = term_patterns
        self._schema_data = None

    def worker(self, task, args):
        result = _process("from usdaeco_check.structure_worker import main; main()",
                          [task, json.dumps(args)], clean=True)
        require(result.returncode == 0, f"{task} subprocess failed (exit {result.returncode}); run its source probe for diagnostics")
        lines = [s for s in result.stdout.splitlines() if s.startswith("STRUCTURE_JSON:")]
        require(bool(lines), "probe did not return data")
        return json.loads(lines[-1].split(":", 1)[1])

    @property
    def schema_data(self):
        if self._schema_data is None:
            self._schema_data = self.worker("schema", [str(self.root), self.name, self.deps])
        return self._schema_data

    @property
    def validators(self):
        return read_json(self.validator_dir / "plugInfo.json")["Plugins"][0]["Info"]["Validators"]

    @property
    def tokens(self):
        tree = ast.parse(_text(self.validator_dir / "validatorTokens.py"))
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try:
                    values[node.targets[0].id] = ast.literal_eval(node.value)
                except ValueError:
                    if isinstance(node.value, (ast.Tuple, ast.List)):
                        values[node.targets[0].id] = [values[n.id] for n in node.value.elts if isinstance(n, ast.Name) and n.id in values]
        return values


@rule(1)
def root_files(c):
    required = "README.md LICENSE CHANGELOG.md library.json dependencies.json flake.nix check.py pyproject.toml".split()
    require(all((c.root / p).is_file() for p in required), "missing required root file")
    return check_licence(c.root, c.manifest, _repository_files(c.root))


@rule(2)
def readme(c):
    title = re.findall(r"(?m)^# (.+)$", _text(c.root / "README.md"))
    require(len(title) == 1 and title[0].startswith(c.name + " — "), "README title must name the library/repository")
    require(_headings(c.root / "README.md") == README_HEADINGS, "README headings differ from the fixed order")


@rule(3)
def metadata(c):
    require(bool(re.fullmatch(r"(?:usdAeco(?:[A-Z][A-Za-z0-9]*)?|usdaeco-[a-z0-9-]+)", c.name)), "invalid library/repository name")
    require(c.kind in KINDS and c.manifest.get("tier") in TIERS, "invalid kind or tier")
    require(bool(re.fullmatch(VERSION, c.manifest.get("version", ""))), "semantic version required")
    ranges(c.manifest.get("requires"))
    for field in ("namespaces", "classPrefixes"):
        _owned_names(c, field, [])


@rule(4)
def dependency_pins(c):
    pins(read_json(c.root / "dependencies.json"), c.manifest["requires"])


@rule(5)
def flake(c):
    text = re.sub(r"(?m)^\s*#.*$", "", _text(c.root / "flake.nix"))
    urls = re.findall(r'\burl\s*=\s*"([^"]+)"', text)
    document = read_json(c.root / "dependencies.json")
    inputs = document["repos"] | fixture_inputs(document)
    expected = [f"github:{PUBLIC_GITHUB_ORG}/{p['repo']}?ref={p['ref']}" for p in inputs.values()]
    require(sorted(urls) == sorted(expected), "flake URLs and exact dependency refs differ")
    require(bool(re.search(r'nixpkgs\.follows\s*=\s*"[^"]+"', text)), "nixpkgs.follows required")
    if c.schema:
        for field in ("packages", "pluginSet", "checks", "library", "structure", "devShells", "apps", "example", "render", "default"):
            require(bool(re.search(r'\b' + field + r'\s*=', text)), f"missing flake output {field}")


@rule(6)
def layout(c):
    directories = [p.parent.name for p in c.root.glob("*/schema.usda")]
    require(directories == [c.name], "schema directory must equal libraryName")
    require(all((c.module / p).is_file() for p in ("schema.usda", "generatedSchema.usda", "plugInfo.json")), "missing generated schema files")


@rule(7)
def global_metadata(c):
    data = c.schema_data
    require(data["global"].get("libraryName") == c.name, "GLOBAL.libraryName differs")
    require(all(data["global"].get(k) is True for k in ("skipCodeGeneration", "useLiteralIdentifier")), "GLOBAL codeless/literal flags required")
    layers = {"usd/schema.usda", "usdGeom/schema.usda"}
    if c.name != "usdAeco":
        layers.add("usdAeco/schema.usda")
    require(layers <= set(data["sublayers"]), "missing standard schema sublayer")


@rule(8)
def classes(c):
    prefixes = tuple(_owned_names(c, "classPrefixes", ["Aeco" + c.suffix]))
    values = c.schema_data["classes"]
    require(bool(values), "schema needs a local class")
    types = read_json(c.module / "plugInfo.json")["Plugins"][0]["Info"]["Types"]
    for cls in values:
        require(cls["name"].startswith(prefixes), "class prefix outside the library's declared classPrefixes")
        registered = "Usd" + c.name.removeprefix("usd") + cls["data"].get("className", cls["name"])
        require(registered in types, "registered type name does not match className")
        require(types[registered].get("schemaIdentifier") == cls["name"], "schema identifier mismatch")


@rule(9)
def namespaces(c):
    owned = _owned_names(c, "namespaces", [c.suffix])
    used = set()

    def matches(namespace):
        if not c.suffix and "namespaces" not in c.manifest:
            return namespace == "aeco" or namespace.startswith("aeco:")
        family, _, remainder = namespace.partition(":")
        matches = {name for name in owned if family == "aeco"
                   and remainder.split(":", 1)[0].lower().startswith(name.lower())}
        used.update(matches)
        return bool(matches)

    for cls in c.schema_data["classes"]:
        data = cls["data"]
        if data.get("apiSchemaType") == "multipleApply":
            namespace = data.get("propertyNamespacePrefix", "")
            require(matches(namespace), "multiple-apply propertyNamespacePrefix differs")
        else:
            overrides = set(cls["inherited_properties"]) | set(cls["api_properties"])
            require(all(matches(p.rpartition(":")[0]) or p in overrides for p in cls["properties"]), "property outside the library namespace")
    if "namespaces" in c.manifest and (unused := sorted(set(owned) - used)):
        return "warning: declared namespaces unused: " + ", ".join(unused)


@rule(10)
def applicability(c):
    for cls in c.schema_data["classes"]:
        data = cls["data"]
        if data.get("apiSchemaType") in ("singleApply", "multipleApply"):
            unrestricted = data.get("aecoApplicability") == "unrestricted" and bool(cls["doc"].strip())
            require(bool(data.get("apiSchemaCanOnlyApplyTo")) or unrestricted,
                    "applied API needs nonempty apiSchemaCanOnlyApplyTo or "
                    'aecoApplicability = "unrestricted" with a nonempty class doc explaining why')


@rule(11)
def generated(c):
    code = "import json; from build_schema import build; a=json.loads(sys.argv[1]); build(a[0],a[1],deps=a[2],validate=True)"
    result = _process(code, [json.dumps([c.name, str(c.root), c.deps])], clean=True)
    require(result.returncode == 0, "usdGenSchema --validate failed; regenerate with build.sh --generate-only (dependencies required)")
    return "usdGenSchema --validate clean; compiler compatibility only"


@rule(12)
def resource_plugin(c):
    entries = read_json(c.module / "plugInfo.json")["Plugins"]
    require(len(entries) == 1, "one resource plugin required")
    entry = entries[0]
    require(entry.get("Name") == c.name and entry.get("Type") == "resource" and not entry.get("LibraryPath"), "invalid resource plugin")
    require(entry["Info"].get("aeco") == {k: c.manifest[k] for k in ("version", "tier", "requires")}, "Info.aeco differs from library.json")
    require(bool(entry["Info"].get("Types")), "generated types absent")


@rule(13)
def user_docs(c):
    base = c.module / "userDoc"
    overview = _text(base / "overview.md")
    require("../examples/minimal.usda" in overview and (c.module / "examples/minimal.usda").is_file(), "overview must link minimal example")
    doc = _text(base / "schemaUserDoc.usda")
    require("@../schema.usda@" in doc and "userDocBrief" in doc and re.search(r'\bover\b', doc), "schema user doc must add brief overs")
    require((base / (c.name + "Example.png")).is_file(), "missing example image")


@rule(14)
def validator_descriptor(c):
    require(all((c.validator_dir / p).is_file() for p in ("plugInfo.json", "__init__.py", "validatorTokens.py")), "validator plugin files missing")
    entry, = read_json(c.validator_dir / "plugInfo.json")["Plugins"]
    require(entry.get("Type") == "python" and entry.get("Name") == c.name + "Validators", "Python plugin name/type differs")
    values = c.validators
    require(values.get("keywords") == [c.keyword], "plugin keyword differs")
    rules = {k: v for k, v in values.items() if k != "keywords"}
    require(bool(rules), "no validators declared")
    for name, data in rules.items():
        require(bool(re.fullmatch(r"[A-Z][A-Za-z0-9]*Checker", name)) and bool(data.get("doc")), "validator needs ProperCase Checker name and docs")
        require(not data.get("keywords") or data["keywords"] == [c.keyword], "rule keyword differs")


@rule(15)
def validator_tokens(c):
    values = c.tokens
    literals = [v for v in values.values() if isinstance(v, str)]
    require(c.keyword in literals, "missing keyword token")
    for name in c.validators:
        if name != "keywords":
            require(c.name + "Validators:" + name in literals, "validator name has no token")
    errors = values.get("ERROR_NAMES", [])
    require(bool(errors) and all(re.fullmatch(r"[A-Z][A-Za-z0-9]*", e) for e in errors), "ERROR_NAMES must contain ProperCase tokens")


@rule(16)
def validator_registry(c):
    actual = c.worker("validators", [str(c.root), c.name, c.deps])
    expected = sorted(c.name + "Validators:" + k for k in c.validators if k != "keywords")
    require(sorted(item["name"] for item in actual) == expected, "validator listing is missing or duplicates rules")
    registered = read_json(c.module / "plugInfo.json")["Plugins"][0]["Info"]["Types"]
    for item in actual:
        for name in item["schemaTypes"]:
            require(name in registered or not name.startswith("UsdAeco" + c.suffix), "invalid validator schemaTypes")
    return f"{len(actual)} validators discovered and loaded"


@rule(17)
def tests(c):
    for suffix in ("Schema", "Validators"):
        script = _text(c.root / "testenv" / ("testUsdAeco" + c.suffix + suffix + ".py"))
        require(script.startswith("#!/pxrpythonsubst\n") and "unittest" in script and "RegisterPlugins(" in script, "testenv must use pxr unittest/register pattern")
        if suffix == "Validators":
            for token in c.tokens["ERROR_NAMES"]:
                require("def test_" + token + "(" in script, "missing test for error token " + token)


@rule(18)
def companion(c):
    package = "usdaeco_" + (c.suffix.lower() or "core")
    require(all((c.root / "tools" / package / p).is_file() for p in ("__init__.py", "cli.py")), "companion package missing")
    import tomllib
    project = tomllib.loads(_text(c.root / "pyproject.toml"))
    require(project["project"]["scripts"].get("aeco-" + (c.suffix.lower() or "core")) == package + ".cli:main", "companion CLI entry point differs")


@rule(19)
def profile(c):
    data = read_json(c.root / "conformance/profiles" / ((c.suffix.lower() or "core") + ".json"))
    require(data.get("keywords") == [c.keyword], "profile keyword differs")
    overrides = data.get("severity_overrides")
    require(isinstance(overrides, dict) and all(v in ("error", "warn", "info") for v in overrides.values()), "invalid severity overrides")


@rule(20)
def usecase(c):
    require(_headings(c.root / "docs/usecase.md") == USECASE_HEADINGS, "use-case sections differ from fixed order")


@rule(21)
def example_files(c):
    require(all((c.example / p).is_file() for p in ("README.md", "run.py", "inputs/cameras.usda", "expected/findings.json", "manifest.json")), "missing example contract file")
    require((c.example / "renders").is_dir(), "missing renders directory")
    from .example_result import result_files
    result_files(c.example / "result")
    require(isinstance(read_json(c.example / "expected/findings.json"), list), "expected findings must be a list")
    require("run_example(" in _text(c.example / "run.py"), "run.py must call the shared harness")


@rule(22)
def example_manifest(c):
    data = read_json(c.example / "manifest.json")
    require(data.get("facility") == "demo-datacentre-01", "manifest facility differs")
    expected = read_json(c.root / "dependencies.json")["repos"]
    require(data.get("pins") == expected, "manifest pins differ")
    dc = data["datacentre"]
    refs = [p["ref"] for p in expected.values() if p["repo"] == "usdaeco-datacentre"]
    require(refs == [dc.get("ref")] and bool(re.fullmatch(r"[a-z][a-z0-9-]*", dc.get("variant", ""))), "datacentre release/variant mismatch")
    require(data.get("source", {}).get("mode") in ("minimal", "override", "pinned"), "manifest source mode required")
    require(data.get("findings_sha256") == hashlib.sha256((c.example / "expected/findings.json").read_bytes()).hexdigest(), "findings hash differs")
    require(bool(data.get("renders")), "render manifest is empty")
    from .images import pixels
    seen = set()
    for item in data["renders"]:
        relative = Path(item["path"])
        require(not relative.is_absolute() and ".." not in relative.parts and relative.parts[0] == "renders", "render path must stay in renders/")
        require(item["path"] not in seen, "duplicate render record")
        seen.add(item["path"])
        path = c.example / relative
        raw = path.read_bytes()
        require(item["sha256"] == hashlib.sha256(raw).hexdigest() and item["bytes"] == len(raw), "render hash/size differs")
        if path.suffix == ".png":
            height, width = pixels(path).shape[:2]
        else:
            from PIL import Image
            with Image.open(path) as image:
                width, height = image.size
        require((item["width"], item["height"]) == (width, height), "render dimensions differ")
    actual = {p.relative_to(c.example).as_posix() for p in (c.example / "renders").iterdir() if p.suffix in (".png", ".gif")}
    require(seen == actual, "unlisted or missing committed renders")
    from .example_result import validate_result
    validate_result(c.example, data.get("result", {}))
    source = data["source"]
    if source["mode"] == "pinned":
        require(bool(re.fullmatch(r"[0-9a-f]{64}", source.get("manifest_sha256", ""))),
                "pinned data-centre manifest hash required")
    require(bool(source.get("layers")), "source layer hashes required")
    for item in source["layers"]:
        require(not Path(item["path"]).is_absolute()
                and bool(re.fullmatch(r"[0-9a-f]{64}", item["sha256"])) and item["bytes"] > 0,
                "invalid source layer record")


@rule(23)
def render_caps(c):
    from .images import pixels
    import numpy as np
    bases = ([c.module / "userDoc"] if c.schema else []) + ([c.example / "renders", c.example / "result"] if c.story else [])
    for base in bases:
        for path in base.rglob("*"):
            if path.suffix.lower() not in (".png", ".gif"):
                continue
            require(path.stat().st_size <= 400000, "image exceeds 400000 bytes")
            if path.suffix.lower() == ".png":
                # Bound allocation before decoding an untrusted PNG header.
                import struct
                width, height = struct.unpack(">II", path.read_bytes()[16:24])
                require(0 < width <= 1600 and 0 < height <= 1600, "image exceeds 1600 pixels")
                data = pixels(path)
            else:
                from PIL import Image
                with Image.open(path) as image:
                    width, height = image.size
                    require(0 < width <= 1600 and 0 < height <= 1600, "image exceeds 1600 pixels")
                    data = np.asarray(image.convert("RGB"))
            require(np.any(data != data[0, 0]), "image has uniform pixels")


@rule(24)
def vanilla(c):
    paths = list((c.module / "examples").glob("*.usd*")) if c.schema else []
    require(bool(paths) or not c.schema, "no vanilla example stages")
    if paths:
        count = c.worker("vanilla", [[str(p) for p in paths]])
        return f"{count} stage roots compose without family plugins"


def _repository_files(root):
    if (root / ".git").exists():
        # Reviewer notes and local configuration may be ignored checkout files;
        # tracked files are always scanned, even when a gitignore matches them.
        result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                text=True, capture_output=True, check=True)
        files = [root / name for name in sorted(set(result.stdout.split("\0"))) if name]
    else:
        files = sorted(root.rglob("*"))
    for path in files:
        relative = path.relative_to(root)
        # Authored layers retain their inputs/out paths inside result/layers.
        # Only the path before result/ may identify a transient build tree.
        transient_parts = relative.parts[:relative.parts.index("result")] if "result" in relative.parts else relative.parts
        if (not path.is_file() or IGNORED.intersection(transient_parts)
                or any(p.endswith(".egg-info") for p in relative.parts)
                or relative.parts[0] == "result" or relative.parts[0].startswith("result-")
                or path.name == "flake.lock"):
            continue
        yield path


@rule(25)
def terms(c):
    regexes = [re.compile(p, re.I) for p in TERM_PATTERNS]
    extra = [re.compile(p, re.I) for p in c.term_patterns]
    failures = []
    for path in _repository_files(c.root):
        relative = path.relative_to(c.root)
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        licence_section = False
        for number, line in enumerate(text.splitlines(), 1):
            if path.name == "README.md" and re.match(r"^#{1,2} ", line):
                licence_section = line.strip() == "## Licence"
            # Public attribution only exempts the holder's name. Other private
            # terms and caller-supplied patterns are always checked.
            notice = is_licence_file(path) and bool(re.fullmatch(r"Copyright \(c\) 2026 Cr[i]ad", line))
            public_line = re.sub(r"\bcr[i]ad\b", "", line, flags=re.I) if notice or licence_section else line
            if path.name == "library.json":
                public_line = re.sub(r'("copyright"\s*:\s*")Copyright \(c\) 2026 Cr[i]ad(")',
                                     r'\1\2', public_line)
            public_line = public_org_text(public_line)
            if any(regex.search(public_line) for regex in regexes) or any(regex.search(line) for regex in extra):
                failures.append(f"{relative}:{number}")
    require(not failures, "term sweep: " + ", ".join(failures[:20]))


@rule(26)
def check_contract(c):
    text = _text(c.root / "check.py")
    required = ["Report", "check_structure", "N checks, M failed"]
    if c.schema:
        required += ["registry_probe", "can_apply", "validate_examples", "GetValidatorMetadataForKeyword"]
    require(all(value in text for value in required), "check.py omits shared contract checks")


@rule(27)
def committed_result(c):
    from .example_result import validate_result
    record = read_json(c.example / "manifest.json").get("result", {})
    validate_result(c.example, record, vanilla=True)
    return f"{record['prim_count']} prims, 0 composition errors in relocated plugin-free result"


@rule(28)
def vanilla_render(c):
    from .example_result import check_vanilla
    info = check_vanilla(c.example, read_json(c.example / "manifest.json").get("result", {}))
    return f"stock Embree render: {info['width']}x{info['height']}, {info['bytes']} bytes, non-uniform"


@rule(29)
def portable_sources(c):
    from .example_paths import check_result_paths
    return check_result_paths(c.example)


def check_structure(root, *, deps=(), term_patterns=(), only=None):
    """Return stable rule Results; each failure is isolated from other rules."""
    c = Context(root, deps, term_patterns)
    results = []
    for number, fn in sorted(RULES.items()):
        name = f"S{number:02d}"
        if only and name not in only:
            continue
        applies = not ((number in SCHEMA_RULES and not c.schema) or
                       (number in (20, 21, 22, 27, 28, 29) and not c.story) or
                       (number in (23, 24) and not (c.schema or c.story)))
        try:
            detail = fn(c) if applies else f"not applicable ({c.kind})"
            results.append(Result(name, True, detail or fn.__name__.replace("_", " ")))
        except Exception as exc:
            detail = str(exc).replace(str(c.root), "<repo>")
            results.append(Result(name, False, detail))
    return results


def print_results(results):
    for result in results:
        print(f"{result.name} {'PASS' if result.ok else 'FAIL'} {result.detail}", flush=True)
    failures = sum(not result.ok for result in results)
    print(f"{len(results)} checks, {failures} failed")
    return int(bool(failures))
