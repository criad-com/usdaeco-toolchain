# S01 seeded repository

The fixture overlays defect.json onto a fresh generated repository.

README wording cases accept each SPDX identifier and full licence name, while
rejecting mismatched, ambiguous and partial names. Manifest declarations still
require SPDX identifiers and LICENSE still requires complete terms.
The test reports the rule id and materializes the complete defective tree.

licences.json additionally covers MIT, declared Apache-2.0, BSD-3-Clause,
legacy inference, mismatched declarations, missing text and invalid metadata.
The complete canonical texts live in tools/usdaeco_check/licences/; the tests
also remove operative terms to ensure titles alone cannot pass.
