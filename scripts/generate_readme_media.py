"""Generate README preview media: animated GIFs + a hero composite.

Output goes to ``docs/``:
    docs/preview-idle.gif
    docs/preview-walk.gif
    docs/preview-sleep.gif
    docs/preview-all.gif       # all three side by side
    docs/hero.png              # pet + speech bubble in a tiny scene

Run after editing sprite sheets:

    python scripts/generate_readme_media.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "pets" / "claw" / "sprites"
DOCS = ROOT / "docs"

# ---- Visual scene -----------------------------------------------------------
SCALE = 4                # pixel-art scale-up factor for previews
SCENE_W = 320
SCENE_H = 180

SKY_TOP = (240, 235, 255, 255)      # very pale lavender
SKY_BOTTOM = (255, 245, 232, 255)   # warm cream
GROUND = (84, 60, 38, 255)          # dirt
GROUND_LINE = (40, 28, 18, 255)
GRASS = (110, 168, 96, 255)
SHADOW = (0, 0, 0, 60)

GROUND_HEIGHT = 28


def _make_scene() -> Image.Image:
    """Return a scene background (sky gradient + ground)."""
    img = Image.new("RGBA", (SCENE_W, SCENE_H), SKY_TOP)
    draw = ImageDraw.Draw(img)
    # vertical gradient
    for y in range(SCENE_H - GROUND_HEIGHT):
        t = y / max(1, (SCENE_H - GROUND_HEIGHT - 1))
        r = int(SKY_TOP[0] * (1 - t) + SKY_BOTTOM[0] * t)
        g = int(SKY_TOP[1] * (1 - t) + SKY_BOTTOM[1] * t)
        b = int(SKY_TOP[2] * (1 - t) + SKY_BOTTOM[2] * t)
        draw.line([(0, y), (SCENE_W, y)], fill=(r, g, b, 255))
    # ground
    draw.rectangle(
        [(0, SCENE_H - GROUND_HEIGHT), (SCENE_W, SCENE_H)], fill=GROUND
    )
    # grass strip
    draw.rectangle(
        [(0, SCENE_H - GROUND_HEIGHT), (SCENE_W, SCENE_H - GROUND_HEIGHT + 4)],
        fill=GRASS,
    )
    draw.line(
        [(0, SCENE_H - GROUND_HEIGHT + 4), (SCENE_W, SCENE_H - GROUND_HEIGHT + 4)],
        fill=GROUND_LINE,
    )
    return img


def _slice_sheet(sheet_path: Path, frame_count: int) -> list[Image.Image]:
    sheet = Image.open(sheet_path).convert("RGBA")
    fw = sheet.width // frame_count
    fh = sheet.height
    return [sheet.crop((i * fw, 0, (i + 1) * fw, fh)) for i in range(frame_count)]


def _scaled_frames(frames: list[Image.Image]) -> list[Image.Image]:
    return [
        f.resize((f.width * SCALE, f.height * SCALE), Image.NEAREST) for f in frames
    ]


def _composite_on_scene(
    frames: list[Image.Image], *, x_offset: int = 0
) -> list[Image.Image]:
    """Paste each frame on a fresh scene at the bottom-center, with a soft shadow."""
    out: list[Image.Image] = []
    for f in frames:
        scene = _make_scene()
        x = (SCENE_W - f.width) // 2 + x_offset
        y = SCENE_H - GROUND_HEIGHT - f.height + 4

        # Shadow (soft ellipse beneath the pet).
        shadow = Image.new("RGBA", scene.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sx = x + f.width // 2
        sy = SCENE_H - GROUND_HEIGHT + 7
        rx, ry = f.width // 2 - 6, 5
        sd.ellipse([(sx - rx, sy - ry), (sx + rx, sy + ry)], fill=SHADOW)
        shadow = shadow.filter(ImageFilter.GaussianBlur(2))
        scene = Image.alpha_composite(scene, shadow)

        layer = Image.new("RGBA", scene.size, (0, 0, 0, 0))
        layer.paste(f, (x, y), f)
        scene = Image.alpha_composite(scene, layer)
        out.append(scene)
    return out


def _save_gif(frames: list[Image.Image], path: Path, fps: float) -> None:
    """Save `frames` as an animated GIF at the given FPS.

    All frames are flattened to RGB and quantized against a SHARED palette
    derived from the first frame, so colors don't drift between frames.
    """
    duration_ms = int(round(1000 / fps))
    rgb_frames = [f.convert("RGB") for f in frames]
    # Build a shared palette from the first frame so every frame uses the same
    # color table (avoids the "frames flicker between palettes" GIF artifact).
    base = rgb_frames[0].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    pal_frames = [base] + [f.quantize(palette=base, dither=Image.Dither.NONE) for f in rgb_frames[1:]]
    pal_frames[0].save(
        path,
        save_all=True,
        append_images=pal_frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=False,
    )
    print(f"wrote {path} ({len(frames)} frames, {fps} fps)")


# ---- Speech bubble ----------------------------------------------------------
def _draw_speech_bubble(
    canvas: Image.Image, anchor: tuple[int, int], text: str
) -> None:
    """Draw a rounded white speech bubble with a tail above `anchor` (pet top-center)."""
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    pad_x, pad_y = 10, 6
    tail_h = 8
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    bw = text_w + 2 * pad_x
    bh = text_h + 2 * pad_y

    bx = anchor[0] - bw // 2
    by = anchor[1] - bh - tail_h - 4

    # Soft shadow
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [(bx + 2, by + 3), (bx + bw + 2, by + bh + 3)],
        radius=8,
        fill=(0, 0, 0, 60),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(2))
    canvas.alpha_composite(shadow)

    # Bubble body
    draw.rounded_rectangle(
        [(bx, by), (bx + bw, by + bh)],
        radius=8,
        fill=(255, 255, 255, 240),
        outline=(60, 60, 60, 220),
        width=1,
    )
    # Tail
    tail_cx = anchor[0]
    tail_top_y = by + bh
    tail_tip_y = tail_top_y + tail_h
    draw.polygon(
        [
            (tail_cx - 6, tail_top_y),
            (tail_cx, tail_tip_y),
            (tail_cx + 6, tail_top_y),
        ],
        fill=(255, 255, 255, 240),
        outline=(60, 60, 60, 220),
    )
    draw.text((bx + pad_x, by + pad_y - 2), text, fill=(30, 30, 30, 255), font=font)


# ---- Hero composite ---------------------------------------------------------
def _hero() -> Image.Image:
    # Wider and a bit taller than the inline GIFs so the speech bubble has headroom.
    hero_h = SCENE_H + 40
    scene = Image.new("RGBA", (SCENE_W * 2, hero_h), SKY_TOP)
    draw = ImageDraw.Draw(scene)
    for y in range(scene.height - GROUND_HEIGHT):
        t = y / max(1, scene.height - GROUND_HEIGHT - 1)
        r = int(SKY_TOP[0] * (1 - t) + SKY_BOTTOM[0] * t)
        g = int(SKY_TOP[1] * (1 - t) + SKY_BOTTOM[1] * t)
        b = int(SKY_TOP[2] * (1 - t) + SKY_BOTTOM[2] * t)
        draw.line([(0, y), (scene.width, y)], fill=(r, g, b, 255))
    draw.rectangle(
        [(0, scene.height - GROUND_HEIGHT), (scene.width, scene.height)], fill=GROUND
    )
    draw.rectangle(
        [(0, scene.height - GROUND_HEIGHT), (scene.width, scene.height - GROUND_HEIGHT + 4)],
        fill=GRASS,
    )

    # Pet (frame 0 of idle, scaled up)
    idle = _slice_sheet(SPRITES / "idle.png", 8)[0]
    pet = idle.resize((idle.width * SCALE, idle.height * SCALE), Image.NEAREST)
    px = scene.width // 2 - pet.width // 2 - 30
    py = scene.height - GROUND_HEIGHT - pet.height + 4

    # Shadow
    sh = Image.new("RGBA", scene.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sx, sy = px + pet.width // 2, scene.height - GROUND_HEIGHT + 7
    sd.ellipse([(sx - 30, sy - 5), (sx + 30, sy + 5)], fill=SHADOW)
    sh = sh.filter(ImageFilter.GaussianBlur(3))
    scene = Image.alpha_composite(scene, sh)

    layer = Image.new("RGBA", scene.size, (0, 0, 0, 0))
    layer.paste(pet, (px, py), pet)
    scene = Image.alpha_composite(scene, layer)

    # Speech bubble pointing at the top of the pet
    _draw_speech_bubble(scene, anchor=(px + pet.width // 2, py), text="Looking for treasure!")

    return scene


def _social_preview() -> Image.Image:
    """1280x640 banner — used for GitHub social preview / OpenGraph cards."""
    W, H = 1280, 640  # noqa: N806
    img = Image.new("RGBA", (W, H), SKY_TOP)
    draw = ImageDraw.Draw(img)

    # Sky gradient
    ground_h = 110
    for y in range(H - ground_h):
        t = y / max(1, H - ground_h - 1)
        r = int(SKY_TOP[0] * (1 - t) + SKY_BOTTOM[0] * t)
        g = int(SKY_TOP[1] * (1 - t) + SKY_BOTTOM[1] * t)
        b = int(SKY_TOP[2] * (1 - t) + SKY_BOTTOM[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))
    # Ground + grass strip
    draw.rectangle([(0, H - ground_h), (W, H)], fill=GROUND)
    draw.rectangle([(0, H - ground_h), (W, H - ground_h + 14)], fill=GRASS)
    draw.line([(0, H - ground_h + 14), (W, H - ground_h + 14)], fill=GROUND_LINE, width=2)

    # Decorative tufts of grass
    for x in range(20, W, 90):
        draw.line([(x, H - ground_h + 6), (x, H - ground_h - 4)], fill=GROUND_LINE, width=2)
        draw.line([(x + 2, H - ground_h + 6), (x + 4, H - ground_h - 6)], fill=GRASS, width=2)
        draw.line([(x - 2, H - ground_h + 6), (x - 4, H - ground_h - 4)], fill=GRASS, width=2)

    # Title + tagline (left side)
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 72)
        tagline_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
        meta_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Menlo.ttc", 22)
    except OSError:
        title_font = tagline_font = meta_font = ImageFont.load_default()

    title_color = (60, 40, 30, 255)
    accent = (180, 90, 40, 255)

    draw.text((60, 110), "openclaw", fill=title_color, font=title_font)
    draw.text((60, 184), "tamagotchi", fill=accent, font=title_font)
    draw.text(
        (60, 280),
        "A desktop pet that lives on top of every window.",
        fill=(70, 55, 45, 255),
        font=tagline_font,
    )
    draw.text(
        (60, 320),
        "PySide6 · pixel-art · cross-platform · open source",
        fill=(120, 100, 90, 255),
        font=tagline_font,
    )

    # Feature bullets
    bullets = [
        "▸ idle / walk / sleep state machine",
        "▸ mood-aware speech bubbles",
        "▸ drag, click, feed, persist",
        "▸ OpenClaw asset importer",
    ]
    for i, line in enumerate(bullets):
        draw.text(
            (60, 380 + i * 32), line, fill=(80, 65, 55, 255), font=meta_font
        )

    # Pet on the right side, scaled big
    idle = _slice_sheet(SPRITES / "idle.png", 8)[0]
    pet_scale = 8
    pet = idle.resize(
        (idle.width * pet_scale, idle.height * pet_scale), Image.NEAREST
    )
    px = W - pet.width - 140
    py = H - ground_h - pet.height + 14

    # Pet shadow
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sx, sy = px + pet.width // 2, H - ground_h + 16
    sd.ellipse([(sx - pet.width // 2 + 14, sy - 10), (sx + pet.width // 2 - 14, sy + 10)], fill=SHADOW)
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, sh)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.paste(pet, (px, py), pet)
    img = Image.alpha_composite(img, layer)

    # Speech bubble above the pet
    _draw_speech_bubble_big(img, anchor=(px + pet.width // 2, py), text="Looking for treasure!")
    return img


def _draw_speech_bubble_big(
    canvas: Image.Image, anchor: tuple[int, int], text: str
) -> None:
    """Larger speech bubble for the social preview banner."""
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    pad_x, pad_y = 22, 14
    tail_h = 16
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    bw = text_w + 2 * pad_x
    bh = text_h + 2 * pad_y
    bx = anchor[0] - bw // 2
    by = anchor[1] - bh - tail_h - 10

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [(bx + 4, by + 6), (bx + bw + 4, by + bh + 6)],
        radius=18,
        fill=(0, 0, 0, 70),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(5))
    canvas.alpha_composite(shadow)

    draw.rounded_rectangle(
        [(bx, by), (bx + bw, by + bh)],
        radius=18,
        fill=(255, 255, 255, 245),
        outline=(60, 60, 60, 230),
        width=2,
    )
    tail_cx = anchor[0]
    tail_top_y = by + bh
    tail_tip_y = tail_top_y + tail_h
    draw.polygon(
        [
            (tail_cx - 12, tail_top_y),
            (tail_cx, tail_tip_y),
            (tail_cx + 12, tail_top_y),
        ],
        fill=(255, 255, 255, 245),
        outline=(60, 60, 60, 230),
    )
    draw.text((bx + pad_x, by + pad_y - 4), text, fill=(30, 30, 30, 255), font=font)


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)

    # 1) idle/walk/sleep GIFs
    pairs = [
        ("idle", 8, 6.0),
        ("walk", 6, 12.0),
        ("sleep", 4, 3.0),
    ]
    composites: dict[str, list[Image.Image]] = {}
    for name, frame_count, fps in pairs:
        frames = _slice_sheet(SPRITES / f"{name}.png", frame_count)
        scaled = _scaled_frames(frames)
        comp = _composite_on_scene(scaled)
        composites[name] = comp
        _save_gif(comp, DOCS / f"preview-{name}.gif", fps=fps)

    # 2) Side-by-side "preview-all" GIF: pad shorter cycles by repeating to a common length.
    common_len = max(len(c) for c in composites.values())
    side_by_side: list[Image.Image] = []
    panel_w = SCENE_W
    panel_h = SCENE_H
    for i in range(common_len):
        canvas = Image.new("RGBA", (panel_w * 3, panel_h), (0, 0, 0, 0))
        for col, name in enumerate(["idle", "walk", "sleep"]):
            seq = composites[name]
            frame = seq[i % len(seq)]
            canvas.paste(frame, (col * panel_w, 0), frame)
        # Labels
        d = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
        except OSError:
            font = ImageFont.load_default()
        for col, label in enumerate(["IDLE", "WALK", "SLEEP"]):
            d.text((col * panel_w + 8, 8), label, fill=(40, 30, 30, 255), font=font)
        side_by_side.append(canvas)
    _save_gif(side_by_side, DOCS / "preview-all.gif", fps=8.0)

    # 3) Hero composite
    hero = _hero()
    hero_path = DOCS / "hero.png"
    hero.save(hero_path)
    print(f"wrote {hero_path} ({hero.size[0]}x{hero.size[1]})")

    # 4) Social preview banner (1280x640, GitHub OG card)
    social = _social_preview()
    social_path = DOCS / "social-preview.png"
    social.convert("RGB").save(social_path, optimize=True)
    print(f"wrote {social_path} ({social.size[0]}x{social.size[1]})")


if __name__ == "__main__":
    main()
