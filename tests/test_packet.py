"""
Tests for braillestream.packet.

These tests lock down the BS1 packet layer:

    header
    payload
    validation
    CRC
    typed BS1 packets
"""

import pytest

from braillestream.packet import (
    DEFAULT_CELL,
    REQUIRED_BS1_FIELDS,
    VERSION_BS1,
    BS1Packet,
    BadCellError,
    BadFieldError,
    BadHeightError,
    BadLengthError,
    BadVersionError,
    BadWidthError,
    BraillePacket,
    CRCMismatchError,
    LengthMismatchError,
    MissingFieldError,
    NoHeaderError,
    NonBraillePayloadError,
    RectangleMismatchError,
    build_bs1_packet,
    build_header,
    build_packet,
    bs1_from_packet,
    crc32_payload,
    find_header_line,
    format_float,
    infer_fields_from_payload,
    normalize_crc,
    normalize_fields,
    normalize_key,
    normalize_value,
    packet_from_bs1,
    packet_summary,
    parse_bs1_packet,
    parse_header,
    parse_packet,
    parse_positive_int_value,
    parse_non_negative_int_value,
    validate_bs1_packet,
    validate_optional_fields,
    validate_packet,
    validate_payload_is_braille,
)


def test_constants():
    assert VERSION_BS1 == "BS1"
    assert DEFAULT_CELL == "2x4"
    assert REQUIRED_BS1_FIELDS == frozenset({"W", "H", "CELL", "LEN"})


def test_format_float():
    assert format_float(1.0) == "1"
    assert format_float(1.25) == "1.25"
    assert format_float(0.5) == "0.5"


def test_normalize_key_uppercases_and_strips():
    assert normalize_key(" w ") == "W"
    assert normalize_key("cell") == "CELL"


@pytest.mark.parametrize("key", ["", " ", "A|B", "A=B", "A\nB", "A\rB"])
def test_normalize_key_rejects_invalid_keys(key):
    with pytest.raises(BadFieldError):
        normalize_key(key)


def test_normalize_value_strips():
    assert normalize_value(" 2x4 ") == "2x4"


@pytest.mark.parametrize("value", ["A|B", "A\nB", "A\rB"])
def test_normalize_value_rejects_invalid_values(value):
    with pytest.raises(BadFieldError):
        normalize_value(value)


def test_normalize_fields():
    fields = normalize_fields({"w": 2, " h ": "1", "cell": "2x4"})

    assert fields == {"W": "2", "H": "1", "CELL": "2x4"}


def test_build_header_minimal():
    header = build_header(
        "BS1",
        {
            "W": 2,
            "H": 1,
            "CELL": "2x4",
            "LEN": 2,
        },
    )

    assert header == "BS1|W=2|H=1|CELL=2x4|LEN=2|"


def test_build_header_rejects_bad_version():
    with pytest.raises(BadVersionError):
        build_header("BS2", {"W": 1})


def test_parse_header_minimal():
    version, fields = parse_header("BS1|W=2|H=1|CELL=2x4|LEN=2|")

    assert version == "BS1"
    assert fields == {
        "W": "2",
        "H": "1",
        "CELL": "2x4",
        "LEN": "2",
    }


def test_parse_header_allows_empty_extra_separator_parts():
    version, fields = parse_header("BS1|W=2||H=1|CELL=2x4|LEN=2|")

    assert version == "BS1"
    assert fields["W"] == "2"
    assert fields["H"] == "1"


def test_parse_header_rejects_empty():
    with pytest.raises(NoHeaderError):
        parse_header("")


def test_parse_header_rejects_bad_version():
    with pytest.raises(BadVersionError):
        parse_header("BS2|W=1|")


def test_parse_header_rejects_missing_final_pipe():
    with pytest.raises(BadFieldError):
        parse_header("BS1|W=1")


def test_parse_header_rejects_field_without_equals():
    with pytest.raises(BadFieldError):
        parse_header("BS1|W=1|BAD|")


