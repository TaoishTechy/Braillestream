"""
BrailleStream.

Text-native visual encoding using Unicode Braille glyphs.
"""

from braillestream.mapping import (
    BRAILLE_COUNT,
    BRAILLE_END,
    BRAILLE_START,
    BRAILLE_TABLE,
    block_2x4_to_char,
    char_to_block_2x4,
    char_to_mask,
    char_to_row_major_bits,
    density_from_char,
    density_from_mask,
    dot_count_from_char,
    dot_count_from_mask,
    is_braille_char,
    mask_to_char,
    mask_to_row_major_bits,
    row_major_bits_to_char,
    row_major_bits_to_mask,
)

__all__ = [
    "BRAILLE_COUNT",
    "BRAILLE_END",
    "BRAILLE_START",
    "BRAILLE_TABLE",
    "block_2x4_to_char",
    "char_to_block_2x4",
    "char_to_mask",
    "char_to_row_major_bits",
    "density_from_char",
    "density_from_mask",
    "dot_count_from_char",
    "dot_count_from_mask",
    "is_braille_char",
    "mask_to_char",
    "mask_to_row_major_bits",
    "row_major_bits_to_char",
    "row_major_bits_to_mask",
]

from braillestream.codec import (
    EncodedImage,
    EncodeOptions,
    image_to_braille_stream,
    pixel_grid_to_stream,
    stream_to_density_grid,
    stream_to_pixel_grid,
)

__all__ += [
    "EncodedImage",
    "EncodeOptions",
    "image_to_braille_stream",
    "pixel_grid_to_stream",
    "stream_to_density_grid",
    "stream_to_pixel_grid",
]

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
    render_dimensions,
    require_pure_braille_stream,
    set_cell,
    unwrap_stream,
    validate_pure_braille_stream,
    width_candidates_for_length,
    wrap_stream,
    wrap_stream_rows,
    xy_to_index,
)

__all__ += [
    "ProjectionCell",
    "RenderDimensions",
    "aspect_ratio_for_width",
    "best_widths_by_aspect",
    "crop_projection",
    "get_cell",
    "index_to_xy",
    "iter_projection",
    "overlay_streams",
    "projection_grid",
    "render_dimensions",
    "require_pure_braille_stream",
    "set_cell",
    "unwrap_stream",
    "validate_pure_braille_stream",
    "width_candidates_for_length",
    "wrap_stream",
    "wrap_stream_rows",
    "xy_to_index",
]

from braillestream.packet import (
    BS1Packet,
    BraillePacket,
    PacketError,
    build_bs1_packet,
    build_header,
    build_packet,
    bs1_from_packet,
    crc32_payload,
    infer_fields_from_payload,
    packet_summary,
    parse_bs1_packet,
    parse_header,
    parse_packet,
    validate_bs1_packet,
    validate_packet,
)

__all__ += [
    "BS1Packet",
    "BraillePacket",
    "PacketError",
    "build_bs1_packet",
    "build_header",
    "build_packet",
    "bs1_from_packet",
    "crc32_payload",
    "infer_fields_from_payload",
    "packet_summary",
    "parse_bs1_packet",
    "parse_header",
    "parse_packet",
    "validate_bs1_packet",
    "validate_packet",
]
