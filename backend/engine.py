import os
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
from scipy.spatial import KDTree

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        # Load dataset
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        # Normalize colors to 0-1
        self.emoji_rgb = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        
        # Build KDTree for ultra-fast color matching using simple RGB Euclidean distance
        self.tree = KDTree(self.emoji_rgb)
        
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
                
        # Fallback transparent image
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
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        contrast_val = float(config.get('contrast', 1.1))
        saturation_val = float(config.get('saturation', 1.0))
        
        # Load image and fix orientation
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img).convert('RGB')
        
        # Apply Contrast and Saturation
        if contrast_val != 1.0:
            from PIL import ImageEnhance
            img = ImageEnhance.Contrast(img).enhance(contrast_val)
        if saturation_val != 1.0:
            from PIL import ImageEnhance
            img = ImageEnhance.Color(img).enhance(saturation_val)
            
        w, h = img.size
        
        # Fidelity Scale (1-10)
        # As requested: what was achieved at 7 (108 cols) is now achieved at 1 or 2.
        # target_cols = 60 + (quality * 20)
        # q=1 -> 80 columns
        # q=2 -> 100 columns
        # q=3 -> 120 columns (Default)
        # q=10 -> 260 columns (Extreme Masterpiece)
        target_cols = 60 + (quality * 20)
        print(f"DEBUG: Processing mosaic with target_cols={target_cols}, emoji_size={emoji_size}, contrast={contrast_val}, saturation={saturation_val}")
        
        # Calculate window size to hit our target columns
        analysis_window = max(1, w // target_cols)
        cols = w // analysis_window
        rows = h // analysis_window
        
        # Resize image to the grid size for bulk processing
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        pixels = np.array(img_small)
        
        # Output canvas dimensions
        out_w = cols * emoji_size
        out_h = rows * emoji_size
        
        # Cap dimensions to prevent OOM on Render (Free Tier = 512MB RAM)
        # 8000x8000 RGBA image takes ~256MB
        MAX_DIM = 8000
        if out_w > MAX_DIM or out_h > MAX_DIM:
            scale_down = MAX_DIM / max(out_w, out_h)
            emoji_size = max(4, int(emoji_size * scale_down))
            out_w = cols * emoji_size
            out_h = rows * emoji_size
            print(f"DEBUG: Scaled down canvas to prevent OOM. New emoji_size: {emoji_size}, canvas: {out_w}x{out_h}")

        # Create transparent canvas
        output = Image.new('RGBA', (out_w, out_h), (255, 255, 255, 0))
        
        # Overlap emojis slightly (1.2x) to prevent gaps
        sprite_size = int(emoji_size * 1.2)

        # Generate mosaic
        for r in range(rows):
            for c in range(cols):
                rgb = pixels[r, c]
                idx = self.get_best_emoji_index(rgb)
                
                x = c * emoji_size
                y = r * emoji_size
                
                sprite = self._get_sprite(idx, sprite_size)
                output.paste(sprite, (x, y), sprite)
        
        output.save(output_path, "PNG")
        return output_path

