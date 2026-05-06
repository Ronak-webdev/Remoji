import os
import numpy as np
import pandas as pd
from PIL import Image, ImageEnhance, ImageOps, ImageChops
from scipy.spatial import KDTree
from skimage.color import rgb2lab

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        # Load dataset
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        
        # Convert RGB (0-255) to LAB for perceptually accurate matching
        rgb_values = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        # rgb2lab expects (M, N, 3), so we reshape (N, 3) -> (1, N, 3) -> (N, 3)
        self.emoji_lab = rgb2lab(rgb_values.reshape(1, -1, 3)).reshape(-1, 3)
        
        # Build KDTree on LAB values
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

    def _get_sprite_tinted(self, index, size, target_rgb, tint_strength=0.6):
        """
        Applies a 'multiply' blend tint to the sprite to match target color
        while preserving original emoji texture.
        """
        sprite = self._get_sprite(index, size)
        if sprite.mode != 'RGBA':
            sprite = sprite.convert('RGBA')
            
        # Create solid color layer for multiply blend
        # target_rgb is [R, G, B]
        tint_layer = Image.new('RGBA', sprite.size, tuple(target_rgb) + (255,))
        
        # Multiply blend (only RGB channels)
        tinted = ImageChops.multiply(sprite, tint_layer)
        
        # Blend original sprite with tinted version based on strength
        # final = original * (1 - strength) + tinted * strength
        return Image.blend(sprite, tinted, tint_strength)

    def get_best_emoji_index(self, rgb):
        """Find the closest emoji using KDTree in LAB space"""
        # Convert input RGB to LAB
        rgb_norm = rgb.astype(np.float32) / 255.0
        lab = rgb2lab(rgb_norm.reshape(1, 1, 3)).flatten()
        
        _, index = self.tree.query(lab)
        return index

    def create_mosaic(self, input_path, output_path, config):
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        tint_strength = float(config.get('tint_strength', 0.6))
        
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img).convert('RGB')
        w, h = img.size
        
        # Fidelity Scale (1-10)
        target_cols = 30 + (quality * 30)
        analysis_window = max(1, w // target_cols)
        
        cols = w // analysis_window
        rows = h // analysis_window
        
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        pixels = np.array(img_small)
        
        out_w = cols * emoji_size * 2
        out_h = rows * emoji_size * 2
        
        output = Image.new('RGBA', (out_w, out_h), (255, 255, 255, 0))
        sprite_size = int(emoji_size * 2 * 1.2)

        for r in range(rows):
            for c in range(cols):
                rgb = pixels[r, c]
                idx = self.get_best_emoji_index(rgb)
                
                x = c * emoji_size * 2
                y = r * emoji_size * 2
                
                # Get tinted sprite for better color match
                sprite = self._get_sprite_tinted(idx, sprite_size, rgb, tint_strength)
                output.paste(sprite, (x, y), sprite)
        
        # --- Alpha Overlay ---
        # Resize original image to match output size and overlay at 30% opacity
        overlay = img.resize((out_w, out_h), Image.Resampling.LANCZOS).convert('RGBA')
        overlay.putalpha(80) # ~31% opacity
        
        final_output = Image.alpha_composite(output, overlay)
        final_output.save(output_path, "PNG")
        
        return output_path
