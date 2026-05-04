"""
Tests for braillestream.codec.

These tests verify the first real BrailleStream image pipeline:

    PIL image / binary grid
    → 2×4 blocks
    → Unicode Braille stream
    → decoded pixel/density grid
"""

from pathlib import Path

import pytest
from PIL import Image

from braillestream.codec import (
    EncodedImage,
    EncodeOptions,
    apply_gamma,
    clamp_threshold,
    crop_to_braille_multiples,
    image_block_to_bits,
    image_to_braille_stream,
    load_stream,
    nearest_positive_multiple,
    open_image,
    pixel_grid_to_stream,
    resize_for_braille,
    save_stream,
    stream_to_density_grid,
    stream_to_pixel_grid,
    validate_cell_dimensions,
    validate_gamma,
)
from braillestream.mapping import (
    char_to_block_2x4,
    mask_to_char,
)


def make_gray_image(width: int, height: int, value: int = 255) -> Image.Image:
    return Image.new("L", (width, height), color=value)


def make_rgb_image(width: int, height: int, color=(255, 255, 255)) -> Image.Image:
    return Image.new("RGB", (width, height), color=color)


def test_clamp_threshold():
    assert clamp_threshold(-1) == 0
    assert clamp_threshold(0) == 0
    assert clamp_threshold(128) == 128
    assert clamp_threshold(255) == 255
    assert clamp_threshold(256) == 255
    assert clamp_threshold(999) == 255


def test_validate_gamma_accepts_positive_values():
    assert validate_gamma(0.1) == 0.1
    assert validate_gamma(1.0) == 1.0
    assert validate_gamma(2.2) == 2.2


@pytest.mark.parametrize("gamma", [0, -1, -0.5])
def test_validate_gamma_rejects_non_positive_values(gamma):
    with pytest.raises(ValueError):
        validate_gamma(gamma)


def test_validate_cell_dimensions_accepts_none_and_positive_values():
    assert validate_cell_dimensions(None, None) == (None, None)
    assert validate_cell_dimensions(80, None) == (80, None)
    assert validate_cell_dimensions(None, 24) == (None, 24)
    assert validate_cell_dimensions(80, 24) == (80, 24)


@pytest.mark.parametrize(
    "width_cells,height_cells",
    [
        (0, None),
        (-1, None),
        (None, 0),
        (None, -1),
        (0, 0),
    ],
)
def test_validate_cell_dimensions_rejects_non_positive_values(
    width_cells,
    height_cells,
):
    with pytest.raises(ValueError):
        validate_cell_dimensions(width_cells, height_cells)


def test_nearest_positive_multiple():
    assert nearest_positive_multiple(1, 2) == 2
    assert nearest_positive_multiple(2, 2) == 2
    assert nearest_positive_multiple(3, 2) in {2, 4}
    assert nearest_positive_multiple(5, 4) == 4
    assert nearest_positive_multiple(6, 4) == 8
    assert nearest_positive_multiple(0, 4) == 4


def test_nearest_positive_multiple_rejects_invalid_multiple():
    with pytest.raises(ValueError):
        nearest_positive_multiple(10, 0)


def test_open_image_from_pil_image_returns_copy():
    img = make_rgb_image(2, 4)
    opened = open_image(img)

    assert opened is not img
    assert opened.size == (2, 4)
    assert opened.mode == "RGB"


def test_open_image_from_path(tmp_path: Path):
    path = tmp_path / "test.png"
    img = make_rgb_image(2, 4, color=(10, 20, 30))
    img.save(path)

    opened = open_image(path)

    assert opened.size == (2, 4)
    assert opened.mode == "RGB"


def test_open_image_rejects_missing_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        open_image(tmp_path / "missing.png")


def test_apply_gamma_one_returns_same_image_object():
    img = make_gray_image(2, 4, value=128)
    out = apply_gamma(img, 1.0)

    assert out is img


