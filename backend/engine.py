import os
import numpy as np
import pandas as pd
from PIL import Image, ImageOps, ImageEnhance, ImageDraw
from scipy.spatial import KDTree
from skimage import color

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        # Load dataset
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        self.base_count = len(self.emojis)
        
        # Load RGB and Mirroring for diversity
        rgb_orig = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        self.emoji_rgb = np.tile(rgb_orig, (2, 1))
        
        # LAB Matching for human perception
        self.emoji_lab = color.rgb2lab(self.emoji_rgb.reshape(-1, 1, 3)).reshape(-1, 3)
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
        is_mirrored = index >= self.base_count
        actual_index = index % self.base_count
        
        key = (index, size)
        if key in self._sprite_cache:
            return self._sprite_cache[key]
            
        hex_code = self.hex_codes[actual_index]
        png_path = self._find_png(hex_code)
        
        if png_path:
            try:
                img = Image.open(png_path).convert("RGBA")
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                if is_mirrored:
                    img = ImageOps.mirror(img)
                self._sprite_cache[key] = img
                return img
            except:
                pass
                
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        self._sprite_cache[key] = img
        return img

    def get_best_emoji_index(self, rgb):
        rgb_norm = rgb.astype(np.float32) / 255.0
        lab = color.rgb2lab(rgb_norm.reshape(1, 1, 3)).reshape(3)
        _, index = self.tree.query(lab)
        return index

    def create_mosaic(self, input_path, output_path, config):
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        contrast_val = float(config.get('contrast', 1.1))
        saturation_val = float(config.get('saturation', 1.0))
        # Planet Mode uses heavier overlay (Default 35%)
        overlay_factor = float(config.get('overlay', 0.35)) 
        
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img).convert('RGB')
        
        # Boost vibrance for Planet effect
        img = ImageEnhance.Contrast(img).enhance(contrast_val)
        img = ImageEnhance.Color(img).enhance(saturation_val)
            
        w, h = img.size
        target_cols = 60 + (quality * 20)
        
        analysis_window = max(1, w // target_cols)
        cols = w // analysis_window
        rows = h // analysis_window
        
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        pixels = np.array(img_small, dtype=np.float32)
        
        out_w = cols * emoji_size
        out_h = rows * emoji_size
        
        MAX_DIM = 8000
        if out_w > MAX_DIM or out_h > MAX_DIM:
            scale_down = MAX_DIM / max(out_w, out_h)
            emoji_size = max(4, int(emoji_size * scale_down))
            out_w = cols * emoji_size
            out_h = rows * emoji_size

        # Create output canvas
        output = Image.new('RGBA', (out_w, out_h), (255, 255, 255, 255))
        sprite_size = int(emoji_size * 1.05) # Clean grid

        print("DEBUG: Processing Planet-Style Mosaic...")
        for y in range(rows):
            for x in range(cols):
                target_rgb = pixels[y, x]
                
                # Planet Secret 1: Solid Fill Background
                # Fill the cell with the exact target color to ensure 100% accuracy in gaps
                px = x * emoji_size
                py = y * emoji_size
                shape = [px, py, px + emoji_size, py + emoji_size]
                ImageDraw.Draw(output).rectangle(shape, fill=tuple(target_rgb.astype(int)))
                
                # Get best emoji
                idx = self.get_best_emoji_index(target_rgb)
                sprite = self._get_sprite(idx, sprite_size)
                
                # Paste emoji with a bit of transparency so the solid color shows through
                # This creates the "Perfect Tint" look
                output.paste(sprite, (px, py), sprite)
        
        # Planet Secret 2: Masterpiece Overlay
        if overlay_factor > 0:
            print(f"DEBUG: Applying Planet Overlay (Factor: {overlay_factor})")
            original_high_res = img.resize((out_w, out_h), Image.Resampling.LANCZOS).convert("RGBA")
            output = Image.blend(output, original_high_res, overlay_factor)

        output.save(output_path, "PNG")
        return output_path



