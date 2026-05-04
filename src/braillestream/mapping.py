"""
BrailleStream Unicode Braille Mapping
=====================================

Core mapping layer for BrailleStream.

A Unicode Braille glyph represents a 2×4 micro-pixel cell:

    dot layout:

        1 4
        2 5
        3 6
        7 8

Unicode Braille characters live at:

    U+2800 .. U+28FF

The final codepoint is:

    U+2800 + bitmask

where each raised dot sets one bit.

This module provides safe, reversible conversion between:

    2×4 binary blocks
    8-bit masks
    Unicode Braille glyphs
    dot-count / density values
"""

from __future__ import annotations

from typing import Iterable, Sequence

BRAILLE_START = 0x2800
BRAILLE_END = 0x28FF
BRAILLE_COUNT = 256

# Internal BrailleStream block order:
#
#   index positions in a flattened 2×4 row-major block:
#
#       0 1
#       2 3
#       4 5
#       6 7
#
# Unicode Braille bit positions:
#
#       dot 1 -> bit 0 -> row 0, col 0
#       dot 2 -> bit 1 -> row 1, col 0
#       dot 3 -> bit 2 -> row 2, col 0
#       dot 4 -> bit 3 -> row 0, col 1
#       dot 5 -> bit 4 -> row 1, col 1
#       dot 6 -> bit 5 -> row 2, col 1
#       dot 7 -> bit 6 -> row 3, col 0
#       dot 8 -> bit 7 -> row 3, col 1
#
# Therefore:
#
#   row-major index -> Unicode Braille bit index
#
ROW_MAJOR_TO_BRAILLE_BIT: tuple[int, ...] = (
    0,  # row 0, col 0 -> dot 1
    3,  # row 0, col 1 -> dot 4
    1,  # row 1, col 0 -> dot 2
    4,  # row 1, col 1 -> dot 5
    2,  # row 2, col 0 -> dot 3
    5,  # row 2, col 1 -> dot 6
    6,  # row 3, col 0 -> dot 7
    7,  # row 3, col 1 -> dot 8
)

# Reverse:
#
#   Unicode Braille bit index -> row-major index
#
BRAILLE_BIT_TO_ROW_MAJOR: tuple[int, ...] = (
    0,  # dot 1 -> row-major 0
    2,  # dot 2 -> row-major 2
    4,  # dot 3 -> row-major 4
    1,  # dot 4 -> row-major 1
    3,  # dot 5 -> row-major 3
    5,  # dot 6 -> row-major 5
    6,  # dot 7 -> row-major 6
    7,  # dot 8 -> row-major 7
)


def clamp_mask(mask: int) -> int:
    """
    Clamp an integer to the valid 8-bit Braille mask range.

    Parameters
    ----------
    mask:
        Any integer.

    Returns
    -------
    int
        Integer in range 0..255.
    """
    return max(0, min(BRAILLE_COUNT - 1, int(mask)))


def mask_to_char(mask: int) -> str:
    """
    Convert an 8-bit Unicode Braille mask to a Unicode Braille character.

    This assumes `mask` already uses Unicode Braille bit order.

    Examples
    --------
    >>> mask_to_char(0)
    '⠀'
    >>> mask_to_char(255)
    '⣿'
    """
    mask = clamp_mask(mask)
    return chr(BRAILLE_START + mask)


def char_to_mask(char: str) -> int:
    """
    Convert a Unicode Braille character to its 8-bit mask.

    Parameters
    ----------
    char:
        A single Unicode Braille character.

    Returns
    -------
    int
        Mask in range 0..255.

    Raises
    ------
    ValueError
        If the input is not exactly one Unicode Braille character.
    """
    if len(char) != 1:
        raise ValueError(f"Expected exactly one character, got {len(char)}.")

    codepoint = ord(char)

    if not BRAILLE_START <= codepoint <= BRAILLE_END:
        raise ValueError(
            f"Character {char!r} is not in Unicode Braille range "
            f"U+2800..U+28FF."
        )

    return codepoint - BRAILLE_START


def row_major_bits_to_mask(bits: Sequence[int | bool]) -> int:
    """
    Convert 8 row-major 2×4 bits into a Unicode Braille mask.

    Input order:

        0 1
        2 3
        4 5
        6 7

    Unicode Braille order:

        1 4
        2 5
        3 6
        7 8

    Parameters
    ----------
    bits:
        Sequence of 8 truthy/falsy values.

    Returns
    -------
    int
        Unicode Braille mask in range 0..255.
    """
    if len(bits) != 8:
        raise ValueError(f"Expected 8 bits for a 2×4 Braille cell, got {len(bits)}.")

    mask = 0

    for row_major_index, value in enumerate(bits):
        if bool(value):
            braille_bit = ROW_MAJOR_TO_BRAILLE_BIT[row_major_index]
            mask |= 1 << braille_bit

    return mask


