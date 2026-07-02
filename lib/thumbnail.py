"""Thumbnail generation with Pillow templates."""

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from lib.image import generate_scene_image


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] thumbnail: {msg}")


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _get_font(size: int, font_name: str = "Montserrat-Bold") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        f"/System/Library/Fonts/Supplemental/{font_name}.ttf",
        f"/Library/Fonts/{font_name}.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def render_text_on_image(
    image_path: str,
    text: str,
    output_path: str,
    font_size: int = 72,
    color: str = "#FFFFFF",
    position: str = "center",
    max_width_percent: float = 0.8,
) -> str:
    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    font = _get_font(font_size)
    max_width = int(img.width * max_width_percent)
    lines = _wrap_text(text, font, max_width, draw)
    line_height = font_size + 10
    total_height = len(lines) * line_height
    if position == "center":
        y = (img.height - total_height) // 2
    elif position == "left":
        y = img.height // 3
    else:
        y = 40
    rgb = _hex_to_rgb(color)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = 40 if position == "left" else (img.width - tw) // 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font, fill=rgb + (255,))
        y += line_height
    img.convert("RGB").save(output_path, "PNG")
    return output_path


def _wrap_text(text: str, font, max_width: int, draw) -> list[str]:
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines or [text]


def add_channel_branding(image_path: str, channel_config: dict, output_path: str) -> str:
    img = Image.open(image_path).convert("RGBA")
    accent = _hex_to_rgb(channel_config.get("color_scheme", {}).get("accent", "#8B5CF6"))
    bar = Image.new("RGBA", (img.width, 8), accent + (255,))
    img.paste(bar, (0, img.height - 8), bar)
    img.convert("RGB").save(output_path, "PNG")
    return output_path


def _apply_dark_impact(img: Image.Image, title: str, channel_config: dict) -> Image.Image:
    w, h = img.size
    left = Image.new("RGBA", (w // 2, h), (10, 10, 15, 230))
    right = img.crop((w // 2, 0, w, h)).filter(ImageFilter.GaussianBlur(8))
    canvas = Image.new("RGBA", (w, h))
    canvas.paste(right, (w // 2, 0))
    canvas.paste(left, (0, 0), left)
    draw = ImageDraw.Draw(canvas)
    font = _get_font(64)
    color = channel_config.get("thumbnail", {}).get("title_color", "#FFFFFF")
    lines = _wrap_text(title, font, w // 2 - 60, draw)
    y = h // 3
    for line in lines:
        draw.text((40, y), line, font=font, fill=_hex_to_rgb(color) + (255,))
        y += 74
    return canvas


def _render_split_screen(
    bg_image: Image.Image,
    title: str,
    channel_config: dict,
    size: tuple[int, int] = (1280, 720),
) -> Image.Image:
    bg = _hex_to_rgb(channel_config.get("color_scheme", {}).get("background", "#0A0A0F"))
    primary = _hex_to_rgb(channel_config.get("color_scheme", {}).get("primary", "#8B5CF6"))
    title_color = channel_config.get("thumbnail", {}).get("title_color", "#FFFFFF")

    result = Image.new("RGB", size, bg)
    ai_img = bg_image.resize((size[0] // 2, size[1]))
    result.paste(ai_img, (size[0] // 2, 0))

    draw = ImageDraw.Draw(result)
    draw.rectangle(
        [(size[0] // 2 - 3, 0), (size[0] // 2 + 3, size[1])],
        fill=primary,
    )

    font = _get_font(56)
    max_width = size[0] // 2 - 80
    lines = _wrap_text(title, font, max_width, draw)
    line_height = 66
    total_height = len(lines) * line_height
    y = (size[1] - total_height) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (size[0] // 2 - tw) // 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=_hex_to_rgb(title_color))
        y += line_height

    return result.convert("RGBA")


def _apply_clean_impact(img: Image.Image, title: str, channel_config: dict) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 100))
    canvas = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(canvas)
    font = _get_font(72)
    color = channel_config.get("thumbnail", {}).get("title_color", "#FFFFFF")
    lines = _wrap_text(title, font, int(img.width * 0.8), draw)
    y = (img.height - len(lines) * 82) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (img.width - tw) // 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), line, font=font, fill=_hex_to_rgb(color) + (255,))
        y += 82
    return canvas


def generate_thumbnail(
    title: str,
    channel_config: dict,
    output_path: str,
    template: str | None = None,
) -> str:
    template = template or channel_config.get("thumbnail", {}).get("template", "dark_impact")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _log(f"Generating thumbnail: {title[:40]}...")

    bg_style = channel_config.get("thumbnail", {}).get("background_style", "cinematic")
    bg_path = out.parent / "thumbnail_bg.png"
    generate_scene_image(bg_style, channel_config, str(bg_path))
    img = Image.open(bg_path).convert("RGBA").resize((1280, 720), Image.LANCZOS)

    if template == "clean_impact":
        result = _apply_clean_impact(img, title, channel_config)
    elif template == "split_screen":
        result = _render_split_screen(img, title, channel_config)
    else:
        result = _apply_dark_impact(img, title, channel_config)

    result.convert("RGB").save(out, "PNG")
    add_channel_branding(str(out), channel_config, str(out))
    return str(out)
