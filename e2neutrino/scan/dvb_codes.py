"""
DVB parameter code mappings for Neutrino scanfiles.

This module provides conversion functions between human-readable DVB parameter
strings (e.g., "QAM256", "3/4", "H") and the integer codes used by Neutrino
in satellites.xml, cables.xml, and terrestrial.xml.

Deutsch:
    DVB-Parameter-Code-Mappings für Neutrino-Scanfiles.

    Dieses Modul stellt Konvertierungsfunktionen zwischen lesbaren DVB-Parameter-
    Strings (z.B. "QAM256", "3/4", "H") und den Integer-Codes bereit, die von
    Neutrino in satellites.xml, cables.xml und terrestrial.xml verwendet werden.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Polarization codes (Satellite only)
POLARIZATION_CODES = {
    "H": 0,  # Horizontal
    "V": 1,  # Vertical
    "L": 2,  # Left circular
    "R": 3,  # Right circular
}

# FEC (Forward Error Correction) codes
FEC_CODES = {
    "NONE": 0,
    "AUTO": 0,
    "0": 0,
    "1/2": 1,
    "2/3": 2,
    "3/4": 3,
    "4/5": 4,
    "5/6": 5,
    "6/7": 6,
    "7/8": 7,
    "8/9": 8,
    "9": 9,  # AUTO alternative
}

# System codes
SYSTEM_CODES = {
    "DVB-S": 0,
    "DVB-C": 0,
    "DVB-T": 0,
    "DVB-S2": 1,
    "DVB-C2": 1,
    "DVB-T2": 1,
}

# Modulation codes for Satellite (DVB-S/S2)
MODULATION_SAT_CODES = {
    "AUTO": 0,
    "QPSK": 1,
    "8PSK": 2,
    "QAM16": 3,
}

# Constellation codes for Cable and Terrestrial (als "modulation" in Enigma2)
CONSTELLATION_CODES = {
    "QPSK": 0,
    "QAM16": 1,
    "QAM32": 2,
    "QAM64": 3,
    "QAM128": 4,
    "QAM256": 5,
    "AUTO": 6,
}

# Bandwidth codes (Terrestrial)
# Input: Hz values, Output: Neutrino code
BANDWIDTH_CODES = {
    8000000: 0,  # 8MHz
    7000000: 1,  # 7MHz
    6000000: 2,  # 6MHz
    0: 3,        # AUTO
}

# Transmission Mode codes (Terrestrial)
TRANSMISSION_MODE_CODES = {
    "2K": 0,
    "2k": 0,
    "8K": 1,
    "8k": 1,
    "AUTO": 2,
}

# Guard Interval codes (Terrestrial)
GUARD_INTERVAL_CODES = {
    "1/32": 0,
    "1/16": 1,
    "1/8": 2,
    "1/4": 3,
    "AUTO": 4,
}

# Hierarchy codes (Terrestrial)
HIERARCHY_CODES = {
    "NONE": 0,
    "0": 0,
    "1": 1,
    "2": 2,
    "4": 3,
    "AUTO": 4,
}


def polarization_to_code(polarization: Optional[str]) -> int:
    """
    Convert polarization string to Neutrino integer code.

    Args:
        polarization: "H", "V", "L", or "R" (case-insensitive)

    Returns:
        Integer code: 0=H, 1=V, 2=L, 3=R

    Default: 0 (H) if unknown or None
    """
    if not polarization:
        return 0

    pol = polarization.upper().strip()
    code = POLARIZATION_CODES.get(pol)

    if code is None:
        logger.warning(f"Unknown polarization '{polarization}', defaulting to H (0)")
        return 0

    return code


def fec_to_code(fec: Optional[str]) -> int:
    """
    Convert FEC string to Neutrino integer code.

    Args:
        fec: "1/2", "2/3", "3/4", "4/5", "5/6", "6/7", "7/8", "8/9", "AUTO", or "NONE"

    Returns:
        Integer code: 0=NONE/AUTO, 1=1/2, 2=2/3, 3=3/4, 4=4/5, 5=5/6, 6=6/7, 7=7/8, 8=8/9, 9=AUTO

    Default: 0 (AUTO) if unknown or None
    """
    if not fec:
        return 0

    fec_str = str(fec).upper().strip()
    code = FEC_CODES.get(fec_str)

    if code is None:
        logger.warning(f"Unknown FEC '{fec}', defaulting to AUTO (0)")
        return 0

    return code


def system_to_code(system: Optional[str]) -> int:
    """
    Convert system string to Neutrino integer code.

    Args:
        system: "DVB-S", "DVB-S2", "DVB-C", "DVB-C2", "DVB-T", "DVB-T2"

    Returns:
        Integer code: 0=DVB-S/C/T, 1=DVB-S2/C2/T2

    Default: 0 if unknown or None
    """
    if not system:
        return 0

    sys_str = system.upper().strip()
    code = SYSTEM_CODES.get(sys_str)

    if code is None:
        logger.warning(f"Unknown system '{system}', defaulting to 0")
        return 0

    return code


def modulation_to_code(modulation: Optional[str], delivery: str) -> int:
    """
    Convert modulation string to Neutrino integer code.

    Args:
        modulation: Modulation/Constellation string
        delivery: Delivery type: "sat", "cable", or "terrestrial"

    Returns:
        Integer code based on delivery type:
        - Satellite: 0=AUTO, 1=QPSK, 2=8PSK, 3=QAM16
        - Cable/Terrestrial: 0=QPSK, 1=QAM16, 2=QAM32, 3=QAM64, 4=QAM128, 5=QAM256, 6=AUTO

    Default: Delivery-specific default (QPSK for sat, AUTO for cable/terrestrial)
    """
    if not modulation:
        return 1 if delivery == "sat" else 6  # QPSK for sat, AUTO for cable/terrestrial

    mod_str = modulation.upper().strip()

    if delivery == "sat":
        code = MODULATION_SAT_CODES.get(mod_str)
        if code is None:
            logger.warning(f"Unknown satellite modulation '{modulation}', defaulting to QPSK (1)")
            return 1
        return code
    else:
        # Cable or Terrestrial use constellation codes
        code = CONSTELLATION_CODES.get(mod_str)
        if code is None:
            logger.warning(f"Unknown constellation '{modulation}', defaulting to AUTO (6)")
            return 6
        return code


def bandwidth_to_code(bandwidth_hz: Optional[int]) -> int:
    """
    Convert bandwidth in Hz to Neutrino integer code.

    Args:
        bandwidth_hz: Bandwidth in Hz (e.g., 8000000 for 8MHz)

    Returns:
        Integer code: 0=8MHz, 1=7MHz, 2=6MHz, 3=AUTO

    Default: 3 (AUTO) if unknown or None
    """
    if not bandwidth_hz:
        return 3  # AUTO

    code = BANDWIDTH_CODES.get(bandwidth_hz)

    if code is None:
        # Try to find closest match
        if bandwidth_hz >= 7500000:  # Closer to 8MHz
            logger.warning(f"Unknown bandwidth {bandwidth_hz} Hz, using 8MHz (0)")
            return 0
        elif bandwidth_hz >= 6500000:  # Closer to 7MHz
            logger.warning(f"Unknown bandwidth {bandwidth_hz} Hz, using 7MHz (1)")
            return 1
        elif bandwidth_hz >= 5000000:  # Closer to 6MHz
            logger.warning(f"Unknown bandwidth {bandwidth_hz} Hz, using 6MHz (2)")
            return 2
        else:
            logger.warning(f"Unknown bandwidth {bandwidth_hz} Hz, defaulting to AUTO (3)")
            return 3

    return code


def transmission_mode_to_code(mode: Optional[str]) -> int:
    """
    Convert transmission mode string to Neutrino integer code.

    Args:
        mode: "2k", "8k", or "AUTO" (case-insensitive)

    Returns:
        Integer code: 0=2k, 1=8k, 2=AUTO

    Default: 2 (AUTO) if unknown or None
    """
    if not mode:
        return 2  # AUTO

    mode_str = mode.upper().strip()
    code = TRANSMISSION_MODE_CODES.get(mode_str)

    if code is None:
        logger.warning(f"Unknown transmission mode '{mode}', defaulting to AUTO (2)")
        return 2

    return code


def guard_interval_to_code(interval: Optional[str]) -> int:
    """
    Convert guard interval string to Neutrino integer code.

    Args:
        interval: "1/32", "1/16", "1/8", "1/4", or "AUTO"

    Returns:
        Integer code: 0=1/32, 1=1/16, 2=1/8, 3=1/4, 4=AUTO

    Default: 4 (AUTO) if unknown or None
    """
    if not interval:
        return 4  # AUTO

    interval_str = interval.upper().strip()
    code = GUARD_INTERVAL_CODES.get(interval_str)

    if code is None:
        logger.warning(f"Unknown guard interval '{interval}', defaulting to AUTO (4)")
        return 4

    return code


def hierarchy_to_code(hierarchy: Optional[str]) -> int:
    """
    Convert hierarchy string to Neutrino integer code.

    Args:
        hierarchy: "NONE", "0", "1", "2", "4", or "AUTO"

    Returns:
        Integer code: 0=NONE, 1=1, 2=2, 3=4, 4=AUTO

    Default: 0 (NONE) if unknown or None
    """
    if not hierarchy:
        return 0  # NONE

    hier_str = hierarchy.upper().strip()
    code = HIERARCHY_CODES.get(hier_str)

    if code is None:
        logger.warning(f"Unknown hierarchy '{hierarchy}', defaulting to NONE (0)")
        return 0

    return code


# Reverse mappings for validation and debugging
def code_to_polarization(code: int) -> str:
    """Convert polarization code to string."""
    reverse = {v: k for k, v in POLARIZATION_CODES.items()}
    return reverse.get(code, "H")


def code_to_fec(code: int) -> str:
    """Convert FEC code to string."""
    reverse = {v: k for k, v in FEC_CODES.items() if k not in ["0", "9", "NONE"]}
    return reverse.get(code, "AUTO")


def code_to_system(code: int) -> str:
    """Convert system code to string."""
    if code == 0:
        return "DVB-S"  # Default to DVB-S for code 0
    elif code == 1:
        return "DVB-S2"
    return "DVB-S"


def code_to_modulation_sat(code: int) -> str:
    """Convert satellite modulation code to string."""
    reverse = {v: k for k, v in MODULATION_SAT_CODES.items()}
    return reverse.get(code, "QPSK")


def code_to_constellation(code: int) -> str:
    """Convert constellation code to string."""
    reverse = {v: k for k, v in CONSTELLATION_CODES.items()}
    return reverse.get(code, "AUTO")


def code_to_bandwidth(code: int) -> str:
    """Convert bandwidth code to string."""
    mapping = {0: "8MHz", 1: "7MHz", 2: "6MHz", 3: "AUTO"}
    return mapping.get(code, "AUTO")


def code_to_transmission_mode(code: int) -> str:
    """Convert transmission mode code to string."""
    mapping = {0: "2k", 1: "8k", 2: "AUTO"}
    return mapping.get(code, "AUTO")


def code_to_guard_interval(code: int) -> str:
    """Convert guard interval code to string."""
    reverse = {v: k for k, v in GUARD_INTERVAL_CODES.items()}
    return reverse.get(code, "AUTO")


def code_to_hierarchy(code: int) -> str:
    """Convert hierarchy code to string."""
    mapping = {0: "NONE", 1: "1", 2: "2", 3: "4", 4: "AUTO"}
    return mapping.get(code, "NONE")
