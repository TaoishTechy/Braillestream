# BrailleStream Example Test 2: Real-World Meme Image

This test validates BrailleStream on a larger, noisy, real-world image with:

```text
text overlay
face/body detail
busy background
mixed contrast
wide layout
large packet geometry
```

The goal is to verify that the full pipeline remains stable beyond synthetic toy images.

---

## Test Input

Input file:

```text
examples/input/canada_suffer.png
```

This image is used as a real-world stress test for composition preservation and high-density Unicode Braille rendering.

---

## 1. Encode Image to BrailleStream

Command:

```bash
braillestream encode examples/input/canada_suffer.png \
  -W 120 \
  -H 64 \
  --resize-mode crop \
  --polarity dark-on-light \
  --gamma 1.15 \
  --dither \
  --info \
  -o examples/output/canada_suffer.bs
```

Expected geometry:

```text
cells=120x64
length=7680
complete=True
```

Confirmed packet geometry:

```text
120 × 64 = 7680 glyphs
```

---

## 2. Render Canonical Projection

Command:

```bash
braillestream render examples/output/canada_suffer.bs \
  -W 120 \
  -o examples/output/canada_suffer.rendered.txt
```

Canonical projection:

```text
W=120
height=64 Braille rows
decoded pixel width=240 micro-pixels
decoded pixel height=256 micro-pixels
```

Note:

```text
The canonical render may appear cut off in narrow terminals or editors because each row is 120 Braille glyphs wide.
This is a viewer-width issue, not a render failure.
```

---

## 3. Build Strict BS1 Packet with CRC

Command:

```bash
braillestream packet-build examples/output/canada_suffer.bs \
  -W 120 \
  -H 64 \
  --crc \
  --strict \
  -o examples/output/canada_suffer.bs1
```

Packet parse command:

```bash
braillestream packet-parse examples/output/canada_suffer.bs1 --summary
```

Confirmed output:

```text
version=BS1
width=120
height=64
cell=2x4
length=7680
declared_length=7680
has_crc=True
complete_rectangle=True
```

This confirms:

```text
LEN == W × H
7680 == 120 × 64
```

Result:

```text
PASS
```

---

## 4. Packet Payload Extraction and Render Verification

Commands:

```bash
braillestream packet-payload examples/output/canada_suffer.bs1 \
  --render-width 120 \
  -o examples/output/canada_suffer.packet.rendered.txt

diff -u examples/output/canada_suffer.rendered.txt \
  examples/output/canada_suffer.packet.rendered.txt
```

Confirmed:

```text
diff produced no output
```

This means:

```text
packet payload render == original render
```

SHA-256 proof:

```text
examples/output/canada_suffer.rendered.txt
1dd64d52ae2f70b39e66d5b081074d2b713db89f6db0671de558c1a4eccaca74

examples/output/canada_suffer.packet.rendered.txt
1dd64d52ae2f70b39e66d5b081074d2b713db89f6db0671de558c1a4eccaca74
```

Result:

```text
PASS
```

---

## 5. Reverse Decode to Micro-Pixel Grid

Command:

```bash
braillestream reverse examples/output/canada_suffer.bs \
  -W 120 \
  --on '#' \
  --off '.' \
  -o examples/output/canada_suffer.pixels.txt
```

Geometry check:

```bash
python - <<'PY'
from pathlib import Path

path = Path("examples/output/canada_suffer.pixels.txt")
rows = path.read_text(encoding="utf-8").splitlines()

print(f"pixels_rows={len(rows)}")
print(f"pixels_cols_unique={sorted(set(len(r) for r in rows))}")
PY
```

Confirmed output:

```text
pixels_rows=256
pixels_cols_unique=[240]
```

This confirms:

```text
120 Braille cells × 2 = 240 micro-pixel columns
64 Braille rows × 4 = 256 micro-pixel rows
```

Result:

```text
PASS
```

---

## 6. Density Signature

Command:

```bash
braillestream density examples/output/canada_suffer.bs \
  -W 120 \
  --numeric \
  --separator ',' \
  -o examples/output/canada_suffer.density.numeric.txt
```

Geometry check:

```bash
python - <<'PY'
from pathlib import Path

path = Path("examples/output/canada_suffer.density.numeric.txt")
rows = path.read_text(encoding="utf-8").splitlines()

print(f"density_rows={len(rows)}")
print(f"density_fields_unique={sorted(set(len(r.split(',')) for r in rows))}")
PY
```

Confirmed output:

```text
density_rows=64
density_fields_unique=[120]
```

This confirms:

```text
density grid = 120 fields × 64 rows
```

Result:

```text
PASS
```

---

## 7. Width Resonance / Alternate Projection Candidates

Command:

```bash
braillestream widths examples/output/canada_suffer.bs \
  --min-width 40 \
  --max-width 160 \
  --target-aspect 1.6 \
  --count 12
```

Confirmed output:

```text
120
96
128
80
64
60
48
40
160
```

Interpretation:

```text
W=120 = canonical packet geometry
W=80  = easier terminal preview
W=60  = folded / alternate projection preview
```

Example preview commands:

```bash
braillestream render examples/output/canada_suffer.bs \
  -W 80 \
  -o examples/output/canada_suffer.W80.txt

braillestream render examples/output/canada_suffer.bs \
  -W 60 \
  -o examples/output/canada_suffer.W60.txt
```

---

## 8. Character Counts and Newline Accounting

Command:

```bash
wc -m \
  examples/output/canada_suffer.bs \
  examples/output/canada_suffer.rendered.txt \
  examples/output/canada_suffer.W80.txt \
  examples/output/canada_suffer.W60.txt
```

Confirmed output:

```text
 7680 examples/output/canada_suffer.bs
 7743 examples/output/canada_suffer.rendered.txt
 7775 examples/output/canada_suffer.W80.txt
 7807 examples/output/canada_suffer.W60.txt
31005 total
```

Explanation:

```text
W=120 → 64 rows  → 63 newline chars  → 7680 + 63  = 7743
W=80  → 96 rows  → 95 newline chars  → 7680 + 95  = 7775
W=60  → 128 rows → 127 newline chars → 7680 + 127 = 7807
```

Result:

```text
PASS
```

---

## 9. Exact Payload Round Trip

A first stdout-based hash check differed because writing to stdout appends a display newline.

Correct file-output check:

```bash
braillestream packet-payload examples/output/canada_suffer.bs1 \
  -o examples/output/canada_suffer.payload.extracted.bs

sha256sum \
  examples/output/canada_suffer.bs \
  examples/output/canada_suffer.payload.extracted.bs
```

Confirmed output:

```text
b575c63d6e1c866e4ed104ccd006576bec9a2abe1c8520421195bd5151471ad5  examples/output/canada_suffer.bs
b575c63d6e1c866e4ed104ccd006576bec9a2abe1c8520421195bd5151471ad5  examples/output/canada_suffer.payload.extracted.bs
```

This proves:

```text
raw payload == packet-extracted payload
```

Result:

```text
PASS
```

---

## 10. Reproducibility Fingerprints

Confirmed fingerprints:

```text
canada_suffer.bs chars=7680
canada_suffer.bs sha256=b575c63d6e1c866e4ed104ccd006576bec9a2abe1c8520421195bd5151471ad5
canada_suffer.bs1 sha256=38933ba653dfd6e72d497bb96529b2522883dcdd2c35fa30aa032da0a2e90c87
```

Rendered-file hash match:

```text
canada_suffer.rendered.txt sha256=1dd64d52ae2f70b39e66d5b081074d2b713db89f6db0671de558c1a4eccaca74
canada_suffer.packet.rendered.txt sha256=1dd64d52ae2f70b39e66d5b081074d2b713db89f6db0671de558c1a4eccaca74
```

---

## 11. Test Result Summary

Example Test 2 confirms:

```text
large real-world image encoding works
120×64 canonical Braille geometry works
7680-glyph payload generation works
fixed-width rendering works
strict BS1 packet build works
CRC packet field works
packet parse summary works
packet payload extraction works
packet render matches original render byte-for-byte
reverse micro-pixel decode dimensions are correct
density numeric dimensions are correct
alternate width projections are generated
newline/hash artifact was identified and explained
reproducibility fingerprints are stable
```

Final result:

```text
PASS
```
