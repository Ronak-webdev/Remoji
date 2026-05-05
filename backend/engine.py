import os
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import pillow_avif
from scipy.spatial import KDTree


class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        self.emoji_rgb = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        self.tree = KDTree(self.emoji_rgb)

        # Directory of pre-downloaded emoji PNGs (Twemoji 72x72)
        self.png_dir = os.path.join(os.path.dirname(__file__), "emoji_pngs")

        # Precompute filename for every emoji so we don't do it per-pixel
        self.emoji_filenames = [self._emoji_to_filename(e) for e in self.emojis]

        # LRU-style image cache (keep up to 1024 resized sprites)
        self._sprite_cache = {}
        self._cache_size_limit = 1024

        # Font fallback (kept for text-only mode if PNGs unavailable)
        self._font_path = self._find_font()
        print(f"PNG dir: {self.png_dir} | exists: {os.path.exists(self.png_dir)}")
        if os.path.exists(self.png_dir):
            print(f"  Sample PNGs: {os.listdir(self.png_dir)[:5]}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _emoji_to_filename(emoji_char):
        """Match Twemoji naming: hex codepoints (without FE0F) joined by '-'."""
        parts = []
        for ch in emoji_char:
            cp = ord(ch)
            if cp == 0xFE0F:  # variation selector-16 – skip
                continue
            parts.append(format(cp, 'x'))
        return '-'.join(parts)

    def _find_font(self):
        local = os.path.join(os.path.dirname(__file__), "NotoColorEmoji.ttf")
        if os.path.exists(local):
            return local
        return None

    def _get_sprite(self, emoji_index, size):
        """Return a PIL Image (RGBA) for the emoji at `size`×`size`."""
        key = (emoji_index, size)
        if key in self._sprite_cache:
            return self._sprite_cache[key]

        filename = self.emoji_filenames[emoji_index]
        png_path = os.path.join(self.png_dir, f"{filename}.png")

        if os.path.exists(png_path):
            try:
                img = Image.open(png_path).convert("RGBA")
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                if len(self._sprite_cache) >= self._cache_size_limit:
                    # Evict oldest entry
                    self._sprite_cache.pop(next(iter(self._sprite_cache)))
                self._sprite_cache[key] = img
                return img
            except Exception as e:
                print(f"  Sprite load error {filename}: {e}")

        # Fallback: solid color square matching the emoji's representative color
        color = tuple((self.emoji_rgb[emoji_index] * 255).astype(np.uint8)) + (255,)
        img = Image.new("RGBA", (size, size), color)
        self._sprite_cache[key] = img
        return img

    def get_best_emoji_index(self, rgb):
        rgb_norm = np.array(rgb, dtype=np.float32) / 255.0
        _, index = self.tree.query(rgb_norm)
        return int(index)

    # ------------------------------------------------------------------
    # Main mosaic generator
    # ------------------------------------------------------------------

    def create_mosaic(self, input_path, output_path, config):
        quality    = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))

        print(f"--- Starting mosaic creation: quality={quality}, size={emoji_size} ---")

        img = Image.open(input_path).convert('RGB')
        w, h = img.size

        target_cols     = 20 + (quality * 20)
        analysis_window = max(1, w // target_cols)
        cols = w // analysis_window
        rows = h // analysis_window

        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        img_small = ImageEnhance.Contrast(img_small).enhance(1.1)
        pixels    = np.array(img_small)
        del img_small

        out_w = cols * emoji_size
        out_h = rows * emoji_size

        output = Image.new('RGBA', (out_w, out_h), (245, 245, 245, 255))

        png_available = os.path.exists(self.png_dir) and bool(os.listdir(self.png_dir))
        print(f"  PNG mode: {png_available}  |  cols={cols}  rows={rows}  out={out_w}x{out_h}")

        if png_available:
            # ---- PNG sprite mode (color, cross-platform) ----
            for r in range(rows):
                for c in range(cols):
                    idx    = self.get_best_emoji_index(pixels[r, c])
                    sprite = self._get_sprite(idx, emoji_size)
                    x = c * emoji_size
                    y = r * emoji_size
                    output.paste(sprite, (x, y), sprite)
        else:
            # ---- Text font fallback ----
            draw = ImageDraw.Draw(output)
            try:
                font = ImageFont.truetype(self._font_path, int(emoji_size * 1.2)) if self._font_path else ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()
            for r in range(rows):
                for c in range(cols):
                    idx   = self.get_best_emoji_index(pixels[r, c])
                    emoji = self.emojis[idx]
                    x = c * emoji_size
                    y = r * emoji_size
                    try:
                        draw.text((x, y), emoji, font=font, embedded_color=True)
                    except Exception:
                        draw.text((x, y), emoji, font=font)

        print(f"--- Saving final output to {output_path} ---")
        output.convert('RGB').save(output_path, "PNG", compress_level=3)
        return output_path