def test_build_packet():
    text = build_packet(
        "BS1",
        {
            "W": 2,
            "H": 1,
            "CELL": "2x4",
            "LEN": 2,
        },
        "⣿⠀",
    )

    assert text == "BS1|W=2|H=1|CELL=2x4|LEN=2|\n⣿⠀"


def test_find_header_line_simple():
    index, header = find_header_line("BS1|W=1|H=1|CELL=2x4|LEN=1|\n⣿")

    assert index == 0
    assert header == "BS1|W=1|H=1|CELL=2x4|LEN=1|"


def test_find_header_line_skips_comments_and_blank_lines():
    text = "\n# comment\n# another\nBS1|W=1|H=1|CELL=2x4|LEN=1|\n⣿"

    index, header = find_header_line(text)

    assert index == 3
    assert header == "BS1|W=1|H=1|CELL=2x4|LEN=1|"


def test_find_header_line_rejects_unexpected_content_before_header():
    with pytest.raises(NoHeaderError):
        find_header_line("hello\nBS1|W=1|H=1|CELL=2x4|LEN=1|\n⣿")


def test_find_header_line_rejects_missing_header():
    with pytest.raises(NoHeaderError):
        find_header_line("# only comment")


def test_parse_packet_basic_no_validation():
    packet = parse_packet("BS1|W=2|H=1|CELL=2x4|LEN=2|\n⣿⠀")

    assert isinstance(packet, BraillePacket)
    assert packet.version == "BS1"
    assert packet.fields["W"] == "2"
    assert packet.payload == "⣿⠀"
    assert packet.length == 2


def test_parse_packet_with_comments():
    packet = parse_packet("# comment\nBS1|W=1|H=1|CELL=2x4|LEN=1|\n⣿")

    assert packet.payload == "⣿"


def test_parse_packet_unwrap_payload():
    text = "BS1|W=4|H=1|CELL=2x4|LEN=4|\n⣿⠀\n⣿⠀"

    packet = parse_packet(text, unwrap_payload=True)

    assert packet.payload == "⣿⠀⣿⠀"


def test_parse_packet_unwrap_payload_and_strip_spaces():
    text = "BS1|W=2|H=1|CELL=2x4|LEN=2|\n⣿ \n⠀"

    packet = parse_packet(text, unwrap_payload=True, strip_payload_spaces=True)

    assert packet.payload == "⣿⠀"


def test_parse_packet_validate_strict():
    packet = parse_packet(
        "BS1|W=2|H=1|CELL=2x4|LEN=2|\n⣿⠀",
        validate=True,
        strict=True,
    )

    assert packet.payload == "⣿⠀"


def test_parse_packet_validate_strict_fails_bad_rectangle():
    with pytest.raises(RectangleMismatchError):
        parse_packet(
            "BS1|W=2|H=2|CELL=2x4|LEN=2|\n⣿⠀",
            validate=True,
            strict=True,
        )


def test_braille_packet_header_and_text_properties():
    packet = BraillePacket(
        version="BS1",
        fields={"W": "2", "H": "1", "CELL": "2x4", "LEN": "2"},
        payload="⣿⠀",
    )

    assert packet.header == "BS1|W=2|H=1|CELL=2x4|LEN=2|"
    assert packet.text == "BS1|W=2|H=1|CELL=2x4|LEN=2|\n⣿⠀"
    assert packet.length == 2


def test_validate_packet_valid_strict():
    packet = BraillePacket(
        version="BS1",
        fields={"W": "2", "H": "1", "CELL": "2x4", "LEN": "2"},
        payload="⣿⠀",
    )

    validate_packet(packet, strict=True)


def test_validate_packet_rejects_bad_version():
    packet = BraillePacket(
        version="BS2",
        fields={"W": "1", "H": "1", "CELL": "2x4", "LEN": "1"},
        payload="⣿",
    )

    with pytest.raises(BadVersionError):
        validate_packet(packet)


def test_validate_packet_rejects_missing_fields():
    packet = BraillePacket(
        version="BS1",
        fields={"W": "1", "CELL": "2x4", "LEN": "1"},
        payload="⣿",
    )

    with pytest.raises(MissingFieldError) as exc:
        validate_packet(packet)

    assert "H" in str(exc.value)


