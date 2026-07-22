import unittest
from unittest.mock import patch

from codex_meter import icon


class IconTests(unittest.TestCase):
    def test_tray_icon_fills_height_without_background_disc(self):
        image = icon._render_icon((0, 0, 0, 255), icon._GLYPH_FRACTION_TRAY)

        alpha = image.getchannel("A")
        bbox = alpha.getbbox()

        self.assertIsNotNone(bbox)
        self.assertIn(bbox[2] - bbox[0], range(125, 129))
        self.assertIn(bbox[3] - bbox[1], range(121, 125))
        opaque_pixels = sum(value >= 128 for value in alpha.get_flattened_data())
        self.assertLess(opaque_pixels, image.width * image.height * 0.6)

    def test_windows_light_theme_uses_black_ink(self):
        with patch.object(icon.sys, "platform", "win32"), patch.object(
            icon, "_is_light_theme", return_value=True
        ):
            image = icon.get_icon()

        opaque_colors = {
            pixel[:3] for pixel in image.get_flattened_data() if pixel[3] >= 250
        }
        self.assertEqual(opaque_colors, {(0, 0, 0)})

    def test_windows_dark_theme_uses_white_ink(self):
        with patch.object(icon.sys, "platform", "win32"), patch.object(
            icon, "_is_light_theme", return_value=False
        ):
            image = icon.get_icon()

        opaque_colors = {
            pixel[:3] for pixel in image.get_flattened_data() if pixel[3] >= 250
        }
        self.assertEqual(opaque_colors, {(255, 255, 255)})


if __name__ == "__main__":
    unittest.main()
