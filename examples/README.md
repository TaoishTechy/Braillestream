# Example Test 1:

---

### python - <<'PY'
from PIL import Image
img = Image.new("L", (16, 16), 255)
for y in range(16):
    for x in range(16):
        if x == y or x == 15 - y:
            img.putpixel((x, y), 0)
img.save("examples/input/x_test.png")
PY

### x_test.png

<img width="16" height="16" alt="x_test" src="https://github.com/user-attachments/assets/0b08fa25-572f-4432-8e7a-ac22893c9916" />


---

### braillestream encode examples/input/x_test.png -W 8 -H 4 --resize-mode stretch --polarity dark-on-light --info -o examples/output/x_test.bs
source_px=16x16
output_px=16x16
cells=8x4
length=32
complete=True

---

### braillestream render examples/output/x_test.bs -W 8 -o examples/output/x_test.rendered.txt

---

### x_test.bs:

⠑⢄⠀⠀⠀⠀⡠⠊⠀⠀⠑⢄⡠⠊⠀⠀⠀⠀⡠⠊⠑⢄⠀⠀⡠⠊⠀⠀⠀⠀⠑⢄


### x_test_rendered.txt:

⠑⢄⠀⠀⠀⠀⡠⠊
⠀⠀⠑⢄⡠⠊⠀⠀
⠀⠀⡠⠊⠑⢄⠀⠀
⡠⠊⠀⠀⠀⠀⠑⢄