@pytest.mark.parametrize(
    "fields,error_type",
    [
        ({"W": "0", "H": "1", "CELL": "2x4", "LEN": "1"}, BadWidthError),
        ({"W": "-1", "H": "1", "CELL": "2x4", "LEN": "1"}, BadWidthError),
        ({"W": "x", "H": "1", "CELL": "2x4", "LEN": "1"}, BadWidthError),
        ({"W": "1", "H": "0", "CELL": "2x4", "LEN": "1"}, BadHeightError),
        ({"W": "1", "H": "-1", "CELL": "2x4", "LEN": "1"}, BadHeightError),
        ({"W": "1", "H": "x", "CELL": "2x4", "LEN": "1"}, BadHeightError),
        ({"W": "1", "H": "1", "CELL": "2x3", "LEN": "1"}, BadCellError),
        ({"W": "1", "H": "1", "CELL": "2x4", "LEN": "-1"}, BadLengthError),
        ({"W": "1", "H": "1", "CELL": "2x4", "LEN": "x"}, BadLengthError),
    ],
)
def test_validate_packet_rejects_bad_required_fields(fields, error_type):
    packet = BraillePacket(version="BS1", fields=fields, payload="⣿")

    with pytest.raises(error_type):
        validate_packet(packet)


def test_validate_packet_rejects_length_mismatch():
    packet = BraillePacket(
        version="BS1",
        fields={"W": "2", "H": "1", "CELL": "2x4", "LEN": "3"},
        payload="⣿⠀",
    )

    with pytest.raises(LengthMismatchError):
        validate_packet(packet)


def test_validate_packet_rejects_non_braille_payload():
    packet = BraillePacket(
        version="BS1",
        fields={"W": "1", "H": "1", "CELL": "2x4", "LEN": "1"},
        payload="A",
    )

    with pytest.raises(NonBraillePayloadError):
        validate_packet(packet)


def test_validate_packet_relaxed_allows_incomplete_rectangle_if_height_large_enough():
    packet = BraillePacket(
        version="BS1",
        fields={"W": "4", "H": "1", "CELL": "2x4", "LEN": "2"},
        payload="⣿⠀",
    )

    validate_packet(packet, strict=False)


def test_validate_packet_relaxed_rejects_height_too_small():
    packet = BraillePacket(
        version="BS1",
        fields={"W": "2", "H": "1", "CELL": "2x4", "LEN": "3"},
        payload="⣿⠀⣿",
    )

    with pytest.raises(RectangleMismatchError):
        validate_packet(packet, strict=False)


def test_validate_packet_strict_rejects_rectangle_mismatch():
    packet = BraillePacket(
        version="BS1",
        fields={"W": "4", "H": "1", "CELL": "2x4", "LEN": "2"},
        payload="⣿⠀",
    )

    with pytest.raises(RectangleMismatchError):
        validate_packet(packet, strict=True)


def test_validate_payload_is_braille_accepts_valid_payload():
    validate_payload_is_braille("")
    validate_payload_is_braille("⠀⣿⠁⢀")


def test_validate_payload_is_braille_rejects_invalid_payload():
    with pytest.raises(NonBraillePayloadError) as exc:
        validate_payload_is_braille("⠀A")

    assert "payload index 1" in str(exc.value)
    assert "U+0041" in str(exc.value)


@pytest.mark.parametrize(
    "fields",
    [
        {"POL": "dark-on-light"},
        {"POL": "light-on-dark"},
        {"GAMMA": "1.0"},
        {"THRESH": "128"},
        {"DITHER": "none"},
        {"DITHER": "floyd-steinberg"},
        {"MODE": "luma"},
        {"MODE": "attention"},
        {"CRC": "00000000"},
    ],
)
def test_validate_optional_fields_accepts_valid_fields(fields):
    validate_optional_fields(fields)


