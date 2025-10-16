"""
Shared data models for the e2neutrino toolchain.

Deutsch:
    Gemeinsame Datenmodelle für die Konvertierungs- und Ingest-Pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

DeliverySystem = str  # "sat", "cable", "terrestrial"


@dataclass(frozen=True)
class Transponder:
    """
    Normalised representation of a single DVB transponder/multiplex.

    Deutsch:
        Normalisierte Repräsentation eines Transponders / Multiplex.
    """

    key: str
    delivery: DeliverySystem
    frequency: int
    symbol_rate: Optional[int]
    polarization: Optional[str]
    fec: Optional[str]
    system: Optional[str]
    modulation: Optional[str]
    orbital_position: Optional[float]
    network_id: int
    transport_stream_id: int
    namespace: int
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Service:
    """
    Service (channel) definition, referencing a transponder via its key.

    Deutsch:
        Service-/Sender-Definition, referenziert den zugehörigen Transponder.
    """

    key: str
    name: str
    service_type: int
    service_id: int
    transponder_key: str
    original_network_id: int
    transport_stream_id: int
    namespace: int
    provider: Optional[str]
    caids: Sequence[int] = field(default_factory=tuple)
    is_radio: bool = False
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class BouquetEntry:
    """
    Entry within a bouquet/userbouquet, pointing at an Enigma2 service ref.

    Deutsch:
        Bouquet-Eintrag, verweist auf eine Enigma2 Service-Referenz.
    """

    service_ref: str
    name: Optional[str] = None


@dataclass
class Bouquet:
    """
    Bouquet (playlist) of services.

    Deutsch:
        Bouquet (Playlist) von Services.
    """

    name: str
    entries: List[BouquetEntry]
    category: str = "tv"
    source_path: Optional[Path] = None


@dataclass
class Profile:
    """
    Complete normalised profile consisting of transponders, services, bouquets.

    Deutsch:
        Vollständiges Profil mit Transpondern, Services und Bouquets.
    """

    services: Dict[str, Service] = field(default_factory=dict)
    transponders: Dict[str, Transponder] = field(default_factory=dict)
    bouquets: List[Bouquet] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def iter_services(self) -> Iterable[Service]:
        return self.services.values()

    def iter_transponders(self) -> Iterable[Transponder]:
        return self.transponders.values()

    def services_by_delivery(self, delivery: DeliverySystem) -> List[Service]:
        return [svc for svc in self.services.values() if self.transponders[svc.transponder_key].delivery == delivery]


@dataclass
class ConversionOptions:
    """
    User-supplied CLI options controlling the conversion behaviour.

    Deutsch:
        CLI-Optionen, die das Konvertierungsverhalten steuern.
    """

    api_version: int = 4
    filter_bouquets: Optional[str] = None
    include_types: Optional[Set[str]] = None
    satellites: Optional[Set[str]] = None
    combinations: Optional[Set[str]] = None
    name_scheme: str = "human"
    name_map_path: Optional[Path] = None
    include_sat: bool = True
    include_cable: bool = True
    include_terrestrial: bool = True
    fail_on_warn: bool = False
