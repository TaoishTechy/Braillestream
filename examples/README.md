# BrailleStream Examples

This directory contains small, reproducible examples for testing the BrailleStream pipeline.

BrailleStream converts images into single-line Unicode Braille streams, then projects those streams back into a visual field by wrapping at a chosen width.

---

# Example Test 1: 16×16 X Pattern

This example verifies the first complete end-to-end workflow:

```text
Pillow image
→ BrailleStream encode
→ single-line `.bs` payload
→ fixed-width render
→ BS1 packet build/parse/payload extraction
→ reverse pixel decode
→ density preview
```

---

## 1. Generate Test Image

```bash
python - <<'PY'
from PIL import Image

img = Image.new("L", (16, 16), 255)

for y in range(16):
    for x in range(16):
        if x == y or x == 15 - y:
            img.putpixel((x, y), 0)

img.save("examples/input/x_test.png")
PY
```

### Source Image

`examples/input/x_test.png`

<img width="16" height="16" alt="x_test" src="https://github.com/user-attachments/assets/0b08fa25-572f-4432-8e7a-ac22893c9916" />

---

## 2. Encode Image to BrailleStream

```bash
braillestream encode examples/input/x_test.png \
  -W 8 \
  -H 4 \
  --resize-mode stretch \
  --polarity dark-on-light \
  --info \
  -o examples/output/x_test.bs
```

Expected metadata:

```text
source_px=16x16
output_px=16x16
cells=8x4
length=32
complete=True
```

The encoded output is a single-line BrailleStream payload.

### `examples/output/x_test.bs`

```text
⠑⢄⠀⠀⠀⠀⡠⠊⠀⠀⠑⢄⡠⠊⠀⠀⠀⠀⡠⠊⠑⢄⠀⠀⡠⠊⠀⠀⠀⠀⠑⢄
```

---

## 3. Render the Stream at Width 8

```bash
braillestream render examples/output/x_test.bs \
  -W 8 \
  -o examples/output/x_test.rendered.txt
```

### `examples/output/x_test.rendered.txt`

```text
⠑⢄⠀⠀⠀⠀⡠⠊
⠀⠀⠑⢄⡠⠊⠀⠀
⠀⠀⡠⠊⠑⢄⠀⠀
⡠⠊⠀⠀⠀⠀⠑⢄
```

This confirms the core projection rule:

```text
x = i mod W
y = floor(i / W)
```

At `W=8`, the 32-glyph payload becomes an 8×4 Braille-cell image.

---

## 4. Build a Strict BS1 Packet with CRC

```bash
braillestream packet-build examples/output/x_test.bs \
  -W 8 \
  -H 4 \
  --crc \
  --strict \
  -o examples/output/x_test.bs1
```

Parse packet summary:

```bash
braillestream packet-parse examples/output/x_test.bs1 --summary
```

Expected summary:

```text
version=BS1
width=8
height=4
cell=2x4
length=32
declared_length=32
has_crc=True
complete_rectangle=True
```

This confirms:

```text
LEN == W × H
32 == 8 × 4
```

and verifies that the payload checksum is present.

---

## 5. Extract and Render Packet Payload

```bash
braillestream packet-payload examples/output/x_test.bs1 \
  --render-width 8 \
  -o examples/output/x_test.packet.rendered.txt
```

Expected output:

```text
⠑⢄⠀⠀⠀⠀⡠⠊
⠀⠀⠑⢄⡠⠊⠀⠀
⠀⠀⡠⠊⠑⢄⠀⠀
⡠⠊⠀⠀⠀⠀⠑⢄
```

The packet payload render should match `x_test.rendered.txt`.

---

## 6. Reverse Decode to Binary Pixels

```bash
braillestream reverse examples/output/x_test.bs \
  -W 8 \
  --on '#' \
  --off '.' \
  -o examples/output/x_test.pixels.txt
```

### `examples/output/x_test.pixels.txt`

```text
#..............#
.#............#.
..#..........#..
...#........#...
....#......#....
.....#....#.....
......#..#......
.......##.......
.......##.......
......#..#......
.....#....#.....
....#......#....
...#........#...
..#..........#..
.#............#.
#..............#
```

This confirms that the 8×4 Braille-cell stream reverses back into the original 16×16 binary pixel structure.

---

## 7. Density Preview

Density preview converts each Braille glyph into a normalized dot-density value.

```bash
braillestream density examples/output/x_test.bs \
  -W 8 \
  --numeric \
  --separator ',' \
  -o examples/output/x_test.density.numeric.txt
```

### `examples/output/x_test.density.numeric.txt`

```text
0.250,0.250,0.000,0.000,0.000,0.000,0.250,0.250
0.000,0.000,0.250,0.250,0.250,0.250,0.000,0.000
0.000,0.000,0.250,0.250,0.250,0.250,0.000,0.000
0.250,0.250,0.000,0.000,0.000,0.000,0.250,0.250
```

A visible density ramp:

```bash
braillestream density examples/output/x_test.bs \
  -W 8 \
  --ramp '░▒▓█' \
  -o examples/output/x_test.density.visible.txt
```

### `examples/output/x_test.density.visible.txt`

```text
▒▒░░░░▒▒
░░▒▒▒▒░░
░░▒▒▒▒░░
▒▒░░░░▒▒
```

ASCII-safe density ramp:

```bash
braillestream density examples/output/x_test.bs \
  -W 8 \
  --ramp '.:+#' \
  -o examples/output/x_test.density.ascii.txt
```

### `examples/output/x_test.density.ascii.txt`

```text
::....::
..::::..
..::::..
::....::
```

Note:

```text
reverse = full 2×4 micro-pixel reconstruction
density = coarse glyph-level signature
```

For this test:

```text
0.000 → first ramp character
0.250 → second ramp character
```

---

## 8. Test Result Summary

Example Test 1 confirms:

```text
image generation works
image encoding works
Braille glyph mapping works
single-line stream output works
fixed-width rendering works
BS1 packet build works
strict packet validation works
CRC packet field works
packet parsing works
packet payload extraction works
reverse micro-pixel decode works
density preview works
```

Result:

```text
PASS
```
