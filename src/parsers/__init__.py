"""Tag parsers for EN and JP Wikidot sources."""

from .en_parser import parse_en_tags
from .jp_parser import parse_jp_mappings

__all__ = ["parse_en_tags", "parse_jp_mappings"]
