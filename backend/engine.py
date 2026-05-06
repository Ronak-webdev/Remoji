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
        
        # Supercharged Expansion (Mirroring + 4 Rotations = 8x the variety!)
        # Effective Dataset: 4136 * 8 = 33,088 emojis
        rgb_orig = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        # We tile 8 times: [Orig, Mirror, R90, R90M, R180, R180M, R270, R270M]
        self.emoji_rgb = np.tile(rgb_orig, (8, 1))
        
        # LAB Matching for human-eye accuracy
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
        variant = index // self.base_count
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
                
                # Apply transformation based on variant
                # 0: Orig, 1: Mirror
                # 2: R90, 3: R90 Mirror
                # 4: R180, 5: R180 Mirror
                # 6: R270, 7: R270 Mirror
                if variant % 2 == 1:
                    img = ImageOps.mirror(img)
                
                rotation = (variant // 2) * 90
                if rotation > 0:
                    img = img.rotate(rotation, expand=False)
                    
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
        # Default overlay for the "Advanced" look is 10% (very subtle)
        overlay_factor = float(config.get('overlay', 0.10)) 
        
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img).convert('RGB')
        
        if contrast_val != 1.0:
            img = ImageEnhance.Contrast(img).enhance(contrast_val)
        if saturation_val != 1.0:
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

        output = Image.new('RGBA', (out_w, out_h), (255, 255, 255, 255))
        sprite_size = int(emoji_size * 1.1)

        print(f"DEBUG: Processing 32k-Variant Authentic Mosaic... (Target cols: {cols})")
        for y in range(rows):
            for x in range(cols):
                old_pixel = pixels[y, x].copy()
                
                px = x * emoji_size
                py = y * emoji_size
                shape = [px, py, px + emoji_size, py + emoji_size]
                bg_color = tuple((old_pixel * 0.85).astype(int))
                ImageDraw.Draw(output).rectangle(shape, fill=bg_color)
                
                idx = self.get_best_emoji_index(old_pixel)
                emoji_rgb = self.emoji_rgb[idx] * 255.0
                
                error = old_pixel - emoji_rgb
                if x + 1 < cols: pixels[y, x + 1] += error * 7 / 16
                if y + 1 < rows:
                    if x > 0: pixels[y + 1, x - 1] += error * 3 / 16
                    pixels[y + 1, x] += error * 5 / 16
                    if x + 1 < cols: pixels[y + 1, x + 1] += error * 1 / 16
                
                sprite = self._get_sprite(idx, sprite_size)
                output.paste(sprite, (px, py), sprite)
        
        if overlay_factor > 0:
            original_high_res = img.resize((out_w, out_h), Image.Resampling.LANCZOS).convert("RGBA")
            output = Image.blend(output, original_high_res, overlay_factor)

        output.save(output_path, "PNG")
        return output_path