def mask_to_row_major_bits(mask: int) -> tuple[int, ...]:
    """
    Convert a Unicode Braille mask into 8 row-major 2×4 bits.

    Output order:

        0 1
        2 3
        4 5
        6 7

    Returns
    -------
    tuple[int, ...]
        Eight 0/1 values.
    """
    mask = clamp_mask(mask)
    bits = [0] * 8

    for braille_bit in range(8):
        if mask & (1 << braille_bit):
            row_major_index = BRAILLE_BIT_TO_ROW_MAJOR[braille_bit]
            bits[row_major_index] = 1

    return tuple(bits)


def row_major_bits_to_char(bits: Sequence[int | bool]) -> str:
    """
    Convert 8 row-major 2×4 bits directly to a Unicode Braille character.
    """
    return mask_to_char(row_major_bits_to_mask(bits))


def char_to_row_major_bits(char: str) -> tuple[int, ...]:
    """
    Convert a Unicode Braille character directly to 8 row-major 2×4 bits.
    """
    return mask_to_row_major_bits(char_to_mask(char))


def block_2x4_to_char(block: Sequence[Sequence[int | bool]]) -> str:
    """
    Convert a 2×4 block to a Unicode Braille character.

    Expected input shape:

        [
            [a, b],
            [c, d],
            [e, f],
            [g, h],
        ]

    Parameters
    ----------
    block:
        Four rows, each containing two truthy/falsy values.

    Returns
    -------
    str
        Unicode Braille character.
    """
    if len(block) != 4:
        raise ValueError(f"Expected 4 rows, got {len(block)}.")

    flat: list[int | bool] = []

    for row_index, row in enumerate(block):
        if len(row) != 2:
            raise ValueError(
                f"Expected row {row_index} to contain 2 values, got {len(row)}."
            )
        flat.extend(row)

    return row_major_bits_to_char(flat)


def char_to_block_2x4(char: str) -> tuple[tuple[int, int], ...]:
    """
    Convert a Unicode Braille character into a 2×4 binary block.

    Returns
    -------
    tuple[tuple[int, int], ...]
        Four rows, each with two 0/1 values.
    """
    bits = char_to_row_major_bits(char)

    return (
        (bits[0], bits[1]),
        (bits[2], bits[3]),
        (bits[4], bits[5]),
        (bits[6], bits[7]),
    )


def dot_count_from_mask(mask: int) -> int:
    """
    Count raised dots in a Unicode Braille mask.

    Returns
    -------
    int
        Dot count from 0..8.
    """
    mask = clamp_mask(mask)
    return mask.bit_count()


def dot_count_from_char(char: str) -> int:
    """
    Count raised dots in a Unicode Braille character.
    """
    return dot_count_from_mask(char_to_mask(char))


def density_from_mask(mask: int) -> float:
    """
    Return normalized density of a Unicode Braille mask.

    Returns
    -------
    float
        Value from 0.0 to 1.0.
    """
    return dot_count_from_mask(mask) / 8.0


def density_from_char(char: str) -> float:
    """
    Return normalized density of a Unicode Braille character.
    """
    return density_from_mask(char_to_mask(char))


def is_braille_char(char: str) -> bool:
    """
    Return True if `char` is exactly one Unicode Braille character.
    """
    return len(char) == 1 and BRAILLE_START <= ord(char) <= BRAILLE_END


def iter_braille_chars() -> Iterable[str]:
    """
    Iterate through all 256 Unicode Braille characters.
    """
    for mask in range(BRAILLE_COUNT):
        yield mask_to_char(mask)


def build_braille_table() -> tuple[str, ...]:
    """
    Return all 256 Unicode Braille characters as a tuple.
    """
    return tuple(iter_braille_chars())


BRAILLE_TABLE: tuple[str, ...] = build_braille_table()


def debug_cell(char: str) -> str:
    """
    Return a readable 2×4 visualization of a Braille character.

    Filled dots are shown as '1', empty dots as '0'.

    Example
    -------
    >>> debug_cell('⣿')
    '11\\n11\\n11\\n11'
    """
    block = char_to_block_2x4(char)
    return "\n".join("".join(str(value) for value in row) for row in block)


def mask_to_hex(mask: int) -> str:
    """
    Return a compact hexadecimal mask label.

    Example
    -------
    >>> mask_to_hex(255)
    '0xFF'
    """
    return f"0x{clamp_mask(mask):02X}"


def char_to_codepoint_label(char: str) -> str:
    """
    Return Unicode codepoint label for a Braille character.

    Example
    -------
    >>> char_to_codepoint_label('⣿')
    'U+28FF'
    """
    if not is_braille_char(char):
        raise ValueError(f"Not a Unicode Braille character: {char!r}")

    return f"U+{ord(char):04X}"


if __name__ == "__main__":
    # Tiny sanity demo.
    samples = [
        (0, "empty"),
        (1, "dot 1"),
        (255, "full"),
    ]

    for mask, label in samples:
        char = mask_to_char(mask)
        print(f"{label}: {char!r} {char} {mask_to_hex(mask)} {char_to_codepoint_label(char)}")
        print(debug_cell(char))
        print()
