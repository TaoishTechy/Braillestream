"""
Tests for BS1 packet commands in braillestream.cli.
"""

from pathlib import Path

import pytest

from braillestream.cli import main
from braillestream.packet import crc32_payload


def test_cli_packet_build_basic(tmp_path: Path):
    stream_path = tmp_path / "payload.bs"
    packet_path = tmp_path / "frame.bs1"
    stream_path.write_text("⣿⠀", encoding="utf-8")

    code = main(
        [
            "packet-build",
            str(stream_path),
            "-W",
            "2",
            "-H",
            "1",
            "-o",
            str(packet_path),
        ]
    )

    assert code == 0
    assert packet_path.read_text(encoding="utf-8") == (
        "BS1|W=2|H=1|CELL=2x4|LEN=2|MODE=luma|\n"
        "⣿⠀"
    )


def test_cli_packet_build_with_crc(tmp_path: Path):
    stream_path = tmp_path / "payload.bs"
    packet_path = tmp_path / "frame.bs1"
    stream_path.write_text("⣿⠀", encoding="utf-8")

    code = main(
        [
            "packet-build",
            str(stream_path),
            "-W",
            "2",
            "-H",
            "1",
            "--crc",
            "-o",
            str(packet_path),
        ]
    )

    assert code == 0

    text = packet_path.read_text(encoding="utf-8")
    assert f"CRC={crc32_payload('⣿⠀')}|" in text
    assert text.endswith("\n⣿⠀")


def test_cli_packet_build_infers_height(tmp_path: Path):
    stream_path = tmp_path / "payload.bs"
    packet_path = tmp_path / "frame.bs1"
    stream_path.write_text("⣿⠀⣿", encoding="utf-8")

    code = main(
        [
            "packet-build",
            str(stream_path),
            "-W",
            "2",
            "-o",
            str(packet_path),
        ]
    )

    assert code == 0
    text = packet_path.read_text(encoding="utf-8")
    assert text.startswith("BS1|W=2|H=2|CELL=2x4|LEN=3|")


def test_cli_packet_build_strict_rejects_incomplete_rectangle(tmp_path: Path, capsys):
    stream_path = tmp_path / "payload.bs"
    stream_path.write_text("⣿⠀⣿", encoding="utf-8")

    code = main(
        [
            "packet-build",
            str(stream_path),
            "-W",
            "2",
            "--strict",
        ]
    )

    assert code == 2
    captured = capsys.readouterr()
    assert "LEN == W × H" in captured.err


def test_cli_packet_build_unwraps_payload(tmp_path: Path):
    stream_path = tmp_path / "payload.bs"
    packet_path = tmp_path / "frame.bs1"
    stream_path.write_text("⣿⠀\n⣿⠀\n", encoding="utf-8")

    code = main(
        [
            "packet-build",
            str(stream_path),
            "-W",
            "4",
            "-H",
            "1",
            "--unwrap",
            "-o",
            str(packet_path),
        ]
    )

    assert code == 0
    assert packet_path.read_text(encoding="utf-8").endswith("\n⣿⠀⣿⠀")


def test_cli_packet_build_rejects_non_braille_by_default(tmp_path: Path, capsys):
    stream_path = tmp_path / "payload.bs"
    stream_path.write_text("A", encoding="utf-8")

    code = main(["packet-build", str(stream_path), "-W", "1", "-H", "1"])

    assert code == 2
    captured = capsys.readouterr()
    assert "Non-Braille character" in captured.err


def test_cli_packet_build_allows_non_braille_but_packet_validation_rejects_it(tmp_path: Path, capsys):
    stream_path = tmp_path / "payload.bs"
    stream_path.write_text("A", encoding="utf-8")

    code = main(
        [
            "packet-build",
            str(stream_path),
            "-W",
            "1",
            "-H",
            "1",
            "--allow-non-braille",
        ]
    )

    assert code == 2
    captured = capsys.readouterr()
    assert "Non-Braille character" in captured.err


