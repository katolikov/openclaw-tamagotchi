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
    pal_frames = [base] + [
        f.quantize(palette=base, dither=Image.Dither.NONE) for f in rgb_frames[1:]
    ]
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
    # 3x SCENE_W gives room for all three pets without clipping.
    hero_h = SCENE_H + 40
    scene = Image.new("RGBA", (SCENE_W * 3, hero_h), SKY_TOP)
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

    # Speech bubble pointing at the top of the (claw) pet
    _draw_speech_bubble(scene, anchor=(px + pet.width // 2, py), text="Looking for treasure!")

    # Add Shamil and Alegra to the right of Claw so the hero shows the lineup.
    extras = [
        (ROOT / "pets" / "rabbit"    / "sprites" / "idle.png", "Shamil"),
        (ROOT / "pets" / "dachshund" / "sprites" / "idle.png", "Alegra"),
    ]
    cur_x = px + pet.width + 50
    for sheet_path, _label in extras:
        epx = _slice_sheet(sheet_path, 8)[0]
        epx_scaled = epx.resize((epx.width * SCALE, epx.height * SCALE), Image.NEAREST)
        epy = scene.height - GROUND_HEIGHT - epx_scaled.height + 4

        sh = Image.new("RGBA", scene.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sx, sy = cur_x + epx_scaled.width // 2, scene.height - GROUND_HEIGHT + 7
        sd.ellipse([(sx - 30, sy - 5), (sx + 30, sy + 5)], fill=SHADOW)
        sh = sh.filter(ImageFilter.GaussianBlur(3))
        scene = Image.alpha_composite(scene, sh)

        layer = Image.new("RGBA", scene.size, (0, 0, 0, 0))
        layer.paste(epx_scaled, (cur_x, epy), epx_scaled)
        scene = Image.alpha_composite(scene, layer)
        cur_x += epx_scaled.width + 30

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

    # All three pets on the right side, scaled big.
    pets = [
        (ROOT / "pets" / "claw"      / "sprites" / "idle.png", "Claw"),
        (ROOT / "pets" / "rabbit"    / "sprites" / "idle.png", "Shamil"),
        (ROOT / "pets" / "dachshund" / "sprites" / "idle.png", "Alegra"),
    ]
    pet_scale = 6
    pet_imgs: list[tuple[Image.Image, str]] = [
        (
            _slice_sheet(p, 8)[0].resize(
                (
                    _slice_sheet(p, 8)[0].width * pet_scale,
                    _slice_sheet(p, 8)[0].height * pet_scale,
                ),
                Image.NEAREST,
            ),
            label,
        )
        for p, label in pets
    ]

    # Layout the pets in a row on the right half of the banner.
    right_half_x = 700
    available_w = W - right_half_x - 60
    spacing = available_w // len(pet_imgs)
    try:
        small_label_font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf", 18
        )
    except OSError:
        small_label_font = ImageFont.load_default()

    for i, (pet_img, label) in enumerate(pet_imgs):
        cx = right_half_x + spacing // 2 + i * spacing
        px = cx - pet_img.width // 2
        py = H - ground_h - pet_img.height + 14

        # Shadow
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sx, sy = cx, H - ground_h + 12
        sd.ellipse(
            [(sx - pet_img.width // 3, sy - 7), (sx + pet_img.width // 3, sy + 7)],
            fill=SHADOW,
        )
        sh = sh.filter(ImageFilter.GaussianBlur(4))
        img = Image.alpha_composite(img, sh)

        # Pet
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        layer.paste(pet_img, (px, py), pet_img)
        img = Image.alpha_composite(img, layer)

        # Pet name underneath
        d2 = ImageDraw.Draw(img)
        bbox = d2.textbbox((0, 0), label, font=small_label_font)
        text_w = bbox[2] - bbox[0]
        d2.text(
            (cx - text_w // 2, H - ground_h + 28),
            label,
            fill=(240, 230, 220, 255),
            font=small_label_font,
        )

    # Speech bubble above the centre pet
    centre_pet_img, _ = pet_imgs[len(pet_imgs) // 2]
    centre_cx = right_half_x + spacing + spacing // 2
    centre_py = H - ground_h - centre_pet_img.height + 14
    _draw_speech_bubble_big(
        img, anchor=(centre_cx, centre_py), text="Looking for treasure!"
    )
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


def _pet_lineup_gif() -> list[Image.Image]:
    """Render a side-by-side animation of all three pets idling on one ground.

    Returns a list of frames (RGBA) ready to feed to _save_gif().
    """
    pet_dirs = [
        ("Claw",   ROOT / "pets" / "claw"      / "sprites" / "idle.png", 8),
        ("Shamil", ROOT / "pets" / "rabbit"    / "sprites" / "idle.png", 8),
        ("Alegra", ROOT / "pets" / "dachshund" / "sprites" / "idle.png", 8),
    ]
    panel_w, panel_h = 200, SCENE_H
    n = 8  # all idle sheets have 8 frames
    out: list[Image.Image] = []
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    # Pre-slice sprites once.
    pet_frames: list[list[Image.Image]] = []
    for _, p, count in pet_dirs:
        frames = _slice_sheet(p, count)
        scaled = [
            f.resize((f.width * SCALE, f.height * SCALE), Image.NEAREST) for f in frames
        ]
        pet_frames.append(scaled)

    for i in range(n):
        canvas = Image.new("RGBA", (panel_w * 3, panel_h), (0, 0, 0, 0))
        for col, ((label, _, _), frames) in enumerate(
            zip(pet_dirs, pet_frames, strict=True)
        ):
            scene = Image.new("RGBA", (panel_w, panel_h), SKY_TOP)
            d = ImageDraw.Draw(scene)
            for y in range(panel_h - GROUND_HEIGHT):
                t = y / max(1, panel_h - GROUND_HEIGHT - 1)
                r = int(SKY_TOP[0] * (1 - t) + SKY_BOTTOM[0] * t)
                g = int(SKY_TOP[1] * (1 - t) + SKY_BOTTOM[1] * t)
                b = int(SKY_TOP[2] * (1 - t) + SKY_BOTTOM[2] * t)
                d.line([(0, y), (panel_w, y)], fill=(r, g, b, 255))
            d.rectangle([(0, panel_h - GROUND_HEIGHT), (panel_w, panel_h)], fill=GROUND)
            d.rectangle(
                [(0, panel_h - GROUND_HEIGHT), (panel_w, panel_h - GROUND_HEIGHT + 4)],
                fill=GRASS,
            )
            f = frames[i % len(frames)]
            x = (panel_w - f.width) // 2
            y = panel_h - GROUND_HEIGHT - f.height + 4
            scene.alpha_composite(f, (x, y))
            d.text((8, 8), label, fill=(40, 30, 30, 255), font=font)
            canvas.paste(scene, (col * panel_w, 0), scene)
        out.append(canvas)
    return out


def _state_lineup_gif(state: str, frame_count: int) -> list[Image.Image]:
    """All three pets performing the same animation, side-by-side."""
    pet_dirs = [
        ("Claw",   ROOT / "pets" / "claw"      / "sprites" / f"{state}.png"),
        ("Shamil", ROOT / "pets" / "rabbit"    / "sprites" / f"{state}.png"),
        ("Alegra", ROOT / "pets" / "dachshund" / "sprites" / f"{state}.png"),
    ]
    panel_w, panel_h = 200, SCENE_H
    pet_frames = [
        [
            f.resize((f.width * SCALE, f.height * SCALE), Image.NEAREST)
            for f in _slice_sheet(p, frame_count)
        ]
        for _, p in pet_dirs
    ]
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    out: list[Image.Image] = []
    for i in range(frame_count):
        canvas = Image.new("RGBA", (panel_w * 3, panel_h), (0, 0, 0, 0))
        for col, ((label, _), frames) in enumerate(
            zip(pet_dirs, pet_frames, strict=True)
        ):
            scene = Image.new("RGBA", (panel_w, panel_h), SKY_TOP)
            d = ImageDraw.Draw(scene)
            for y in range(panel_h - GROUND_HEIGHT):
                t = y / max(1, panel_h - GROUND_HEIGHT - 1)
                r = int(SKY_TOP[0] * (1 - t) + SKY_BOTTOM[0] * t)
                g = int(SKY_TOP[1] * (1 - t) + SKY_BOTTOM[1] * t)
                b = int(SKY_TOP[2] * (1 - t) + SKY_BOTTOM[2] * t)
                d.line([(0, y), (panel_w, y)], fill=(r, g, b, 255))
            d.rectangle(
                [(0, panel_h - GROUND_HEIGHT), (panel_w, panel_h)], fill=GROUND
            )
            d.rectangle(
                [(0, panel_h - GROUND_HEIGHT), (panel_w, panel_h - GROUND_HEIGHT + 4)],
                fill=GRASS,
            )
            f = frames[i % len(frames)]
            x = (panel_w - f.width) // 2
            y = panel_h - GROUND_HEIGHT - f.height + 4
            scene.alpha_composite(f, (x, y))
            d.text((8, 8), label, fill=(40, 30, 30, 255), font=font)
            canvas.paste(scene, (col * panel_w, 0), scene)
        out.append(canvas)
    return out


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)

    # 1) idle/walk/sleep GIFs — all three pets side-by-side per state.
    pairs = [
        ("idle", 8, 6.0),
        ("walk", 6, 12.0),
        ("sleep", 4, 3.0),
    ]
    for name, frame_count, fps in pairs:
        frames = _state_lineup_gif(name, frame_count)
        _save_gif(frames, DOCS / f"preview-{name}.gif", fps=fps)

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

    # 5) Per-pet idle GIFs + lineup GIF
    for pet_name, frame_count, fps in [
        ("claw", 8, 6.0),
        ("rabbit", 8, 6.0),
        ("dachshund", 8, 5.0),
    ]:
        sheet_path = ROOT / "pets" / pet_name / "sprites" / "idle.png"
        frames = _slice_sheet(sheet_path, frame_count)
        scaled = _scaled_frames(frames)
        comp = _composite_on_scene(scaled)
        _save_gif(comp, DOCS / f"pet-{pet_name}.gif", fps=fps)

    # All three pets idling side-by-side on one ground line.
    lineup = _pet_lineup_gif()
    _save_gif(lineup, DOCS / "pets-lineup.gif", fps=6.0)


if __name__ == "__main__":
    main()
