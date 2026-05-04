"""
Tests for braillestream.render.

These tests lock down the projection calculus layer:

    index → (x, y)
    (x, y) → index
    single-line stream → hard-wrapped rows
    hard-wrapped rows → single-line stream
"""

import pytest

from braillestream.render import (
    ProjectionCell,
    RenderDimensions,
    aspect_ratio_for_width,
    best_widths_by_aspect,
    crop_projection,
    get_cell,
    index_to_xy,
    iter_projection,
    overlay_streams,
    projection_grid,
    rank_widths_by_aspect,
    render_dimensions,
    require_pure_braille_stream,
    set_cell,
    unwrap_stream,
    validate_index,
    validate_pure_braille_stream,
    validate_width,
    width_candidates_for_length,
    wrap_stream,
    wrap_stream_rows,
    xy_to_index,
)


def test_validate_width_accepts_positive_integer():
    assert validate_width(1) == 1
    assert validate_width(80) == 80
    assert validate_width("12") == 12


@pytest.mark.parametrize("width", [0, -1, -80])
def test_validate_width_rejects_non_positive(width):
    with pytest.raises(ValueError):
        validate_width(width)


def test_validate_index_accepts_non_negative_integer():
    assert validate_index(0) == 0
    assert validate_index(10) == 10
    assert validate_index("12") == 12


@pytest.mark.parametrize("index", [-1, -10])
def test_validate_index_rejects_negative(index):
    with pytest.raises(ValueError):
        validate_index(index)


@pytest.mark.parametrize(
    "index,width,expected",
    [
        (0, 80, (0, 0)),
        (1, 80, (1, 0)),
        (79, 80, (79, 0)),
        (80, 80, (0, 1)),
        (81, 80, (1, 1)),
        (159, 80, (79, 1)),
        (160, 80, (0, 2)),
        (5, 2, (1, 2)),
        (5, 3, (2, 1)),
    ],
)
def test_index_to_xy(index, width, expected):
    assert index_to_xy(index, width) == expected


@pytest.mark.parametrize(
    "x,y,width,expected",
    [
        (0, 0, 80, 0),
        (1, 0, 80, 1),
        (79, 0, 80, 79),
        (0, 1, 80, 80),
        (1, 1, 80, 81),
        (79, 1, 80, 159),
        (0, 2, 80, 160),
        (1, 2, 2, 5),
        (2, 1, 3, 5),
    ],
)
def test_xy_to_index(x, y, width, expected):
    assert xy_to_index(x, y, width) == expected


@pytest.mark.parametrize("index", range(200))
@pytest.mark.parametrize("width", [1, 2, 3, 7, 80])
def test_index_xy_round_trip(index, width):
    x, y = index_to_xy(index, width)

    assert xy_to_index(x, y, width) == index


def test_xy_to_index_rejects_negative_x():
    with pytest.raises(ValueError):
        xy_to_index(-1, 0, 80)


def test_xy_to_index_rejects_negative_y():
    with pytest.raises(ValueError):
        xy_to_index(0, -1, 80)


def test_xy_to_index_rejects_x_outside_width():
    with pytest.raises(ValueError):
        xy_to_index(80, 0, 80)


def test_render_dimensions_empty_stream():
    dims = render_dimensions("", width=80)

    assert isinstance(dims, RenderDimensions)
    assert dims.width_cells == 80
    assert dims.height_cells == 0
    assert dims.width_px == 160
    assert dims.height_px == 0
    assert dims.length == 0
    assert dims.complete_final_row is True


def test_render_dimensions_complete_final_row():
    dims = render_dimensions("abcdef", width=3)

    assert dims.width_cells == 3
    assert dims.height_cells == 2
    assert dims.width_px == 6
    assert dims.height_px == 8
    assert dims.length == 6
    assert dims.complete_final_row is True


def test_render_dimensions_incomplete_final_row():
    dims = render_dimensions("abcdefg", width=3)

    assert dims.width_cells == 3
    assert dims.height_cells == 3
    assert dims.width_px == 6
    assert dims.height_px == 12
    assert dims.length == 7
    assert dims.complete_final_row is False


def test_wrap_stream_rows_even_chunks():
    assert wrap_stream_rows("abcdef", 2) == ["ab", "cd", "ef"]


def test_wrap_stream_rows_incomplete_final_row():
    assert wrap_stream_rows("abcdefg", 3) == ["abc", "def", "g"]


def test_wrap_stream_rows_empty_stream():
    assert wrap_stream_rows("", 3) == []


def test_wrap_stream_rows_with_padding():
    assert wrap_stream_rows("abcdefg", 3, pad=True, pad_char="_") == [
        "abc",
        "def",
        "g__",
    ]


