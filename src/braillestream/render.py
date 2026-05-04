"""
BrailleStream Render Geometry
=============================

Projection and wrapping helpers for BrailleStream.

BrailleStream stores visual data as a one-dimensional Unicode Braille stream.
A render width `W` folds that stream into a two-dimensional text field:

    x = index mod W
    y = floor(index / W)

This module makes that folding geometry explicit.

It does not encode images.
It does not decode Braille dots.
It only handles stream projection, wrapping, unwrapping, and coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable, Iterator

from braillestream.mapping import is_braille_char


@dataclass(frozen=True)
class ProjectionCell:
    """
    One projected BrailleStream glyph.

    Attributes
    ----------
    index:
        Original one-dimensional stream index.

    x:
        Column after wrapping at width W.

    y:
        Row after wrapping at width W.

    char:
        Unicode character at this projected position.
    """

    index: int
    x: int
    y: int
    char: str


@dataclass(frozen=True)
class RenderDimensions:
    """
    Dimensions of a stream rendered at a given Braille-cell width.

    Width and height are measured in Braille glyph cells.

    Pixel dimensions are measured in Braille micro-pixels:

        1 Braille cell = 2 px wide × 4 px tall
    """

    width_cells: int
    height_cells: int
    width_px: int
    height_px: int
    length: int
    complete_final_row: bool


def validate_width(width: int) -> int:
    """
    Validate a render width.

    Parameters
    ----------
    width:
        Number of Braille glyph cells per rendered row.

    Returns
    -------
    int
        Validated positive width.

    Raises
    ------
    ValueError
        If width is less than 1.
    """
    width = int(width)

    if width <= 0:
        raise ValueError(f"Render width must be positive, got {width}.")

    return width


def validate_index(index: int) -> int:
    """
    Validate a non-negative stream index.
    """
    index = int(index)

    if index < 0:
        raise ValueError(f"Index must be non-negative, got {index}.")

    return index


def index_to_xy(index: int, width: int) -> tuple[int, int]:
    """
    Convert one-dimensional stream index to projected 2D coordinate.

    Formula:

        x = index mod width
        y = floor(index / width)

    Examples
    --------
    >>> index_to_xy(0, 80)
    (0, 0)
    >>> index_to_xy(80, 80)
    (0, 1)
    """
    index = validate_index(index)
    width = validate_width(width)

    return index % width, index // width


def xy_to_index(x: int, y: int, width: int) -> int:
    """
    Convert projected 2D coordinate back to one-dimensional stream index.

    Formula:

        index = y * width + x
    """
    x = int(x)
    y = int(y)
    width = validate_width(width)

    if x < 0:
        raise ValueError(f"x must be non-negative, got {x}.")

    if y < 0:
        raise ValueError(f"y must be non-negative, got {y}.")

    if x >= width:
        raise ValueError(f"x={x} is outside render width {width}.")

    return y * width + x


def render_dimensions(stream: str, width: int) -> RenderDimensions:
    """
    Return rendered dimensions for a stream at width W.

    The final row may be incomplete if len(stream) is not divisible by width.
    """
    width = validate_width(width)
    length = len(stream)

    height_cells = ceil(length / width) if length else 0

    return RenderDimensions(
        width_cells=width,
        height_cells=height_cells,
        width_px=width * 2,
        height_px=height_cells * 4,
        length=length,
        complete_final_row=(length % width == 0 if length else True),
    )


def wrap_stream_rows(stream: str, width: int, pad: bool = False, pad_char: str = "⠀") -> list[str]:
    """
    Hard-wrap a single-line stream into rows.

    Parameters
    ----------
    stream:
        Input stream.

    width:
        Number of characters per row.

    pad:
        If True, pad the final row to `width`.

    pad_char:
        Character used for final-row padding. Defaults to blank Braille U+2800.

    Returns
    -------
    list[str]
        Wrapped rows.

    Examples
    --------
    >>> wrap_stream_rows("abcdef", 2)
    ['ab', 'cd', 'ef']
    """
    width = validate_width(width)

    if len(pad_char) != 1:
        raise ValueError("pad_char must be exactly one character.")

    rows = [stream[start : start + width] for start in range(0, len(stream), width)]

    if pad and rows and len(rows[-1]) < width:
        rows[-1] = rows[-1] + (pad_char * (width - len(rows[-1])))

    return rows


def wrap_stream(stream: str, width: int, pad: bool = False, pad_char: str = "⠀") -> str:
    """
    Hard-wrap a single-line stream into newline-separated rows.

    This is useful when you want to force a projection instead of relying on
    textarea or terminal soft wrapping.
    """
    return "\n".join(wrap_stream_rows(stream, width, pad=pad, pad_char=pad_char))


def unwrap_stream(text: str, strip_spaces: bool = False) -> str:
    """
    Remove line breaks from wrapped text, returning a one-line stream.

    Parameters
    ----------
    text:
        Wrapped text.

    strip_spaces:
        If True, remove regular spaces and tabs as well.

        This should usually stay False, because spaces may be intentional data
        in non-pure Braille experiments.
    """
    stream = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "")

    if strip_spaces:
        stream = stream.replace(" ", "").replace("\t", "")

    return stream


def iter_projection(stream: str, width: int) -> Iterator[ProjectionCell]:
    """
    Iterate over stream characters with their projected coordinates.

    Yields
    ------
    ProjectionCell
        index, x, y, char.
    """
    width = validate_width(width)

    for index, char in enumerate(stream):
        x, y = index_to_xy(index, width)
        yield ProjectionCell(index=index, x=x, y=y, char=char)


def projection_grid(
    stream: str,
    width: int,
    pad: bool = False,
    pad_char: str = "⠀",
) -> list[list[str]]:
    """
    Convert a stream into a 2D character grid.

    Parameters
    ----------
    stream:
        Input stream.

    width:
        Number of cells per row.

    pad:
        If True, pad the final row to full width.

    Returns
    -------
    list[list[str]]
        2D grid of characters.
    """
    rows = wrap_stream_rows(stream, width, pad=pad, pad_char=pad_char)
    return [list(row) for row in rows]


def get_cell(stream: str, x: int, y: int, width: int, default: str | None = None) -> str | None:
    """
    Get projected cell at coordinate (x, y).

    If the coordinate maps beyond the stream length:

        - return `default` if provided
        - otherwise raise IndexError
    """
    index = xy_to_index(x, y, width)

    if index >= len(stream):
        if default is not None:
            return default
        raise IndexError(
            f"Coordinate ({x}, {y}) maps to index {index}, "
            f"but stream length is {len(stream)}."
        )

    return stream[index]


def set_cell(stream: str, x: int, y: int, width: int, char: str) -> str:
    """
    Return a copy of stream with one projected cell replaced.

    This does not mutate the original string.
    """
    if len(char) != 1:
        raise ValueError("Replacement char must be exactly one character.")

    index = xy_to_index(x, y, width)

    if index >= len(stream):
        raise IndexError(
            f"Coordinate ({x}, {y}) maps to index {index}, "
            f"but stream length is {len(stream)}."
        )

    return stream[:index] + char + stream[index + 1 :]


def crop_projection(
    stream: str,
    width: int,
    x: int,
    y: int,
    crop_width: int,
    crop_height: int,
    fill: str = "⠀",
) -> list[str]:
    """
    Crop a rectangular region from a projected stream.

    Missing cells outside the stream are filled with `fill`.

    Returns rows as strings.
    """
    width = validate_width(width)
    x = int(x)
    y = int(y)
    crop_width = int(crop_width)
    crop_height = int(crop_height)

    if x < 0:
        raise ValueError(f"x must be non-negative, got {x}.")

    if y < 0:
        raise ValueError(f"y must be non-negative, got {y}.")

    if crop_width <= 0:
        raise ValueError(f"crop_width must be positive, got {crop_width}.")

    if crop_height <= 0:
        raise ValueError(f"crop_height must be positive, got {crop_height}.")

    if len(fill) != 1:
        raise ValueError("fill must be exactly one character.")

    rows: list[str] = []

    for yy in range(y, y + crop_height):
        row_chars: list[str] = []
        for xx in range(x, x + crop_width):
            if xx >= width:
                row_chars.append(fill)
                continue

            row_chars.append(get_cell(stream, xx, yy, width, default=fill) or fill)

        rows.append("".join(row_chars))

    return rows


def overlay_streams(
    base: str,
    overlay: str,
    overlay_offset: int = 0,
    transparent: str = "⠀",
) -> str:
    """
    Overlay one stream onto another in one-dimensional index space.

    Any overlay character equal to `transparent` leaves the base unchanged.

    This is intentionally 1D. For 2D overlay, compute offset as:

        overlay_offset = y * width + x
    """
    overlay_offset = int(overlay_offset)

    if overlay_offset < 0:
        raise ValueError(f"overlay_offset must be non-negative, got {overlay_offset}.")

    if len(transparent) != 1:
        raise ValueError("transparent must be exactly one character.")

    output = list(base)

    required_length = overlay_offset + len(overlay)

    if required_length > len(output):
        output.extend(transparent * (required_length - len(output)))

    for i, char in enumerate(overlay):
        if char == transparent:
            continue

        output[overlay_offset + i] = char

    return "".join(output)


def validate_pure_braille_stream(stream: str) -> bool:
    """
    Return True if every character in stream is Unicode Braille.

    Empty streams return True.
    """
    return all(is_braille_char(char) for char in stream)


def require_pure_braille_stream(stream: str) -> str:
    """
    Validate that a stream contains only Unicode Braille characters.

    Returns the stream unchanged if valid.
    """
    for index, char in enumerate(stream):
        if not is_braille_char(char):
            raise ValueError(
                f"Non-Braille character at index {index}: {char!r} "
                f"(U+{ord(char):04X})"
            )

    return stream


def width_candidates_for_length(
    length: int,
    min_width: int = 1,
    max_width: int | None = None,
    divisors_only: bool = True,
) -> list[int]:
    """
    Return candidate projection widths for a stream length.

    Parameters
    ----------
    length:
        Stream length.

    min_width:
        Smallest width to consider.

    max_width:
        Largest width to consider. Defaults to length.

    divisors_only:
        If True, only widths that divide length exactly are returned.

    Returns
    -------
    list[int]
        Candidate widths.
    """
    length = int(length)
    min_width = validate_width(min_width)

    if length < 0:
        raise ValueError(f"length must be non-negative, got {length}.")

    if length == 0:
        return []

    if max_width is None:
        max_width = length
    else:
        max_width = int(max_width)

    if max_width <= 0:
        raise ValueError(f"max_width must be positive, got {max_width}.")

    if max_width < min_width:
        return []

    max_width = min(max_width, length)

    widths: list[int] = []

    for width in range(min_width, max_width + 1):
        if divisors_only and length % width != 0:
            continue
        widths.append(width)

    return widths


def aspect_ratio_for_width(length: int, width: int) -> float:
    """
    Return projected cell aspect ratio for a stream length at width.

    Ratio is:

        width_cells / height_cells

    Returns 0.0 for empty length.
    """
    length = int(length)
    width = validate_width(width)

    if length < 0:
        raise ValueError(f"length must be non-negative, got {length}.")

    if length == 0:
        return 0.0

    height = ceil(length / width)
    return width / height


def rank_widths_by_aspect(
    length: int,
    target_aspect: float,
    min_width: int = 1,
    max_width: int | None = None,
    divisors_only: bool = True,
) -> list[tuple[float, int]]:
    """
    Rank candidate widths by closeness to a target cell aspect ratio.

    Returns
    -------
    list[tuple[float, int]]
        Sorted list of (error, width).
    """
    target_aspect = float(target_aspect)

    if target_aspect <= 0:
        raise ValueError(f"target_aspect must be positive, got {target_aspect}.")

    candidates = width_candidates_for_length(
        length,
        min_width=min_width,
        max_width=max_width,
        divisors_only=divisors_only,
    )

    ranked = [
        (abs(aspect_ratio_for_width(length, width) - target_aspect), width)
        for width in candidates
    ]

    ranked.sort(key=lambda item: (item[0], item[1]))
    return ranked


def best_widths_by_aspect(
    length: int,
    target_aspect: float,
    count: int = 10,
    min_width: int = 1,
    max_width: int | None = None,
    divisors_only: bool = True,
) -> list[int]:
    """
    Return best candidate widths by target aspect ratio.
    """
    count = int(count)

    if count <= 0:
        raise ValueError(f"count must be positive, got {count}.")

    ranked = rank_widths_by_aspect(
        length,
        target_aspect=target_aspect,
        min_width=min_width,
        max_width=max_width,
        divisors_only=divisors_only,
    )

    return [width for _, width in ranked[:count]]
