"""Configuration management for SCP Wiki Tag Translator."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    """Configuration for tag translator."""

    # Input files
    en_file: Path = Path("05command_tech-hub-tag-list.wikidot")
    jp_pattern: str = "scp-jp*tag-list*.wikidot"
    jp_directory: Path = Path(".")

    # Output files
    output_dir: Path = Path("dictionaries")
    output_file: str = "en_to_jp.json"
    audit_csv: str = "mapping_audit.csv"

    # Validation rules
    object_classes: list[str] = None
    required_tags: list[str] = None

    def __post_init__(self):
        """Initialize default lists."""
        if self.object_classes is None:
            self.object_classes = [
                "safe",
                "euclid",
                "keter",
                "thaumiel",
                "apollyon",
                "archon",
                "neutralized",
                "explained",
            ]

        if self.required_tags is None:
            self.required_tags = ["scp", "tale", "goi-format", "supplement", "joke"]

    @property
    def output_path(self) -> Path:
        """Get full output path for dictionary."""
        return self.output_dir / self.output_file

    @property
    def audit_path(self) -> Path:
        """Get full path for audit CSV."""
        return Path(self.audit_csv)
