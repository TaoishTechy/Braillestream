# BrailleStream

**BrailleStream** is a text-native visual encoding system that converts images, frames, simulations, and agent observations into a single-line Unicode Braille stream.

It is not classic ASCII art.

Classic ASCII art depends on visible symbols, spaces, and fixed line breaks. BrailleStream uses Unicode Braille characters as 2×4 micro-pixel cells. A continuous one-line stream becomes an image only when it is soft-wrapped by a terminal, textarea, editor, or renderer.

```text
1D Unicode Braille stream
→ soft-wrap at width W
→ 2D visual field
````

Changing the wrap width changes the projection.

That means the same stream can recompose into different coherent visual forms at different widths.

---

## Core Idea

Each Unicode Braille character represents an 8-bit dot pattern:

```text
2 columns × 4 rows = 8 micro-pixels
```

The Unicode Braille block spans:

```text
U+2800 .. U+28FF
```

That gives 256 possible glyph states per character.

Dense glyphs like:

```text
⣿ ⣷ ⣾ ⡿ ⢿ ⠿
```

act like filled visual tiles.

Sparse glyphs like:

```text
⠄ ⠁ ⠂ ⡀ ⢀ ⠠
```

act like low-density visual tiles.

A BrailleStream image is flattened into one continuous line:

```text
⣿⣿⣿⣿⣿⠟⠛⢉⢉⠉⠉⠻⣿⣿⣿⣿⣿...
```

The renderer decides where the visual line breaks occur.

---

## Projection Rule

Given a stream `S` and a wrap width `W`, each glyph index `i` maps into 2D space:

```text
x = i mod W
y = floor(i / W)
```

So the image is not stored as fixed rows.

The rows are created by projection.

```text
Render(S, W) → ImageW
```

This makes BrailleStream a **modulo-fold raster format**.

---

## Why It Works

A textarea or terminal does not scale the image like a bitmap. It reflows the character-pixel matrix.

If the textarea can fit 80 glyphs per row, the visual break happens every 80 characters.

If it can fit 40 glyphs per row, the visual break happens every 40 characters.

Same data. Different fold.

At harmonic widths, the same stream can reveal:

```text
W      → one full image
W / 2  → two folded copies
W / 3  → three folded copies
```

This creates a text-native folding/holographic effect.

---

## Goals

BrailleStream aims to become:

* A Unicode Braille image codec
* A terminal-native visual renderer
* A resizable textarea visual field
* A symbolic framebuffer for LLMs and agents
* A compact visual memory format
* A foundation for text-only simulation displays
* A multi-width projection and folding-steganography system

---

## Core Pipeline

```text
image / frame / simulation state
→ grayscale or multi-channel preprocessing
→ resize to 2×4 Braille-cell grid
→ threshold / dither / gamma correction
→ map each 2×4 block to Unicode Braille
→ flatten into one continuous stream
→ render by soft-wrapping at width W
```

---

## Minimal Algorithm

1. Load image.
2. Convert to grayscale.
3. Resize or crop so width is divisible by 2 and height is divisible by 4.
4. Split into 2×4 blocks.
5. Threshold each block into 8 binary dots.
6. Convert dot bitmask into Unicode Braille.
7. Flatten all glyphs into a single line.
8. Display in a monospace textarea or terminal with soft wrapping.

---

## Example Dot Mapping

A 2×4 pixel block:

```text
1 0
1 1
0 1
0 0
```

becomes an 8-bit Braille mask, then a Unicode character.

Each glyph is a micro-tile, not a letter.

---

## Planned Features

### Core

* Image to BrailleStream conversion
* Single-line stream output
* Fixed-width rendering
* Soft-wrap rendering
* Reverse parser from stream back to dot grid
* Width resonance scoring
* Metadata headers

### Image Quality

* Adaptive thresholding
* Floyd-Steinberg dithering
* Gamma correction
* Edge emphasis
* Density balancing
* Perceptual loss tuning

### Folding Intelligence

* Best-width detection
* Harmonic width presets
* Multi-width coherent encoding
* Folding steganography
* Width sweep previews
* Seam-aware optimization

### LLM / Agent Support

* LLM vision prompt pack
* Reverse decode to sparse pixel map
* Density histogram signatures
* Visual diff timeline
* Object-layer JSON sidecars
* Attention heatmap streams
* Symbolic vision tokens

### Animation

* GIF / video frame encoding
* Delta frame compression
* Predictive frame interpolation
* Loop-aware stream format
* Terminal playback mode

### Advanced

* ANSI color channels
* Depth-from-density
* Multi-stream sensorium mode
* Braille OCR / classifier
* Agent memory snapshots
* Closed-loop LLM renderer

---

## Proposed Packet Format

```text
BS1|W=80|H=32|CELL=2x4|MODE=luma|GAMMA=1.0|LEN=2560|CRC=91AF|
<payload>
```

Future packet fields may include:

```text
ID
timestamp
width hints
height hints
polarity
gamma
palette
frame index
delta mode
sidecar hash
checksum
```

---

## Example LLM Prompt Pack

```text
You are viewing a BrailleStream image.