def test_apply_gamma_changes_midtones():
    img = make_gray_image(1, 1, value=128)

    darker = apply_gamma(img, 2.0)
    brighter = apply_gamma(img, 0.5)

    assert darker.getpixel((0, 0)) < 128
    assert brighter.getpixel((0, 0)) > 128


def test_crop_to_braille_multiples_keeps_valid_dimensions():
    img = make_gray_image(6, 8)

    cropped = crop_to_braille_multiples(img)

    assert cropped.size == (6, 8)


def test_crop_to_braille_multiples_crops_invalid_dimensions():
    img = make_gray_image(7, 10)

    cropped = crop_to_braille_multiples(img)

    assert cropped.size == (6, 8)


def test_crop_to_braille_multiples_rejects_too_small_image():
    img = make_gray_image(1, 3)

    with pytest.raises(ValueError):
        crop_to_braille_multiples(img)


def test_resize_for_braille_without_targets_crops_to_multiples():
    img = make_gray_image(7, 10)

    out = resize_for_braille(img)

    assert out.size == (6, 8)


def test_resize_for_braille_width_only_preserves_aspect_to_valid_height():
    img = make_gray_image(10, 10)

    out = resize_for_braille(img, width_cells=4)

    assert out.width == 8
    assert out.height % 4 == 0


def test_resize_for_braille_height_only_preserves_aspect_to_valid_width():
    img = make_gray_image(10, 10)

    out = resize_for_braille(img, height_cells=3)

    assert out.height == 12
    assert out.width % 2 == 0


def test_resize_for_braille_stretch_exact_dimensions():
    img = make_gray_image(10, 10)

    out = resize_for_braille(
        img,
        width_cells=4,
        height_cells=3,
        mode="stretch",
    )

    assert out.size == (8, 12)


def test_resize_for_braille_fit_exact_canvas_dimensions():
    img = make_gray_image(20, 10, value=0)

    out = resize_for_braille(
        img,
        width_cells=10,
        height_cells=10,
        mode="fit",
    )

    assert out.size == (20, 40)


def test_resize_for_braille_crop_exact_dimensions():
    img = make_gray_image(20, 10)

    out = resize_for_braille(
        img,
        width_cells=10,
        height_cells=10,
        mode="crop",
    )

    assert out.size == (20, 40)


def test_resize_for_braille_rejects_unknown_mode():
    img = make_gray_image(10, 10)

    with pytest.raises(ValueError):
        resize_for_braille(
            img,
            width_cells=4,
            height_cells=3,
            mode="strange",  # type: ignore[arg-type]
        )


def test_image_block_to_bits_dark_on_light_full_black_block():
    img = make_gray_image(2, 4, value=0)

    block = image_block_to_bits(
        img,
        x=0,
        y=0,
        threshold=128,
        polarity="dark-on-light",
    )

    assert block == (
        (1, 1),
        (1, 1),
        (1, 1),
        (1, 1),
    )


def test_image_block_to_bits_dark_on_light_empty_white_block():
    img = make_gray_image(2, 4, value=255)

    block = image_block_to_bits(
        img,
        x=0,
        y=0,
        threshold=128,
        polarity="dark-on-light",
    )

    assert block == (
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 0),
    )


def test_image_block_to_bits_light_on_dark_full_white_block():
    img = make_gray_image(2, 4, value=255)

    block = image_block_to_bits(
        img,
        x=0,
        y=0,
        threshold=128,
        polarity="light-on-dark",
    )

    assert block == (
        (1, 1),
        (1, 1),
        (1, 1),
        (1, 1),
    )


def test_image_block_to_bits_light_on_dark_empty_black_block():
    img = make_gray_image(2, 4, value=0)

    block = image_block_to_bits(
        img,
        x=0,
        y=0,
        threshold=128,
        polarity="light-on-dark",
    )

    assert block == (
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 0),
    )


