# BrailleStream CLI Usage

BrailleStream includes a command-line tool:

```bash
braillestream
````

It can:

```text
encode images into Unicode Braille streams
hard-wrap streams at chosen projection widths
reverse streams into 0/1 pixel grids
inspect stream geometry
suggest projection widths
build BS1 packets
parse BS1 packets
extract packet payloads
```

---

## 1. Install for Local Development

From repo root:

```bash
python -m pip install -e .
```

Verify:

```bash
braillestream --help
```

Run tests:

```bash
python -m pytest
```

---

## 2. Encode an Image

Basic image to BrailleStream:

```bash
braillestream encode input.png -o output.bs
```

This writes a single-line Unicode Braille stream to:

```text
output.bs
```

Print to terminal:

```bash
braillestream encode input.png
```

Encode with target width and height in Braille cells:

```bash
braillestream encode input.png -W 80 -H 32 --resize-mode stretch -o output.bs
```

Remember:

```text
1 Braille cell = 2 pixels wide × 4 pixels tall
```

So:

```text
-W 80 -H 32
```

means the output image grid is:

```text
160 px wide × 128 px tall
```

before conversion into Braille glyphs.

---

## 3. Encoding Options

### Threshold

```bash
braillestream encode input.png --threshold 128 -o output.bs
```

Threshold range:

```text
0..255
```

Lower threshold means fewer pixels become raised dots.

Higher threshold means more pixels become raised dots in `dark-on-light` mode.

---

### Gamma

```bash
braillestream encode input.png --gamma 1.2 -o output.bs
```

Gamma behavior:

```text
1.0  unchanged
>1.0 darkens midtones
<1.0 brightens midtones
```

---

### Dither

```bash
braillestream encode input.png --dither -o output.bs
```

Uses Floyd-Steinberg dithering.

This helps gradients and texture survive the 1-bit dot conversion.

---

### Invert

```bash
braillestream encode input.png --invert -o output.bs
```

Inverts grayscale before thresholding.

---

### Polarity

```bash
braillestream encode input.png --polarity dark-on-light -o output.bs
```

Supported values:

```text
dark-on-light
light-on-dark
```

`dark-on-light`:

```text
dark pixels become raised Braille dots
```

`light-on-dark`:

```text
bright pixels become raised Braille dots
```

---

### Resize Mode

```bash
braillestream encode input.png -W 80 -H 32 --resize-mode fit -o output.bs
```

Supported modes:

```text
none
fit
stretch
crop
```

`none`:

```text
Do not preserve requested target as a canvas mode.
Crop/resize minimally to valid 2×4 geometry.
```

`fit`:

```text
Preserve aspect ratio inside target dimensions and pad.
```

`stretch`:

```text
Force exact target dimensions.
```

`crop`:

```text
Preserve aspect ratio while filling target dimensions, cropping excess.
```

---

## 4. Encode With Metadata Header

```bash
braillestream encode input.png -W 80 -H 32 --header -o frame.txt
```

Example output:

```text
BS1|W=80|H=32|CELL=2x4|POL=dark-on-light|GAMMA=1.0|LEN=2560|
<payload>
```

This is a simple header from the encoder.

For stricter packet handling, use `packet-build`.

---

## 5. Encode and Hard-Wrap Immediately

```bash
braillestream encode input.png -W 80 -H 32 --wrap 80 -o rendered.txt
```

This outputs rows instead of one line.

Useful for quick viewing.

But the canonical BrailleStream payload should usually remain one line.

---

## 6. Print Encoding Info

```bash
braillestream encode input.png -W 80 -H 32 --resize-mode stretch --info -o output.bs
```

Metadata is printed to stderr:

```text
source_px=640x480
output_px=160x128
cells=80x32
length=2560
complete=True
```

---

## 7. Render a Stream

Hard-wrap a single-line stream at width `W`:

```bash
braillestream render output.bs -W 80
```

Write rendered text to file:

```bash
braillestream render output.bs -W 80 -o rendered.txt
```

Example:

```bash
printf '⣿⠀⣿⠀' | braillestream render -W 2 --unwrap
```

Output:

```text
⣿⠀
⣿⠀
```

---

## 8. Render With Padding

```bash
braillestream render output.bs -W 80 --pad
```

Default pad character is blank Braille:

```text
⠀
```

Custom pad character:

```bash
braillestream render output.bs -W 80 --pad --pad-char _
```

---

## 9. Unwrap Wrapped Input

If a stream has already been hard-wrapped:

```text
⣿⠀
⣿⠀
```

you can unwrap it before processing:

```bash
braillestream render wrapped.txt -W 4 --unwrap
```

Output:

```text
⣿⠀⣿⠀
```

Strip spaces and tabs while unwrapping:

```bash
braillestream render wrapped.txt -W 4 --unwrap --strip-spaces
```

---

## 10. Reverse Decode to Pixel Grid

Decode Braille glyphs into a binary 0/1 pixel grid:

```bash
braillestream reverse output.bs -W 80 -o pixels.txt
```

Example:

```bash
printf '⣿' | braillestream reverse -W 1
```

Output:

```text
11
11
11
11
```

Because `⣿` is a full 2×4 cell.

Example:

```bash
printf '⠀' | braillestream reverse -W 1
```

Output:

```text
00
00
00
00
```

Use custom symbols:

```bash
braillestream reverse output.bs -W 80 --on '#' --off '.'
```

---

## 11. Density Preview

Convert each Braille glyph to a normalized density value or ramp character.

Ramp preview:

```bash
braillestream density output.bs -W 80
```

Custom ramp:

```bash
braillestream density output.bs -W 80 --ramp ' .#'
```

Numeric density:

```bash
braillestream density output.bs -W 80 --numeric
```

Numeric density with comma separator:

```bash
braillestream density output.bs -W 80 --numeric --separator ','
```

Example:

```bash
printf '⠀⣿' | braillestream density -W 2 --numeric --separator ','
```

Output:

```text
0.000,1.000
```

---

## 12. Inspect Stream Geometry

```bash
braillestream inspect output.bs -W 80
```

Example output:

```text
length=2560
width_cells=80
height_cells=32
width_px=160
height_px=128
complete_final_row=True
```

This tells you how the one-line stream projects at width `W`.

---

## 13. Suggest Widths

Suggest divisor widths for a stream length:

```bash
braillestream widths --length 2560 --min-width 20 --max-width 200
```

Use an actual stream:

```bash
braillestream widths output.bs --min-width 20 --max-width 200
```

Include non-divisor widths:

```bash
braillestream widths output.bs --min-width 20 --max-width 200 --all
```

Rank widths by target aspect ratio:

```bash
braillestream widths output.bs --target-aspect 1.333 --min-width 20 --max-width 200
```

Limit count:

```bash
braillestream widths output.bs --count 5
```

---

# BS1 Packet Commands

BS1 packets wrap a raw BrailleStream payload with metadata.

Canonical form:

```text
BS1|W=80|H=32|CELL=2x4|LEN=2560|MODE=luma|CRC=A91F2C44|
<payload>
```

---

## 14. Build a Packet

From a raw payload:

```bash
braillestream packet-build output.bs -W 80 -H 32 -o frame.bs1
```

Infer height:

```bash
braillestream packet-build output.bs -W 80 -o frame.bs1
```

Include CRC:

```bash
braillestream packet-build output.bs -W 80 -H 32 --crc -o frame.bs1
```

Add metadata fields:

```bash
braillestream packet-build output.bs \
  -W 80 \
  -H 32 \
  --polarity dark-on-light \
  --gamma 1.0 \
  --threshold 128 \
  --dither-mode none \
  --mode luma \
  --crc \
  -o frame.bs1
