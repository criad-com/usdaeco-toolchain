"""Command-line access to the reusable checks."""
import argparse
import os

from . import Report, can_apply, link_check, plugin_requires, registry_probe, term_sweep, validate_examples


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", action="append", default=[])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("requires")
    probe = sub.add_parser("registry")
    probe.add_argument("--api", action="append", default=[])
    probe.add_argument("--type", action="append", default=[])
    apply = sub.add_parser("can-apply")
    apply.add_argument("type")
    apply.add_argument("api")
    apply.add_argument("--refuse", action="store_true")
    apply.add_argument("--instance")
    examples = sub.add_parser("examples")
    examples.add_argument("directory")
    examples.add_argument("--expect-errors", type=int, default=0)
    links = sub.add_parser("links")
    links.add_argument("directory")
    terms = sub.add_parser("terms")
    terms.add_argument("paths", nargs="+")
    terms.add_argument("--pattern", action="append", required=True)
    structure = sub.add_parser("structure")
    structure.add_argument("repository")
    structure.add_argument("--dep", action="append", default=[])
    structure.add_argument("--term-pattern", action="append", default=[])
    family = sub.add_parser("family")
    family.add_argument("file")
    family.add_argument("--siblings", default=os.environ.get("AECO_FAMILY_SIBLINGS") or None)
    family.add_argument("--inventory", action="store_true", help="report unreleased seeds and range drift without claiming a compatible train")
    publication = sub.add_parser("publication")
    publication.add_argument("repository")
    publication.add_argument("--term-pattern", action="append", default=[])
    args = parser.parse_args(argv)
    if args.command == "publication":
        from .publication import check_publication
        report = Report()
        report.run("publication sweep", check_publication, args.repository, args.term_pattern)
        return report.finish()
    if args.command == "family":
        from .family import validate_family
        report = Report()
        report.add(validate_family(args.file, sibling_root=args.siblings, inventory=args.inventory))
        return report.finish()
    if args.command == "structure":
        from .structure import check_structure, print_results
        return print_results(check_structure(args.repository, deps=args.dep, term_patterns=args.term_pattern))
    report = Report()
    if args.command in ("requires", "registry", "can-apply", "examples"):
        if not report.run("plugin requirements", plugin_requires, args.plugin):
            return report.finish()
    if args.command == "registry":
        report.run("schema registry", registry_probe, args.api, args.type)
    elif args.command == "can-apply":
        case = (args.type, args.api, not args.refuse)
        if args.instance:
            case += (args.instance,)
        report.run("CanApplyAPI restrictions", can_apply, [case])
    elif args.command == "examples":
        report.run("example validation", validate_examples, args.directory, (), args.expect_errors)
    elif args.command == "links":
        report.run("local documentation links", link_check, args.directory)
    elif args.command == "terms":
        report.run("term sweep", term_sweep, args.paths, args.pattern)
    return report.finish()
