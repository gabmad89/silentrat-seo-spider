#!/usr/bin/env python3
"""Generate silentrat.ico with the rat logo (SilentRat brand)."""
import os
from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (43, 47, 54, 255))  # dark background
d = ImageDraw.Draw(img)

def sc(*coords):
    return [c / 64 * SIZE for c in coords]

# body
d.ellipse(sc(10, 20, 44, 48), fill=(91, 100, 112))
# head
d.ellipse(sc(32, 14, 54, 36), fill=(107, 116, 130))
# ears
d.ellipse(sc(31, 6, 44, 20), fill=(125, 134, 149))
d.ellipse(sc(42, 6, 55, 20), fill=(125, 134, 149))
d.ellipse(sc(34, 9, 41, 16), fill=(201, 141, 166))
d.ellipse(sc(45, 9, 52, 16), fill=(201, 141, 166))
# eye
d.ellipse(sc(46, 21, 51, 26), fill=(20, 24, 30))
# nose
d.ellipse(sc(52, 24, 57, 29), fill=(192, 57, 43))
# whiskers
for y1, y2 in ((26, 22), (27, 27), (28, 33)):
    d.line(sc(53, y1, 63, y2), fill=(230, 230, 230), width=2)
# tail
d.line(sc(12, 40, 2, 54), fill=(91, 100, 112), width=4)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "silentrat.ico")
img.save(out, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64),
                                   (128, 128), (256, 256)])
print("Icon generated:", out)
