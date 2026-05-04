# BrailleStream Packet Format

BrailleStream packets wrap a Unicode Braille payload with a compact metadata header.

The packet format lets a decoder know:

```text
how wide to render the stream
how tall the intended frame is
which cell geometry is used
which polarity was used
how long the payload should be
whether the payload is corrupt
````

The first packet version is:

```text
BS1
```

---

## 1. Minimal Packet

```text
BS1|W=80|H=32|CELL=2x4|LEN=2560|
<payload>
```

The payload is a single-line Unicode Braille stream.

Example:

```text
BS1|W=2|H=1|CELL=2x4|LEN=2|
⣿⠀
```

This means:

```text
version: BS1
width: 2 Braille cells
height: 1 Braille cell
cell geometry: 2×4 micro-pixels
payload length: 2 Unicode Braille glyphs
```

Rendered at width `2`, the payload becomes:

```text
⣿⠀
```

Decoded to binary pixels, it becomes:

```text
1100
1100
1100
1100
```

---

## 2. Core Layout

A packet has two parts:

```text
<header>
<payload>
```

The header is one line.

The payload begins after the first newline.

```text
BS1|KEY=value|KEY=value|KEY=value|
⣿⠀⣿⠀⣿⠀
```

The header always begins with:

```text
BS1|
```

Each field uses:

```text
KEY=value|
```

So the full header grammar is:

```text
BS1|FIELD=VALUE|FIELD=VALUE|...|
```

---

## 3. Required Fields

The minimal stable fields are:

| Field  | Meaning                                 | Example    |
| ------ | --------------------------------------- | ---------- |
| `W`    | Intended render width in Braille cells  | `W=80`     |
| `H`    | Intended render height in Braille cells | `H=32`     |
| `CELL` | Micro-pixel geometry per glyph          | `CELL=2x4` |
| `LEN`  | Payload length in Unicode characters    | `LEN=2560` |

Minimal valid header:

```text
BS1|W=80|H=32|CELL=2x4|LEN=2560|
```

For `BS1`, `CELL` should normally be:

```text
CELL=2x4
```

because Unicode Braille glyphs encode a 2-column × 4-row dot matrix.

---

## 4. Recommended Fields

These fields are optional but strongly recommended.

| Field    | Meaning                        | Example                  |
| -------- | ------------------------------ | ------------------------ |
| `POL`    | Polarity mode                  | `POL=dark-on-light`      |
| `GAMMA`  | Gamma used before thresholding | `GAMMA=1.0`              |
| `THRESH` | Luminance threshold            | `THRESH=128`             |
| `DITHER` | Dither mode                    | `DITHER=floyd-steinberg` |
| `MODE`   | Payload mode                   | `MODE=luma`              |
| `CRC`    | Payload checksum               | `CRC=A91F2C44`           |

Recommended full header:

```text
BS1|W=80|H=32|CELL=2x4|POL=dark-on-light|GAMMA=1.0|THRESH=128|DITHER=none|MODE=luma|LEN=2560|CRC=A91F2C44|
```

---

## 5. Field Definitions

### `W`

Intended render width in Braille glyph cells.

```text
W=80
```

Projection formula:

```text
x = i mod W
y = floor(i / W)
```

The decoder should use `W` as the default render width.

---

### `H`

Intended render height in Braille glyph cells.

```text
H=32
```

Normally:

```text
H = ceil(LEN / W)
```

For complete rectangular frames:

```text
LEN = W × H
```

If `LEN != W × H`, the final row is incomplete unless padding is declared.

---

### `CELL`

Micro-pixel geometry per glyph.

For `BS1`, the normal value is:

```text
CELL=2x4
```

This means one Unicode Braille glyph expands into:

```text
2 pixels wide
4 pixels tall
8 binary dots total
```

---

### `POL`

Polarity used during encoding.

Supported values:

```text
dark-on-light
light-on-dark
```

`dark-on-light` means darker source pixels become raised Braille dots.

`light-on-dark` means brighter source pixels become raised Braille dots.

---

### `GAMMA`

Gamma correction used before thresholding.

```text
GAMMA=1.0
```

`1.0` means unchanged.

Values greater than `1.0` darken midtones.

Values less than `1.0` brighten midtones.

---

### `THRESH`

Threshold used to decide whether each micro-pixel becomes raised or empty.

```text
THRESH=128
```

Valid range:

```text
0..255
```

---

### `DITHER`

Dithering mode.

Suggested values:

```text
none
floyd-steinberg
ordered
adaptive
```

Initial implementation should support:

```text
none
floyd-steinberg
```

---

### `MODE`

Payload interpretation mode.

Suggested values:

```text
luma
mask
density
depth
attention
delta
ansi-color
sensorium
```

For the first implementation:

```text
MODE=luma
```

is enough.

---

### `LEN`

Payload length in Unicode characters.

```text
LEN=2560
```

This is not byte length.

It is the number of Unicode Braille glyphs in the payload.

For a complete rectangular frame:

```text
LEN = W × H
```

---

### `CRC`

Checksum of the payload.

```text
CRC=A91F2C44
```

Initial recommendation:

```text
CRC32 over UTF-8 encoded payload bytes
```

The checksum should be written as 8 uppercase hexadecimal characters.

Example:

```text
CRC=09AF13E2
```

---

## 6. Payload Rules

The payload should be a single line of Unicode Braille characters:

```text
U+2800 .. U+28FF
```

Allowed:

```text
⠀ ⠁ ⠂ ... ⣿
```

Not allowed in a pure `MODE=luma` payload:

```text
regular spaces
tabs
newlines inside payload
ASCII letters
emoji
control characters
```

The payload may be hard-wrapped for human viewing, but canonical packet payloads should be stored as one line.

Canonical:

```text
BS1|W=4|H=1|CELL=2x4|LEN=4|
⣿⠀⣿⠀
```

Display/rendered copy:

```text
⣿⠀
⣿⠀
```

The rendered copy is not the canonical packet unless the decoder explicitly unwraps it.

---

## 7. Comments

Packet comments may appear before the header.

Comment lines begin with `#`.

