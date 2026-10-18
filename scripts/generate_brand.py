"""Generate the integration icon (Pillow only)."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "custom_components" / "haunted_house" / "brand"


def ghost(size):
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 5, fill=(32, 24, 56, 255))
    x0, x1, top, bottom = s * .22, s * .78, s * .16, s * .82
    d.ellipse((x0, top, x1, top + (x1 - x0)), fill=(245, 245, 255, 255))
    d.rectangle((x0, top + (x1 - x0) / 2, x1, bottom - s * .06), fill=(245, 245, 255, 255))
    n = 3
    w = (x1 - x0) / n
    for i in range(n):
        d.ellipse((x0 + i * w, bottom - s * .12, x0 + (i + 1) * w, bottom), fill=(245, 245, 255, 255))
    d.polygon([(x0, bottom - s * .06), (x1, bottom - s * .06), (x1, bottom - s * .03), (x0, bottom - s * .03)],
              fill=(245, 245, 255, 255))
    for cx in (.40, .60):
        d.ellipse((s * cx - s * .04, s * .40, s * cx + s * .04, s * .50), fill=(32, 24, 56, 255))
    d.ellipse((s * .46, s * .54, s * .54, s * .64), fill=(32, 24, 56, 255))
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    ghost(256).save(OUT / "icon.png")
    ghost(512).save(OUT / "icon@2x.png")