@pytest.mark.parametrize(
    "fields",
    [
        {"POL": "bad"},
        {"GAMMA": "0"},
        {"GAMMA": "-1"},
        {"GAMMA": "x"},
        {"THRESH": "-1"},
        {"THRESH": "256"},
        {"THRESH": "x"},
        {"DITHER": "bad"},
        {"MODE": "bad"},
        {"CRC": "bad"},
    ],
)
def test_validate_optional_fields_rejects_invalid_fields(fields):
    with pytest.raises(BadFieldError):
        validate_optional_fields(fields)


def test_crc32_payload_is_8_uppercase_hex():
    crc = crc32_payload("⣿⠀")

    assert len(crc) == 8
    assert crc == crc.upper()
    int(crc, 16)


def test_normalize_crc_accepts_lowercase_and_uppercases():
    assert normalize_crc("abcdef12") == "ABCDEF12"


@pytest.mark.parametrize("crc", ["", "123", "123456789", "GGGGGGGG"])
def test_normalize_crc_rejects_invalid_crc(crc):
    with pytest.raises(BadFieldError):
        normalize_crc(crc)


def test_validate_packet_accepts_matching_crc():
    payload = "⣿⠀"
    crc = crc32_payload(payload)

    packet = BraillePacket(
        version="BS1",
        fields={"W": "2", "H": "1", "CELL": "2x4", "LEN": "2", "CRC": crc},
        payload=payload,
    )

    validate_packet(packet)


def test_validate_packet_rejects_bad_crc():
    packet = BraillePacket(
        version="BS1",
        fields={"W": "2", "H": "1", "CELL": "2x4", "LEN": "2", "CRC": "00000000"},
        payload="⣿⠀",
    )

    with pytest.raises(CRCMismatchError):
        validate_packet(packet)


def test_parse_positive_int_value():
    assert parse_positive_int_value("1", "W", BadWidthError) == 1

    with pytest.raises(BadWidthError):
        parse_positive_int_value("0", "W", BadWidthError)

    with pytest.raises(BadWidthError):
        parse_positive_int_value("x", "W", BadWidthError)


def test_parse_non_negative_int_value():
    assert parse_non_negative_int_value("0", "LEN", BadLengthError) == 0
    assert parse_non_negative_int_value("1", "LEN", BadLengthError) == 1

    with pytest.raises(BadLengthError):
        parse_non_negative_int_value("-1", "LEN", BadLengthError)

    with pytest.raises(BadLengthError):
        parse_non_negative_int_value("x", "LEN", BadLengthError)


def test_bs1_packet_fields_minimal():
    packet = BS1Packet(width=2, height=1, payload="⣿⠀")

    assert packet.version == "BS1"
    assert packet.length == 2
    assert packet.fields == {
        "W": "2",
        "H": "1",
        "CELL": "2x4",
        "LEN": "2",
        "MODE": "luma",
    }


def test_bs1_packet_fields_full_with_crc_and_extra_fields():
    packet = BS1Packet(
        width=2,
        height=1,
        payload="⣿⠀",
        polarity="dark-on-light",
        gamma=1.0,
        threshold=128,
        dither="none",
        mode="luma",
        crc="abcdef12",
        extra_fields={"ID": "frame0"},
    )

    fields = packet.fields

    assert fields["W"] == "2"
    assert fields["H"] == "1"
    assert fields["CELL"] == "2x4"
    assert fields["LEN"] == "2"
    assert fields["POL"] == "dark-on-light"
    assert fields["GAMMA"] == "1"
    assert fields["THRESH"] == "128"
    assert fields["DITHER"] == "none"
    assert fields["MODE"] == "luma"
    assert fields["CRC"] == "ABCDEF12"
    assert fields["ID"] == "frame0"


def test_bs1_packet_header_and_text():
    packet = BS1Packet(width=2, height=1, payload="⣿⠀")

    assert packet.header == "BS1|W=2|H=1|CELL=2x4|LEN=2|MODE=luma|"
    assert packet.text == "BS1|W=2|H=1|CELL=2x4|LEN=2|MODE=luma|\n⣿⠀"


