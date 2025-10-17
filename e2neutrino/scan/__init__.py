"""
Scanfile normalisation and writer helpers.

Deutsch:
    Hilfsfunktionen rund um Scanfiles (Kabel/Terrestrik).
"""

from __future__ import annotations

from .normalizer import (
    ScanfileBundle,
    ScanfileDedupDecision,
    ScanfileNormalizationResult,
    deduplicate_scan_entries,
    normalize_scan_entries,
)
from .writer import ScanfileError, ScanfileWriteReport, write_scanfiles

__all__ = [
    "ScanfileBundle",
    "ScanfileDedupDecision",
    "ScanfileNormalizationResult",
    "ScanfileWriteReport",
    "ScanfileError",
    "deduplicate_scan_entries",
    "normalize_scan_entries",
    "write_scanfiles",
]
