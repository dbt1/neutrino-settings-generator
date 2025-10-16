"""
Command line entry point.

Deutsch:
    Kommandozeilen-Einstiegspunkt.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .converter import ConversionError, ConversionOptions, convert
from .ingest import IngestError, ingest
from .logging_conf import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="e2neutrino",
        description="Enigma2 → Neutrino conversion toolkit",
    )
    parser.add_argument("--version", action="version", version=f"e2neutrino {__version__}")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="enable verbose logging / detailliertes Logging aktivieren",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    conv = subparsers.add_parser("convert", help="convert Enigma2 profile to Neutrino settings")
    conv.add_argument("--input", required=True, type=Path, help="input directory mit lamedb/bouquets")
    conv.add_argument("--output", required=True, type=Path, help="output directory for Neutrino settings")
    conv.add_argument("--api-version", type=int, default=4, help="Neutrino API version (default: 4)")
    conv.add_argument("--filter-bouquets", help="Regex to filter bouquets")
    conv.add_argument("--include-types", help="Comma separated filter of delivery types (S,C,T)")
    conv.add_argument("--satellites", help="Comma separated list of satellite codes/names to include")
    conv.add_argument("--combinations", help="Comma separated satellite combinations (NameA+NameB)")
    conv.add_argument("--name-scheme", choices=["human", "code"], default="human")
    conv.add_argument("--name-map", type=Path, help="JSON/YAML mapping for friendly names")
    conv.add_argument("--no-sat", action="store_true", help="disable satellite outputs")
    conv.add_argument("--no-cable", action="store_true", help="disable cable outputs")
    conv.add_argument("--no-terrestrial", action="store_true", help="disable terrestrial outputs")
    conv.add_argument("--fail-on-warn", action="store_true", help="treat validation warnings as fatal")

    ing = subparsers.add_parser("ingest", help="ingest official sources")
    ing.add_argument("--config", required=True, type=Path, help="YAML file describing sources")
    ing.add_argument("--out", required=True, type=Path, help="working directory to place normalized profiles")
    ing.add_argument("--only", help="Comma separated list of source IDs to process")
    ing.add_argument("--cache", type=Path, help="cache directory for HTTP/git")

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging("DEBUG" if args.verbose else "INFO")

    if args.command == "convert":
        options = ConversionOptions(
            api_version=args.api_version,
            filter_bouquets=args.filter_bouquets,
            include_types=_split(args.include_types),
            satellites=_split(args.satellites),
            combinations=_split(args.combinations),
            name_scheme=args.name_scheme,
            name_map_path=args.name_map,
            include_sat=not args.no_sat,
            include_cable=not args.no_cable,
            include_terrestrial=not args.no_terrestrial,
            fail_on_warn=args.fail_on_warn,
        )
        try:
            result = convert(args.input, args.output, options)
        except ConversionError as exc:
            logging.getLogger(__name__).error(str(exc))
            return 2
        logging.getLogger(__name__).info("conversion completed with %d warnings", len(result.warnings))
        return 0

    if args.command == "ingest":
        only = _split(args.only)
        try:
            results = ingest(args.config, args.out, only=only, cache_dir=args.cache)
        except IngestError as exc:
            logging.getLogger(__name__).error(str(exc))
            return 3
        logging.getLogger(__name__).info("ingested %d profiles", len(results))
        logger = logging.getLogger(__name__)
        for ingest_result in results:
            logger.info("%s/%s -> %s", ingest_result.source_id, ingest_result.profile_id, ingest_result.output_path)
        return 0

    parser.print_help()
    return 1


def _split(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


if __name__ == "__main__":
    sys.exit(main())
