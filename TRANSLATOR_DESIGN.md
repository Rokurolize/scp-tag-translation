# SCP Tag Translator Engine Design

## Core Requirements

The translator must correctly handle:

1. **Simple Tags**: Direct dictionary lookup (`safe` → `safe`)
2. **Compound Tags**: Split and translate parts (`fireinscription` → `fire` + `inscription` → `火災` + `碑文`)
3. **Longest Match**: Prefer longer dictionary matches over shorter ones
4. **Unmapped Tags**: Return original tag if no mapping exists
5. **Multiple Input**: Handle lists of tags efficiently

## Design Architecture

### 1. Translation Engine Core

```python
class TagTranslator:
    def __init__(self, dictionary: dict[str, str]):
        self.dictionary = dictionary
        self.sorted_tags = sorted(dictionary.keys(), key=len, reverse=True)  # Longest first

    def translate_single(self, tag: str) -> str:
        """Translate a single tag with compound splitting."""

    def translate_batch(self, tags: list[str]) -> dict[str, str]:
        """Translate multiple tags efficiently."""
```

### 2. Compound Tag Algorithm

For compound tags like `fireinscription`:

1. **Try exact match first**: Check if `fireinscription` exists in dictionary
2. **Longest match splitting**: Try all possible splits, prefer longer components:
   - `fire` + `inscription` (lengths: 4, 11) → Total: 15
   - `fir` + `einscription` (if both existed) → Total: 14
   - Choose the split with highest total length of matched components
3. **Fallback**: If no valid split found, return original tag

### 3. Performance Considerations

- **Pre-sorted dictionary**: Sort keys by length (descending) for efficient longest-match
- **Memoization**: Cache results for repeated tags
- **Early termination**: Stop searching when exact match found

### 4. Error Handling

- **Partial matches**: If only some components of compound tag match, translate what we can
- **Invalid input**: Handle empty strings, None values gracefully
- **Dictionary errors**: Fail gracefully if dictionary is corrupted

## Test Cases

### Basic Translation

```python
translator.translate_single("safe") == "safe"
translator.translate_single("adult") == "アダルト"
translator.translate_single("nonexistent") == "nonexistent"  # Unchanged
```

### Compound Tag Splitting

```python
translator.translate_single("fireinscription") == "火災碑文"  # fire + inscription
translator.translate_single("safeketer") == "safeketer"  # Can't split meaningfully
```

### Batch Processing

```python
translator.translate_batch(["safe", "fireinscription", "adult"]) == {
    "safe": "safe",
    "fireinscription": "火災碑文",
    "adult": "アダルト"
}
```

## Integration Points

1. **CLI Interface**: Add `translate` subcommand
2. **Web Interface**: JavaScript API compatibility
3. **Validation**: Ensure translated tags are valid JP wiki tags

## Success Criteria

1. **Accuracy**: 95%+ correct translation on known test cases
2. **Performance**: Handle 1000+ tags in <1 second
3. **Robustness**: Never crash on invalid input
4. **Maintainability**: Clear separation between dictionary loading and translation logic
