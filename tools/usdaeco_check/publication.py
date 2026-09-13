"""Inspect an exact public tree, including tracked data and binary USD layers."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .licences import check_licence, detect_licence, is_licence_file
from .structure import TERM_PATTERNS, public_org_text
from .report import Result

MAX_FILE_BYTES = 10_000_000
MAX_TREE_BYTES = 50_000_000
# Literal spellings never need to appear in public fixtures or diagnostics.
PUBLIC_PATTERNS = TERM_PATTERNS + [
    r"\b(?:cd[c]1|pa[r]02|st[b]1a|oa[k]6a)\b", r"\bfor[u]m-\d+\b",
    r"\b(?:fe80|f[cd][0-9a-f]{2}):[0-9a-f:]+",
    r"(?:https?|ssh)://(?:[^\s/@]+@)?(?!localhost(?=[:/\s]|$))[\w-]+(?=[:/\s]|$)",
]


def check_publication(root, patterns=()):
    """Check candidate repository files, retaining tracked published outputs."""
    root = Path(root)
    if (root / ".git").exists():
        result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                check=True, capture_output=True, text=True)
        paths = [root / name for name in sorted(set(result.stdout.split("\0"))) if name]
    else:
        paths = None
    report = inspect_tree(root, paths=paths, patterns=patterns)
    details = f"{report['file_count']} files, {report['bytes']} bytes, {len(report['sweep']['findings'])} findings"
    if not report["ok"]:
        details += "; " + ", ".join(f"{r['path']}:{r.get('line', 0)} {r['rule']}" for r in report["sweep"]["findings"][:20])
    return Result("publication sweep", report["ok"], details)


def text_findings(text, name, patterns=()):
    """Return locations and categories, never the matched private text."""
    standard = [re.compile(p, re.I) for p in PUBLIC_PATTERNS]
    extra = [re.compile(p, re.I) for p in patterns]
    findings = []
    licence_section = False
    for number, line in enumerate(text.splitlines(), 1):
        if Path(name).name == "README.md" and re.match(r"^#{1,2} ", line):
            licence_section = line.strip() == "## Licence"
        notice = is_licence_file(Path(name)) and bool(re.fullmatch(r"Copyright \(c\) 2026 Cr[i]ad", line))
        public = re.sub(r"\bcr[i]ad\b", "", line, flags=re.I) if notice or licence_section else line
        if Path(name).name == "library.json":
            public = re.sub(r'("copyright"\s*:\s*")Copyright \(c\) 2026 Cr[i]ad(")', r'\1\2', public)
        public = public_org_text(public)
        if any(p.search(public) for p in standard) or any(p.search(line) for p in extra):
            findings.append({"path": name, "line": number, "rule": "PrivateText"})
    return findings


def safe_name(name, patterns=()):
    if any(ord(c) < 32 or ord(c) == 127 for c in name) or text_findings(name, "path", patterns):
        return "[withheld-" + hashlib.sha256(name.encode()).hexdigest()[:12] + "]"
    return name


def _crate_text(path):
    # Open a layer only: do not compose or resolve any authored external assets.
    code = "from pxr import Sdf; import sys; l=Sdf.Layer.OpenAsAnonymous(sys.argv[1]); assert l; print(l.ExportToString())"
    import os
    env = {k: v for k, v in os.environ.items() if k not in
           ("PYTHONPATH", "PXR_PLUGINPATH_NAME", "PXR_AR_DEFAULT_SEARCH_PATH")}
    result = subprocess.run([sys.executable, "-I", "-c", code, str(path)],
                            env=env, capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError("USD layer could not be inspected")
    return result.stdout.decode("utf-8")


def _image_text(path):
    from PIL import Image
    with Image.open(path) as image:
        metadata = []
        for frame in range(getattr(image, "n_frames", 1)):
            image.seek(frame)
            metadata.append(str(image.info))
            metadata.append(str(dict(image.getexif())))
        return "\n".join(metadata)


def inspect_tree(root, *, paths=None, patterns=(), max_file=MAX_FILE_BYTES, max_tree=MAX_TREE_BYTES):
    """No ignore rules: every selected file is part of the publication contract."""
    root = Path(root)
    files = sorted(paths if paths is not None else
                   (p for p in root.rglob("*") if ".git" not in p.relative_to(root).parts and (p.is_symlink() or not p.is_dir())))
    records, findings, licences = [], [], []
    included = {p.absolute() for p in files}
    for path in files:
        name = path.relative_to(root).as_posix()
        display = safe_name(name, patterns)
        if display != name:
            findings.append({"path": display, "rule": "PrivatePath"})
        if path.is_symlink():
            target = os.readlink(path)
            try:
                resolved = path.resolve(strict=True)
                covered = (resolved.is_file() and resolved in included) or (
                    resolved.is_dir() and resolved != root.resolve() and resolved not in path.absolute().parents
                    and any(resolved in p.parents for p in included))
                valid = not Path(target).is_absolute() and resolved.is_relative_to(root.resolve()) and covered
            except (OSError, RuntimeError):
                valid = False
            if not valid:
                findings.append({"path": display, "rule": "UnsafeSymlink"})
            findings.extend(text_findings(target, display, patterns))
            data = target.encode()
            records.append({"path": display, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "type": "symlink"})
            continue
        if not path.is_file():
            findings.append({"path": display, "rule": "UnsupportedFile"})
            continue
        size = path.stat().st_size
        if size > max_file:
            findings.append({"path": display, "rule": "FileSizeExceeded"})
        data = path.read_bytes()
        records.append({"path": display, "bytes": size, "sha256": hashlib.sha256(data).hexdigest()})
        try:
            if data.startswith(b"PXR-USDC") or path.suffix.lower() == ".usdc":
                text = _crate_text(path)
            elif (data.startswith((b"PK\x03\x04", b"\x1f\x8b", b"BZh", b"\xfd7zXZ", b"7z\xbc\xaf"))
                  or path.suffix.lower() in {".zip", ".usdz", ".gz", ".bz2", ".xz", ".7z", ".tar", ".zst"}):
                # Archives need their own recursive inspection policy.
                findings.append({"path": display, "rule": "ArchiveNotInspected"})
                continue
            else:
                if path.suffix.lower() in {".png", ".gif", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
                    findings.extend(text_findings(_image_text(path), display, patterns))
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    # Metadata and printable strings in images/native artifacts.
                    text = data.decode("utf-8", errors="replace")
                    for encoding in ("utf-16-le", "utf-16-be"):
                        findings.extend(text_findings(data.decode(encoding, errors="replace"), display, patterns))
            findings.extend(text_findings(text, display, patterns))
            if is_licence_file(path):
                licence = detect_licence(text)
                if licence is None:
                    match = re.search(r"SPDX-License-Identifier:\s*([\w.+-]+)", text)
                    licence = match.group(1) if match else "Additional terms; inspect file"
                licences.append({"path": display, "licence": licence, "sha256": hashlib.sha256(data).hexdigest()})
        except (ValueError, OSError, ImportError, subprocess.TimeoutExpired):
            findings.append({"path": display, "rule": "ContentNotInspected"})
    total = sum(record["bytes"] for record in records)
    if total > max_tree:
        findings.append({"path": ".", "rule": "TreeSizeExceeded"})
    try:
        metadata = json.loads((root / "library.json").read_text())
        if metadata.get("kind") == "meta":
            findings.append({"path": "library.json", "rule": "PrivateRepository"})
        licence_detail = check_licence(root, metadata, files)
    except (ValueError, OSError, TypeError):
        licence_detail = "Root licence or directory disclosures failed S01"
        findings.append({"path": "LICENSE", "rule": "LicenceMismatch"})
    return {"ok": not findings, "files": records, "file_count": len(records), "bytes": total,
            "licences": licences, "licence_check": licence_detail,
            "limits": {"file_bytes": max_file, "tree_bytes": max_tree},
            "sweep": {"ok": not findings, "findings": findings},
            "image_labels": "Reviewed source artwork; pixel text is not inspected by OCR"}
