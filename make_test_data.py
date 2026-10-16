"""Create synthetic test images + ZIPs (small/medium/large) for load testing.
Usage: python make_test_data.py   -> writes ./test_data/"""
import os
import random
import zipfile

from PIL import Image, ImageDraw

os.makedirs("test_data/images", exist_ok=True)


def make_image(path, size=(640, 480)):
    img = Image.new("RGB", size, tuple(random.randint(0, 255) for _ in range(3)))
    d = ImageDraw.Draw(img)
    for _ in range(12):
        x0, y0 = random.randint(0, size[0] - 50), random.randint(0, size[1] - 50)
        d.ellipse(
            [x0, y0, x0 + random.randint(40, 200), y0 + random.randint(40, 200)],
            fill=tuple(random.randint(0, 255) for _ in range(3)),
        )
    img.save(path)


paths = []
for i in range(60):
    p = f"test_data/images/img_{i:03d}.jpg"
    make_image(p)
    paths.append(p)

for name, n in [("bulk_5.zip", 5), ("bulk_20.zip", 20), ("bulk_50.zip", 50)]:
    with zipfile.ZipFile(f"test_data/{name}", "w") as z:
        for p in paths[:n]:
            z.write(p, os.path.basename(p))
print("Wrote test_data/ (single images + bulk_5/20/50.zip)")
