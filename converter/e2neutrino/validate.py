"""
Validation helpers for profiles and output.

Deutsch:
    Validierungshilfen für Profile und generierte Dateien.
"""

from __future__ import annotations

import logging
from typing import Iterable, List

from .models import Profile, Service, Transponder

log = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails. / Wird geworfen, wenn die Validierung fehlschlägt."""


def validate_profile(profile: Profile) -> List[str]:
    """
    Run consistency checks. Returns warnings (empty list on perfect data).

    Deutsch:
        Führt Konsistenzprüfungen aus. Gibt Warnungen zurück.
    """

    warnings: List[str] = []

    if not profile.services:
        warnings.append("profile contains no services")
    if not profile.transponders:
        warnings.append("profile contains no transponders")

    # Ensure service references are resolvable.
    for svc in profile.services.values():
        if svc.transponder_key not in profile.transponders:
            msg = f"service {svc.name} references unknown transponder {svc.transponder_key}"
            warnings.append(msg)

    # Validate duplicate service ids per TS.
    _validate_duplicate_services(profile.services.values(), profile.transponders, warnings)

    return warnings


def _validate_duplicate_services(
    services: Iterable[Service],
    transponders: dict[str, Transponder],
    warnings: List[str],
) -> None:
    seen: dict[tuple[int, int, int], Service] = {}
    for svc in services:
        key = (svc.original_network_id, svc.transport_stream_id, svc.service_id)
        if key in seen:
            other = seen[key]
            warnings.append(
                f"duplicate service triple {key}: {svc.name} vs {other.name}",
            )
        else:
            seen[key] = svc
