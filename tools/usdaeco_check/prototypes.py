"""Canonical names for the internal prototype roots emitted by Stage.Flatten."""
import hashlib
import re

from .contracts import require


def _specs(layer):
    from pxr import Sdf
    paths = []
    layer.Traverse(Sdf.Path.absoluteRootPath, paths.append)
    return [spec for path in paths if isinstance(
        spec := layer.GetObjectAtPath(path), (Sdf.PrimSpec, Sdf.PropertySpec))]


def _remap_paths(layer, mapping):
    """Remap typed USD paths, preserving list operations and literal strings."""
    from pxr import Sdf

    def remap(value):
        if isinstance(value, Sdf.Path):
            root = value.GetPrefixes()[0] if value.IsAbsolutePath() and value.GetPrefixes() else None
            return value.ReplacePrefix(root, mapping[root]) if root in mapping else value
        if isinstance(value, Sdf.Reference):
            return Sdf.Reference(value.assetPath,
                                 value.primPath if value.assetPath else remap(value.primPath),
                                 value.layerOffset, value.customData)
        if isinstance(value, Sdf.Payload):
            return Sdf.Payload(value.assetPath,
                               value.primPath if value.assetPath else remap(value.primPath),
                               value.layerOffset)
        if isinstance(value, (Sdf.PathListOp, Sdf.ReferenceListOp, Sdf.PayloadListOp)):
            result = type(value)()
            for field in fields(value):
                setattr(result, field, [remap(item) for item in getattr(value, field)])
            return result
        if isinstance(value, dict):
            return {remap(key): remap(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return type(value)(remap(item) for item in value)
        return value

    def fields(value):
        return ("explicitItems",) if value.isExplicit else (
            "addedItems", "prependedItems", "appendedItems", "deletedItems", "orderedItems")

    for spec in _specs(layer):
        for key in spec.ListInfoKeys():
            value = spec.GetInfo(key)
            mapped = remap(value)
            if mapped == value:
                continue
            # Target/connection children must be edited through their proxies.
            if key in ("targetPaths", "connectionPaths"):
                proxy = spec.targetPathList if key == "targetPaths" else spec.connectionPathList
                for field in fields(mapped):
                    setattr(proxy, field, getattr(mapped, field))
            else:
                spec.SetInfo(key, mapped)


def canonicalize_prototypes(layer):
    """Rename only referenced Flattened_Prototype_N overs, in a private layer.

    Hash a copied subtree at a neutral root. References to other prototypes use
    stable instance-site names while hashing, including nested instances. Equal
    subtrees keep separate roots, ordered by their first expanded instance site.
    """
    from pxr import Sdf
    candidates = {p.path: p for p in layer.rootPrims
                  if p.specifier == Sdf.SpecifierOver
                  and re.fullmatch(r"Flattened_Prototype_[0-9]+", p.name)}
    if not candidates:
        return
    incoming = {}
    for spec in _specs(layer):
        if isinstance(spec, Sdf.PrimSpec) and spec.instanceable:
            for ref in spec.referenceList.GetAppliedItems():
                if not ref.assetPath and ref.primPath in candidates:
                    incoming.setdefault(ref.primPath, []).append(spec.path)
    if not incoming:
        return

    sites = {}
    visiting = set()

    def site(root):
        if root in sites:
            return sites[root]
        require(root not in visiting, "ResultInvalid: cyclic prototype references")
        visiting.add(root)
        uses = []
        for owner in incoming[root]:
            parent = owner.GetPrefixes()[0]
            uses.append(str(owner.ReplacePrefix(parent, Sdf.Path(site(parent))))
                        if parent in incoming else str(owner))
        visiting.remove(root)
        sites[root] = min(uses)
        return sites[root]

    anchors = {root: Sdf.Path("/PrototypeSite_" + hashlib.sha256(site(root).encode()).hexdigest())
               for root in incoming}
    groups = {}
    for root in incoming:
        subtree = Sdf.Layer.CreateAnonymous()
        require(Sdf.CopySpec(layer, root, subtree, Sdf.Path("/Prototype")),
                "ResultInvalid: cannot copy prototype subtree")
        _remap_paths(subtree, anchors)
        digest = hashlib.sha256(subtree.ExportToString().encode("utf-8")).hexdigest()
        groups.setdefault(digest, []).append(root)

    occupied = {p.name for p in layer.rootPrims if p.path not in incoming}
    mapping = {}
    for digest, roots in sorted(groups.items()):
        for root in sorted(roots, key=site):
            name = "Flattened_Prototype_" + digest
            suffix = 0
            while name in occupied:
                suffix += 1
                name = f"Flattened_Prototype_{digest}_{suffix}"
            occupied.add(name)
            mapping[root] = Sdf.Path("/" + name)

    roots = list(layer.rootPrims)
    slots = [i for i, prim in enumerate(roots) if prim.path in mapping]
    prototypes = [roots[i] for i in slots]
    _remap_paths(layer, mapping)
    for prim in prototypes:
        prim.name = mapping[prim.path].name
    for index, prim in zip(slots, sorted(prototypes, key=lambda p: p.name)):
        roots[index] = prim
    layer.rootPrims[:] = roots
    names = {old.name: new.name for old, new in mapping.items()}
    if layer.defaultPrim in names:
        layer.defaultPrim = names[layer.defaultPrim]
    if layer.rootPrimOrder:
        layer.rootPrimOrder = [names.get(name, name) for name in layer.rootPrimOrder]
