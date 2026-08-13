| Source | Purpose | Concrete Referent | Role | Ordering | Candidate Term | First-Use Definition |
| --- | --- | --- | --- | --- | --- | --- |
| Two command-local staging-write findings | Centralize safe UTF-8 text serialization for generated outputs | The operation that fully writes a UTF-8 string to a same-directory temporary file and atomically replaces its destination | Means | render content, atomically serialize text, then complete any enclosing batch publication | write_text | `write_text` refers to atomically serializing a complete UTF-8 string to its destination. |
