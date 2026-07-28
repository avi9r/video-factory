"""Text overlays and title cards."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from lib.thumbnail import _get_font, _hex_to_rgb, _wrap_text

_ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")


def _roman(n: int) -> str:
    if 0 < n < len(_ROMAN):
        return _ROMAN[n]
    return str(n)


def _gradient_background(w: int, h: int, channel_config: dict) -> Image.Image:
    """Fallback cinematic gradient when no topic image is available."""
    top = _hex_to_rgb(channel_config.get("color_scheme", {}).get("background", "#0A0A0F"))
    bottom = _hex_to_rgb(channel_config.get("color_scheme", {}).get("primary", "#8B5CF6"))
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t * 0.35) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)
    return img.convert("RGBA")


def _load_topic_background(
    background_image: str | None,
    channel_config: dict,
    size: tuple[int, int] = (1920, 1080),
) -> Image.Image:
    w, h = size
    if background_image and Path(background_image).exists():
        bg = Image.open(background_image).convert("RGB").resize((w, h), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(14))
        canvas = bg.convert("RGBA")
        tint = _hex_to_rgb(channel_config.get("color_scheme", {}).get("background", "#0B1020"))
        overlay = Image.new("RGBA", (w, h), tint + (175,))
        canvas = Image.alpha_composite(canvas, overlay)
    else:
        canvas = _gradient_background(w, h, channel_config)

    return _cinematic_vignette(canvas, channel_config)


def _cinematic_vignette(img: Image.Image, channel_config: dict) -> Image.Image:
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bg_rgb = _hex_to_rgb(channel_config.get("color_scheme", {}).get("background", "#0B1020"))
    for i in range(140):
        alpha = int(200 * (1 - i / 140))
        draw.rectangle([0, i, w, i + 1], fill=bg_rgb + (alpha,))
        draw.rectangle([0, h - i - 1, w, h - i], fill=bg_rgb + (alpha,))
    for i in range(100):
        alpha = int(140 * (1 - i / 100))
        draw.rectangle([i, 0, i + 1, h], fill=bg_rgb + (alpha,))
        draw.rectangle([w - i - 1, 0, w - i, h], fill=bg_rgb + (alpha,))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def create_act_title_card(
    act_title: str,
    channel_config: dict,
    output_path: str,
    *,
    act_number: int = 1,
    background_image: str | None = None,
) -> str:
    """Cinematic act transition card with topic imagery, act label, and title."""
    w, h = 1920, 1080
    primary = _hex_to_rgb(channel_config.get("color_scheme", {}).get("primary", "#F59E0B"))
    accent = _hex_to_rgb(channel_config.get("color_scheme", {}).get("accent", "#FBBF24"))
    text_color = _hex_to_rgb(channel_config.get("color_scheme", {}).get("text", "#FFFFFF"))

    canvas = _load_topic_background(background_image, channel_config, (w, h))
    draw = ImageDraw.Draw(canvas)

    # Accent bars framing the title block
    center_y = h // 2
    bar_w = 420
    draw.rectangle(
        [w // 2 - bar_w, center_y - 118, w // 2 + bar_w, center_y - 115],
        fill=accent + (255,),
    )
    draw.rectangle(
        [w // 2 - bar_w, center_y + 115, w // 2 + bar_w, center_y + 118],
        fill=primary + (255,),
    )

    label_font = _get_font(32)
    label = f"ACT {_roman(act_number)}"
    lb = draw.textbbox((0, 0), label, font=label_font)
    lw = lb[2] - lb[0]
    draw.text(
        ((w - lw) // 2, center_y - 95),
        label,
        font=label_font,
        fill=accent + (230,),
    )

    title_font = _get_font(76)
    lines = _wrap_text(act_title.strip(), title_font, int(w * 0.72), draw)
    line_h = 86
    total_h = len(lines) * line_h
    y = center_y - total_h // 2 + 10
    for line in lines:
        tb = draw.textbbox((0, 0), line, font=title_font)
        tw = tb[2] - tb[0]
        x = (w - tw) // 2
        draw.text((x + 3, y + 3), line, font=title_font, fill=(0, 0, 0, 160))
        draw.text((x, y), line, font=title_font, fill=text_color + (255,))
        y += line_h

    # Bottom channel accent strip
    draw.rectangle([0, h - 5, w, h], fill=primary + (255,))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, "PNG")
    return output_path


def add_lower_third(
    image_path: str,
    text: str,
    channel_config: dict,
    output_path: str,
) -> str:
    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    primary = _hex_to_rgb(channel_config.get("color_scheme", {}).get("primary", "#8B5CF6"))
    bar_height = 60
    bar = Image.new("RGBA", (img.width, bar_height), primary + (200,))
    img.paste(bar, (0, img.height - bar_height), bar)
    font = _get_font(28)
    draw.text((20, img.height - bar_height + 15), text, font=font, fill=(255, 255, 255, 255))
    img.convert("RGB").save(output_path, "PNG")
    return output_path


def create_title_card(
    text: str,
    channel_config: dict,
    output_path: str,
    duration_seconds: int = 3,
    *,
    background_image: str | None = None,
) -> str:
    """Simple centered title — used for intro/outro when no act styling needed."""
    w, h = 1920, 1080
    canvas = _load_topic_background(background_image, channel_config, (w, h))
    draw = ImageDraw.Draw(canvas)
    font = _get_font(72)
    accent = _hex_to_rgb(channel_config.get("color_scheme", {}).get("primary", "#8B5CF6"))
    text_color = _hex_to_rgb(channel_config.get("color_scheme", {}).get("text", "#FFFFFF"))
    lines = _wrap_text(text, font, int(w * 0.8), draw)
    y = (h - len(lines) * 82) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 140))
        draw.text((x, y), line, font=font, fill=text_color + (255,))
        y += 82
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, "PNG")
    return output_path


def create_intro_card(
    channel_config: dict,
    output_path: str,
    *,
    background_image: str | None = None,
) -> str:
    name = channel_config.get("name", "Channel")
    intro = channel_config.get("script", {}).get("intro_text", name)
    return create_title_card(
        intro, channel_config, output_path, duration_seconds=3, background_image=background_image
    )
