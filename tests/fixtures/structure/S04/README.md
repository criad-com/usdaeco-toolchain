# S04 seeded repository

The fixture overlays defect.json onto a fresh generated repository.

names.json covers family names, the exact kit/upstream allowlist, legacy
lowercase slugs and rejected unknown names. Rejections must identify both the
input key and repository name and list the accepted forms. kit-pins.json seeds
complete use-case and integration repositories; all 28 rules run without adapters.
The test reports the rule id and materializes the complete defective tree.
