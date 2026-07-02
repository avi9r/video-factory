"""Text overlays and title cards."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from lib.thumbnail import _get_font, _hex_to_rgb, _wrap_text


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
) -> str:
    w, h = 1920, 1080
    bg = _hex_to_rgb(channel_config.get("color_scheme", {}).get("background", "#0A0A0F"))
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    font = _get_font(72)
    accent = _hex_to_rgb(channel_config.get("color_scheme", {}).get("primary", "#8B5CF6"))
    lines = _wrap_text(text, font, int(w * 0.8), draw)
    y = (h - len(lines) * 82) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2
        draw.text((x, y), line, font=font, fill=accent)
        y += 82
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


def create_intro_card(channel_config: dict, output_path: str) -> str:
    name = channel_config.get("name", "Channel")
    intro = channel_config.get("script", {}).get("intro_text", name)
    return create_title_card(intro, channel_config, output_path, duration_seconds=3)
