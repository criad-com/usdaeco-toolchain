# S08 seeded repository

The fixture overlays defect.json onto a fresh generated repository.
The test reports the rule id and materializes the complete defective tree.

ownership.json adds four manifest cases: declared extras pass, undeclared extras
fail, malformed declarations fail, and an unused namespace warns without failing.
The tests materialize each case with both single-apply and multiple-apply APIs
and check S03, S08 and S09 together.
