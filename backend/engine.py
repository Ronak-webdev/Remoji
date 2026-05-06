import os
import numpy as np
import pandas as pd
from PIL import Image, ImageOps, ImageEnhance
from scipy.spatial import KDTree

def rgb_to_lab(rgb_array):
    """Convert Nx3 RGB (0-255) array to LAB color space for perceptual matching."""
    # Normalize to 0-1
    rgb = rgb_array.astype(np.float32) / 255.0
    
    # Linearize (gamma correction)
    mask = rgb > 0.04045
    rgb[mask] = ((rgb[mask] + 0.055) / 1.055) ** 2.4
    rgb[~mask] = rgb[~mask] / 12.92
    
    # RGB to XYZ (D65 illuminant)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = rgb @ M.T
    
    # XYZ to LAB
    xyz[:, 0] /= 0.95047
    xyz[:, 2] /= 1.08883
    
    mask2 = xyz > 0.008856
    xyz[mask2] = xyz[mask2] ** (1/3)
    xyz[~mask2] = (7.787 * xyz[~mask2]) + (16/116)
    
    lab = np.zeros_like(xyz)
    lab[:, 0] = (116 * xyz[:, 1]) - 16
    lab[:, 1] = 500 * (xyz[:, 0] - xyz[:, 1])
    lab[:, 2] = 200 * (xyz[:, 1] - xyz[:, 2])
    return lab


class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        
        # Build LAB KDTree for perceptually accurate color matching
        rgb_vals = self.df[['r', 'g', 'b']].values.astype(np.float32)
        self.emoji_lab = rgb_to_lab(rgb_vals.copy())
        self.tree = KDTree(self.emoji_lab)
        
        if 'hex' in self.df.columns:
            self.hex_codes = self.df['hex'].values
        else:
            self.hex_codes = [self._emoji_to_filename(e) for e in self.emojis]

        self.png_dir = os.path.join(os.path.dirname(__file__), "emoji_pngs")
        self._sprite_cache = {}

    @staticmethod
    def _emoji_to_filename(emoji_char):
        parts = []
        for ch in emoji_char:
            cp = ord(ch)
            if cp in (0xFE0F, 0xFE0E): continue
            parts.append(format(cp, 'X'))
        return '-'.join(parts)

    def _find_png(self, filename_base):
        variants = [filename_base, filename_base.lower(), filename_base.upper()]
        for v in variants:
            path = os.path.join(self.png_dir, f"{v}.png")
            if os.path.exists(path):
                return path
        return None

    def _get_sprite(self, index, size):
        key = (index, size)
        if key in self._sprite_cache:
            return self._sprite_cache[key]
            
        hex_code = self.hex_codes[index]
        png_path = self._find_png(hex_code)
        
        if png_path:
            try:
                img = Image.open(png_path).convert("RGBA")
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                self._sprite_cache[key] = img
                return img
            except:
                pass
                
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        self._sprite_cache[key] = img
        return img

    def get_best_emoji_index(self, rgb_pixel):
        """LAB-based perceptual color matching — much more accurate than RGB."""
        pixel_lab = rgb_to_lab(np.array([[rgb_pixel[0], rgb_pixel[1], rgb_pixel[2]]], dtype=np.float32))
        _, index = self.tree.query(pixel_lab[0])
        return index

    def create_mosaic(self, input_path, output_path, config):
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        
        # 2x Super-Resolution for sharpness
        SCALE = 2
        
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img).convert('RGB')
        w, h = img.size
        
        # Fidelity: more quality = more cols = finer mosaic
        target_cols = 40 + (quality * 15)
        analysis_window = max(1, w // target_cols)
        cols = w // analysis_window
        rows = h // analysis_window
        
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        pixels = np.array(img_small)
        
        # Canvas at 2x scale
        cell = emoji_size * SCALE
        out_w = cols * cell
        out_h = rows * cell
        
        # Memory Protection
        MAX_DIM = 12000
        if out_w > MAX_DIM or out_h > MAX_DIM:
            scale_down = MAX_DIM / max(out_w, out_h)
            emoji_size = max(4, int(emoji_size * scale_down))
            cell = emoji_size * SCALE
            out_w = cols * cell
            out_h = rows * cell

        # White background — clean base, no transparency gaps
        output = Image.new('RGB', (out_w, out_h), (255, 255, 255))
        
        # Sprite size: exactly cell size (1.0x) — no unwanted overlap/bleed
        sprite_size = cell

        print(f"Generating LAB-Matched Mosaic... Cols={cols}, Canvas={out_w}x{out_h}")
        for r in range(rows):
            for c in range(cols):
                rgb = pixels[r, c]
                x = c * cell
                y = r * cell
                
                idx = self.get_best_emoji_index(rgb)
                sprite = self._get_sprite(idx, sprite_size)
                
                # Paste with transparency mask — no color bleeding
                output.paste(sprite.convert('RGB'), (x, y))
        
        # Light sharpening for crispness
        output = ImageEnhance.Sharpness(output).enhance(1.15)
        
        output.save(output_path, "PNG")
        return output_path
