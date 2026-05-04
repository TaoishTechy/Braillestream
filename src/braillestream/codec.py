"""
BrailleStream Codec
===================

Image/frame encoding and decoding helpers for BrailleStream.

This module converts images into single-line Unicode Braille streams.

Core pipeline:

    PIL image
    → grayscale luminance
    → optional gamma correction
    → optional resize/crop to 2×4 cell geometry
    → threshold each 2×4 block
    → map block to Unicode Braille
    → flatten into one continuous stream

Important:

    This file does not handle terminal wrapping or packet metadata.
    It only handles image/grid ↔ BrailleStream conversion.

    Rendering at a chosen width belongs in render.py.
    Packet headers belong in packet.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

try:
    from PIL import Image, ImageOps
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "BrailleStream codec requires Pillow. Install it with: pip install pillow"
    ) from exc

from braillestream.mapping import (
    block_2x4_to_char,
    char_to_block_2x4,
    density_from_char,
)

Polarity = Literal["light-on-dark", "dark-on-light"]
ResizeMode = Literal["fit", "stretch", "crop", "none"]


@dataclass(frozen=True)
class EncodeOptions:
    """
    Options for encoding an image into a BrailleStream.

    Attributes
    ----------
    width_cells:
        Target output width in Braille cells. Each cell is 2 pixels wide.

    height_cells:
        Target output height in Braille cells. Each cell is 4 pixels tall.

    threshold:
        Luminance threshold from 0..255.

    gamma:
        Gamma correction factor. 1.0 means unchanged.

    dither:
        If True, apply Pillow's Floyd-Steinberg 1-bit dithering before block
        conversion.

    invert:
        If True, invert grayscale before thresholding.

    polarity:
        Defines which luminance side becomes a raised Braille dot.

        "light-on-dark":
            Pixels brighter than threshold become raised dots.

        "dark-on-light":
            Pixels darker than threshold become raised dots.

    resize_mode:
        "fit":
            Preserve aspect ratio inside target dimensions and pad.

        "stretch":
            Force exact target dimensions without preserving aspect ratio.

        "crop":
            Preserve aspect ratio while filling target dimensions, cropping excess.

        "none":
            Do not resize. Crop to nearest valid multiple of 2×4.
    """

    width_cells: int | None = None
    height_cells: int | None = None
    threshold: int = 128
    gamma: float = 1.0
    dither: bool = False
    invert: bool = False
    polarity: Polarity = "dark-on-light"
    resize_mode: ResizeMode = "none"


@dataclass(frozen=True)
class EncodedImage:
    """
    Result of encoding an image into a BrailleStream.
    """

    stream: str
    width_cells: int
    height_cells: int
    source_width_px: int
    source_height_px: int
    output_width_px: int
    output_height_px: int
    options: EncodeOptions

    @property
    def length(self) -> int:
        return len(self.stream)

    @property
    def expected_length(self) -> int:
        return self.width_cells * self.height_cells

    @property
    def is_complete(self) -> bool:
        return self.length == self.expected_length


def clamp_threshold(threshold: int) -> int:
    """
    Clamp threshold to valid 8-bit luminance range.
    """
    return max(0, min(255, int(threshold)))


def validate_gamma(gamma: float) -> float:
    """
    Validate and return gamma.

    Gamma must be positive.
    """
    gamma = float(gamma)

    if gamma <= 0:
        raise ValueError(f"Gamma must be positive, got {gamma}.")

    return gamma


def validate_cell_dimensions(
    width_cells: int | None,
    height_cells: int | None,
) -> tuple[int | None, int | None]:
    """
    Validate optional Braille-cell dimensions.
    """
    if width_cells is not None:
        width_cells = int(width_cells)
        if width_cells <= 0:
            raise ValueError(f"width_cells must be positive, got {width_cells}.")

    if height_cells is not None:
        height_cells = int(height_cells)
        if height_cells <= 0:
            raise ValueError(f"height_cells must be positive, got {height_cells}.")

    return width_cells, height_cells


def open_image(image: str | Path | Image.Image) -> Image.Image:
    """
    Open an image path or copy an existing PIL image.

    Returns a detached PIL Image instance.
    """
    if isinstance(image, Image.Image):
        return image.copy()

    path = Path(image)

    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    return Image.open(path).copy()


def apply_gamma(img: Image.Image, gamma: float) -> Image.Image:
    """
    Apply gamma correction to an 8-bit grayscale image.

    gamma > 1 darkens midtones.
    gamma < 1 brightens midtones.
    """
    gamma = validate_gamma(gamma)

    if gamma == 1.0:
        return img

    if img.mode != "L":
        img = img.convert("L")

    lut = [
        int(255 * ((value / 255.0) ** gamma))
        for value in range(256)
    ]

    return img.point(lut)


def normalize_image(
    image: str | Path | Image.Image,
    options: EncodeOptions,
) -> Image.Image:
    """
    Load and normalize image before Braille conversion.

    Returns an 8-bit grayscale PIL image whose dimensions are valid multiples
    of 2×4.
    """
    width_cells, height_cells = validate_cell_dimensions(
        options.width_cells,
        options.height_cells,
    )

    threshold = clamp_threshold(options.threshold)
    gamma = validate_gamma(options.gamma)

    # Rebuild options values through locals without mutating frozen dataclass.
    _ = threshold

    img = open_image(image)
    img = img.convert("L")

    if options.invert:
        img = ImageOps.invert(img)

    img = apply_gamma(img, gamma)

    img = resize_for_braille(
        img,
        width_cells=width_cells,
        height_cells=height_cells,
        mode=options.resize_mode,
    )

    return img


def resize_for_braille(
    img: Image.Image,
    width_cells: int | None = None,
    height_cells: int | None = None,
    mode: ResizeMode = "none",
) -> Image.Image:
    """
    Resize or crop image to valid Braille pixel dimensions.

    Output dimensions must be:

        width_px  = width_cells × 2
        height_px = height_cells × 4

    If no target dimensions are provided, image is cropped down to the nearest
    valid multiple of 2×4.
    """
    width_cells, height_cells = validate_cell_dimensions(width_cells, height_cells)

    if img.mode != "L":
        img = img.convert("L")

    if width_cells is None and height_cells is None:
        return crop_to_braille_multiples(img)

    if width_cells is None:
        assert height_cells is not None
        target_height_px = height_cells * 4
        scale = target_height_px / img.height
        target_width_px = max(2, int(round(img.width * scale)))
        target_width_px = nearest_positive_multiple(target_width_px, 2)
    elif height_cells is None:
        target_width_px = width_cells * 2
        scale = target_width_px / img.width
        target_height_px = max(4, int(round(img.height * scale)))
        target_height_px = nearest_positive_multiple(target_height_px, 4)
    else:
        target_width_px = width_cells * 2
        target_height_px = height_cells * 4

    if mode == "none":
        resized = img.resize((target_width_px, target_height_px), Image.Resampling.LANCZOS)
        return crop_to_braille_multiples(resized)

    if mode == "stretch":
        return img.resize((target_width_px, target_height_px), Image.Resampling.LANCZOS)

    if mode == "fit":
        fitted = ImageOps.contain(img, (target_width_px, target_height_px), Image.Resampling.LANCZOS)
        canvas = Image.new("L", (target_width_px, target_height_px), color=255)
        x = (target_width_px - fitted.width) // 2
        y = (target_height_px - fitted.height) // 2
        canvas.paste(fitted, (x, y))
        return canvas

    if mode == "crop":
        return ImageOps.fit(img, (target_width_px, target_height_px), Image.Resampling.LANCZOS)

    raise ValueError(f"Unknown resize mode: {mode!r}")


def crop_to_braille_multiples(img: Image.Image) -> Image.Image:
    """
    Crop image down to the nearest dimensions divisible by 2 and 4.
    """
    if img.mode != "L":
        img = img.convert("L")

    width = (img.width // 2) * 2
    height = (img.height // 4) * 4

    if width <= 0 or height <= 0:
        raise ValueError(
            f"Image too small for one Braille cell: {img.width}x{img.height}px."
        )

    if width == img.width and height == img.height:
        return img

    return img.crop((0, 0, width, height))


def nearest_positive_multiple(value: int, multiple: int) -> int:
    """
    Round value to nearest positive multiple.

    Guarantees at least one multiple.
    """
    value = int(value)
    multiple = int(multiple)

    if multiple <= 0:
        raise ValueError(f"multiple must be positive, got {multiple}.")

    rounded = int(round(value / multiple)) * multiple
    return max(multiple, rounded)


def image_to_braille_stream(
    image: str | Path | Image.Image,
    options: EncodeOptions | None = None,
) -> EncodedImage:
    """
    Encode an image into a single-line Unicode Braille stream.

    Parameters
    ----------
    image:
        Image path or PIL image.

    options:
        EncodeOptions.

    Returns
    -------
    EncodedImage
        Stream plus dimensions and metadata.
    """
    options = options or EncodeOptions()

    source = open_image(image)
    source_width_px, source_height_px = source.size

    img = normalize_image(source, options)

    if options.dither:
        # Pillow produces mode "1"; convert back to L with 0/255 values.
        img = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG).convert("L")

    threshold = clamp_threshold(options.threshold)

    chars: list[str] = []

    for y in range(0, img.height, 4):
        for x in range(0, img.width, 2):
            block = image_block_to_bits(
                img,
                x=x,
                y=y,
                threshold=threshold,
                polarity=options.polarity,
            )
            chars.append(block_2x4_to_char(block))

    width_cells = img.width // 2
    height_cells = img.height // 4

    return EncodedImage(
        stream="".join(chars),
        width_cells=width_cells,
        height_cells=height_cells,
        source_width_px=source_width_px,
        source_height_px=source_height_px,
        output_width_px=img.width,
        output_height_px=img.height,
        options=options,
    )


def image_block_to_bits(
    img: Image.Image,
    x: int,
    y: int,
    threshold: int = 128,
    polarity: Polarity = "dark-on-light",
) -> tuple[tuple[int, int], ...]:
    """
    Convert one 2×4 pixel block into binary dot bits.

    Parameters
    ----------
    img:
        8-bit grayscale image.

    x, y:
        Top-left pixel coordinate of the 2×4 block.

    threshold:
        Luminance threshold.

    polarity:
        "dark-on-light":
            dark pixels become raised dots.

        "light-on-dark":
            light pixels become raised dots.

    Returns
    -------
    tuple[tuple[int, int], ...]
        Four rows of two binary values.
    """
    if img.mode != "L":
        img = img.convert("L")

    threshold = clamp_threshold(threshold)

    rows: list[tuple[int, int]] = []

    for yy in range(y, y + 4):
        values: list[int] = []
        for xx in range(x, x + 2):
            luminance = img.getpixel((xx, yy))

            if polarity == "dark-on-light":
                bit = int(luminance < threshold)
            elif polarity == "light-on-dark":
                bit = int(luminance > threshold)
            else:
                raise ValueError(f"Unknown polarity: {polarity!r}")

            values.append(bit)

        rows.append((values[0], values[1]))

    return (rows[0], rows[1], rows[2], rows[3])


def stream_to_density_grid(
    stream: str,
    width_cells: int,
) -> list[list[float]]:
    """
    Convert a BrailleStream into a 2D grid of normalized glyph densities.

    This is useful for rough previews, signatures, and tests.

    Parameters
    ----------
    stream:
        Unicode Braille stream.

    width_cells:
        Desired wrap width in Braille cells.

    Returns
    -------
    list[list[float]]
        2D density grid.
    """
    width_cells = int(width_cells)

    if width_cells <= 0:
        raise ValueError(f"width_cells must be positive, got {width_cells}.")

    rows: list[list[float]] = []

    for start in range(0, len(stream), width_cells):
        chunk = stream[start : start + width_cells]
        rows.append([density_from_char(char) for char in chunk])

    return rows


def stream_to_pixel_grid(
    stream: str,
    width_cells: int,
) -> list[list[int]]:
    """
    Decode a BrailleStream into a full binary pixel grid.

    Each Braille glyph expands into a 2×4 block.

    Parameters
    ----------
    stream:
        Unicode Braille stream.

    width_cells:
        Number of Braille glyphs per rendered row.

    Returns
    -------
    list[list[int]]
        Binary pixel grid with dimensions:

            height = ceil(len(stream) / width_cells) × 4
            width  = width_cells × 2

        If the final row is incomplete, it is decoded only to its actual width.
    """
    width_cells = int(width_cells)

    if width_cells <= 0:
        raise ValueError(f"width_cells must be positive, got {width_cells}.")

    pixel_rows: list[list[int]] = []

    for start in range(0, len(stream), width_cells):
        chunk = stream[start : start + width_cells]

        expanded_rows = [[], [], [], []]

        for char in chunk:
            block = char_to_block_2x4(char)
            for row_index in range(4):
                expanded_rows[row_index].extend(block[row_index])

        pixel_rows.extend(expanded_rows)

    return pixel_rows


def pixel_grid_to_stream(
    pixels: Sequence[Sequence[int | bool]],
) -> EncodedImage:
    """
    Encode a binary pixel grid into a BrailleStream.

    The pixel grid must have dimensions divisible by 2×4.

    This is useful for tests, procedural renderers, and future simulation output.
    """
    if not pixels:
        raise ValueError("Pixel grid cannot be empty.")

    height_px = len(pixels)
    width_px = len(pixels[0])

    if width_px <= 0:
        raise ValueError("Pixel grid rows cannot be empty.")

    for row_index, row in enumerate(pixels):
        if len(row) != width_px:
            raise ValueError(
                f"Pixel grid must be rectangular. "
                f"Row 0 has width {width_px}, row {row_index} has width {len(row)}."
            )

    if width_px % 2 != 0:
        raise ValueError(f"Pixel grid width must be divisible by 2, got {width_px}.")

    if height_px % 4 != 0:
        raise ValueError(f"Pixel grid height must be divisible by 4, got {height_px}.")

    chars: list[str] = []

    for y in range(0, height_px, 4):
        for x in range(0, width_px, 2):
            block = (
                (int(bool(pixels[y][x])), int(bool(pixels[y][x + 1]))),
                (int(bool(pixels[y + 1][x])), int(bool(pixels[y + 1][x + 1]))),
                (int(bool(pixels[y + 2][x])), int(bool(pixels[y + 2][x + 1]))),
                (int(bool(pixels[y + 3][x])), int(bool(pixels[y + 3][x + 1]))),
            )
            chars.append(block_2x4_to_char(block))

    options = EncodeOptions(
        width_cells=width_px // 2,
        height_cells=height_px // 4,
        threshold=128,
        gamma=1.0,
        dither=False,
        invert=False,
        polarity="dark-on-light",
        resize_mode="none",
    )

    return EncodedImage(
        stream="".join(chars),
        width_cells=width_px // 2,
        height_cells=height_px // 4,
        source_width_px=width_px,
        source_height_px=height_px,
        output_width_px=width_px,
        output_height_px=height_px,
        options=options,
    )


def save_stream(stream: str, path: str | Path) -> None:
    """
    Save a BrailleStream as UTF-8 text.
    """
    Path(path).write_text(stream, encoding="utf-8")


def load_stream(path: str | Path) -> str:
    """
    Load a BrailleStream from UTF-8 text.
    """
    return Path(path).read_text(encoding="utf-8")