Render width: 80 characters.
Each character is a Unicode Braille 2×4 micro-pixel block.
Decode each glyph using the Unicode Braille dot mapping.
Describe objects, edges, symmetry, density, and anomalies.

STREAM:
<single-line-braille-payload>
```

This allows an LLM to inspect a stream as structured visual text.

---

## Why This Matters

BrailleStream turns text into a visual substrate.

It can carry:

```text
image
motion
depth
attention
semantic labels
simulation state
agent memory
visual diffs
```

Because it remains plain Unicode text, it can move through systems that cannot easily handle binary image formats:

```text
terminal
SSH
logs
chat
LLM context
markdown
web textarea
plain text files
```

The long-term target is not just “image-to-text art.”

The target is a **text-native visual bus**.

---

## Project Structure

Planned layout:

```text
braillestream/
├── README.md
├── LICENSE
├── pyproject.toml
├── src/
│   └── braillestream/
│       ├── __init__.py
│       ├── codec.py
│       ├── mapping.py
│       ├── render.py
│       ├── reverse.py
│       ├── resonance.py
│       ├── packet.py
│       └── cli.py
├── web/
│   ├── app.py
│   └── templates/
│       └── index.html
├── examples/
│   ├── input/
│   └── output/
├── tests/
│   ├── test_mapping.py
│   ├── test_codec.py
│   └── test_reverse.py
└── docs/
    ├── projection-calculus.md
    ├── packet-format.md
    └── llm-agent-vision.md
```

---

## CLI Sketch

```bash
braillestream encode image.png --width 80 --dither --gamma 1.2 > image.bs

braillestream render image.bs --width 80

braillestream reverse image.bs --width 80 --output reconstructed.png

braillestream resonance image.bs --min-width 20 --max-width 200

braillestream prompt image.bs --width 80
```

---

## Python Sketch

```python
from braillestream import encode_image, render_stream, reverse_stream

stream = encode_image(
    "input.png",
    width_cells=80,
    dither=True,
    gamma=1.2,
)

print(stream)

grid = render_stream(stream, width=80)

pixels = reverse_stream(stream, width=80)
```

---

## Status

Early repository setup.

Current milestone:

```text
M0: README and conceptual foundation
M1: Minimal image-to-Braille converter
M2: CLI encoder/renderer/reverse parser
M3: Flask/Web demo with live textarea folding
M4: Packet format + LLM prompt pack
M5: Multi-width resonance and folding experiments
```

---

## License

MIT License

Copyright (c) 2026 TaoishTechy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the “Software”), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM,
OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE

---

## Author

TaoishTechy

Project concept: BrailleStream / text-native visual bus / modulo-fold raster hologram.
