"""
Logging configuration helpers.

Deutsch:
    Logging-Konfiguration.
"""

from __future__ import annotations

import logging
import os


def configure_logging(default_level: str = "INFO") -> None:
    """
    Configure the root logger once.

    Deutsch:
        Setzt das Root-Logging mit einfacher, CI-freundlicher Formatierung auf.
    """

    level_name = os.getenv("E2NEUTRINO_LOGLEVEL", default_level).upper()
    level = getattr(logging, level_name, logging.INFO)

    if len(logging.getLogger().handlers) > 0:
        logging.getLogger().setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
