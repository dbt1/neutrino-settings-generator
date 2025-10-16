"""
Adapter for legacy Neutrino (services.xml/bouquets.xml) input.

Deutsch:
    Adapter für bestehende Neutrino-Eingaben (services.xml/bouquets.xml).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
from xml.etree import ElementTree as ET

from ..models import Bouquet, BouquetEntry, Profile, Service, Transponder
from . import BaseAdapter, register


class NeutrinoAdapter(BaseAdapter):
    name = "neutrino"

    def ingest(self, source_path: Path, config: Dict[str, object]) -> List[Profile]:
        services_path = Path(source_path) / "services.xml"
        bouquets_path = Path(source_path) / "bouquets.xml"
        if not services_path.exists() or not bouquets_path.exists():
            raise FileNotFoundError("neutrino adapter expects services.xml and bouquets.xml")

        profile = _parse_neutrino(services_path, bouquets_path)
        profile.metadata.setdefault("format", "neutrino")
        profile.metadata.setdefault("profile_id", Path(source_path).name)
        profile.metadata.setdefault("source_path", str(source_path))
        return [profile]


def _parse_neutrino(services_path: Path, bouquets_path: Path) -> Profile:
    services: Dict[str, Service] = {}
    transponders: Dict[str, Transponder] = {}

    tree = ET.parse(services_path)
    root = tree.getroot()
    for container in root:
        category = container.tag  # satellites/cables/terrestrials
        for group in container:
            trans_nodes = group.findall("transponder")
            for trans_node in trans_nodes:
                trans_key = trans_node.get("key") or _derive_trans_key(trans_node, group)
                delivery = _delivery_from_container(category)
                transponders[trans_key] = Transponder(
                    key=trans_key,
                    delivery=delivery,
                    frequency=int(trans_node.get("frequency") or 0),
                    symbol_rate=_optional_int(trans_node.get("symbol_rate")),
                    polarization=trans_node.get("polarization"),
                    fec=trans_node.get("fec"),
                    system=trans_node.get("system"),
                    modulation=trans_node.get("modulation"),
                    orbital_position=_optional_float(group.get("position") or trans_node.get("position")),
                    network_id=int(trans_node.get("onid") or 0),
                    transport_stream_id=int(trans_node.get("tsid") or 0),
                    namespace=int(trans_node.get("namespace", "0"), 16) if trans_node.get("namespace") else 0,
                    extra={"display_name": group.get("name", "")},
                )
                for svc_node in trans_node.findall("service"):
                    sid = int(svc_node.get("sid") or svc_node.get("id") or 0)
                    svc_key = f"{trans_key}:{sid:04x}"
                    namespace_attr = svc_node.get("namespace")
                    namespace = (
                        int(namespace_attr, 16)
                        if namespace_attr
                        else transponders[trans_key].namespace
                    )
                    services[svc_key] = Service(
                        key=svc_key,
                        name=svc_node.get("name") or f"Service {sid}",
                        service_type=int(svc_node.get("type") or 1),
                        service_id=sid,
                        transponder_key=trans_key,
                        original_network_id=int(
                            svc_node.get("onid") or trans_node.get("onid") or 0
                        ),
                        transport_stream_id=int(
                            svc_node.get("tsid") or trans_node.get("tsid") or 0
                        ),
                        namespace=namespace,
                        provider=svc_node.get("provider"),
                        caids=tuple(),
                        is_radio=svc_node.get("radio") == "1",
                    )

    bouquets: List[Bouquet] = []
    tree = ET.parse(bouquets_path)
    root = tree.getroot()
    for bouquet_node in root.findall("bouquet"):
        bouquet = Bouquet(
            name=bouquet_node.get("name", "Bouquet"),
            entries=[],
            category=bouquet_node.get("category", "tv"),
        )
        for chan in bouquet_node.findall("channel"):
            ref = chan.get("service_ref")
            if not ref:
                sid = int(chan.get("sid") or 0)
                onid = int(chan.get("onid") or 0)
                tsid = int(chan.get("tsid") or 0)
                namespace = transponders[next(iter(transponders))].namespace if transponders else 0
                ref = f"1:0:1:{sid:04x}:{tsid:04x}:{onid:04x}:{namespace:08x}:0:0:0:"
            bouquet.entries.append(BouquetEntry(service_ref=ref, name=chan.get("name")))
        bouquets.append(bouquet)

    return Profile(services=services, transponders=transponders, bouquets=bouquets)


def _derive_trans_key(node: ET.Element, parent: ET.Element) -> str:
    namespace_attr = node.get("namespace") or parent.get("namespace") or "0x0"
    if namespace_attr.startswith("0x"):
        namespace = int(namespace_attr, 16)
    else:
        namespace = int(namespace_attr)
    tsid = int(node.get("tsid") or 0)
    onid = int(node.get("onid") or 0)
    return f"{namespace:08x}:{tsid:04x}:{onid:04x}"


def _optional_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _optional_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _delivery_from_container(tag: str) -> str:
    if tag == "satellites":
        return "sat"
    if tag == "cables":
        return "cable"
    if tag == "terrestrials":
        return "terrestrial"
    return "sat"


register(NeutrinoAdapter())
