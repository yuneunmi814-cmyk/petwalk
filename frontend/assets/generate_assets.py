"""Generate PetWalk app icon + splash source images (a paw in the brand green).

Run:  ../../backend/.venv/bin/python generate_assets.py
Then: npx @capacitor/assets generate   (produces all iOS/Android sizes)
"""

from PIL import Image, ImageDraw, ImageFont

GREEN = (21, 163, 74)        # --primary #15a34a
GREEN_DARK = (15, 26, 20)    # dark splash bg
LIGHT = (244, 247, 244)      # --bg #f4f7f4
WHITE = (255, 255, 255)

# Paw, defined as ellipses relative to a center point (4 toes + 1 pad).
_PAW = [
    (-170, -142, -60, 2),
    (-95, -192, 15, -48),
    (-15, -192, 95, -48),
    (60, -142, 170, 2),
    (-130, -50, 130, 190),
]


def draw_paw(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, fill) -> None:
    for x0, y0, x1, y1 in _PAW:
        d.ellipse([cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s], fill=fill)


def _font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def icon_only() -> Image.Image:
    img = Image.new("RGBA", (1024, 1024), (*GREEN, 255))
    draw_paw(ImageDraw.Draw(img), 512, 512, 1.85, WHITE)
    return img


def icon_foreground() -> Image.Image:
    # Transparent bg; paw kept within the adaptive-icon safe zone (smaller scale).
    img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw_paw(ImageDraw.Draw(img), 512, 512, 1.45, WHITE)
    return img


def icon_background() -> Image.Image:
    return Image.new("RGBA", (1024, 1024), (*GREEN, 255))


def splash(bg, paw_fill) -> Image.Image:
    img = Image.new("RGBA", (2732, 2732), (*bg, 255))
    d = ImageDraw.Draw(img)
    draw_paw(d, 1366, 1230, 4.0, paw_fill)
    text = "PetWalk"
    font = _font(220)
    w = d.textlength(text, font=font)
    d.text((1366 - w / 2, 1760), text, font=font, fill=paw_fill)
    return img


def main() -> None:
    icon_only().save("icon-only.png")
    icon_foreground().save("icon-foreground.png")
    icon_background().save("icon-background.png")
    splash(LIGHT, GREEN).save("splash.png")
    splash(GREEN_DARK, WHITE).save("splash-dark.png")
    print("wrote: icon-only.png, icon-foreground.png, icon-background.png, splash.png, splash-dark.png")


if __name__ == "__main__":
    main()
