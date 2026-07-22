"""Monochrome ChatGPT tray icon with platform-native theme handling."""

import logging
import os
import subprocess
import sys

from PIL import Image, ImageChops, ImageOps

logger = logging.getLogger(__name__)

_RENDER_SIZE = 128
_GLYPH_FRACTION = 0.80
_GLYPH_FRACTION_TRAY = 1.0
_TEMPLATE_INK = (0, 0, 0, 255)


def _icon_path() -> str:
    project_root = os.path.dirname(os.path.dirname(__file__))
    candidates = (
        os.path.join(project_root, "favicon.ico"),
        os.path.join(sys.prefix, "share", "codex-meter", "favicon.ico"),
    )
    path = next((candidate for candidate in candidates if os.path.isfile(candidate)), None)
    if path is None:
        raise FileNotFoundError("The bundled ChatGPT tray icon is missing.")
    return path


def _source_mask() -> Image.Image:
    with Image.open(_icon_path()) as source:
        source.seek(getattr(source, "n_frames", 1) - 1)
        rgba = source.convert("RGBA")

    # The official favicon is a white disc with a black Blossom. Inverted
    # luminance extracts only the Blossom strokes and discards the background.
    alpha = rgba.getchannel("A")
    blossom = ImageOps.invert(ImageOps.grayscale(rgba))
    return ImageChops.multiply(alpha, blossom)


def _render_icon(ink, fraction: float) -> Image.Image:
    mask = _source_mask()
    bbox = mask.getbbox()
    if not bbox:
        return Image.new("RGBA", (_RENDER_SIZE, _RENDER_SIZE), (0, 0, 0, 0))
    mask = mask.crop(bbox)
    target = _RENDER_SIZE * fraction
    factor = target / max(mask.width, mask.height)
    width = max(1, round(mask.width * factor))
    height = max(1, round(mask.height * factor))
    mask = mask.resize((width, height), Image.Resampling.LANCZOS)

    glyph = Image.new("RGBA", (width, height), tuple(ink[:3]) + (0,))
    glyph.putalpha(mask)
    canvas = Image.new("RGBA", (_RENDER_SIZE, _RENDER_SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(
        glyph,
        ((_RENDER_SIZE - width) // 2, (_RENDER_SIZE - height) // 2),
    )
    return canvas


def get_icon() -> Image.Image:
    if sys.platform == "darwin":
        return _render_icon(_TEMPLATE_INK, _GLYPH_FRACTION)
    ink = (0, 0, 0, 255) if _is_light_theme() else (255, 255, 255, 255)
    return _render_icon(ink, _GLYPH_FRACTION_TRAY)


def apply_macos_template(tray_icon) -> None:
    if sys.platform != "darwin":
        return
    try:
        button = tray_icon._status_item.button()
        image = button.image()
        if image is not None:
            image.setTemplate_(True)
            button.setImage_(image)
    except Exception:
        logger.debug("Could not flag tray image as a template", exc_info=True)


def _is_light_theme() -> bool:
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.stdout.strip() != "Dark"
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("Theme detection failed: %s", exc)
            return False
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                0,
                winreg.KEY_READ,
            ) as key:
                value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
                return value == 1
        except OSError as exc:
            logger.debug("Theme detection failed: %s", exc)
            return False
    return False
