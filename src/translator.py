"""Tag translator with automatic segmentation for concatenated input."""

import json
import time
from functools import lru_cache
from pathlib import Path

from .logger import logger


class TrieNode:
    """Node in the Trie structure for efficient tag lookup."""

    def __init__(self):
        self.children = {}
        self.is_word = False
        self.word = None


class TagTranslator:
    """
    Translator that handles both individual tags and concatenated tag strings.
    
    Combines translation dictionary with trie-based segmentation for handling
    clipboard input where tags are concatenated without spaces.
    """

    def __init__(self, dictionary_path: Path):
        """Initialize translator with dictionary and build trie for segmentation."""
        self.dictionary_path = dictionary_path
        self.dictionary = self._load_dictionary()
        self.trie = self._build_trie()
        
        # Pre-compute dictionary statistics for O(1) access
        self._dictionary_size = len(self.dictionary)
        self._mapped_entries = sum(1 for v in self.dictionary.values() if v is not None)
        
        self.stats = {
            "segments_attempted": 0,
            "segments_successful": 0,
        }
        logger.debug(f"Loaded {self._dictionary_size} tags from {self.dictionary_path}")
        logger.debug(f"Mapped entries: {self._mapped_entries}/{self._dictionary_size} ({self._mapped_entries/self._dictionary_size*100:.1f}%)")

    def _load_dictionary(self) -> dict[str, str | None]:
        """Load translation dictionary from JSON file."""
        if not self.dictionary_path.exists():
            raise FileNotFoundError(f"Dictionary not found: {self.dictionary_path}")

        try:
            with self.dictionary_path.open("r", encoding="utf-8") as f:
                dictionary = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from {self.dictionary_path}: {e}")

        if not isinstance(dictionary, dict):
            raise ValueError(f"Dictionary must be a JSON object, got {type(dictionary)}")

        self._validate_dictionary(dictionary)
        return dictionary
    
    def _validate_dictionary(self, dictionary: dict) -> None:
        """Validate dictionary structure and content."""
        for key, value in dictionary.items():
            if not isinstance(key, str):
                raise ValueError(f"Dictionary key must be string, got {type(key)}: {key}")
            if value is not None and not isinstance(value, str):
                raise ValueError(f"Dictionary value must be string or None, got {type(value)}: {value}")

    def _build_trie(self) -> TrieNode:
        """Build trie from dictionary keys for efficient segmentation."""
        root = TrieNode()
        for tag in self.dictionary:
            node = root
            for char in tag.lower():
                if char not in node.children:
                    node.children[char] = TrieNode()
                node = node.children[char]
            node.is_word = True
            node.word = tag
        return root

    def _find_all_prefixes(self, text: str) -> list[str]:
        """Find all valid tag prefixes, longest first."""
        prefixes = []
        node = self.trie
        for i, char in enumerate(text.lower()):
            if char not in node.children:
                break
            node = node.children[char]
            if node.is_word:
                prefixes.append(node.word)
        return prefixes[::-1]  # Reverse for longest-first

    @lru_cache(maxsize=1024)  # Limit cache size to prevent memory exhaustion
    def _segment_recursive(self, text: str) -> tuple[str, ...] | None:
        """Recursive segmentation with LRU cache, trying longest matches first."""
        if not text:
            return ()

        # Get all possible prefixes, longest first
        prefixes = self._find_all_prefixes(text)
        
        # Try each prefix, longest first
        for prefix in prefixes:
            suffix_result = self._segment_recursive(text[len(prefix):])
            if suffix_result is not None:
                return (prefix,) + suffix_result

        # No valid segmentation found
        return None

    def segment(self, concatenated: str) -> list[str] | None:
        """
        Segment concatenated string into known tags using backtracking.

        Args:
            concatenated: String like "autonomousectoentropiceuclid"

        Returns:
            List of segmented tags if successful, None otherwise
        """
        self.stats["segments_attempted"] += 1

        result = self._segment_recursive(concatenated.lower())
        if result is None:
            logger.debug(f"Cannot segment: '{concatenated}'")
            return None

        self.stats["segments_successful"] += 1
        result_list = list(result)  # Convert tuple back to list
        if logger.isEnabledFor(10):  # DEBUG level
            logger.debug(f"Segmented '{concatenated}' into {len(result_list)} tags")
        return result_list

    def translate_single(self, tag: str) -> str:
        """
        Translate a single tag or concatenated tag string.

        Args:
            tag: Individual tag ("safe") or concatenated string ("autonomouseuclid")

        Returns:
            Translated result - individual translation or concatenated translations
        """
        start_time = time.perf_counter()
        
        # Direct lookup first (most common case)
        if tag in self.dictionary:
            translation = self.dictionary[tag]
            elapsed = time.perf_counter() - start_time
            if logger.isEnabledFor(10):  # DEBUG level
                logger.debug(f"Direct lookup for '{tag}' took {elapsed*1000:.2f}ms")
            return translation if translation is not None else tag

        # Try segmentation for concatenated input
        segment_start = time.perf_counter()
        segments = self.segment(tag)
        segment_time = time.perf_counter() - segment_start
        
        if segments and len(segments) > 1:
            if logger.isEnabledFor(10):  # DEBUG level
                logger.debug(f"Segmentation of '{tag}' into {len(segments)} parts took {segment_time*1000:.2f}ms")

            # Translate each segment
            translations = []
            for segment in segments:
                segment_translation = self.dictionary.get(segment, segment)
                if segment_translation is None:
                    segment_translation = segment
                translations.append(segment_translation)

            elapsed = time.perf_counter() - start_time
            if logger.isEnabledFor(10):  # DEBUG level
                logger.debug(f"Total translation of concatenated '{tag}' took {elapsed*1000:.2f}ms")
            # Return space-separated format for Wikidot tag input
            return " ".join(translations)

        # Return original if no translation or segmentation possible
        elapsed = time.perf_counter() - start_time
        if logger.isEnabledFor(10):  # DEBUG level
            logger.debug(f"No translation for '{tag}' (took {elapsed*1000:.2f}ms)")
        return tag

    def translate_batch(self, tags: list[str]) -> list[tuple[str, str]]:
        """
        Translate multiple tags.

        Args:
            tags: List of tags to translate

        Returns:
            List of (original, translated) tuples
        """
        results = []
        for tag in tags:
            translated = self.translate_single(tag)
            results.append((tag, translated))
        return results

    @property
    def success_rate(self) -> float:
        """Get segmentation success rate."""
        if self.stats["segments_attempted"] == 0:
            return 0.0
        return self.stats["segments_successful"] / self.stats["segments_attempted"]
    
    def reset_stats(self) -> None:
        """Reset segmentation statistics."""
        self.stats["segments_attempted"] = 0
        self.stats["segments_successful"] = 0
    
    def get_stats(self) -> dict:
        """Return comprehensive translator statistics (O(1) access)."""
        return {
            "dictionary_size": self._dictionary_size,
            "mapped_entries": self._mapped_entries,
            "segmentation_stats": dict(self.stats)  # Convert to regular dict
        }