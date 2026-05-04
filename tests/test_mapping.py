"""
Tests for braillestream.mapping.

These tests protect the most important invariant in the whole project:

    2×4 row-major bits
    ↔ Unicode Braille bitmask
    ↔ Unicode Braille character

If this layer is wrong, every image encoded by BrailleStream will be subtly wrong.
"""

import pytest

from braillestream.mapping import (
    BRAILLE_COUNT,
    BRAILLE_END,
    BRAILLE_START,
    BRAILLE_TABLE,
    ROW_MAJOR_TO_BRAILLE_BIT,
    BRAILLE_BIT_TO_ROW_MAJOR,
    block_2x4_to_char,
    char_to_block_2x4,
    char_to_codepoint_label,
    char_to_mask,
    char_to_row_major_bits,
    debug_cell,
    density_from_char,
    density_from_mask,
    dot_count_from_char,
    dot_count_from_mask,
    is_braille_char,
    iter_braille_chars,
    mask_to_char,
    mask_to_hex,
    mask_to_row_major_bits,
    row_major_bits_to_char,
    row_major_bits_to_mask,
)


def test_unicode_braille_constants_are_correct():
    assert BRAILLE_START == 0x2800
    assert BRAILLE_END == 0x28FF
    assert BRAILLE_COUNT == 256


def test_braille_table_has_all_256_characters():
    assert len(BRAILLE_TABLE) == 256
    assert BRAILLE_TABLE[0] == "⠀"
    assert BRAILLE_TABLE[-1] == "⣿"


def test_iter_braille_chars_yields_all_256_characters():
    chars = tuple(iter_braille_chars())

    assert len(chars) == 256
    assert chars[0] == "⠀"
    assert chars[-1] == "⣿"
    assert chars == BRAILLE_TABLE


def test_mask_to_char_empty_and_full():
    assert mask_to_char(0) == "⠀"
    assert mask_to_char(255) == "⣿"


def test_char_to_mask_empty_and_full():
    assert char_to_mask("⠀") == 0
    assert char_to_mask("⣿") == 255


def test_mask_to_char_clamps_low_and_high_values():
    assert mask_to_char(-1) == "⠀"
    assert mask_to_char(256) == "⣿"
    assert mask_to_char(9999) == "⣿"


@pytest.mark.parametrize(
    "mask",
    [0, 1, 2, 3, 7, 8, 15, 16, 31, 64, 127, 128, 170, 255],
)
def test_mask_to_char_and_char_to_mask_round_trip(mask):
    char = mask_to_char(mask)

    assert char_to_mask(char) == mask


def test_char_to_mask_rejects_non_braille_character():
    with pytest.raises(ValueError):
        char_to_mask("A")


def test_char_to_mask_rejects_multiple_characters():
    with pytest.raises(ValueError):
        char_to_mask("⣿⣿")


def test_is_braille_char():
    assert is_braille_char("⠀") is True
    assert is_braille_char("⣿") is True
    assert is_braille_char("A") is False
    assert is_braille_char("⣿⣿") is False
    assert is_braille_char("") is False


def test_row_major_mapping_table_is_correct():
    # Row-major positions:
    #
    #   0 1
    #   2 3
    #   4 5
    #   6 7
    #
    # Unicode Braille dot layout:
    #
    #   dot 1 bit 0    dot 4 bit 3
    #   dot 2 bit 1    dot 5 bit 4
    #   dot 3 bit 2    dot 6 bit 5
    #   dot 7 bit 6    dot 8 bit 7
    assert ROW_MAJOR_TO_BRAILLE_BIT == (0, 3, 1, 4, 2, 5, 6, 7)


def test_reverse_mapping_table_is_correct():
    assert BRAILLE_BIT_TO_ROW_MAJOR == (0, 2, 4, 1, 3, 5, 6, 7)


@pytest.mark.parametrize(
    "row_major_index, expected_mask, expected_char",
    [
        (0, 0b00000001, "⠁"),  # dot 1
        (1, 0b00001000, "⠈"),  # dot 4
        (2, 0b00000010, "⠂"),  # dot 2
        (3, 0b00010000, "⠐"),  # dot 5
        (4, 0b00000100, "⠄"),  # dot 3
        (5, 0b00100000, "⠠"),  # dot 6
        (6, 0b01000000, "⡀"),  # dot 7
        (7, 0b10000000, "⢀"),  # dot 8
    ],
)
def test_single_row_major_bit_to_mask_and_char(
    row_major_index,
    expected_mask,
    expected_char,
):
    bits = [0] * 8
    bits[row_major_index] = 1

    assert row_major_bits_to_mask(bits) == expected_mask
    assert row_major_bits_to_char(bits) == expected_char


def test_row_major_bits_to_mask_empty():
    bits = [0, 0, 0, 0, 0, 0, 0, 0]

    assert row_major_bits_to_mask(bits) == 0
    assert row_major_bits_to_char(bits) == "⠀"


def test_row_major_bits_to_mask_full():
    bits = [1, 1, 1, 1, 1, 1, 1, 1]

    assert row_major_bits_to_mask(bits) == 255
    assert row_major_bits_to_char(bits) == "⣿"