def test_cli_packet_parse_summary(tmp_path: Path):
    packet_path = tmp_path / "frame.bs1"
    output_path = tmp_path / "summary.txt"
    packet_path.write_text(
        "BS1|W=2|H=1|CELL=2x4|LEN=2|MODE=luma|\n⣿⠀",
        encoding="utf-8",
    )

    code = main(
        [
            "packet-parse",
            str(packet_path),
            "--summary",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0

    text = output_path.read_text(encoding="utf-8")
    assert "version=BS1" in text
    assert "width=2" in text
    assert "height=1" in text
    assert "cell=2x4" in text
    assert "length=2" in text
    assert "declared_length=2" in text
    assert "has_crc=False" in text
    assert "complete_rectangle=True" in text


def test_cli_packet_parse_full(tmp_path: Path):
    packet_path = tmp_path / "frame.bs1"
    output_path = tmp_path / "parsed.txt"
    packet_path.write_text(
        "BS1|W=2|H=1|CELL=2x4|LEN=2|POL=dark-on-light|GAMMA=1.25|THRESH=128|DITHER=none|MODE=luma|\n⣿⠀",
        encoding="utf-8",
    )

    code = main(
        [
            "packet-parse",
            str(packet_path),
            "-o",
            str(output_path),
        ]
    )

    assert code == 0

    text = output_path.read_text(encoding="utf-8")
    assert "version=BS1" in text
    assert "width=2" in text
    assert "height=1" in text
    assert "cell=2x4" in text
    assert "length=2" in text
    assert "polarity=dark-on-light" in text
    assert "gamma=1.25" in text
    assert "threshold=128" in text
    assert "dither=none" in text
    assert "mode=luma" in text


def test_cli_packet_parse_rejects_bad_crc(tmp_path: Path, capsys):
    packet_path = tmp_path / "frame.bs1"
    packet_path.write_text(
        "BS1|W=2|H=1|CELL=2x4|LEN=2|CRC=00000000|\n⣿⠀",
        encoding="utf-8",
    )

    code = main(["packet-parse", str(packet_path)])

    assert code == 2
    captured = capsys.readouterr()
    assert "CRC mismatch" in captured.err


def test_cli_packet_parse_relaxed_allows_incomplete_rectangle(tmp_path: Path):
    packet_path = tmp_path / "frame.bs1"
    output_path = tmp_path / "summary.txt"
    packet_path.write_text(
        "BS1|W=4|H=1|CELL=2x4|LEN=2|MODE=luma|\n⣿⠀",
        encoding="utf-8",
    )

    code = main(
        [
            "packet-parse",
            str(packet_path),
            "--relaxed",
            "--summary",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert "complete_rectangle=False" in output_path.read_text(encoding="utf-8")


def test_cli_packet_parse_strict_rejects_incomplete_rectangle(tmp_path: Path, capsys):
    packet_path = tmp_path / "frame.bs1"
    packet_path.write_text(
        "BS1|W=4|H=1|CELL=2x4|LEN=2|MODE=luma|\n⣿⠀",
        encoding="utf-8",
    )

    code = main(["packet-parse", str(packet_path)])

    assert code == 2
    captured = capsys.readouterr()
    assert "LEN == W × H" in captured.err


def test_cli_packet_payload_extracts_payload(tmp_path: Path):
    packet_path = tmp_path / "frame.bs1"
    output_path = tmp_path / "payload.bs"
    packet_path.write_text(
        "BS1|W=2|H=1|CELL=2x4|LEN=2|MODE=luma|\n⣿⠀",
        encoding="utf-8",
    )

    code = main(
        [
            "packet-payload",
            str(packet_path),
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⣿⠀"


def test_cli_packet_payload_renders_payload(tmp_path: Path):
    packet_path = tmp_path / "frame.bs1"
    output_path = tmp_path / "payload.txt"
    packet_path.write_text(
        "BS1|W=4|H=1|CELL=2x4|LEN=4|MODE=luma|\n⣿⠀⣿⠀",
        encoding="utf-8",
    )

    code = main(
        [
            "packet-payload",
            str(packet_path),
            "--render-width",
            "2",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⣿⠀\n⣿⠀"


def test_cli_packet_payload_relaxed_extracts_incomplete_rectangle(tmp_path: Path):
    packet_path = tmp_path / "frame.bs1"
    output_path = tmp_path / "payload.bs"
    packet_path.write_text(
        "BS1|W=4|H=1|CELL=2x4|LEN=2|MODE=luma|\n⣿⠀",
        encoding="utf-8",
    )

    code = main(
        [
            "packet-payload",
            str(packet_path),
            "--relaxed",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⣿⠀"


def test_cli_packet_payload_no_validate_extracts_bad_packet(tmp_path: Path):
    packet_path = tmp_path / "frame.bs1"
    output_path = tmp_path / "payload.bs"
    packet_path.write_text(
        "BS1|W=4|H=1|CELL=2x4|LEN=999|MODE=luma|\n⣿⠀",
        encoding="utf-8",
    )

    code = main(
        [
            "packet-payload",
            str(packet_path),
            "--no-validate",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⣿⠀"


def test_cli_packet_payload_rejects_bad_packet_by_default(tmp_path: Path, capsys):
    packet_path = tmp_path / "frame.bs1"
    packet_path.write_text(
        "BS1|W=4|H=1|CELL=2x4|LEN=999|MODE=luma|\n⣿⠀",
        encoding="utf-8",
    )

    code = main(["packet-payload", str(packet_path)])

    assert code == 2
    captured = capsys.readouterr()
    assert "LEN field says 999" in captured.err
