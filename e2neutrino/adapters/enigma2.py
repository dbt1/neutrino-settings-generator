"""
Adapter for native Enigma2 directory structures.

Deutsch:
    Adapter für native Enigma2-Verzeichnisse.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from .. import io_enigma
from ..models import Profile
from . import BaseAdapter, register

log = logging.getLogger(__name__)


class Enigma2Adapter(BaseAdapter):
    name = "enigma2"

    def ingest(self, source_path: Path, config: Dict[str, Any]) -> List[Profile]:
        include = config.get("include")
        paths: List[Path] = []
        if isinstance(include, list):
            for pattern in include:
                pattern_str = str(pattern)
                for match in Path(source_path).glob(pattern_str):
                    if (match / "lamedb").exists() or (match / "lamedb5").exists():
                        paths.append(match)
        else:
            if (source_path / "lamedb").exists() or (source_path / "lamedb5").exists():
                paths.append(source_path)
            else:
                for sub in Path(source_path).rglob("lamedb"):
                    paths.append(sub.parent)

        profiles: List[Profile] = []
        for profile_path in sorted(set(paths)):
            profile = io_enigma.load_profile(profile_path)
            profile.metadata.setdefault("profile_id", profile_path.name)
            profile.metadata.setdefault("source_path", str(profile_path))
            profiles.append(profile)
        return profiles


register(Enigma2Adapter())