def test_image_block_to_bits_known_pattern_dark_on_light():
    img = Image.new("L", (2, 4))
    values = [
        [0, 255],
        [0, 0],
        [255, 0],
        [255, 255],
    ]

    for y, row in enumerate(values):
        for x, value in enumerate(row):
            img.putpixel((x, y), value)

    block = image_block_to_bits(
        img,
        x=0,
        y=0,
        threshold=128,
        polarity="dark-on-light",
    )

    assert block == (
        (1, 0),
        (1, 1),
        (0, 1),
        (0, 0),
    )


def test_image_block_to_bits_rejects_unknown_polarity():
    img = make_gray_image(2, 4)

    with pytest.raises(ValueError):
        image_block_to_bits(
            img,
            x=0,
            y=0,
            polarity="weird",  # type: ignore[arg-type]
        )


def test_image_to_braille_stream_black_cell_dark_on_light():
    img = make_gray_image(2, 4, value=0)

    result = image_to_braille_stream(
        img,
        EncodeOptions(polarity="dark-on-light"),
    )

    assert isinstance(result, EncodedImage)
    assert result.stream == "⣿"
    assert result.width_cells == 1
    assert result.height_cells == 1
    assert result.output_width_px == 2
    assert result.output_height_px == 4
    assert result.length == 1
    assert result.expected_length == 1
    assert result.is_complete is True


def test_image_to_braille_stream_white_cell_dark_on_light():
    img = make_gray_image(2, 4, value=255)

    result = image_to_braille_stream(
        img,
        EncodeOptions(polarity="dark-on-light"),
    )

    assert result.stream == "⠀"
    assert result.width_cells == 1
    assert result.height_cells == 1


def test_image_to_braille_stream_white_cell_light_on_dark():
    img = make_gray_image(2, 4, value=255)

    result = image_to_braille_stream(
        img,
        EncodeOptions(polarity="light-on-dark"),
    )

    assert result.stream == "⣿"
    assert result.width_cells == 1
    assert result.height_cells == 1


def test_image_to_braille_stream_known_pattern():
    img = Image.new("L", (2, 4))
    values = [
        [0, 255],
        [0, 0],
        [255, 0],
        [255, 255],
    ]

    for y, row in enumerate(values):
        for x, value in enumerate(row):
            img.putpixel((x, y), value)

    result = image_to_braille_stream(
        img,
        EncodeOptions(polarity="dark-on-light"),
    )

    # From tests in mapping.py: block [[1,0],[1,1],[0,1],[0,0]]
    # becomes mask 51.
    assert result.stream == mask_to_char(51)


def test_image_to_braille_stream_two_cells_wide():
    img = Image.new("L", (4, 4), color=255)

    # Left 2×4 block black, right 2×4 block white.
    for y in range(4):
        for x in range(2):
            img.putpixel((x, y), 0)

    result = image_to_braille_stream(
        img,
        EncodeOptions(polarity="dark-on-light"),
    )

    assert result.stream == "⣿⠀"
    assert result.width_cells == 2
    assert result.height_cells == 1
    assert result.length == 2


def test_image_to_braille_stream_two_cells_tall():
    img = Image.new("L", (2, 8), color=255)

    # Top 2×4 block black, bottom 2×4 block white.
    for y in range(4):
        for x in range(2):
            img.putpixel((x, y), 0)

    result = image_to_braille_stream(
        img,
        EncodeOptions(polarity="dark-on-light"),
    )

    assert result.stream == "⣿⠀"
    assert result.width_cells == 1
    assert result.height_cells == 2
    assert result.length == 2


def test_image_to_braille_stream_resizes_to_requested_cells():
    img = make_gray_image(10, 10, value=0)

    result = image_to_braille_stream(
        img,
        EncodeOptions(
            width_cells=4,
            height_cells=3,
            resize_mode="stretch",
            polarity="dark-on-light",
        ),
    )

    assert result.width_cells == 4
    assert result.height_cells == 3
    assert result.output_width_px == 8
    assert result.output_height_px == 12
    assert result.length == 12
    assert result.stream == "⣿" * 12