```

---

## 15. Build Packet From Wrapped Payload

If payload file is wrapped:

```text
⣿⠀
⣿⠀
```

build a packet after unwrapping:

```bash
braillestream packet-build wrapped.txt -W 4 -H 1 --unwrap -o frame.bs1
```

Strip regular spaces and tabs too:

```bash
braillestream packet-build wrapped.txt -W 4 -H 1 --unwrap --strip-spaces -o frame.bs1
```

---

## 16. Strict Packet Build

Strict packet build requires:

```text
LEN == W × H
```

Example:

```bash
braillestream packet-build output.bs -W 80 -H 32 --strict -o frame.bs1
```

If the payload length does not exactly match the rectangle, the command fails.

---

## 17. Parse a Packet

```bash
braillestream packet-parse frame.bs1
```

Example output:

```text
version=BS1
width=80
height=32
cell=2x4
length=2560
polarity=dark-on-light
gamma=1.0
threshold=128
dither=none
mode=luma
crc=A91F2C44
```

---

## 18. Packet Summary

```bash
braillestream packet-parse frame.bs1 --summary
```

Example:

```text
version=BS1
width=80
height=32
cell=2x4
length=2560
declared_length=2560
has_crc=True
complete_rectangle=True
```

---

## 19. Relaxed Packet Parsing

By default, packet parsing is strict.

Strict means:

```text
LEN == W × H
```

Relaxed parsing allows incomplete final rows if `H` is large enough.

```bash
braillestream packet-parse frame.bs1 --relaxed
```

Use relaxed mode for partial streams, fragments, or experimental projections.

---

## 20. Parse Wrapped Packet Payload

If the packet payload itself is hard-wrapped:

```bash
braillestream packet-parse frame.bs1 --unwrap-payload
```

Strip spaces and tabs too:

```bash
braillestream packet-parse frame.bs1 --unwrap-payload --strip-spaces
```

---

## 21. Extract Packet Payload

```bash
braillestream packet-payload frame.bs1 -o payload.bs
```

Extract and hard-wrap:

```bash
braillestream packet-payload frame.bs1 --render-width 80 -o rendered.txt
```

Extract in relaxed mode:

```bash
braillestream packet-payload frame.bs1 --relaxed -o payload.bs
```

Extract without validation:

```bash
braillestream packet-payload frame.bs1 --no-validate -o payload.bs
```

Use `--no-validate` only for debugging broken packets.

---

## 22. Example Full Workflow

Encode an image:

```bash
braillestream encode input.png \
  -W 80 \
  -H 32 \
  --resize-mode crop \
  --dither \
  --polarity dark-on-light \
  -o image.bs