def test_row_major_bits_to_mask_rejects_wrong_length():
    with pytest.raises(ValueError):
        row_major_bits_to_mask([1, 0, 1])

    with pytest.raises(ValueError):
        row_major_bits_to_mask([1] * 9)


@pytest.mark.parametrize(
    "bits",
    [
        [0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0, 0, 0],
        [0, 1, 0, 1, 0, 1, 0, 1],
        [1, 0, 1, 0, 1, 0, 1, 0],
        [1, 1, 1, 1, 1, 1, 1, 1],
    ],
)
def test_row_major_bits_round_trip(bits):
    char = row_major_bits_to_char(bits)

    assert list(char_to_row_major_bits(char)) == bits


@pytest.mark.parametrize("mask", range(256))
def test_every_mask_round_trips_through_bits(mask):
    bits = mask_to_row_major_bits(mask)
    rebuilt_mask = row_major_bits_to_mask(bits)

    assert rebuilt_mask == mask


@pytest.mark.parametrize("mask", range(256))
def test_every_mask_round_trips_through_char(mask):
    char = mask_to_char(mask)

    assert char_to_mask(char) == mask


@pytest.mark.parametrize("char", BRAILLE_TABLE)
def test_every_char_round_trips_through_bits(char):
    bits = char_to_row_major_bits(char)
    rebuilt_char = row_major_bits_to_char(bits)

    assert rebuilt_char == char


def test_block_2x4_to_char_empty():
    block = [
        [0, 0],
        [0, 0],
        [0, 0],
        [0, 0],
    ]

    assert block_2x4_to_char(block) == "⠀"


def test_block_2x4_to_char_full():
    block = [
        [1, 1],
        [1, 1],
        [1, 1],
        [1, 1],
    ]

    assert block_2x4_to_char(block) == "⣿"


def test_block_2x4_to_char_known_pattern():
    block = [
        [1, 0],
        [1, 1],
        [0, 1],
        [0, 0],
    ]

    # Row-major bits:
    # [1,0,1,1,0,1,0,0]
    #
    # Unicode bits set:
    # row-major 0 -> bit 0
    # row-major 2 -> bit 1
    # row-major 3 -> bit 4
    # row-major 5 -> bit 5
    #
    # mask = 1 + 2 + 16 + 32 = 51
    assert block_2x4_to_char(block) == mask_to_char(51)


def test_block_2x4_to_char_rejects_wrong_row_count():
    with pytest.raises(ValueError):
        block_2x4_to_char([[1, 0], [0, 1]])


def test_block_2x4_to_char_rejects_wrong_column_count():
    with pytest.raises(ValueError):
        block_2x4_to_char(
            [
                [1, 0],
                [1, 0, 1],
                [1, 0],
                [1, 0],
            ]
        )


def test_char_to_block_2x4_empty():
    assert char_to_block_2x4("⠀") == (
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 0),
    )


def test_char_to_block_2x4_full():
    assert char_to_block_2x4("⣿") == (
        (1, 1),
        (1, 1),
        (1, 1),
        (1, 1),
    )


def test_char_to_block_2x4_known_single_dots():
    assert char_to_block_2x4("⠁") == (
        (1, 0),
        (0, 0),
        (0, 0),
        (0, 0),
    )

    assert char_to_block_2x4("⠈") == (
        (0, 1),
        (0, 0),
        (0, 0),
        (0, 0),
    )

    assert char_to_block_2x4("⡀") == (
        (0, 0),
        (0, 0),
        (0, 0),
        (1, 0),
    )

    assert char_to_block_2x4("⢀") == (
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 1),
    )


@pytest.mark.parametrize("mask", range(256))
def test_dot_count_from_mask_matches_python_bit_count(mask):
    assert dot_count_from_mask(mask) == mask.bit_count()


def test_dot_count_from_char_empty_and_full():
    assert dot_count_from_char("⠀") == 0
    assert dot_count_from_char("⣿") == 8


def test_density_from_mask_empty_half_and_full():
    assert density_from_mask(0) == 0.0
    assert density_from_mask(15) == 0.5
    assert density_from_mask(255) == 1.0


def test_density_from_char_empty_and_full():
    assert density_from_char("⠀") == 0.0
    assert density_from_char("⣿") == 1.0


def test_mask_to_hex():
    assert mask_to_hex(0) == "0x00"
    assert mask_to_hex(1) == "0x01"
    assert mask_to_hex(15) == "0x0F"
    assert mask_to_hex(255) == "0xFF"


def test_mask_to_hex_clamps():
    assert mask_to_hex(-10) == "0x00"
    assert mask_to_hex(999) == "0xFF"


def test_char_to_codepoint_label():
    assert char_to_codepoint_label("⠀") == "U+2800"
    assert char_to_codepoint_label("⣿") == "U+28FF"


def test_char_to_codepoint_label_rejects_non_braille():
    with pytest.raises(ValueError):
        char_to_codepoint_label("A")


def test_debug_cell_empty():
    assert debug_cell("⠀") == "00\n00\n00\n00"


def test_debug_cell_full():
    assert debug_cell("⣿") == "11\n11\n11\n11"


def test_debug_cell_known_pattern():
    char = block_2x4_to_char(
        [
            [1, 0],
            [1, 1],
            [0, 1],
            [0, 0],
        ]
    )

    assert debug_cell(char) == "10\n11\n01\n00"