```text
# Object: black-white test cell
# Intended display: terminal or textarea
BS1|W=2|H=1|CELL=2x4|LEN=2|
⣿⠀
```

Comments are not part of the payload.

Comments should be ignored by strict decoders until the first line beginning with:

```text
BS1|
```

---

## 8. Multiple Frames

Multiple frames may be represented as repeated packets:

```text
BS1|ID=frame0|T=0|W=80|H=32|CELL=2x4|MODE=luma|LEN=2560|CRC=...|
<payload0>
BS1|ID=frame1|T=1|W=80|H=32|CELL=2x4|MODE=luma|LEN=2560|CRC=...|
<payload1>
```

Recommended frame fields:

| Field   | Meaning                    |
| ------- | -------------------------- |
| `ID`    | Frame or packet identifier |
| `T`     | Frame index or timestamp   |
| `FPS`   | Intended playback rate     |
| `PREV`  | Previous frame ID/hash     |
| `DELTA` | Delta encoding mode        |

Example:

```text
BS1|ID=f001|T=1|FPS=12|W=80|H=32|CELL=2x4|MODE=delta|DELTA=xor|LEN=2560|
<payload>
```

---

## 9. Delta Packets

A future delta packet may store only changed cells.

Suggested delta syntax:

```text
BS1|ID=f002|PREV=f001|MODE=delta|DELTA=sparse|W=80|H=32|COUNT=3|
@124=⣟,@125=⣿,@241=⠄
```

For `BS1`, sparse delta payload entries use:

```text
@index=glyph
```

Example:

```text
@124=⣟
```

means:

```text
replace stream[124] with ⣟
```

This is not required for the first implementation.

---

## 10. Sidecars

A packet may reference sidecar files.

Suggested fields:

| Field     | Meaning                  |
| --------- | ------------------------ |
| `SIDE`    | Sidecar path or URI      |
| `SIDECRC` | Sidecar checksum         |
| `OBJECTS` | Object-layer sidecar     |
| `ATTN`    | Attention stream sidecar |
| `DEPTH`   | Depth stream sidecar     |

Example:

```text
BS1|W=80|H=32|CELL=2x4|MODE=luma|LEN=2560|SIDE=frame001.objects.json|
<payload>
```