def test_bs1_packet_with_crc():
    packet = BS1Packet(width=2, height=1, payload="⣿⠀").with_crc()

    assert packet.crc == crc32_payload("⣿⠀")
    assert packet.fields["CRC"] == crc32_payload("⣿⠀")


def test_packet_from_bs1():
    bs1 = BS1Packet(width=2, height=1, payload="⣿⠀")
    packet = packet_from_bs1(bs1)

    assert isinstance(packet, BraillePacket)
    assert packet.version == "BS1"
    assert packet.fields["W"] == "2"
    assert packet.payload == "⣿⠀"


def test_validate_bs1_packet():
    packet = BS1Packet(width=2, height=1, payload="⣿⠀")

    validate_bs1_packet(packet, strict=True)


def test_bs1_from_packet():
    packet = BraillePacket(
        version="BS1",
        fields={
            "W": "2",
            "H": "1",
            "CELL": "2x4",
            "LEN": "2",
            "POL": "dark-on-light",
            "GAMMA": "1.25",
            "THRESH": "128",
            "DITHER": "none",
            "MODE": "luma",
            "ID": "frame0",
        },
        payload="⣿⠀",
    )

    bs1 = bs1_from_packet(packet)

    assert bs1.width == 2
    assert bs1.height == 1
    assert bs1.payload == "⣿⠀"
    assert bs1.polarity == "dark-on-light"
    assert bs1.gamma == 1.25
    assert bs1.threshold == 128
    assert bs1.dither == "none"
    assert bs1.mode == "luma"
    assert bs1.extra_fields == {"ID": "frame0"}


def test_parse_bs1_packet():
    text = "BS1|W=2|H=1|CELL=2x4|LEN=2|POL=dark-on-light|\n⣿⠀"

    packet = parse_bs1_packet(text)

    assert isinstance(packet, BS1Packet)
    assert packet.width == 2
    assert packet.height == 1
    assert packet.payload == "⣿⠀"
    assert packet.polarity == "dark-on-light"


def test_build_bs1_packet_infers_height():
    packet = build_bs1_packet("⣿⠀⣿", width=2)

    assert packet.width == 2
    assert packet.height == 2
    assert packet.length == 3


def test_build_bs1_packet_with_crc():
    packet = build_bs1_packet("⣿⠀", width=2, height=1, include_crc=True)

    assert packet.crc == crc32_payload("⣿⠀")


def test_build_bs1_packet_rejects_bad_width():
    with pytest.raises(BadWidthError):
        build_bs1_packet("⣿", width=0)


def test_build_bs1_packet_rejects_bad_height():
    with pytest.raises(BadHeightError):
        build_bs1_packet("⣿", width=1, height=0)


def test_build_bs1_packet_rejects_non_braille_payload():
    with pytest.raises(NonBraillePayloadError):
        build_bs1_packet("A", width=1, height=1)


def test_infer_fields_from_payload_without_crc():
    fields = infer_fields_from_payload("⣿⠀⣿", width=2)

    assert fields == {
        "W": "2",
        "H": "2",
        "CELL": "2x4",
        "LEN": "3",
    }


def test_infer_fields_from_payload_with_crc():
    fields = infer_fields_from_payload("⣿⠀", width=2, include_crc=True)

    assert fields["W"] == "2"
    assert fields["H"] == "1"
    assert fields["CELL"] == "2x4"
    assert fields["LEN"] == "2"
    assert fields["CRC"] == crc32_payload("⣿⠀")


def test_packet_summary():
    packet = BraillePacket(
        version="BS1",
        fields={"W": "2", "H": "1", "CELL": "2x4", "LEN": "2", "CRC": crc32_payload("⣿⠀")},
        payload="⣿⠀",
    )

    summary = packet_summary(packet)

    assert summary == {
        "version": "BS1",
        "width": 2,
        "height": 1,
        "cell": "2x4",
        "length": 2,
        "declared_length": 2,
        "has_crc": True,
        "complete_rectangle": True,
    }
