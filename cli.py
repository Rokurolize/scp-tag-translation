#!/usr/bin/env python3
"""Unified command-line interface for SCP Wiki Tag Translator."""

import argparse
import logging
import sys
from pathlib import Path

from src.auditor import audit_mappings
from src.config import Config
from src.generator import generate_dictionary
from src.logger import setup_logger
from src.parsers import parse_en_tags
from src.translator import TagTranslator
from src.validator import validate_business_rules


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="SCP Wiki Tag Translator - EN to JP tag mapping and translation tool")

    # Global options
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-critical output")

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # Generate command (dictionary creation)
    gen_parser = subparsers.add_parser("generate", help="Generate EN to JP dictionary")
    gen_parser.add_argument("--en-file", type=Path, help="Path to EN tags file")
    gen_parser.add_argument("--jp-dir", type=Path, help="Directory containing JP fragment files")
    gen_parser.add_argument("--output", type=Path, help="Output path for dictionary JSON")
    gen_parser.add_argument("--skip-validation", action="store_true", help="Skip business rule validation")
    gen_parser.add_argument("--skip-audit", action="store_true", help="Skip mapping audit")

    # Translate command
    translate_parser = subparsers.add_parser("translate", help="Translate tags")
    translate_parser.add_argument(
        "tags", nargs="+", help="Tags to translate (individual tags or concatenated strings from clipboard)"
    )
    translate_parser.add_argument(
        "--dict-path", type=Path, default=Path("dictionaries/en_to_jp.json"), help="Path to dictionary file"
    )

    return parser.parse_args()


def handle_generate(args, logger) -> int:
    """Handle the generate command."""
    config = Config()

    # Override config with command-line arguments
    if args.en_file:
        config.en_file = args.en_file
    if args.jp_dir:
        config.jp_directory = args.jp_dir
    if args.output:
        config.output_dir = args.output.parent
        config.output_file = args.output.name

    logger.info("=== SCP Wiki Dictionary Generator ===")

    # Generate dictionary
    logger.info("Generating dictionary...")
    try:
        dictionary, stats = generate_dictionary(
            en_file=config.en_file, jp_directory=config.jp_directory, output_path=config.output_path
        )
        logger.info(f"Generated {stats['total']} entries")
        logger.info(f"Mapped: {stats['mapped']} ({stats['coverage']}%)")
        logger.info(f"Unmapped: {stats['unmapped']}")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Dictionary generation failed: {e}")
        return 1

    # Validate business rules
    if not args.skip_validation:
        logger.info("Validating business rules...")
        critical, warnings = validate_business_rules(dictionary)

        if critical:
            logger.error(f"{len(critical)} critical issues:")
            for error in critical[:5]:
                logger.error(f"  - {error}")
        else:
            logger.info("✅ No critical issues")

        if warnings:
            logger.warning(f"{len(warnings)} warnings found")

    # Audit mappings
    if not args.skip_audit:
        logger.info("Auditing mappings...")
        try:
            en_tags = parse_en_tags(config.en_file)
            results, audit_stats = audit_mappings(
                en_tags, jp_directory=config.jp_directory, output_csv=config.audit_path
            )
            logger.info(f"Audit coverage: {audit_stats['coverage']}%")
        except FileNotFoundError as e:
            logger.error(f"Audit failed: {e}")
            return 1

    # Final result
    if not args.skip_validation and critical:
        logger.error("❌ CRITICAL ISSUES - Fix before using dictionary")
        return 1
    else:
        logger.info(f"✅ SUCCESS - Dictionary ready ({stats['coverage']}% coverage)")
        return 0


def handle_translate(args, logger) -> int:
    """Handle the translate command."""
    logger.info("=== SCP Wiki Tag Translator ===")

    # Check dictionary exists
    if not args.dict_path.exists():
        logger.error(f"Dictionary not found at {args.dict_path}")
        logger.error("Run 'generate' command first to create dictionary")
        return 1

    try:
        # Initialize translator
        translator = TagTranslator(args.dict_path)
        stats = translator.get_stats()
        logger.info(f"Loaded dictionary: {stats['mapped_entries']}/{stats['dictionary_size']} entries")

        # Translate each input
        results = []
        for tag_input in args.tags:
            translation = translator.translate_single(tag_input)
            results.append((tag_input, translation))

            if tag_input == translation:
                print(f"{tag_input} → (unchanged)")
            else:
                print(f"{tag_input} → {translation}")

        # Summary
        changed = sum(1 for orig, trans in results if orig != trans)
        logger.info(f"Translated {changed}/{len(results)} inputs")

        if args.verbose:
            seg_stats = stats["segmentation_stats"]
            logger.info(
                f"Segmentation: {seg_stats['segments_successful']}/{seg_stats['segments_attempted']} successful"
            )

        return 0

    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return 1


def main() -> int:
    """Main CLI entry point."""
    args = parse_args()

    # Configure logging
    if args.quiet:
        log_level = logging.WARNING
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logger = setup_logger(level=log_level)

    # Route to appropriate handler
    if args.command == "generate":
        return handle_generate(args, logger)
    elif args.command == "translate":
        return handle_translate(args, logger)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
