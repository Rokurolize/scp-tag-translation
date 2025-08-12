#!/usr/bin/env python3
"""Command-line interface for SCP Wiki Tag Translator."""

import argparse
import logging
import sys
from pathlib import Path

from src.auditor import audit_mappings
from src.config import Config
from src.generator import generate_dictionary
from src.logger import setup_logger
from src.parsers import parse_en_tags
from src.validator import validate_business_rules


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="SCP Wiki Tag Translator - EN to JP tag mapping tool")

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-critical output")

    parser.add_argument(
        "--en-file", type=Path, help="Path to EN tags file (default: 05command_tech-hub-tag-list.wikidot)"
    )

    parser.add_argument(
        "--jp-dir", type=Path, help="Directory containing JP fragment files (default: current directory)"
    )

    parser.add_argument(
        "--output", type=Path, help="Output path for dictionary JSON (default: dictionaries/en_to_jp.json)"
    )

    parser.add_argument("--skip-validation", action="store_true", help="Skip business rule validation")

    parser.add_argument("--skip-audit", action="store_true", help="Skip mapping audit")

    return parser.parse_args()


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

    # Load configuration
    config = Config()

    # Override config with command-line arguments
    if args.en_file:
        config.en_file = args.en_file
    if args.jp_dir:
        config.jp_directory = args.jp_dir
    if args.output:
        config.output_dir = args.output.parent
        config.output_file = args.output.name

    logger.info("=== SCP Wiki Tag Translator ===")

    # Generate dictionary
    logger.info("Generating dictionary...")
    try:
        dictionary, stats = generate_dictionary(
            en_file=config.en_file, jp_directory=config.jp_directory, output_path=config.output_path
        )
        logger.info(f"Total entries: {stats['total']}")
        logger.info(f"Mapped: {stats['mapped']} ({stats['coverage']}%)")
        logger.info(f"Unmapped: {stats['unmapped']}")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Failed to generate dictionary: {e}")
        return 1

    # Validate business rules
    if not args.skip_validation:
        logger.info("Validating business rules...")
        critical, warnings = validate_business_rules(dictionary)

        if critical:
            logger.error(f"{len(critical)} critical issues found:")
            for error in critical[:5]:
                logger.error(f"  - {error}")
            if len(critical) > 5:
                logger.error(f"  ... and {len(critical) - 5} more")
        else:
            logger.info("✅ No critical issues")

        if warnings:
            logger.warning(f"{len(warnings)} warnings found")
            for warning in warnings[:3]:
                logger.debug(f"  - {warning}")

    # Audit mappings
    if not args.skip_audit:
        logger.info("Auditing mappings...")
        try:
            en_tags = parse_en_tags(config.en_file)
            results, audit_stats = audit_mappings(
                en_tags, jp_directory=config.jp_directory, output_csv=config.audit_path
            )
            logger.info(f"Coverage: {audit_stats['coverage']}%")
            logger.debug(f"Found exact: {audit_stats['found_exact']}")
            logger.debug(f"Found without underscore: {audit_stats['found_without_underscore']}")
            logger.debug(f"Not found: {audit_stats['not_found']}")
        except FileNotFoundError as e:
            logger.error(f"Audit failed: {e}")
            return 1

    # Final verdict
    if not args.skip_validation and critical:
        logger.error("❌ FAILED: Critical issues must be fixed")
        return 1
    elif stats["coverage"] < 80:
        logger.warning(f"⚠️  Coverage is {stats['coverage']}% (target: 80%+)")
        return 1
    else:
        logger.info(f"✅ PASSED: {stats['coverage']}% coverage")
        return 0


if __name__ == "__main__":
    sys.exit(main())
