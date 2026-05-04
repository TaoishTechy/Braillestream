"""
Tests for braillestream.cli.

These tests verify the command-line interface without shelling out to a real
terminal process. The CLI commands are tested through main(argv).
"""

from pathlib import Path

import pytest
from PIL import Image

from braillestream.cli import (
    build_parser,
    main,
    parse_widths,
    read_text_input,
    write_text_output,
)


def make_gray_image(path: Path, width: int = 2, height: int = 4, value: int = 0) -> Path:
    img = Image.new("L", (width, height), color=value)
    img.save(path)
    return path


def test_parse_widths_empty_values():
    assert parse_widths(None) == []
    assert parse_widths("") == []
    assert parse_widths("   ") == []


def test_parse_widths_comma_separated_values():
    assert parse_widths("40,80,120") == [40, 80, 120]


def test_parse_widths_ignores_empty_parts():
    assert parse_widths("40,,80, ,120") == [40, 80, 120]


def test_read_text_input_from_path(tmp_path: Path):
    path = tmp_path / "stream.bs"
    path.write_text("⣿⠀", encoding="utf-8")

    assert read_text_input(path) == "⣿⠀"


def test_write_text_output_to_path(tmp_path: Path):
    path = tmp_path / "out.bs"

    write_text_output("⣿⠀", path)

    assert path.read_text(encoding="utf-8") == "⣿⠀"


def test_build_parser_has_expected_program_name():
    parser = build_parser()

    assert parser.prog == "braillestream"


def test_main_no_args_returns_error(capsys):
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args([])

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "usage:" in captured.err


def test_cli_widths_from_explicit_length(capsys):
    code = main(
        [
            "widths",
            "--length",
            "12",
            "--min-width",
            "1",
            "--max-width",
            "12",
        ]
    )

    assert code == 0
    captured = capsys.readouterr()
    assert captured.out == "1\n2\n3\n4\n6\n12\n"


def test_cli_widths_all_from_explicit_length(capsys):
    code = main(
        [
            "widths",
            "--length",
            "5",
            "--min-width",
            "1",
            "--max-width",
            "5",
            "--all",
        ]
    )

    assert code == 0
    captured = capsys.readouterr()
    assert captured.out == "1\n2\n3\n4\n5\n"


def test_cli_widths_target_aspect(capsys):
    code = main(
        [
            "widths",
            "--length",
            "12",
            "--min-width",
            "1",
            "--max-width",
            "12",
            "--target-aspect",
            "1.0",
            "--count",
            "3",
        ]
    )

    assert code == 0
    captured = capsys.readouterr()
    assert captured.out == "3\n4\n2\n"