Example object sidecar:

```json
{
  "objects": [
    {
      "label": "face",
      "bbox": [22, 4, 38, 28],
      "confidence": 0.81
    }
  ]
}
```

---

## 11. Canonical Validation

A strict decoder should validate:

```text
header begins with BS1|
required fields exist
W is positive integer
H is positive integer
CELL equals 2x4
LEN is non-negative integer
payload length equals LEN
payload contains only Unicode Braille characters
if CRC exists, checksum matches payload
if H exists, H equals ceil(LEN / W) or LEN equals W × H depending on strictness
```

For complete rectangular frames:

```text
LEN == W × H
```

For stream fragments:

```text
LEN <= W × H
```

or `H` may be omitted in future relaxed profiles.

---

## 12. Strict vs Relaxed Profiles

### Strict Profile

Use for files, tests, reproducible frames, and packet transport.

Rules:

```text
required: W, H, CELL, LEN
CELL must be 2x4
LEN must equal payload character count
LEN must equal W × H
payload must be pure Unicode Braille
CRC must match if present
```

### Relaxed Profile

Use for experiments, partial streams, and human-edited data.

Rules:

```text
required: W, CELL, LEN
H may be inferred
LEN must equal payload character count
final row may be incomplete
comments allowed
CRC optional
```

---

## 13. Error Codes

Suggested parser error names:

```text
ERR_NO_HEADER
ERR_BAD_VERSION
ERR_MISSING_FIELD
ERR_BAD_FIELD
ERR_BAD_WIDTH
ERR_BAD_HEIGHT
ERR_BAD_CELL
ERR_BAD_LENGTH
ERR_LENGTH_MISMATCH
ERR_NON_BRAILLE_PAYLOAD
ERR_CRC_MISMATCH
ERR_RECTANGLE_MISMATCH
```

These should become exception types or error codes in `packet.py`.

---

## 14. Examples

### One Full Cell

```text
BS1|W=1|H=1|CELL=2x4|POL=dark-on-light|LEN=1|
⣿
```

Pixel decode:

```text
11
11
11
11
```

---

### One Empty Cell

```text
BS1|W=1|H=1|CELL=2x4|POL=dark-on-light|LEN=1|
⠀
```

Pixel decode:

```text
00
00
00
00
```

---

### Two Cells Wide

```text
BS1|W=2|H=1|CELL=2x4|POL=dark-on-light|LEN=2|
⣿⠀
```

Pixel decode:

```text
1100
1100
1100
1100
```

---

### Two Cells Tall

```text
BS1|W=1|H=2|CELL=2x4|POL=dark-on-light|LEN=2|
⣿⠀
```

Rendered:

```text
⣿
⠀
```

Pixel decode:

```text
11
11
11
11
00
00
00
00
```

---

### Wrapped Display Copy

Canonical packet payload:

```text
BS1|W=4|H=2|CELL=2x4|LEN=8|
⣿⠀⣿⠀⣿⠀⣿⠀
```

Rendered at `W=4`:

```text
⣿⠀⣿⠀
⣿⠀⣿⠀
```

Rendered at `W=2`:

```text
⣿⠀
⣿⠀
⣿⠀
⣿⠀
```

Same stream, different projection.

---

## 15. Design Principles

BrailleStream packets should remain:

```text
plain UTF-8
human-readable
line-oriented
easy to parse
safe to paste into chat
safe to store in git
friendly to terminals
friendly to LLM context
```

Avoid binary headers for `BS1`.

The format should be boring and robust.

The novelty belongs in the projection.

---

## 16. First Implementation Target

The first `packet.py` should implement:

```text
parse_header()
build_header()
parse_packet()
build_packet()
validate_packet()
crc32_payload()
```

Initial dataclass:

```python
@dataclass(frozen=True)
class BraillePacket:
    version: str
    fields: dict[str, str]
    payload: str
```

Then later upgrade to typed fields:

```python
@dataclass(frozen=True)
class BS1Packet:
    width: int
    height: int
    cell: str
    length: int
    payload: str
    polarity: str | None = None
    gamma: float | None = None
    threshold: int | None = None
    dither: str | None = None
    mode: str | None = None
    crc: str | None = None
```