def test_image_to_braille_stream_invert_flips_black_and_white():
    img = make_gray_image(2, 4, value=0)

    result = image_to_braille_stream(
        img,
        EncodeOptions(
            invert=True,
            polarity="dark-on-light",
        ),
    )

    assert result.stream == "⠀"


def test_image_to_braille_stream_accepts_rgb_image():
    img = make_rgb_image(2, 4, color=(0, 0, 0))

    result = image_to_braille_stream(
        img,
        EncodeOptions(polarity="dark-on-light"),
    )

    assert result.stream == "⣿"


def test_image_to_braille_stream_accepts_path(tmp_path: Path):
    path = tmp_path / "black.png"
    img = make_gray_image(2, 4, value=0)
    img.save(path)

    result = image_to_braille_stream(
        path,
        EncodeOptions(polarity="dark-on-light"),
    )

    assert result.stream == "⣿"


def test_image_to_braille_stream_dither_runs():
    img = make_gray_image(4, 4, value=128)

    result = image_to_braille_stream(
        img,
        EncodeOptions(
            dither=True,
            polarity="dark-on-light",
        ),
    )

    assert result.width_cells == 2
    assert result.height_cells == 1
    assert result.length == 2
    assert result.is_complete is True


def test_pixel_grid_to_stream_empty_grid_rejected():
    with pytest.raises(ValueError):
        pixel_grid_to_stream([])


def test_pixel_grid_to_stream_empty_row_rejected():
    with pytest.raises(ValueError):
        pixel_grid_to_stream([[]])


def test_pixel_grid_to_stream_non_rectangular_rejected():
    pixels = [
        [1, 0],
        [1],
        [0, 1],
        [0, 0],
    ]

    with pytest.raises(ValueError):
        pixel_grid_to_stream(pixels)


def test_pixel_grid_to_stream_rejects_invalid_width():
    pixels = [
        [1, 0, 1],
        [1, 0, 1],
        [1, 0, 1],
        [1, 0, 1],
    ]

    with pytest.raises(ValueError):
        pixel_grid_to_stream(pixels)


def test_pixel_grid_to_stream_rejects_invalid_height():
    pixels = [
        [1, 0],
        [1, 0],
        [1, 0],
    ]

    with pytest.raises(ValueError):
        pixel_grid_to_stream(pixels)


def test_pixel_grid_to_stream_full_cell():
    pixels = [
        [1, 1],
        [1, 1],
        [1, 1],
        [1, 1],
    ]

    result = pixel_grid_to_stream(pixels)

    assert result.stream == "⣿"
    assert result.width_cells == 1
    assert result.height_cells == 1
    assert result.output_width_px == 2
    assert result.output_height_px == 4


def test_pixel_grid_to_stream_empty_cell():
    pixels = [
        [0, 0],
        [0, 0],
        [0, 0],
        [0, 0],
    ]

    result = pixel_grid_to_stream(pixels)

    assert result.stream == "⠀"


def test_pixel_grid_to_stream_known_pattern():
    pixels = [
        [1, 0],
        [1, 1],
        [0, 1],
        [0, 0],
    ]

    result = pixel_grid_to_stream(pixels)

    assert result.stream == mask_to_char(51)


def test_pixel_grid_to_stream_multiple_cells():
    pixels = [
        [1, 1, 0, 0],
        [1, 1, 0, 0],
        [1, 1, 0, 0],
        [1, 1, 0, 0],
    ]

    result = pixel_grid_to_stream(pixels)

    assert result.stream == "⣿⠀"
    assert result.width_cells == 2
    assert result.height_cells == 1


def test_stream_to_pixel_grid_full_cell():
    pixels = stream_to_pixel_grid("⣿", width_cells=1)

    assert pixels == [
        [1, 1],
        [1, 1],
        [1, 1],
        [1, 1],
    ]


