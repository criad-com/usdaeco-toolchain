# Preparing a public release

`usdaeco-publish` produces an orphan repository from one exact source tag.
Report mode is the default. It clones the source into temporary storage, reads
Git blobs without running repository code, and writes a new destination containing
`tree/`, `report.json` and `report.md`. The report lists every file, byte size,
SHA-256, licence file and sweep finding. Its public URL column and JSON
`public_url` field name the intended repository under `github.com/criad-com`;
they do not prove that the destination exists. Schema library names map to
their family repository names, including `usdAeco` to `usdaeco-core`.
The source checkout is never changed.
Neither original history nor original authors, commit messages, remotes, hooks
or Git configuration enter the new repository. The new commit and annotated tag
use a fixed public identity and timestamp for deterministic preparation.

From a source checkout, use an existing USD-enabled Python with Pillow; no package install
or setuptools is needed. The installed entry point is `usdaeco-publish`.

```sh
export PYTHON=python3
env -u PYTHONPATH "$PYTHON" tools/publish.py ../usdaeco-core --tag v0.9.2 --output ../publication/core-v0.9.2 --report
```

For a fresh source clone, obtain its URL from local configuration rather than
putting deployment addresses in this repository:

```sh
git clone --depth 1 --branch "$TAG" "$SOURCE_URL" "../release-sources/$REPO"
env -u PYTHONPATH "$PYTHON" tools/publish.py "../release-sources/$REPO" --tag "$TAG" --output "../publication/$REPO-$TAG" --report
```

Repeat for each non-private, tagged entry in the selected family.json. An absent
tag is NOT RUN, never PASS. The tool makes its own fresh clone even when given
a checkout. The destination must not exist and must be outside that checkout.
The report belongs outside `tree/`, so its generated inventory does not change
the tree under review. A failed sweep exits nonzero and leaves the candidate and
report for inspection, without creating a Git repository or pushing. Missing
tags or manifests fail during preparation. Fix the source in its owning repo
and tag a new release; the tool does not rewrite content to suppress findings.

The sweep checks every selected file, including tracked `dist/`, hidden files,
filenames and committed result layers. USD crates are decoded with stock Sdf in
an isolated process and checked as text. Other binary files have printable and
UTF-16 strings checked. Pillow decodes image metadata, including compressed PNG
text and EXIF; image labels still require inspection of the source
artwork, since the tool performs no OCR. Compressed archives fail closed until a
recursive archive policy is available. Private terms, private addresses,
deployment hostnames, local filesystem paths and MAC addresses fail. Add
organization-specific regexes with repeated `--term-pattern`. Reports give
locations and categories without echoing matched text; unsafe filenames are
represented by a hash. The S25 copyright attribution exception remains scoped.
The exact public org slug `criad-com` is allowed; the bare company term and
caller-supplied patterns remain checked under the S25 rules.

Files are capped at 10,000,000 bytes and the selected tree at 50,000,000 bytes.
Internal relative symlinks to included files or directories are retained;
external, dangling, ancestor and cyclic links and submodules fail. Executable bits survive.
The fixed exclusions are root operational notes and local lockfiles, root
`out/`, `build/`, Nix result links, and VCS, environment and Python cache trees.
Nested `examples/*/result/layers/out/` and published `dist/` remain included.
The report lists exclusions. Source ignore rules cannot silently drop inspected
files when the orphan commit is staged. Licences are detected from complete S01
terms, verified against declared metadata and inventoried without modification.

After explicit approval for this repository, tag and destination, run:

```sh
env -u PYTHONPATH "$PYTHON" tools/publish.py "../release-sources/$REPO" --tag "$TAG" --output "../approved-publication/$REPO-$TAG" --push --remote "$PUBLIC_REMOTE"
```

`--push` requires an explicit remote URL or path, never an implicit source remote.
It runs the same checks again and sends one atomic update of `main` and the
selected tag, without force. It does not create repositories or change their
visibility. An existing unrelated public history is refused; updates to a public
history need a separately reviewed release process. The metadata repository is
always refused, including when its source path is renamed.

Run the sweep as an independent gate with the installed
`usdaeco-check publication .`, or from source:

```sh
env -u PYTHONPATH "$PYTHON" tools/check_publication.py .
```

## Regenerating the family index

The release gate owns family.json. Pass its path explicitly; this tool does not
select newer tags or mutate the release train. Tagged library manifests,
README purposes and use-case status paragraphs are read through Git, regardless
of the working branch. For untagged entries, available checkout metadata is
clearly labelled unreleased. Private metadata contents are never read or linked.
The captured source cards retain hashes and revisions for reproduction. The
index reports actual licences at the selected tags, including older releases.

```sh
env -u PYTHONPATH "$PYTHON" tools/family_readme.py --family ../usdaeco-scenarios/family.json --repos ../release-sources
env -u PYTHONPATH "$PYTHON" tools/family_readme.py --family ../usdaeco-scenarios/family.json --repos ../release-sources --check
env -u PYTHONPATH "$PYTHON" check.py --family ../usdaeco-scenarios/family.json --family-repos ../release-sources
```

Commit both `docs/family/README.md` and `docs/family/index.json`. The default gate
checks rendering against committed source cards, so it works without sibling
checkouts. Supplying the two source arguments additionally checks the cards
against the live train and tagged files; this is the release freshness check.
Neither check asserts that links to intended public mirrors already resolve.

Board v0.1.2 already provides the static HTML snapshot, the 50 MB cap, local-link
checks, image metadata removal and the export sweep. Follow its
[static-export contract](https://github.com/criad-com/usdaeco-board/blob/v0.1.2/docs/static-export.md).
This release uses that existing interface and does not modify the board.
