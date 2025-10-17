"""
Neutrino (Zapit) output helpers.

Deutsch:
    Neutrino (Zapit) Ausgabe-Helfer.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
from xml.etree import ElementTree as ET

from .models import Bouquet, BouquetEntry, ConversionOptions, Profile, Service, Transponder

log = logging.getLogger(__name__)

DeliveryToOption = {"sat": "include_sat", "cable": "include_cable", "terrestrial": "include_terrestrial"}


@dataclass
class OutputGroup:
    key: str
    display_name: str
    category: str  # sat|cable|terrestrial|all
    services: List[Service]
    transponders: Dict[str, Transponder]
    bouquets: List[Bouquet]
    metadata: Dict[str, str]


class NameResolver:
    """
    Resolve folder/display names for delivery types.

    Deutsch:
        Ermittelt Anzeige- und Ordnernamen pro Verbreitungsweg.
    """

    DEFAULT_SAT_NAMES = {
        19.2: "Astra-19.2E",
        13.0: "Hotbird-13.0E",
        23.5: "Astra-23.5E",
        28.2: "Astra-28.2E",
        9.0: "Eutelsat-9.0E",
        16.0: "Eutelsat-16.0E",
        42.0: "Turksat-42.0E",
    }

    def __init__(self, name_scheme: str, name_map: Optional[Mapping[str, Mapping[str, str]]] = None):
        self.name_scheme = name_scheme
        self.name_map = name_map or {}

    def satellite(self, trans: Transponder) -> Tuple[str, str]:
        position = trans.orbital_position or 0.0
        code = self._format_satellite_code(position)
        human = self.DEFAULT_SAT_NAMES.get(round(position, 1), code.replace("S", "Sat-"))
        mapped = self._lookup("sat", code) or self._lookup("sat", human) or human
        display = mapped if self.name_scheme == "human" else code
        folder = display.replace(" ", "-")
        return code, folder

    def cable(self, hint: str) -> Tuple[str, str]:
        code = self._slugify(hint) if hint else "cable-generic"
        mapped = self._lookup("cable", code) or self._lookup("cable", hint) or hint or "Cable"
        display = mapped if self.name_scheme == "human" else code.upper()
        folder = display.replace(" ", "-")
        return code, folder

    def terrestrial(self, hint: str) -> Tuple[str, str]:
        code = self._slugify(hint) if hint else "terrestrial-generic"
        mapped = self._lookup("terrestrial", code) or self._lookup("terrestrial", hint) or hint or "Terrestrial"
        display = mapped if self.name_scheme == "human" else code.upper()
        folder = display.replace(" ", "-")
        return code, folder

    def _format_satellite_code(self, position: float) -> str:
        hemisphere = "E" if position >= 0 else "W"
        pos = abs(position)
        return f"S{pos:.1f}{hemisphere}".replace(".0", "")

    def _lookup(self, category: str, key: str) -> Optional[str]:
        category_map = self.name_map.get(category, {}) if isinstance(self.name_map, Mapping) else {}
        return category_map.get(key)

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.lower()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        return value.strip("-")


def write_outputs(
    profile: Profile,
    out_dir: Path,
    options: ConversionOptions,
    name_map: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if options.api_version not in {3, 4}:
        raise ValueError("api_version must be either 3 or 4")
    resolver = NameResolver(options.name_scheme, name_map)

    selected_services = _filter_services(profile, options)
    groups = _build_groups(profile, selected_services, resolver, options)

    # Add master bundle (all in one).
    master_group = OutputGroup(
        key="all",
        display_name="All",
        category="all",
        services=sorted(selected_services, key=lambda svc: (svc.is_radio, svc.name.lower(), svc.service_id)),
        transponders={svc.transponder_key: profile.transponders[svc.transponder_key] for svc in selected_services},
        bouquets=_filter_bouquets(profile.bouquets, selected_services, options),
        metadata={"display_name": "All"},
    )

    _write_group(master_group, out_dir, options, profile.metadata)

    for group in groups:
        category = group.category
        if category == "sat":
            if not options.include_sat:
                continue
        elif category == "cable":
            if not options.include_cable:
                continue
        elif category == "terrestrial":
            if not options.include_terrestrial:
                continue
        _write_group(group, out_dir / category / group.display_name, options, profile.metadata)

    if options.combinations:
        _write_combinations(options, groups, out_dir, profile.metadata)


def _filter_services(profile: Profile, options: ConversionOptions) -> List[Service]:
    delivery_filter: Optional[Set[str]] = None
    if options.include_types:
        mapping = {"S": "sat", "C": "cable", "T": "terrestrial"}
        delivery_filter = {mapping.get(item.upper(), item.lower()) for item in options.include_types}
    result: List[Service] = []
    for service in profile.iter_services():
        trans = profile.transponders.get(service.transponder_key)
        if not trans:
            continue
        if delivery_filter and trans.delivery not in delivery_filter:
            continue
        result.append(service)
    return result


def _build_groups(
    profile: Profile,
    services: Sequence[Service],
    resolver: NameResolver,
    options: ConversionOptions,
) -> List[OutputGroup]:
    services_by_trans = defaultdict(list)
    for svc in services:
        services_by_trans[svc.transponder_key].append(svc)

    groups: Dict[Tuple[str, str], OutputGroup] = {}
    for trans_key, svc_list in services_by_trans.items():
        trans = profile.transponders[trans_key]
        if trans.delivery == "sat":
            code, folder = resolver.satellite(trans)
            if options.satellites and code not in options.satellites and folder not in options.satellites:
                continue
            key = (trans.delivery, folder)
            display = folder
            metadata = {"display_name": display, "satellite_code": code}
        elif trans.delivery == "cable":
            hint = _derive_hint_from_services(svc_list)
            code, folder = resolver.cable(hint)
            key = (trans.delivery, folder)
            display = folder
            metadata = {"display_name": display, "provider_code": code}
        else:
            hint = _derive_hint_from_services(svc_list)
            code, folder = resolver.terrestrial(hint)
            key = (trans.delivery, folder)
            display = folder
            metadata = {"display_name": display, "region_code": code}

        existing = groups.get(key)
        if existing is None:
            group = OutputGroup(
                key=f"{trans.delivery}:{folder}",
                display_name=display,
                category=trans.delivery,
                services=[],
                transponders={},
                bouquets=[],
                metadata=metadata,
            )
            groups[key] = group
        else:
            group = existing

        group.services.extend(sorted(svc_list, key=lambda svc: (svc.is_radio, svc.name.lower(), svc.service_id)))
        trans_with_display = replace(trans, extra={**trans.extra, "display_name": display})
        group.transponders[trans_key] = trans_with_display

    # Attach bouquets per group
    for group in groups.values():
        group.bouquets = _filter_bouquets(profile.bouquets, group.services, options)

    sorted_groups = sorted(groups.values(), key=lambda g: (g.category, g.display_name.lower()))
    return sorted_groups


def _derive_hint_from_services(services: Sequence[Service]) -> str:
    providers = [svc.provider for svc in services if svc.provider]
    if providers:
        # Deterministic: pick most common, tie -> lexicographically smallest.
        provider_counts: Dict[str, int] = {}
        for provider in providers:
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
        max_count = max(provider_counts.values())
        candidates = [prov for prov, cnt in provider_counts.items() if cnt == max_count]
        selected = sorted(candidates)[0]
        return selected
    return f"ns-{services[0].namespace:08x}" if services else "unknown"


def _filter_bouquets(
    bouquets: Iterable[Bouquet],
    services: Sequence[Service],
    options: ConversionOptions,
) -> List[Bouquet]:
    allowed_keys = {svc.key for svc in services}
    filtered: List[Bouquet] = []
    pattern: Optional[re.Pattern[str]] = None
    if options.filter_bouquets:
        pattern = re.compile(options.filter_bouquets)

    for bouquet in bouquets:
        if pattern and not pattern.search(bouquet.name):
            continue
        entries: List[BouquetEntry] = []
        for entry in bouquet.entries:
            svc_key = _service_ref_to_key(entry.service_ref)
            if svc_key in allowed_keys:
                entries.append(BouquetEntry(service_ref=entry.service_ref, name=entry.name))
        if entries:
            filtered.append(Bouquet(name=bouquet.name, entries=entries, category=bouquet.category))
    if not filtered:
        return _generate_auto_bouquets(services)
    return filtered


def _service_ref_to_key(service_ref: str) -> str:
    parts = service_ref.split(":")
    if len(parts) < 7:
        return service_ref
    sid = parts[3]
    tsid = parts[4]
    onid = parts[5]
    namespace = parts[6]
    return f"{namespace.lower()}:{tsid.lower()}:{onid.lower()}:{int(sid, 16):04x}"


def _service_to_ref(service: Service) -> str:
    return (
        f"1:0:{service.service_type}:"
        f"{service.service_id:04x}:"
        f"{service.transport_stream_id:04x}:"
        f"{service.original_network_id:04x}:"
        f"{service.namespace:08x}:0:0:0:"
    )


def _write_group(group: OutputGroup, out_path: Path, options: ConversionOptions, metadata: Mapping[str, str]) -> None:
    out_path.mkdir(parents=True, exist_ok=True)
    transponders = {k: group.transponders[k] for k in sorted(group.transponders)}
    services = group.services
    bouquets = group.bouquets

    services_xml = out_path / "services.xml"
    bouquets_xml = out_path / "bouquets.xml"
    buildinfo_json = out_path / "BUILDINFO.json"

    _write_services_xml(services_xml, services, transponders, options)
    _write_bouquets_xml(bouquets_xml, bouquets, services)

    buildinfo = {
        "display_name": group.metadata.get("display_name", group.display_name),
        "category": group.category,
        "api_version": options.api_version,
        "service_count": len(services),
        "bouquet_count": len(bouquets),
    }
    buildinfo.update(metadata)
    buildinfo.update(group.metadata)
    buildinfo_json.write_text(json.dumps(buildinfo, indent=2, sort_keys=True), encoding="utf-8")


def _write_services_xml(
    path: Path,
    services: Sequence[Service],
    transponders: Mapping[str, Transponder],
    options: ConversionOptions,
) -> None:
    root = ET.Element("zapit", attrib={"api": str(options.api_version)})

    categories: Dict[str, ET.Element] = {}
    for service in services:
        trans = transponders[service.transponder_key]
        container = categories.get(trans.delivery)
        if container is None:
            container_tag = {
                "sat": "satellites",
                "cable": "cables",
                "terrestrial": "terrestrials",
            }.get(trans.delivery, "others")
            container = ET.SubElement(root, container_tag)
            categories[trans.delivery] = container

        parent_tag = {"sat": "satellite", "cable": "cable", "terrestrial": "terrestrial"}.get(trans.delivery, "group")
        group_key = f"{trans.key}"
        parent = None
        for node in container.findall(parent_tag):
            if node.get("key") == group_key:
                parent = node
                break
        if parent is None:
            attrib = {
                "key": group_key,
                "name": trans.extra.get("display_name", group_key),
                "namespace": f"0x{trans.namespace:08x}",
            }
            if trans.delivery == "sat" and trans.orbital_position is not None:
                attrib["position"] = f"{trans.orbital_position:.1f}".rstrip("0").rstrip(".")
            parent = ET.SubElement(container, parent_tag, attrib=attrib)

        trans_el = None
        for node in parent.findall("transponder"):
            if node.get("key") == trans.key:
                trans_el = node
                break
        if trans_el is None:
            trans_attrib = {
                "key": trans.key,
                "frequency": str(trans.frequency),
                "symbol_rate": str(trans.symbol_rate or 0),
                "polarization": trans.polarization or "",
                "fec": trans.fec or "",
                "system": trans.system or "",
                "modulation": trans.modulation or "",
            }
            trans_el = ET.SubElement(parent, "transponder", attrib=trans_attrib)

        svc_attrib = {
            "id": f"0x{service.service_id:04x}",
            "sid": str(service.service_id),
            "name": service.name,
            "type": str(service.service_type),
            "provider": service.provider or "",
            "onid": str(service.original_network_id),
            "tsid": str(service.transport_stream_id),
            "namespace": f"0x{service.namespace:08x}",
        }
        if service.is_radio:
            svc_attrib["radio"] = "1"
        ET.SubElement(trans_el, "service", attrib=svc_attrib)

    _indent(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _write_bouquets_xml(path: Path, bouquets: Sequence[Bouquet], services: Sequence[Service]) -> None:
    service_index = {svc.key: svc for svc in services}
    root = ET.Element("zapit")
    for bouquet in bouquets:
        b_el = ET.SubElement(root, "bouquet", attrib={"name": bouquet.name, "category": bouquet.category})
        for entry in bouquet.entries:
            svc_key = _service_ref_to_key(entry.service_ref)
            svc = service_index.get(svc_key)
            if not svc:
                continue
            attrib = {
                "service_ref": entry.service_ref,
                "name": entry.name or svc.name,
                "service_name": svc.name,
                "provider": svc.provider or "",
                "sid": str(svc.service_id),
                "onid": str(svc.original_network_id),
                "tsid": str(svc.transport_stream_id),
            }
            ET.SubElement(b_el, "channel", attrib=attrib)
    _indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _indent(elem: ET.Element, level: int = 0) -> None:
    indent_str = "  "
    children = list(elem)
    if children:
        elem.text = "\n" + indent_str * (level + 1)
        for idx, child in enumerate(children):
            _indent(child, level + 1)
            if idx == len(children) - 1:
                child.tail = "\n" + indent_str * level
            else:
                child.tail = "\n" + indent_str * (level + 1)
    else:
        elem.text = None
    if level:
        elem.tail = "\n" + indent_str * level
    else:
        elem.tail = "\n"


def _write_combinations(
    options: ConversionOptions,
    groups: Sequence[OutputGroup],
    out_dir: Path,
    metadata: Mapping[str, str],
) -> None:
    if not options.combinations:
        return
    sat_groups = [group for group in groups if group.category == "sat"]
    if not sat_groups:
        return

    name_to_group = {}
    for group in sat_groups:
        name_to_group[group.display_name] = group
        name_to_group[group.metadata.get("satellite_code", "")] = group

    for combo in sorted(options.combinations):
        parts = combo.split("+")
        selected: List[OutputGroup] = []
        for part in parts:
            part = part.strip()
            candidate = name_to_group.get(part)
            if candidate:
                selected.append(candidate)
        if not selected:
            log.warning("combo '%s' matches no satellite group", combo)
            continue

        services: List[Service] = []
        transponders: Dict[str, Transponder] = {}
        bouquets: List[Bouquet] = []
        for group in selected:
            services.extend(group.services)
            transponders.update(group.transponders)
            bouquets.extend(group.bouquets)

        combo_group = OutputGroup(
            key=f"combo:{combo}",
            display_name=combo.replace(" ", ""),
            category="sat",
            services=sorted(services, key=lambda svc: (svc.is_radio, svc.name.lower(), svc.service_id)),
            transponders=transponders,
            bouquets=_merge_bouquets(bouquets),
            metadata={"display_name": combo},
        )
        _write_group(combo_group, out_dir / "sat" / combo_group.display_name, options, metadata)


def _merge_bouquets(bouquets: Sequence[Bouquet]) -> List[Bouquet]:
    merged: Dict[str, Bouquet] = {}
    for bouquet in bouquets:
        target = merged.get(bouquet.name)
        if not target:
            merged[bouquet.name] = Bouquet(name=bouquet.name, entries=list(bouquet.entries), category=bouquet.category)
        else:
            existing_refs = {entry.service_ref for entry in target.entries}
            for entry in bouquet.entries:
                if entry.service_ref not in existing_refs:
                    target.entries.append(entry)
    result = list(merged.values())
    for bouquet in result:
        bouquet.entries.sort(key=lambda entry: entry.service_ref)
    result.sort(key=lambda b: b.name.lower())
    return result


def _generate_auto_bouquets(services: Sequence[Service]) -> List[Bouquet]:
    tv_services = [svc for svc in services if not svc.is_radio]
    radio_services = [svc for svc in services if svc.is_radio]

    def _sorted_unique(items: Iterable[Service]) -> List[Service]:
        seen = set()
        ordered: List[Service] = []
        for svc in sorted(items, key=lambda item: (item.name.lower(), item.service_id)):
            if svc.key in seen:
                continue
            seen.add(svc.key)
            ordered.append(svc)
        return ordered

    def _entries(items: Iterable[Service]) -> List[BouquetEntry]:
        entries: List[BouquetEntry] = []
        seen_refs: Set[str] = set()
        for svc in _sorted_unique(items):
            ref = _service_to_ref(svc)
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            entries.append(BouquetEntry(service_ref=ref, name=svc.name))
        return entries

    bouquets: List[Bouquet] = []

    if tv_services:
        free_tv = [svc for svc in tv_services if not svc.caids]
        pay_tv = [svc for svc in tv_services if svc.caids]
        hd_types = {0x11, 0x16, 0x19, 0x1A, 0x1F, 0x20, 0x21, 0x22, 0x86}
        uhd_types = {0x1F, 0x20, 0x21, 0x22, 0x87}
        free_hd = [svc for svc in free_tv if svc.service_type in hd_types]
        free_uhd = [svc for svc in free_tv if svc.service_type in uhd_types]
        pay_hd = [svc for svc in pay_tv if svc.service_type in hd_types]

        public_keywords = {
            "ARD",
            "ZDF",
            "ORF",
            "SRF",
            "SRG",
            "3SAT",
            "ARTE",
            "PHOENIX",
            "TAGESSCHAU",
            "KIKA",
            "DEUTSCHLANDRADIO",
            "WDR",
            "NDR",
            "MDR",
            "RBB",
            "HR",
            "SWR",
            "BR",
        }

        def _is_public_service(svc: Service) -> bool:
            name_upper = svc.name.upper()
            provider_upper = (svc.provider or "").upper()
            return any(keyword in name_upper or keyword in provider_upper for keyword in public_keywords)

        public_tv = [svc for svc in free_tv if _is_public_service(svc)]
        private_tv = [svc for svc in free_tv if svc not in public_tv]

        bouquet_recipes = [
            ("TV – Free", free_tv),
            ("TV – Free HD", free_hd),
            ("TV – Free UHD", free_uhd),
            ("TV – Public Service", public_tv),
            ("TV – Private", private_tv),
            ("TV – Pay", pay_tv),
            ("TV – Pay HD", pay_hd),
        ]

        for name, svc_list in bouquet_recipes:
            entries = _entries(svc_list)
            if entries:
                bouquets.append(Bouquet(name=name, entries=entries, category="tv"))

        provider_map: Dict[str, List[Service]] = defaultdict(list)
        for svc in tv_services:
            if svc.provider:
                provider_map[svc.provider].append(svc)
        for provider, svc_list in sorted(provider_map.items(), key=lambda item: item[0].upper()):
            entries = _entries(svc_list)
            if entries:
                bouquets.append(Bouquet(name=f"TV – Provider: {provider}", entries=entries, category="tv"))

    if radio_services:
        free_radio = [svc for svc in radio_services if not svc.caids]
        pay_radio = [svc for svc in radio_services if svc.caids]
        radio_recipes = [
            ("Radio – Free", free_radio),
            ("Radio – Pay", pay_radio),
        ]
        for name, svc_list in radio_recipes:
            entries = _entries(svc_list)
            if entries:
                bouquets.append(Bouquet(name=name, entries=entries, category="radio"))

        provider_radio: Dict[str, List[Service]] = defaultdict(list)
        for svc in radio_services:
            if svc.provider:
                provider_radio[svc.provider].append(svc)
        for provider, svc_list in sorted(provider_radio.items(), key=lambda item: item[0].upper()):
            entries = _entries(svc_list)
            if entries:
                bouquets.append(Bouquet(name=f"Radio – Provider: {provider}", entries=entries, category="radio"))

    return sorted(bouquets, key=lambda bouquet: bouquet.name.lower())
