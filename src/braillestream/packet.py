"""
BrailleStream Packet Format
===========================

Packet helpers for BrailleStream.

A BS1 packet wraps a Unicode Braille payload with a compact metadata header:

    BS1|W=80|H=32|CELL=2x4|LEN=2560|CRC=A91F2C44|
    <payload>

This module intentionally does not depend on Pillow.

It handles:

    header construction
    header parsing
    packet construction
    packet parsing
    strict validation
    CRC32 checksums
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from typing import Mapping
import zlib

from braillestream.mapping import is_braille_char
from braillestream.render import render_dimensions, unwrap_stream


VERSION_BS1 = "BS1"
DEFAULT_CELL = "2x4"

REQUIRED_BS1_FIELDS = frozenset({"W", "H", "CELL", "LEN"})

VALID_POLARITIES = frozenset({"dark-on-light", "light-on-dark"})
VALID_DITHER_MODES = frozenset({"none", "floyd-steinberg", "ordered", "adaptive"})
VALID_MODES = frozenset(
    {
        "luma",
        "mask",
        "density",
        "depth",
        "attention",
        "delta",
        "ansi-color",
        "sensorium",
    }
)


class PacketError(ValueError):
    """
    Base packet error.
    """

    code = "ERR_PACKET"


class NoHeaderError(PacketError):
    code = "ERR_NO_HEADER"


class BadVersionError(PacketError):
    code = "ERR_BAD_VERSION"


class MissingFieldError(PacketError):
    code = "ERR_MISSING_FIELD"


class BadFieldError(PacketError):
    code = "ERR_BAD_FIELD"


class BadWidthError(PacketError):
    code = "ERR_BAD_WIDTH"


class BadHeightError(PacketError):
    code = "ERR_BAD_HEIGHT"


class BadCellError(PacketError):
    code = "ERR_BAD_CELL"


class BadLengthError(PacketError):
    code = "ERR_BAD_LENGTH"


class LengthMismatchError(PacketError):
    code = "ERR_LENGTH_MISMATCH"


class NonBraillePayloadError(PacketError):
    code = "ERR_NON_BRAILLE_PAYLOAD"


class CRCMismatchError(PacketError):
    code = "ERR_CRC_MISMATCH"


class RectangleMismatchError(PacketError):
    code = "ERR_RECTANGLE_MISMATCH"


@dataclass(frozen=True)
class BraillePacket:
    """
    Generic BrailleStream packet.

    Attributes
    ----------
    version:
        Packet version, usually "BS1".

    fields:
        Raw header fields as strings.

    payload:
        Unicode Braille payload.
    """

    version: str
    fields: dict[str, str]
    payload: str

    @property
    def header(self) -> str:
        return build_header(self.version, self.fields)

    @property
    def text(self) -> str:
        return build_packet(self.version, self.fields, self.payload)

    @property
    def length(self) -> int:
        return len(self.payload)


@dataclass(frozen=True)
class BS1Packet:
    """
    Typed BS1 packet.

    This is the strict, ergonomic representation used by application code.
    """

    width: int
    height: int
    payload: str
    cell: str = DEFAULT_CELL
    polarity: str | None = None
    gamma: float | None = None
    threshold: int | None = None
    dither: str | None = None
    mode: str | None = "luma"
    crc: str | None = None
    extra_fields: Mapping[str, str] = field(default_factory=dict)

    @property
    def version(self) -> str:
        return VERSION_BS1

    @property
    def length(self) -> int:
        return len(self.payload)

    @property
    def fields(self) -> dict[str, str]:
        fields: dict[str, str] = {
            "W": str(self.width),
            "H": str(self.height),
            "CELL": self.cell,
            "LEN": str(self.length),
        }

        if self.polarity is not None:
            fields["POL"] = self.polarity

        if self.gamma is not None:
            fields["GAMMA"] = format_float(self.gamma)

        if self.threshold is not None:
            fields["THRESH"] = str(self.threshold)

        if self.dither is not None:
            fields["DITHER"] = self.dither

        if self.mode is not None:
            fields["MODE"] = self.mode

        fields.update(dict(self.extra_fields))

        if self.crc is not None:
            fields["CRC"] = normalize_crc(self.crc)

        return fields

    @property
    def header(self) -> str:
        return build_header(self.version, self.fields)

    @property
    def text(self) -> str:
        return build_packet(self.version, self.fields, self.payload)

    def with_crc(self) -> "BS1Packet":
        """
        Return a copy with CRC computed from payload.
        """
        return BS1Packet(
            width=self.width,
            height=self.height,
            payload=self.payload,
            cell=self.cell,
            polarity=self.polarity,
            gamma=self.gamma,
            threshold=self.threshold,
            dither=self.dither,
            mode=self.mode,
            crc=crc32_payload(self.payload),
            extra_fields=self.extra_fields,
        )


def format_float(value: float) -> str:
    """
    Format a float compactly without unnecessary trailing zero noise.
    """
    return f"{float(value):g}"


def normalize_key(key: str) -> str:
    """
    Normalize a header key.

    Header keys are uppercase ASCII-ish labels.
    """
    key = str(key).strip().upper()

    if not key:
        raise BadFieldError("Header field key cannot be empty.")

    if any(ch in key for ch in "|\n\r="):
        raise BadFieldError(f"Invalid header key: {key!r}")

    return key


def normalize_value(value: object) -> str:
    """
    Normalize a header value.
    """
    value = str(value).strip()

    if any(ch in value for ch in "|\n\r"):
        raise BadFieldError(f"Invalid header value: {value!r}")

    return value


def normalize_fields(fields: Mapping[str, object]) -> dict[str, str]:
    """
    Normalize a field mapping into packet-safe strings.
    """
    normalized: dict[str, str] = {}

    for key, value in fields.items():
        normalized[normalize_key(key)] = normalize_value(value)

    return normalized


def build_header(version: str = VERSION_BS1, fields: Mapping[str, object] | None = None) -> str:
    """
    Build a packet header line.

    Example
    -------
    >>> build_header("BS1", {"W": 2, "H": 1, "CELL": "2x4", "LEN": 2})
    'BS1|W=2|H=1|CELL=2x4|LEN=2|'
    """
    version = str(version).strip().upper()

    if version != VERSION_BS1:
        raise BadVersionError(f"Unsupported packet version: {version!r}")

    normalized = normalize_fields(fields or {})

    parts = [version]

    for key, value in normalized.items():
        parts.append(f"{key}={value}")

    return "|".join(parts) + "|"


def parse_header(header: str) -> tuple[str, dict[str, str]]:
    """
    Parse a packet header line.

    Returns
    -------
    tuple[str, dict[str, str]]
        Version and raw string fields.
    """
    header = header.strip()

    if not header:
        raise NoHeaderError("Packet header is empty.")

    if not header.startswith(f"{VERSION_BS1}|"):
        raise BadVersionError(f"Unsupported or missing packet version in header: {header!r}")

    if not header.endswith("|"):
        raise BadFieldError("Header must end with '|'.")

    parts = header.split("|")

    version = parts[0]

    if version != VERSION_BS1:
        raise BadVersionError(f"Unsupported packet version: {version!r}")

    fields: dict[str, str] = {}

    for part in parts[1:-1]:
        if not part:
            continue

        if "=" not in part:
            raise BadFieldError(f"Bad header field: {part!r}")

        key, value = part.split("=", 1)

        key = normalize_key(key)
        value = normalize_value(value)

        fields[key] = value

    return version, fields


def build_packet(
    version: str = VERSION_BS1,
    fields: Mapping[str, object] | None = None,
    payload: str = "",
) -> str:
    """
    Build packet text from version, fields, and payload.
    """
    return f"{build_header(version, fields)}\n{payload}"


def find_header_line(text: str) -> tuple[int, str]:
    """
    Find the first packet header line in text.

    Comment lines before the header are allowed.

    Returns
    -------
    tuple[int, str]
        Header line index and header line.
    """
    lines = text.splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("#"):
            continue

        if stripped.startswith(f"{VERSION_BS1}|"):
            return index, stripped

        raise NoHeaderError(f"Expected BS1 header, got: {line!r}")

    raise NoHeaderError("No BS1 header found.")


def parse_packet(
    text: str,
    *,
    unwrap_payload: bool = False,
    strip_payload_spaces: bool = False,
    validate: bool = False,
    strict: bool = True,
) -> BraillePacket:
    """
    Parse packet text into a generic BraillePacket.

    Comments before the header are ignored.

    Parameters
    ----------
    unwrap_payload:
        Remove line breaks from payload.

    strip_payload_spaces:
        When unwrapping, also remove regular spaces and tabs.

    validate:
        Validate packet after parsing.

    strict:
        Strict validation requires LEN == W × H.
    """
    header_index, header = find_header_line(text)
    version, fields = parse_header(header)

    lines = text.splitlines()
    payload_lines = lines[header_index + 1 :]

    payload = "\n".join(payload_lines)

    if unwrap_payload:
        payload = unwrap_stream(payload, strip_spaces=strip_payload_spaces)
    else:
        payload = payload.rstrip("\r\n")

    packet = BraillePacket(version=version, fields=fields, payload=payload)

    if validate:
        validate_packet(packet, strict=strict)

    return packet


def parse_bs1_packet(
    text: str,
    *,
    unwrap_payload: bool = False,
    strip_payload_spaces: bool = False,
    strict: bool = True,
) -> BS1Packet:
    """
    Parse packet text into a typed BS1Packet and validate it.
    """
    packet = parse_packet(
        text,
        unwrap_payload=unwrap_payload,
        strip_payload_spaces=strip_payload_spaces,
        validate=True,
        strict=strict,
    )

    return bs1_from_packet(packet, strict=strict)


def bs1_from_packet(packet: BraillePacket, *, strict: bool = True) -> BS1Packet:
    """
    Convert a generic packet into a typed BS1 packet.
    """
    validate_packet(packet, strict=strict)

    fields = dict(packet.fields)

    width = parse_positive_int_field(fields, "W", BadWidthError)
    height = parse_positive_int_field(fields, "H", BadHeightError)
    cell = fields.get("CELL", DEFAULT_CELL)

    polarity = fields.get("POL")
    gamma = parse_optional_float(fields, "GAMMA")
    threshold = parse_optional_int(fields, "THRESH")
    dither = fields.get("DITHER")
    mode = fields.get("MODE")
    crc = fields.get("CRC")

    known = {
        "W",
        "H",
        "CELL",
        "LEN",
        "POL",
        "GAMMA",
        "THRESH",
        "DITHER",
        "MODE",
        "CRC",
    }

    extra_fields = {key: value for key, value in fields.items() if key not in known}

    return BS1Packet(
        width=width,
        height=height,
        payload=packet.payload,
        cell=cell,
        polarity=polarity,
        gamma=gamma,
        threshold=threshold,
        dither=dither,
        mode=mode,
        crc=crc,
        extra_fields=extra_fields,
    )


def packet_from_bs1(packet: BS1Packet) -> BraillePacket:
    """
    Convert typed BS1Packet to generic BraillePacket.
    """
    return BraillePacket(
        version=packet.version,
        fields=packet.fields,
        payload=packet.payload,
    )


def build_bs1_packet(
    payload: str,
    width: int,
    height: int | None = None,
    *,
    cell: str = DEFAULT_CELL,
    polarity: str | None = None,
    gamma: float | None = None,
    threshold: int | None = None,
    dither: str | None = None,
    mode: str | None = "luma",
    include_crc: bool = False,
    extra_fields: Mapping[str, str] | None = None,
) -> BS1Packet:
    """
    Build a typed BS1 packet.

    If height is omitted, it is inferred as ceil(len(payload) / width).
    """
    width = parse_positive_int_value(width, "width", BadWidthError)

    if height is None:
        height = ceil(len(payload) / width) if payload else 0
        if height <= 0:
            height = 1
    else:
        height = parse_positive_int_value(height, "height", BadHeightError)

    packet = BS1Packet(
        width=width,
        height=height,
        payload=payload,
        cell=cell,
        polarity=polarity,
        gamma=gamma,
        threshold=threshold,
        dither=dither,
        mode=mode,
        crc=None,
        extra_fields=extra_fields or {},
    )

    validate_bs1_packet(packet, strict=False)

    if include_crc:
        packet = packet.with_crc()

    return packet


def validate_packet(packet: BraillePacket, *, strict: bool = True) -> None:
    """
    Validate a generic BraillePacket.
    """
    if packet.version != VERSION_BS1:
        raise BadVersionError(f"Unsupported packet version: {packet.version!r}")

    missing = REQUIRED_BS1_FIELDS - set(packet.fields)

    if missing:
        missing_list = ", ".join(sorted(missing))
        raise MissingFieldError(f"Missing required BS1 field(s): {missing_list}")

    width = parse_positive_int_field(packet.fields, "W", BadWidthError)
    height = parse_positive_int_field(packet.fields, "H", BadHeightError)
    length = parse_non_negative_int_field(packet.fields, "LEN", BadLengthError)

    cell = packet.fields.get("CELL")

    if cell != DEFAULT_CELL:
        raise BadCellError(f"Unsupported CELL value: {cell!r}. Expected {DEFAULT_CELL!r}.")

    if length != len(packet.payload):
        raise LengthMismatchError(
            f"LEN field says {length}, but payload has {len(packet.payload)} characters."
        )

    validate_payload_is_braille(packet.payload)

    validate_optional_fields(packet.fields)

    if strict and length != width * height:
        raise RectangleMismatchError(
            f"Strict BS1 packet requires LEN == W × H. "
            f"Got LEN={length}, W={width}, H={height}, W×H={width * height}."
        )

    if not strict:
        expected_height = ceil(length / width) if length else 0
        if height < expected_height:
            raise RectangleMismatchError(
                f"H={height} is too small for LEN={length} at W={width}; "
                f"expected at least {expected_height}."
            )

    crc = packet.fields.get("CRC")
    if crc is not None:
        expected = crc32_payload(packet.payload)
        actual = normalize_crc(crc)

        if actual != expected:
            raise CRCMismatchError(f"CRC mismatch: expected {expected}, got {actual}.")


def validate_bs1_packet(packet: BS1Packet, *, strict: bool = True) -> None:
    """
    Validate a typed BS1Packet.
    """
    validate_packet(packet_from_bs1(packet), strict=strict)


def validate_payload_is_braille(payload: str) -> None:
    """
    Validate payload contains only Unicode Braille characters.
    """
    for index, char in enumerate(payload):
        if not is_braille_char(char):
            raise NonBraillePayloadError(
                f"Non-Braille character at payload index {index}: "
                f"{char!r} U+{ord(char):04X}"
            )


def validate_optional_fields(fields: Mapping[str, str]) -> None:
    """
    Validate optional known fields.
    """
    polarity = fields.get("POL")
    if polarity is not None and polarity not in VALID_POLARITIES:
        raise BadFieldError(f"Invalid POL value: {polarity!r}")

    gamma = fields.get("GAMMA")
    if gamma is not None:
        parsed = parse_float_value(gamma, "GAMMA")
        if parsed <= 0:
            raise BadFieldError(f"GAMMA must be positive, got {parsed}.")

    threshold = fields.get("THRESH")
    if threshold is not None:
        parsed = parse_int_value(threshold, "THRESH")
        if not 0 <= parsed <= 255:
            raise BadFieldError(f"THRESH must be in range 0..255, got {parsed}.")

    dither = fields.get("DITHER")
    if dither is not None and dither not in VALID_DITHER_MODES:
        raise BadFieldError(f"Invalid DITHER value: {dither!r}")

    mode = fields.get("MODE")
    if mode is not None and mode not in VALID_MODES:
        raise BadFieldError(f"Invalid MODE value: {mode!r}")

    crc = fields.get("CRC")
    if crc is not None:
        normalize_crc(crc)


def crc32_payload(payload: str) -> str:
    """
    Return CRC32 over UTF-8 payload bytes as 8 uppercase hex characters.
    """
    checksum = zlib.crc32(payload.encode("utf-8")) & 0xFFFFFFFF
    return f"{checksum:08X}"


def normalize_crc(crc: str) -> str:
    """
    Normalize and validate CRC field.
    """
    crc = str(crc).strip().upper()

    if len(crc) != 8:
        raise BadFieldError(f"CRC must be 8 hex characters, got {crc!r}.")

    try:
        int(crc, 16)
    except ValueError as exc:
        raise BadFieldError(f"CRC must be hexadecimal, got {crc!r}.") from exc

    return crc


def parse_int_value(value: object, name: str = "value") -> int:
    """
    Parse an integer field value.
    """
    try:
        return int(str(value))
    except ValueError as exc:
        raise BadFieldError(f"{name} must be an integer, got {value!r}.") from exc


def parse_float_value(value: object, name: str = "value") -> float:
    """
    Parse a float field value.
    """
    try:
        return float(str(value))
    except ValueError as exc:
        raise BadFieldError(f"{name} must be a float, got {value!r}.") from exc


def parse_positive_int_value(
    value: object,
    name: str,
    error_type: type[PacketError] = BadFieldError,
) -> int:
    """
    Parse a positive integer.
    """
    try:
        parsed = int(str(value))
    except ValueError as exc:
        raise error_type(f"{name} must be a positive integer, got {value!r}.") from exc

    if parsed <= 0:
        raise error_type(f"{name} must be positive, got {parsed}.")

    return parsed


def parse_non_negative_int_value(
    value: object,
    name: str,
    error_type: type[PacketError] = BadFieldError,
) -> int:
    """
    Parse a non-negative integer.
    """
    try:
        parsed = int(str(value))
    except ValueError as exc:
        raise error_type(f"{name} must be a non-negative integer, got {value!r}.") from exc

    if parsed < 0:
        raise error_type(f"{name} must be non-negative, got {parsed}.")

    return parsed


def parse_positive_int_field(
    fields: Mapping[str, str],
    key: str,
    error_type: type[PacketError],
) -> int:
    """
    Parse a required positive integer field.
    """
    if key not in fields:
        raise MissingFieldError(f"Missing required field: {key}")

    return parse_positive_int_value(fields[key], key, error_type)


def parse_non_negative_int_field(
    fields: Mapping[str, str],
    key: str,
    error_type: type[PacketError],
) -> int:
    """
    Parse a required non-negative integer field.
    """
    if key not in fields:
        raise MissingFieldError(f"Missing required field: {key}")

    return parse_non_negative_int_value(fields[key], key, error_type)


def parse_optional_int(fields: Mapping[str, str], key: str) -> int | None:
    """
    Parse an optional integer field.
    """
    if key not in fields:
        return None

    return parse_int_value(fields[key], key)


def parse_optional_float(fields: Mapping[str, str], key: str) -> float | None:
    """
    Parse an optional float field.
    """
    if key not in fields:
        return None

    return parse_float_value(fields[key], key)


def infer_fields_from_payload(
    payload: str,
    width: int,
    *,
    cell: str = DEFAULT_CELL,
    include_crc: bool = False,
) -> dict[str, str]:
    """
    Infer minimal BS1 fields from payload and render width.
    """
    dims = render_dimensions(payload, width)

    fields = {
        "W": str(dims.width_cells),
        "H": str(dims.height_cells),
        "CELL": cell,
        "LEN": str(len(payload)),
    }

    if include_crc:
        fields["CRC"] = crc32_payload(payload)

    return fields


def packet_summary(packet: BraillePacket) -> dict[str, object]:
    """
    Return a compact dictionary summary of a packet.
    """
    width = int(packet.fields["W"]) if "W" in packet.fields else None
    height = int(packet.fields["H"]) if "H" in packet.fields else None
    length = len(packet.payload)

    return {
        "version": packet.version,
        "width": width,
        "height": height,
        "cell": packet.fields.get("CELL"),
        "length": length,
        "declared_length": int(packet.fields["LEN"]) if "LEN" in packet.fields else None,
        "has_crc": "CRC" in packet.fields,
        "complete_rectangle": bool(width and height and length == width * height),
    }