def test_cli_render_from_file(tmp_path: Path):
    stream_path = tmp_path / "stream.bs"
    output_path = tmp_path / "rendered.txt"
    stream_path.write_text("⣿⠀⣿⠀", encoding="utf-8")

    code = main(
        [
            "render",
            str(stream_path),
            "-W",
            "2",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⣿⠀\n⣿⠀"


def test_cli_render_with_padding_from_file(tmp_path: Path):
    stream_path = tmp_path / "stream.bs"
    output_path = tmp_path / "rendered.txt"
    stream_path.write_text("⣿⠀⣿", encoding="utf-8")

    code = main(
        [
            "render",
            str(stream_path),
            "-W",
            "2",
            "--pad",
            "--pad-char",
            "_",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⣿⠀\n⣿_"


def test_cli_render_rejects_non_braille_by_default(tmp_path: Path, capsys):
    stream_path = tmp_path / "stream.bs"
    stream_path.write_text("A", encoding="utf-8")

    code = main(["render", str(stream_path), "-W", "2"])

    assert code == 2
    captured = capsys.readouterr()
    assert "Non-Braille character" in captured.err


def test_cli_render_allows_non_braille_when_requested(tmp_path: Path):
    stream_path = tmp_path / "stream.bs"
    output_path = tmp_path / "rendered.txt"
    stream_path.write_text("abcd", encoding="utf-8")

    code = main(
        [
            "render",
            str(stream_path),
            "-W",
            "2",
            "--allow-non-braille",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "ab\ncd"


def test_cli_render_unwraps_wrapped_stream(tmp_path: Path):
    stream_path = tmp_path / "wrapped.bs"
    output_path = tmp_path / "rendered.txt"
    stream_path.write_text("⣿⠀\n⣿⠀\n", encoding="utf-8")

    code = main(
        [
            "render",
            str(stream_path),
            "-W",
            "4",
            "--unwrap",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⣿⠀⣿⠀"


def test_cli_inspect_from_file(tmp_path: Path):
    stream_path = tmp_path / "stream.bs"
    output_path = tmp_path / "inspect.txt"
    stream_path.write_text("⣿⠀⣿⠀", encoding="utf-8")

    code = main(
        [
            "inspect",
            str(stream_path),
            "-W",
            "2",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0

    text = output_path.read_text(encoding="utf-8")
    assert "length=4" in text
    assert "width_cells=2" in text
    assert "height_cells=2" in text
    assert "width_px=4" in text
    assert "height_px=8" in text
    assert "complete_final_row=True" in text


def test_cli_reverse_full_cell(tmp_path: Path):
    stream_path = tmp_path / "stream.bs"
    output_path = tmp_path / "pixels.txt"
    stream_path.write_text("⣿", encoding="utf-8")

    code = main(
        [
            "reverse",
            str(stream_path),
            "-W",
            "1",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "11\n11\n11\n11"


def test_cli_reverse_custom_on_off(tmp_path: Path):
    stream_path = tmp_path / "stream.bs"
    output_path = tmp_path / "pixels.txt"
    stream_path.write_text("⣿⠀", encoding="utf-8")

    code = main(
        [
            "reverse",
            str(stream_path),
            "-W",
            "2",
            "--on",
            "#",
            "--off",
            ".",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "##..\n##..\n##..\n##.."


def test_cli_density_ramp(tmp_path: Path):
    stream_path = tmp_path / "stream.bs"
    output_path = tmp_path / "density.txt"
    stream_path.write_text("⠀⣿", encoding="utf-8")

    code = main(
        [
            "density",
            str(stream_path),
            "-W",
            "2",
            "--ramp",
            " .#",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == " #"


def test_cli_density_numeric(tmp_path: Path):
    stream_path = tmp_path / "stream.bs"
    output_path = tmp_path / "density.txt"
    stream_path.write_text("⠀⣿", encoding="utf-8")

    code = main(
        [
            "density",
            str(stream_path),
            "-W",
            "2",
            "--numeric",
            "--separator",
            ",",
            "-o",
            str(output_path),
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "0.000,1.000"


def test_cli_encode_black_cell_to_file(tmp_path: Path):
    image_path = make_gray_image(tmp_path / "black.png", value=0)
    output_path = tmp_path / "out.bs"

    code = main(
        [
            "encode",
            str(image_path),
            "-o",
            str(output_path),
            "--polarity",
            "dark-on-light",
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⣿"


def test_cli_encode_white_cell_dark_on_light_to_file(tmp_path: Path):
    image_path = make_gray_image(tmp_path / "white.png", value=255)
    output_path = tmp_path / "out.bs"

    code = main(
        [
            "encode",
            str(image_path),
            "-o",
            str(output_path),
            "--polarity",
            "dark-on-light",
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⠀"


def test_cli_encode_with_header(tmp_path: Path):
    image_path = make_gray_image(tmp_path / "black.png", value=0)
    output_path = tmp_path / "out.bs"

    code = main(
        [
            "encode",
            str(image_path),
            "-o",
            str(output_path),
            "--polarity",
            "dark-on-light",
            "--header",
        ]
    )

    assert code == 0

    text = output_path.read_text(encoding="utf-8")
    assert text.startswith("BS1|W=1|H=1|CELL=2x4|")
    assert text.endswith("\n⣿")


def test_cli_encode_with_wrap(tmp_path: Path):
    image_path = make_gray_image(tmp_path / "wide.png", width=4, height=4, value=0)
    output_path = tmp_path / "out.txt"

    code = main(
        [
            "encode",
            str(image_path),
            "-o",
            str(output_path),
            "--polarity",
            "dark-on-light",
            "--wrap",
            "1",
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⣿\n⣿"


def test_cli_encode_with_dimensions_and_info(tmp_path: Path, capsys):
    image_path = make_gray_image(tmp_path / "black.png", width=10, height=10, value=0)
    output_path = tmp_path / "out.bs"

    code = main(
        [
            "encode",
            str(image_path),
            "-o",
            str(output_path),
            "-W",
            "4",
            "-H",
            "3",
            "--resize-mode",
            "stretch",
            "--polarity",
            "dark-on-light",
            "--info",
        ]
    )

    assert code == 0
    assert output_path.read_text(encoding="utf-8") == "⣿" * 12

    captured = capsys.readouterr()
    assert "source_px=10x10" in captured.err
    assert "output_px=8x12" in captured.err
    assert "cells=4x3" in captured.err
    assert "length=12" in captured.err
    assert "complete=True" in captured.err


def test_cli_encode_missing_file_returns_error(capsys):
    code = main(["encode", "missing_file.png"])

    assert code == 2
    captured = capsys.readouterr()
    assert "Image not found" in captured.err


def test_cli_density_empty_ramp_returns_error(tmp_path: Path, capsys):
    stream_path = tmp_path / "stream.bs"
    stream_path.write_text("⣿", encoding="utf-8")

    code = main(
        [
            "density",
            str(stream_path),
            "-W",
            "1",
            "--ramp",
            "",
        ]
    )

    assert code == 2
    captured = capsys.readouterr()
    assert "Density ramp cannot be empty" in captured.err
