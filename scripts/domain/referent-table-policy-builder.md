# Policy-builder referent table

| Artifact | Referent | Role | Name |
| --- | --- | --- | --- |
| `scripts/domain/policy_builder.py` | Repository policy documents | Validated override, replacement, and crosswalk inputs used to assemble the runtime mapping policy | `MappingPolicyInputs` |
| `scripts/domain/policy_builder.py` | Policy assembly boundary | Converts validated source records and policy documents into `MappingPolicy` | `build_mapping_policy` |
| `scripts/domain/policy_builder.py` | Crosswalk policy parser | Filters official crosswalk labels to current JP tags before merge | `parse_official_crosswalk` |