def test_wrap_stream_rows_rejects_invalid_pad_char():
    with pytest.raises(ValueError):
        wrap_stream_rows("abc", 2, pad=True, pad_char="__")


def test_wrap_stream():
    assert wrap_stream("abcdef", 2) == "ab\ncd\nef"


def test_wrap_stream_with_padding():
    assert wrap_stream("abcdefg", 3, pad=True, pad_char="_") == "abc\ndef\ng__"


def test_unwrap_stream_removes_line_breaks():
    assert unwrap_stream("ab\ncd\nef") == "abcdef"
    assert unwrap_stream("ab\r\ncd\ref") == "abcdef"


def test_unwrap_stream_keeps_spaces_by_default():
    assert unwrap_stream("ab c\n d") == "ab c d"


def test_unwrap_stream_can_strip_spaces_and_tabs():
    assert unwrap_stream("ab c\n\td", strip_spaces=True) == "abcd"


def test_iter_projection_empty_stream():
    assert list(iter_projection("", 80)) == []


def test_iter_projection_cells():
    cells = list(iter_projection("abcdef", 3))

    assert cells == [
        ProjectionCell(index=0, x=0, y=0, char="a"),
        ProjectionCell(index=1, x=1, y=0, char="b"),
        ProjectionCell(index=2, x=2, y=0, char="c"),
        ProjectionCell(index=3, x=0, y=1, char="d"),
        ProjectionCell(index=4, x=1, y=1, char="e"),
        ProjectionCell(index=5, x=2, y=1, char="f"),
    ]


def test_projection_grid_without_padding():
    assert projection_grid("abcdefg", 3) == [
        ["a", "b", "c"],
        ["d", "e", "f"],
        ["g"],
    ]


def test_projection_grid_with_padding():
    assert projection_grid("abcdefg", 3, pad=True, pad_char="_") == [
        ["a", "b", "c"],
        ["d", "e", "f"],
        ["g", "_", "_"],
    ]


def test_get_cell():
    stream = "abcdef"

    assert get_cell(stream, 0, 0, 3) == "a"
    assert get_cell(stream, 1, 0, 3) == "b"
    assert get_cell(stream, 2, 0, 3) == "c"
    assert get_cell(stream, 0, 1, 3) == "d"
    assert get_cell(stream, 1, 1, 3) == "e"
    assert get_cell(stream, 2, 1, 3) == "f"


def test_get_cell_returns_default_when_beyond_stream():
    assert get_cell("abcdef", 0, 2, 3, default="_") == "_"


def test_get_cell_raises_when_beyond_stream_without_default():
    with pytest.raises(IndexError):
        get_cell("abcdef", 0, 2, 3)


def test_set_cell():
    assert set_cell("abcdef", 1, 1, 3, "X") == "abcdXf"


def test_set_cell_first_and_last():
    stream = "abcdef"

    assert set_cell(stream, 0, 0, 3, "X") == "Xbcdef"
    assert set_cell(stream, 2, 1, 3, "X") == "abcdeX"


def test_set_cell_rejects_multi_character_replacement():
    with pytest.raises(ValueError):
        set_cell("abcdef", 1, 1, 3, "XX")


def test_set_cell_raises_when_beyond_stream():
    with pytest.raises(IndexError):
        set_cell("abcdef", 0, 2, 3, "X")


def test_crop_projection_basic():
    rows = crop_projection(
        "abcdefghi",
        width=3,
        x=1,
        y=1,
        crop_width=2,
        crop_height=2,
        fill="_",
    )

    assert rows == [
        "ef",
        "hi",
    ]


def test_crop_projection_fills_beyond_stream():
    rows = crop_projection(
        "abcdefg",
        width=3,
        x=1,
        y=1,
        crop_width=3,
        crop_height=2,
        fill="_",
    )

    assert rows == [
        "ef_",
        "__ _".replace(" ", ""),
    ]


def test_crop_projection_fills_x_beyond_width():
    rows = crop_projection(
        "abcdefghi",
        width=3,
        x=2,
        y=0,
        crop_width=3,
        crop_height=2,
        fill="_",
    )

    assert rows == [
        "c__",
        "f__",
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"x": -1, "y": 0, "crop_width": 1, "crop_height": 1},
        {"x": 0, "y": -1, "crop_width": 1, "crop_height": 1},
        {"x": 0, "y": 0, "crop_width": 0, "crop_height": 1},
        {"x": 0, "y": 0, "crop_width": 1, "crop_height": 0},
    ],
)
def test_crop_projection_rejects_invalid_dimensions(kwargs):
    with pytest.raises(ValueError):
        crop_projection("abcdef", width=3, fill="_", **kwargs)


