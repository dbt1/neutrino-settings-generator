"""Click-based command line entry point for e2neutrino."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Iterable, Optional, Set

import click

from . import __version__
from .converter import ConversionError, ConversionResult, run_convert
from .ingest import IngestError, IngestResult, run_ingest
from .logging_conf import configure_logging


@click.group(help="Enigma2 → Neutrino conversion toolkit")
@click.version_option(__version__)
@click.option("--verbose", is_flag=True, help="Enable verbose logging output.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """
    Root CLI group configuring logging before subcommands execute.
    """

    configure_logging("DEBUG" if verbose else "INFO")
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command("convert")
@click.option("--input", "inp", required=True, type=click.Path(path_type=Path, exists=True, file_okay=False))
@click.option("--output", "out", required=True, type=click.Path(path_type=Path, file_okay=False))
@click.option("--api-version", default=4, show_default=True, type=int, help="Target Neutrino API version.")
@click.option("--filter-bouquets", default=None, help="Regex used to select bouquets, leave empty for all.")
@click.option(
    "--include-types",
    default="S,C,T",
    show_default=True,
    help="Comma separated filter of delivery types (S,C,T).",
)
@click.option("--satellites", default=None, help="Comma separated list of satellite identifiers to include.")
@click.option("--combinations", default=None, help="Comma separated satellite combinations (NameA+NameB).")
@click.option("--name-scheme", default="human", type=click.Choice(["human", "code"]), show_default=True)
@click.option("--name-map", default=None, type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option("--no-sat", is_flag=True, default=False, help="Disable generation of satellite outputs.")
@click.option("--no-cable", is_flag=True, default=False, help="Disable generation of cable outputs.")
@click.option("--no-terrestrial", is_flag=True, default=False, help="Disable generation of terrestrial outputs.")
@click.option("--fail-on-warn", is_flag=True, default=False, help="Treat validation warnings as fatal.")
@click.option("--strict", is_flag=True, default=False, help="Enable strict mode (warnings become errors).")
@click.option(
    "--abort-on-empty/--allow-empty",
    default=False,
    show_default=True,
    help="Abort when generated outputs fall below minimum service thresholds.",
)
@click.option("--min-services-sat", default=50, show_default=True, type=int, help="Minimum SAT services required.")
@click.option(
    "--min-services-cable",
    default=20,
    show_default=True,
    type=int,
    help="Minimum cable services required.",
)
@click.option(
    "--min-services-terrestrial",
    default=20,
    show_default=True,
    type=int,
    help="Minimum terrestrial services required.",
)
@click.option("--include-stale", is_flag=True, default=False, help="Allow converting stale sources without aborting.")
@click.option("--stale-after-days", default=120, show_default=True, type=int, help="Staleness threshold in days.")
@click.option(
    "--emit-scanfiles/--no-emit-scanfiles",
    default=True,
    show_default=True,
    help="Enable generation of cable.xml and terrestrial.xml scanfiles.",
)
@click.option(
    "--providers",
    default=None,
    help="Comma separated list of cable providers to include in scanfiles.",
)
@click.option(
    "--regions",
    default=None,
    help="Comma separated list of terrestrial regions to include in scanfiles.",
)
@click.option(
    "--strict-scanfiles",
    is_flag=True,
    default=False,
    help="Fail conversion when scanfile thresholds are not satisfied.",
)
@click.option(
    "--min-scanfile-entries-cable",
    default=10,
    show_default=True,
    type=int,
    help="Minimum cable transponders per provider (only enforced with --strict-scanfiles).",
)
@click.option(
    "--min-scanfile-entries-terrestrial",
    default=3,
    show_default=True,
    type=int,
    help="Minimum terrestrial multiplexes per region (only enforced with --strict-scanfiles).",
)
def cli_convert(**kwargs: Any) -> None:
    """Convert Enigma2-like folders into Neutrino XML outputs."""

    try:
        result: ConversionResult = run_convert(**_transform_convert_kwargs(kwargs))
    except ConversionError as exc:
        raise click.ClickException(str(exc)) from exc
    logging.getLogger(__name__).info(
        "conversion completed with %d warnings -> %s", len(result.warnings), result.output_path
    )


@cli.command("ingest")
@click.option("--config", "config_path", required=True, type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option("--out", "out_dir", required=True, type=click.Path(path_type=Path, file_okay=False))
@click.option("--only", default=None, help="Comma separated list of source IDs to process.")
@click.option(
    "--cache",
    default=Path("/tmp/e2n-cache"),
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False),
    help="Cache directory used for HTTP metadata.",
)
def cli_ingest(**kwargs: Any) -> None:
    """Fetch and normalise upstream sources (git/http/file)."""

    try:
        results: list[IngestResult] = run_ingest(**_transform_ingest_kwargs(kwargs))
    except IngestError as exc:
        raise click.ClickException(str(exc)) from exc
    logger = logging.getLogger(__name__)
    logger.info("ingested %d profiles", len(results))
    for item in results:
        logger.info("%s/%s -> %s", item.source_id, item.profile_id, item.output_path)


def _transform_convert_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    mutated = dict(kwargs)
    mutated["include_types"] = _normalise(mutated.get("include_types"))
    mutated["satellites"] = _normalise(mutated.get("satellites"))
    mutated["combinations"] = _normalise(mutated.get("combinations"))
    mutated["providers"] = _normalise(mutated.get("providers"))
    mutated["regions"] = _normalise(mutated.get("regions"))
    return mutated


def _transform_ingest_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    mutated = dict(kwargs)
    mutated["only"] = _normalise(mutated.get("only"))
    cache_value = mutated.get("cache")
    if cache_value is not None:
        mutated["cache"] = Path(cache_value)
    return mutated


def _normalise(value: Optional[Any]) -> Optional[Set[str]]:
    if value is None:
        return None
    if isinstance(value, (set, frozenset)):
        return set(value)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Path)):
        return {str(item).strip() for item in value if str(item).strip()}
    text = str(value)
    return {item.strip() for item in text.split(",") if item and item.strip()} or None


def main(argv: Optional[Iterable[str]] = None) -> int:
    """
    Backwards compatible entry point returning an exit code for setuptools console scripts.
    """

    argv_list = list(argv or sys.argv[1:])
    try:
        cli.main(args=argv_list, prog_name="e2neutrino", standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return 1
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