def test_stream_to_pixel_grid_empty_cell():
    pixels = stream_to_pixel_grid("⠀", width_cells=1)

    assert pixels == [
        [0, 0],
        [0, 0],
        [0, 0],
        [0, 0],
    ]


def test_stream_to_pixel_grid_two_cells_wide():
    pixels = stream_to_pixel_grid("⣿⠀", width_cells=2)

    assert pixels == [
        [1, 1, 0, 0],
        [1, 1, 0, 0],
        [1, 1, 0, 0],
        [1, 1, 0, 0],
    ]


def test_stream_to_pixel_grid_two_cells_tall():
    pixels = stream_to_pixel_grid("⣿⠀", width_cells=1)

    assert pixels == [
        [1, 1],
        [1, 1],
        [1, 1],
        [1, 1],
        [0, 0],
        [0, 0],
        [0, 0],
        [0, 0],
    ]


def test_stream_to_pixel_grid_rejects_invalid_width():
    with pytest.raises(ValueError):
        stream_to_pixel_grid("⣿", width_cells=0)


def test_pixel_grid_round_trip():
    pixels = [
        [1, 0, 0, 1],
        [1, 1, 0, 0],
        [0, 1, 1, 0],
        [0, 0, 1, 1],
        [1, 1, 1, 1],
        [0, 0, 0, 0],
        [1, 0, 1, 0],
        [0, 1, 0, 1],
    ]

    encoded = pixel_grid_to_stream(pixels)
    decoded = stream_to_pixel_grid(encoded.stream, encoded.width_cells)

    assert decoded == pixels


def test_stream_to_density_grid_empty_and_full():
    grid = stream_to_density_grid("⠀⣿", width_cells=2)

    assert grid == [[0.0, 1.0]]


def test_stream_to_density_grid_wraps_rows():
    grid = stream_to_density_grid("⠀⣿⠀⣿", width_cells=2)

    assert grid == [
        [0.0, 1.0],
        [0.0, 1.0],
    ]


def test_stream_to_density_grid_allows_incomplete_final_row():
    grid = stream_to_density_grid("⠀⣿⠀", width_cells=2)

    assert grid == [
        [0.0, 1.0],
        [0.0],
    ]


def test_stream_to_density_grid_rejects_invalid_width():
    with pytest.raises(ValueError):
        stream_to_density_grid("⣿", width_cells=0)


@pytest.mark.parametrize(
    "char",
    [
        "⠀",
        "⠁",
        "⠈",
        "⡀",
        "⢀",
        "⣿",
        mask_to_char(51),
    ],
)
def test_stream_to_pixel_grid_matches_mapping_blocks(char):
    pixels = stream_to_pixel_grid(char, width_cells=1)
    block = char_to_block_2x4(char)

    assert pixels == [list(row) for row in block]


def test_save_and_load_stream(tmp_path: Path):
    path = tmp_path / "image.bs"
    stream = "⠀⣿⠁⢀"

    save_stream(stream, path)
    loaded = load_stream(path)

    assert loaded == stream


def test_encoded_image_properties():
    options = EncodeOptions()
    encoded = EncodedImage(
        stream="⣿⠀",
        width_cells=2,
        height_cells=1,
        source_width_px=4,
        source_height_px=4,
        output_width_px=4,
        output_height_px=4,
        options=options,
    )

    assert encoded.length == 2
    assert encoded.expected_length == 2
    assert encoded.is_complete is True


def test_encoded_image_detects_incomplete_stream():
    options = EncodeOptions()
    encoded = EncodedImage(
        stream="⣿",
        width_cells=2,
        height_cells=1,
        source_width_px=4,
        source_height_px=4,
        output_width_px=4,
        output_height_px=4,
        options=options,
    )

    assert encoded.length == 1
    assert encoded.expected_length == 2
    assert encoded.is_complete is False