def test_crop_projection_rejects_multi_character_fill():
    with pytest.raises(ValueError):
        crop_projection(
            "abcdef",
            width=3,
            x=0,
            y=0,
            crop_width=1,
            crop_height=1,
            fill="__",
        )


def test_overlay_streams_basic():
    assert overlay_streams("abcdef", "XY", overlay_offset=2) == "abXYef"


def test_overlay_streams_transparent_char_leaves_base_unchanged():
    assert overlay_streams("abcdef", "X⠀Y", overlay_offset=1) == "aXcYef"


def test_overlay_streams_extends_base_if_needed():
    assert overlay_streams("abc", "XYZ", overlay_offset=2, transparent="_") == "abXYZ"


def test_overlay_streams_rejects_negative_offset():
    with pytest.raises(ValueError):
        overlay_streams("abc", "X", overlay_offset=-1)


def test_overlay_streams_rejects_multi_character_transparent():
    with pytest.raises(ValueError):
        overlay_streams("abc", "X", transparent="__")


def test_validate_pure_braille_stream():
    assert validate_pure_braille_stream("") is True
    assert validate_pure_braille_stream("⠀⣿⠁⢀") is True
    assert validate_pure_braille_stream("abc") is False
    assert validate_pure_braille_stream("⠀A⣿") is False


def test_require_pure_braille_stream_accepts_valid_stream():
    stream = "⠀⣿⠁⢀"

    assert require_pure_braille_stream(stream) == stream


def test_require_pure_braille_stream_rejects_invalid_stream():
    with pytest.raises(ValueError) as exc:
        require_pure_braille_stream("⠀A⣿")

    assert "Non-Braille character at index 1" in str(exc.value)
    assert "U+0041" in str(exc.value)


def test_width_candidates_for_length_divisors_only():
    assert width_candidates_for_length(12, min_width=1, max_width=12) == [
        1,
        2,
        3,
        4,
        6,
        12,
    ]


def test_width_candidates_for_length_all_widths():
    assert width_candidates_for_length(
        5,
        min_width=1,
        max_width=5,
        divisors_only=False,
    ) == [1, 2, 3, 4, 5]


def test_width_candidates_for_length_applies_min_and_max():
    assert width_candidates_for_length(12, min_width=3, max_width=8) == [3, 4, 6]


def test_width_candidates_for_length_defaults_max_to_length():
    assert width_candidates_for_length(6) == [1, 2, 3, 6]


def test_width_candidates_for_length_empty_length():
    assert width_candidates_for_length(0) == []


def test_width_candidates_for_length_max_less_than_min():
    assert width_candidates_for_length(12, min_width=8, max_width=4) == []


def test_width_candidates_for_length_rejects_negative_length():
    with pytest.raises(ValueError):
        width_candidates_for_length(-1)


def test_width_candidates_for_length_rejects_non_positive_max_width():
    with pytest.raises(ValueError):
        width_candidates_for_length(12, max_width=0)


def test_aspect_ratio_for_width_empty_length():
    assert aspect_ratio_for_width(0, 80) == 0.0


def test_aspect_ratio_for_width_complete_rows():
    # length 12 at width 4 → 4×3 cells → aspect 4/3
    assert aspect_ratio_for_width(12, 4) == pytest.approx(4 / 3)


def test_aspect_ratio_for_width_incomplete_final_row():
    # length 13 at width 4 → 4×4 cells visually
    assert aspect_ratio_for_width(13, 4) == 1.0


def test_aspect_ratio_for_width_rejects_negative_length():
    with pytest.raises(ValueError):
        aspect_ratio_for_width(-1, 4)


def test_rank_widths_by_aspect():
    ranked = rank_widths_by_aspect(
        length=12,
        target_aspect=1.0,
        min_width=1,
        max_width=12,
        divisors_only=True,
    )

    # Divisor candidates:
    # width 1  -> 1/12
    # width 2  -> 2/6
    # width 3  -> 3/4
    # width 4  -> 4/3
    # width 6  -> 6/2
    # width 12 -> 12/1
    #
    # Closest to 1.0 are 3 and 4 equally distant by 0.25 and 0.333...
    assert ranked[0][1] == 3
    assert ranked[0][0] == pytest.approx(0.25)


def test_rank_widths_by_aspect_rejects_non_positive_target():
    with pytest.raises(ValueError):
        rank_widths_by_aspect(12, target_aspect=0)


def test_best_widths_by_aspect():
    best = best_widths_by_aspect(
        length=12,
        target_aspect=1.0,
        count=3,
        min_width=1,
        max_width=12,
        divisors_only=True,
    )

    assert best == [3, 4, 2]


def test_best_widths_by_aspect_rejects_non_positive_count():
    with pytest.raises(ValueError):
        best_widths_by_aspect(12, target_aspect=1.0, count=0)
