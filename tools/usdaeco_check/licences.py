"""S01 licence detection from complete canonical grants, conditions and disclaimers."""
from functools import lru_cache
from pathlib import Path
import re

from .contracts import require

LICENCES = {
    "MIT": "Permission is hereby granted",
    "Apache-2.0": "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
    "BSD-3-Clause": "Redistribution and use in source and binary forms",
}
LICENCE_NAMES = {
    "MIT": ("MIT", "MIT License"),
    "Apache-2.0": ("Apache-2.0", "Apache License 2.0"),
    "BSD-3-Clause": ("BSD-3-Clause", "BSD 3-Clause"),
}


def _normalize(text):
    # Wrapping, case, typographic quotes and BSD bullet style are immaterial.
    text = text.translate(str.maketrans({'“': '"', '”': '"', '’': "'"}))
    text = " ".join(text.casefold().split())
    return re.sub(r"(?<!\S)(?:[123]\.|\*)\s+(?=redistributions|neither)", "", text)


@lru_cache(maxsize=3)
def _body_pattern(name):
    text = (Path(__file__).with_name("licences") / (name + ".txt")).read_text()
    body = _normalize(text[text.index(LICENCES[name]):])
    pattern = re.escape(body)
    if name == "BSD-3-Clause":
        # BSD allows a named organization in its non-endorsement condition.
        pattern = pattern.replace(re.escape("the copyright holder nor the names"),
                                  r"[^.]+?\ nor\ the\ names")
    return re.compile(pattern)


def detect_licence(text):
    """Return one allowlisted name, or None for missing/abridged/ambiguous terms.

    Compare every operative clause, ignoring the heading, copyright holder,
    whitespace and optional Apache appendix. A title or SPDX tag alone fails.
    """
    normalized = _normalize(text)
    matches = [name for name in LICENCES if _body_pattern(name).search(normalized)]
    return matches[0] if len(matches) == 1 else None


def is_licence_file(path):
    return bool(re.fullmatch(r"licen[cs]e(?:\.(?:md|txt))?", path.name, re.I))


def check_licence(root, manifest, files):
    detected = detect_licence((root / "LICENSE").read_text())
    require(detected is not None, "LICENSE requires full MIT, Apache-2.0 or BSD-3-Clause text")
    declared = manifest.get("licence", detected)
    require(isinstance(declared, str) and declared in LICENCES,
            "library.json licence must be MIT, Apache-2.0 or BSD-3-Clause")
    require(declared == detected, f"library.json licence {declared} differs from LICENSE ({detected})")
    readme = (root / "README.md").read_text()
    section = re.search(r"(?ms)^## Licence\s*\n(.*?)(?=^## |\Z)", readme)
    require(section is not None, "README needs a Licence section")
    section = section.group(1).strip()
    # The opening paragraph declares the repository's terms; dependency tables
    # and per-directory notices must not satisfy a mismatched root declaration.
    primary = section.split("\n\n", 1)[0]
    names = {name for name, spellings in LICENCE_NAMES.items()
             if any(re.search(r"(?<![\w-])" + re.escape(spelling) + r"(?![\w-])", primary)
                    for spelling in spellings)}
    require(names == {detected}, f"README Licence opening paragraph must name {detected}")
    additional = sorted(p.relative_to(root).as_posix() for p in files
                        if p.parent != root and is_licence_file(p))
    missing = [name for name in additional if name not in section]
    require(not missing, "README Licence must mention additional licences: " + ", ".join(missing))
    detail = f"{detected} ({'declared' if 'licence' in manifest else 'inferred'})"
    if additional:
        detail += "; INFO additional per-directory licences: " + ", ".join(additional)
    return detail