```

Build a packet:

```bash
braillestream packet-build image.bs \
  -W 80 \
  -H 32 \
  --polarity dark-on-light \
  --gamma 1.0 \
  --threshold 128 \
  --dither-mode floyd-steinberg \
  --mode luma \
  --crc \
  --strict \
  -o image.bs1
```

Validate summary:

```bash
braillestream packet-parse image.bs1 --summary
```

Render payload for viewing:

```bash
braillestream packet-payload image.bs1 --render-width 80 -o image.rendered.txt
```

Reverse to pixel grid:

```bash
braillestream packet-payload image.bs1 -o image.payload.bs
braillestream reverse image.payload.bs -W 80 -o image.pixels.txt
```

---

## 23. Textarea / Browser Viewing

For the folding effect, paste a raw payload into a monospace textarea with soft-wrap enabled.

Changing the textarea width changes:

```text
W = floor(textarea_pixel_width / glyph_cell_pixel_width)
```

That changes the projection:

```text
x = i mod W
y = floor(i / W)
```

So the same one-line stream may become one image, two images, three images, or a distorted/interference pattern depending on the width.

To preserve fixed layout instead, hard-wrap it:

```bash
braillestream render image.bs -W 80 -o fixed.txt
```

---

## 24. Pure Braille Payload Rule

Most commands validate that payloads contain only Unicode Braille characters:

```text
U+2800 .. U+28FF
```

This rejects:

```text
ASCII letters
regular spaces
tabs
emoji
punctuation
```

For debugging only, some commands support:

```bash
--allow-non-braille
```

or:

```bash
--no-validate
```

Canonical BrailleStream payloads should stay pure.

---

## 25. Recommended Development Checks

Run all tests:

```bash
python -m pytest
```

Run only packet CLI tests:

```bash
python -m pytest tests/test_cli_packet.py
```

Run only codec tests:

```bash
python -m pytest tests/test_codec.py
```

Run only render tests:

```bash
python -m pytest tests/test_render.py
```

---

## 26. Current CLI Commands

```text
encode
render
reverse
density
inspect
widths
packet-build
packet-parse
packet-payload
```

Use:

```bash
braillestream <command> --help
```

Examples:

```bash
braillestream encode --help
braillestream packet-build --help
braillestream packet-parse --help
```

---

## 27. Next CLI Targets

Likely next commands:

```text
diff
resonance
prompt-pack
snapshot
animate
sidecar
```

Suggested future examples:

```bash
braillestream prompt-pack image.bs1 -o prompt.txt
braillestream diff before.bs after.bs -W 80 -o diff.txt
braillestream animate frames/ -W 80 --fps 12 -o animation.bs1
```

