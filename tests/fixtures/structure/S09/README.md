# S09 seeded repository

The fixture overlays defect.json onto a fresh generated repository.
The test reports the rule id and materializes the complete defective tree.

`stock_override.usda` overrides the expansion rule of the applied stock
CollectionAPI:members and must pass. `foreign_property.usda` adds an unrelated
foreign:driver beside the same override and must fail. Inheritance probes
also exercise local and sublayered bases and reject the wrong API instance.
