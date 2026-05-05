import os
import numpy as np
import pandas as pd
from PIL import Image, ImageEnhance, ImageOps
from scipy.spatial import KDTree

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        # Load dataset
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        # Normalize colors to 0-1
        self.emoji_rgb = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        
        # Build KDTree for ultra-fast color matching
        self.tree = KDTree(self.emoji_rgb)
        
        # Directory of pre-downloaded emoji PNGs
        # Since we use OpenMoji now, we need to map hex codes correctly.
        # We will use the 'hex' column from our updated process_openmoji.py
        if 'hex' in self.df.columns:
            self.hex_codes = self.df['hex'].values
        else:
            # Fallback if no hex column (unlikely)
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
                
        # Fallback empty transparent image
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        self._sprite_cache[key] = img
        return img

    def get_best_emoji_index(self, rgb):
        """Find the closest emoji using KDTree (Euclidean distance in RGB)"""
        # Normalize input RGB
        rgb_norm = rgb / 255.0
        _, index = self.tree.query(rgb_norm)
        return index

    def create_mosaic(self, input_path, output_path, config):
        """
        Generates a high-fidelity emoji mosaic with minimum, smart parameters.
        - quality: 1 (Draft) to 5 (Masterpiece)
        - emoji_size: Final size of emojis in px
        """
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        
        # Load image and fix orientation based on EXIF
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img).convert('RGB')
        w, h = img.size
        
        # Fidelity Scale (1-10):
        # q=1 -> 60 columns
        # q=3 -> 120 columns (Sweet Spot - Default)
        # q=10 -> 330 columns (Extreme Detail)
        target_cols = 30 + (quality * 30)
        
        # Calculate window size to hit our target columns
        analysis_window = max(1, w // target_cols)
        
        cols = w // analysis_window
        rows = h // analysis_window
        
        # Resize image to the grid size for bulk processing
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        pixels = np.array(img_small)
        
        # Output canvas dimensions (2x scale for high-quality zoom)
        out_w = cols * emoji_size * 2
        out_h = rows * emoji_size * 2
        
        # Create high-res canvas (TRANSPARENT BACKGROUND, as in the original commit)
        output = Image.new('RGBA', (out_w, out_h), (255, 255, 255, 0))
        
        # Overlap emojis slightly (1.2x) to prevent gaps and create a rich texture
        sprite_size = int(emoji_size * 2 * 1.2)

        # Generate mosaic
        for r in range(rows):
            for c in range(cols):
                rgb = pixels[r, c]
                
                # Process every pixel for full coverage
                idx = self.get_best_emoji_index(rgb)
                
                x = c * emoji_size * 2
                y = r * emoji_size * 2
                
                # Draw the emoji (pasting PNG instead of drawing text)
                sprite = self._get_sprite(idx, sprite_size)
                output.paste(sprite, (x, y), sprite)
        
        # Convert back to RGB or keep RGBA if needed
        # The original commit saved it without converting to RGB explicitly, just "PNG"
        output.save(output_path, "PNG")
        return output_path
