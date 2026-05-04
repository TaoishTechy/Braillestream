"""
BrailleStream CLI
=================

Command-line interface for BrailleStream.

Primary commands:

    encode      image -> single-line BrailleStream
    render      stream -> hard-wrapped rows
    reverse     stream -> decoded 0/1 pixel grid text
    density     stream -> glyph density grid
    inspect     stream -> metadata and width geometry
    widths      stream length -> candidate projection widths
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from braillestream.codec import (
    EncodeOptions,
    image_to_braille_stream,
    load_stream,
    save_stream,
    stream_to_density_grid,
    stream_to_pixel_grid,
)
from braillestream.render import (
    best_widths_by_aspect,
    render_dimensions,
    require_pure_braille_stream,
    unwrap_stream,
    width_candidates_for_length,
    wrap_stream,
)
from braillestream.packet import (
    build_bs1_packet,
    packet_summary,
    parse_bs1_packet,
    parse_packet,
    validate_packet,
)

def read_text_input(path: str | Path | None) -> str:
    """
    Read UTF-8 text from a path or stdin.

    If path is None or "-", stdin is used.
    """
    if path is None or str(path) == "-":
        return sys.stdin.read()

    return Path(path).read_text(encoding="utf-8")


def write_text_output(text: str, path: str | Path | None) -> None:
    """
    Write UTF-8 text to a path or stdout.

    If path is None or "-", stdout is used.
    """
    if path is None or str(path) == "-":
        sys.stdout.write(text)
        if text and not text.endswith("\n"):
            sys.stdout.write("\n")
        return

    Path(path).write_text(text, encoding="utf-8")


def parse_widths(value: str | None) -> list[int]:
    """
    Parse comma-separated integer widths.
    """
    if not value:
        return []

    widths: list[int] = []

    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        widths.append(int(part))

    return widths


def add_common_stream_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "stream",
        nargs="?",
        default="-",
        help="BrailleStream file path, or '-' / omitted for stdin.",
    )
    parser.add_argument(
        "--allow-non-braille",
        action="store_true",
        help="Allow non-Braille characters in the stream.",
    )
    parser.add_argument(
        "--unwrap",
        action="store_true",
        help="Remove line breaks before processing.",
    )
    parser.add_argument(
        "--strip-spaces",
        action="store_true",
        help="When used with --unwrap, also remove spaces and tabs.",
    )


def prepare_stream(args: argparse.Namespace) -> str:
    """
    Load and optionally unwrap/validate a stream from CLI args.
    """
    stream = read_text_input(args.stream)

    if getattr(args, "unwrap", False):
        stream = unwrap_stream(stream, strip_spaces=getattr(args, "strip_spaces", False))

    # Most stream files have a trailing newline if saved from stdout.
    # Remove line endings unless user is intentionally processing raw wrapped text.
    if not getattr(args, "unwrap", False):
        stream = stream.rstrip("\r\n")

    if not getattr(args, "allow_non_braille", False):
        require_pure_braille_stream(stream)

    return stream


def command_encode(args: argparse.Namespace) -> int:
    """
    Encode an image into a BrailleStream.
    """
    options = EncodeOptions(
        width_cells=args.width,
        height_cells=args.height,
        threshold=args.threshold,
        gamma=args.gamma,
        dither=args.dither,
        invert=args.invert,
        polarity=args.polarity,
        resize_mode=args.resize_mode,
    )

    encoded = image_to_braille_stream(args.image, options)

    payload = encoded.stream

    if args.header:
        payload = (
            f"BS1|W={encoded.width_cells}|H={encoded.height_cells}|"
            f"CELL=2x4|POL={options.polarity}|GAMMA={options.gamma}|"
            f"LEN={encoded.length}|\n"
            f"{encoded.stream}"
        )

    if args.wrap:
        payload = wrap_stream(encoded.stream, args.wrap)

    write_text_output(payload, args.output)

    if args.info:
        print(
            "\n".join(
                [
                    f"source_px={encoded.source_width_px}x{encoded.source_height_px}",
                    f"output_px={encoded.output_width_px}x{encoded.output_height_px}",
                    f"cells={encoded.width_cells}x{encoded.height_cells}",
                    f"length={encoded.length}",
                    f"complete={encoded.is_complete}",
                ]
            ),
            file=sys.stderr,
        )

    return 0


def command_render(args: argparse.Namespace) -> int:
    """
    Hard-wrap a BrailleStream at a chosen width.
    """
    stream = prepare_stream(args)

    rendered = wrap_stream(
        stream,
        width=args.width,
        pad=args.pad,
        pad_char=args.pad_char,
    )

    write_text_output(rendered, args.output)
    return 0


def command_reverse(args: argparse.Namespace) -> int:
    """
    Decode a BrailleStream into a 0/1 pixel grid text representation.
    """
    stream = prepare_stream(args)
    pixels = stream_to_pixel_grid(stream, width_cells=args.width)

    on = args.on
    off = args.off

    rows = ["".join(on if value else off for value in row) for row in pixels]
    write_text_output("\n".join(rows), args.output)
    return 0


def command_density(args: argparse.Namespace) -> int:
    """
    Decode a BrailleStream into a glyph-density grid.
    """
    stream = prepare_stream(args)
    grid = stream_to_density_grid(stream, width_cells=args.width)

    if args.numeric:
        rows = [
            args.separator.join(f"{value:.3f}" for value in row)
            for row in grid
        ]
    else:
        ramp = args.ramp
        if not ramp:
            raise ValueError("Density ramp cannot be empty.")

        rows = []
        for row in grid:
            chars = []
            for value in row:
                index = round(value * (len(ramp) - 1))
                chars.append(ramp[index])
            rows.append("".join(chars))

    write_text_output("\n".join(rows), args.output)
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    """
    Print stream and projection information.
    """
    stream = prepare_stream(args)
    dims = render_dimensions(stream, args.width)

    lines = [
        f"length={dims.length}",
        f"width_cells={dims.width_cells}",
        f"height_cells={dims.height_cells}",
        f"width_px={dims.width_px}",
        f"height_px={dims.height_px}",
        f"complete_final_row={dims.complete_final_row}",
    ]

    write_text_output("\n".join(lines), args.output)
    return 0


def command_widths(args: argparse.Namespace) -> int:
    """
    Suggest candidate projection widths.
    """
    if args.length is not None:
        length = args.length
    else:
        stream = prepare_stream(args)
        length = len(stream)

    if args.target_aspect is not None:
        widths = best_widths_by_aspect(
            length=length,
            target_aspect=args.target_aspect,
            count=args.count,
            min_width=args.min_width,
            max_width=args.max_width,
            divisors_only=not args.all,
        )
    else:
        widths = width_candidates_for_length(
            length=length,
            min_width=args.min_width,
            max_width=args.max_width,
            divisors_only=not args.all,
        )

        widths = widths[: args.count]

    write_text_output("\n".join(str(width) for width in widths), args.output)
    return 0

def command_packet_build(args: argparse.Namespace) -> int:
    """
    Build a BS1 packet from a raw BrailleStream payload.
    """
    payload = read_text_input(args.stream)

    if args.unwrap:
        payload = unwrap_stream(payload, strip_spaces=args.strip_spaces)
    else:
        payload = payload.rstrip("\r\n")

    if not args.allow_non_braille:
        require_pure_braille_stream(payload)

    packet = build_bs1_packet(
        payload=payload,
        width=args.width,
        height=args.height,
        polarity=args.polarity,
        gamma=args.gamma,
        threshold=args.threshold,
        dither=args.dither_mode,
        mode=args.mode,
        include_crc=args.crc,
    )

    if args.strict:
        validate_packet(parse_packet(packet.text), strict=True)

    write_text_output(packet.text, args.output)
    return 0


def command_packet_parse(args: argparse.Namespace) -> int:
    """
    Parse and validate a BS1 packet.
    """
    text = read_text_input(args.packet)

    packet = parse_packet(
        text,
        unwrap_payload=args.unwrap_payload,
        strip_payload_spaces=args.strip_spaces,
        validate=True,
        strict=args.strict,
    )

    if args.summary:
        summary = packet_summary(packet)
        lines = [f"{key}={value}" for key, value in summary.items()]
        write_text_output("\n".join(lines), args.output)
        return 0

    bs1 = parse_bs1_packet(
        text,
        unwrap_payload=args.unwrap_payload,
        strip_payload_spaces=args.strip_spaces,
        strict=args.strict,
    )

    lines = [
        f"version={bs1.version}",
        f"width={bs1.width}",
        f"height={bs1.height}",
        f"cell={bs1.cell}",
        f"length={bs1.length}",
        f"polarity={bs1.polarity}",
        f"gamma={bs1.gamma}",
        f"threshold={bs1.threshold}",
        f"dither={bs1.dither}",
        f"mode={bs1.mode}",
        f"crc={bs1.crc}",
    ]

    if bs1.extra_fields:
        for key, value in sorted(bs1.extra_fields.items()):
            lines.append(f"extra.{key}={value}")

    write_text_output("\n".join(lines), args.output)
    return 0


def command_packet_payload(args: argparse.Namespace) -> int:
    """
    Extract payload from a BS1 packet.
    """
    text = read_text_input(args.packet)

    packet = parse_packet(
        text,
        unwrap_payload=args.unwrap_payload,
        strip_payload_spaces=args.strip_spaces,
        validate=not args.no_validate,
        strict=args.strict,
    )

    payload = packet.payload

    if args.render_width is not None:
        payload = wrap_stream(
            payload,
            width=args.render_width,
            pad=args.pad,
            pad_char=args.pad_char,
        )

    write_text_output(payload, args.output)
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="braillestream",
        description="Text-native visual encoding using Unicode Braille streams.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # encode
    encode = subparsers.add_parser(
        "encode",
        help="Encode an image into a single-line BrailleStream.",
    )
    encode.add_argument("image", help="Input image path.")
    encode.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output stream path, or '-' for stdout.",
    )
    encode.add_argument(
        "-W",
        "--width",
        type=int,
        default=None,
        help="Target width in Braille cells.",
    )
    encode.add_argument(
        "-H",
        "--height",
        type=int,
        default=None,
        help="Target height in Braille cells.",
    )
    encode.add_argument(
        "--threshold",
        type=int,
        default=128,
        help="Luminance threshold 0..255.",
    )
    encode.add_argument(
        "--gamma",
        type=float,
        default=1.0,
        help="Gamma correction factor.",
    )
    encode.add_argument(
        "--dither",
        action="store_true",
        help="Apply Floyd-Steinberg dithering.",
    )
    encode.add_argument(
        "--invert",
        action="store_true",
        help="Invert grayscale before thresholding.",
    )
    encode.add_argument(
        "--polarity",
        choices=["dark-on-light", "light-on-dark"],
        default="dark-on-light",
        help="Which luminance side becomes raised Braille dots.",
    )
    encode.add_argument(
        "--resize-mode",
        choices=["none", "fit", "stretch", "crop"],
        default="none",
        help="Resize behavior when target dimensions are supplied.",
    )
    encode.add_argument(
        "--header",
        action="store_true",
        help="Prepend a simple BS1 metadata header.",
    )
    encode.add_argument(
        "--wrap",
        type=int,
        default=None,
        help="Hard-wrap encoded stream at this width before output.",
    )
    encode.add_argument(
        "--info",
        action="store_true",
        help="Print encode metadata to stderr.",
    )
    encode.set_defaults(func=command_encode)

    # render
    render = subparsers.add_parser(
        "render",
        help="Hard-wrap a BrailleStream at a selected width.",
    )
    add_common_stream_input_args(render)
    render.add_argument(
        "-W",
        "--width",
        type=int,
        required=True,
        help="Render width in Braille cells.",
    )
    render.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output path, or '-' for stdout.",
    )
    render.add_argument(
        "--pad",
        action="store_true",
        help="Pad final row.",
    )
    render.add_argument(
        "--pad-char",
        default="⠀",
        help="Padding character.",
    )
    render.set_defaults(func=command_render)

    # reverse
    reverse = subparsers.add_parser(
        "reverse",
        help="Decode a BrailleStream into a 0/1 pixel grid text preview.",
    )
    add_common_stream_input_args(reverse)
    reverse.add_argument(
        "-W",
        "--width",
        type=int,
        required=True,
        help="Render width in Braille cells.",
    )
    reverse.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output path, or '-' for stdout.",
    )
    reverse.add_argument(
        "--on",
        default="1",
        help="Character for raised pixels.",
    )
    reverse.add_argument(
        "--off",
        default="0",
        help="Character for empty pixels.",
    )
    reverse.set_defaults(func=command_reverse)

    # density
    density = subparsers.add_parser(
        "density",
        help="Decode a BrailleStream into a glyph-density grid.",
    )
    add_common_stream_input_args(density)
    density.add_argument(
        "-W",
        "--width",
        type=int,
        required=True,
        help="Render width in Braille cells.",
    )
    density.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output path, or '-' for stdout.",
    )
    density.add_argument(
        "--numeric",
        action="store_true",
        help="Output numeric density values instead of ramp characters.",
    )
    density.add_argument(
        "--separator",
        default=" ",
        help="Separator for numeric density output.",
    )
    density.add_argument(
        "--ramp",
        default=" .:-=+*#@",
        help="Density ramp for non-numeric output.",
    )
    density.set_defaults(func=command_density)

    # inspect
    inspect = subparsers.add_parser(
        "inspect",
        help="Inspect stream length and projection geometry.",
    )
    add_common_stream_input_args(inspect)
    inspect.add_argument(
        "-W",
        "--width",
        type=int,
        required=True,
        help="Render width in Braille cells.",
    )
    inspect.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output path, or '-' for stdout.",
    )
    inspect.set_defaults(func=command_inspect)

    # widths
    widths = subparsers.add_parser(
        "widths",
        help="Suggest candidate projection widths.",
    )
    add_common_stream_input_args(widths)
    widths.add_argument(
        "--length",
        type=int,
        default=None,
        help="Use explicit stream length instead of reading a stream.",
    )
    widths.add_argument(
        "--min-width",
        type=int,
        default=1,
        help="Minimum candidate width.",
    )
    widths.add_argument(
        "--max-width",
        type=int,
        default=None,
        help="Maximum candidate width.",
    )
    widths.add_argument(
        "--all",
        action="store_true",
        help="Include non-divisor widths.",
    )
    widths.add_argument(
        "--target-aspect",
        type=float,
        default=None,
        help="Rank widths by closeness to target cell aspect ratio.",
    )
    widths.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of widths to output.",
    )
    widths.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output path, or '-' for stdout.",
    )
    widths.set_defaults(func=command_widths)

    # packet-build
    packet_build = subparsers.add_parser(
        "packet-build",
        help="Build a BS1 packet from a raw BrailleStream payload.",
    )
    packet_build.add_argument(
        "stream",
        nargs="?",
        default="-",
        help="Raw BrailleStream payload path, or '-' / omitted for stdin.",
    )
    packet_build.add_argument(
        "-W",
        "--width",
        type=int,
        required=True,
        help="Packet render width in Braille cells.",
    )
    packet_build.add_argument(
        "-H",
        "--height",
        type=int,
        default=None,
        help="Packet render height in Braille cells. Inferred if omitted.",
    )
    packet_build.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output packet path, or '-' for stdout.",
    )
    packet_build.add_argument(
        "--polarity",
        choices=["dark-on-light", "light-on-dark"],
        default=None,
        help="Optional POL field.",
    )
    packet_build.add_argument(
        "--gamma",
        type=float,
        default=None,
        help="Optional GAMMA field.",
    )
    packet_build.add_argument(
        "--threshold",
        type=int,
        default=None,
        help="Optional THRESH field.",
    )
    packet_build.add_argument(
        "--dither-mode",
        choices=["none", "floyd-steinberg", "ordered", "adaptive"],
        default=None,
        help="Optional DITHER field.",
    )
    packet_build.add_argument(
        "--mode",
        choices=[
            "luma",
            "mask",
            "density",
            "depth",
            "attention",
            "delta",
            "ansi-color",
            "sensorium",
        ],
        default="luma",
        help="Optional MODE field.",
    )
    packet_build.add_argument(
        "--crc",
        action="store_true",
        help="Include CRC32 payload checksum.",
    )
    packet_build.add_argument(
        "--strict",
        action="store_true",
        help="Require LEN == W × H.",
    )
    packet_build.add_argument(
        "--unwrap",
        action="store_true",
        help="Remove line breaks from payload before packetizing.",
    )
    packet_build.add_argument(
        "--strip-spaces",
        action="store_true",
        help="When used with --unwrap, remove spaces and tabs too.",
    )
    packet_build.add_argument(
        "--allow-non-braille",
        action="store_true",
        help="Allow non-Braille characters in payload.",
    )
    packet_build.set_defaults(func=command_packet_build)

    # packet-parse
    packet_parse = subparsers.add_parser(
        "packet-parse",
        help="Parse and validate a BS1 packet.",
    )
    packet_parse.add_argument(
        "packet",
        nargs="?",
        default="-",
        help="BS1 packet path, or '-' / omitted for stdin.",
    )
    packet_parse.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output path, or '-' for stdout.",
    )
    packet_parse.add_argument(
        "--summary",
        action="store_true",
        help="Print compact packet summary.",
    )
    packet_parse.add_argument(
        "--relaxed",
        action="store_true",
        help="Use relaxed validation instead of strict rectangle validation.",
    )
    packet_parse.add_argument(
        "--unwrap-payload",
        action="store_true",
        help="Remove payload line breaks before validation.",
    )
    packet_parse.add_argument(
        "--strip-spaces",
        action="store_true",
        help="When used with --unwrap-payload, remove spaces and tabs too.",
    )
    packet_parse.set_defaults(
        func=lambda args: command_packet_parse(
            argparse.Namespace(**{**vars(args), "strict": not args.relaxed})
        )
    )

    # packet-payload
    packet_payload = subparsers.add_parser(
        "packet-payload",
        help="Extract payload from a BS1 packet.",
    )
    packet_payload.add_argument(
        "packet",
        nargs="?",
        default="-",
        help="BS1 packet path, or '-' / omitted for stdin.",
    )
    packet_payload.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output path, or '-' for stdout.",
    )
    packet_payload.add_argument(
        "--relaxed",
        action="store_true",
        help="Use relaxed validation instead of strict rectangle validation.",
    )
    packet_payload.add_argument(
        "--no-validate",
        action="store_true",
        help="Extract payload without validating packet.",
    )
    packet_payload.add_argument(
        "--unwrap-payload",
        action="store_true",
        help="Remove payload line breaks.",
    )
    packet_payload.add_argument(
        "--strip-spaces",
        action="store_true",
        help="When used with --unwrap-payload, remove spaces and tabs too.",
    )
    packet_payload.add_argument(
        "--render-width",
        type=int,
        default=None,
        help="Hard-wrap extracted payload at this width.",
    )
    packet_payload.add_argument(
        "--pad",
        action="store_true",
        help="Pad final rendered row when using --render-width.",
    )
    packet_payload.add_argument(
        "--pad-char",
        default="⠀",
        help="Padding character for --pad.",
    )
    packet_payload.set_defaults(
        func=lambda args: command_packet_payload(
            argparse.Namespace(**{**vars(args), "strict": not args.relaxed})
        )
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except BrokenPipeError:  # pragma: no cover
        return 1
    except Exception as exc:
        print(f"braillestream: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
