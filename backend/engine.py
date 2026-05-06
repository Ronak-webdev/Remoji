import os
import numpy as np
import pandas as pd
from PIL import Image, ImageOps, ImageDraw, ImageEnhance
from scipy.spatial import KDTree

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        # Load dataset (3786+ emojis)
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        # Simple RGB colors (0-1)
        self.emoji_rgb = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        
        # Build KDTree for ultra-fast matching
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
                
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        self._sprite_cache[key] = img
        return img

    def get_best_emoji_index(self, rgb):
        """Simple RGB matching"""
        rgb_norm = rgb / 255.0
        _, index = self.tree.query(rgb_norm)
        return index

    def create_mosaic(self, input_path, output_path, config):
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        
        # Super-Resolution Multiplier (2x for extreme sharpness)
        SCALE = 2
        
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img).convert('RGB')
        w, h = img.size
        
        # Fidelity Scale
        target_cols = 40 + (quality * 15)
        
        analysis_window = max(1, w // target_cols)
        cols = w // analysis_window
        rows = h // analysis_window
        
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        pixels = np.array(img_small)
        
        # Render at 2x Scale
        out_w = cols * emoji_size * SCALE
        out_h = rows * emoji_size * SCALE
        
        # Memory Protection
        MAX_DIM = 12000 # Increased for Pro quality
        if out_w > MAX_DIM or out_h > MAX_DIM:
            scale_down = MAX_DIM / max(out_w, out_h)
            emoji_size = max(4, int(emoji_size * scale_down))
            out_w = cols * emoji_size * SCALE
            out_h = rows * emoji_size * SCALE

        # Solid background (white) to prevent any transparency leaks
        output = Image.new('RGBA', (out_w, out_h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(output)
        
        # Aggressive 1.3x Overlap for depth
        sprite_size = int(emoji_size * SCALE * 1.3)

        print(f"DEBUG: Generating Super-HD Mosaic... (Cols: {cols}, Res: {out_w}x{out_h})")
        for r in range(rows):
            for c in range(cols):
                rgb = pixels[r, c]
                
                # POSITION (2x Scaled)
                x = c * emoji_size * SCALE
                y = r * emoji_size * SCALE
                
                # 1. GAP FILL: Draw target color background for this cell
                shape = [x, y, x + emoji_size * SCALE, y + emoji_size * SCALE]
                draw.rectangle(shape, fill=tuple(rgb))
                
                # 2. EMOJI PASTE
                idx = self.get_best_emoji_index(rgb)
                sprite = self._get_sprite(idx, sprite_size)
                # Offset slightly to center the 1.3x larger sprite
                offset = (sprite_size - (emoji_size * SCALE)) // 2
                output.paste(sprite, (x - offset, y - offset), sprite)
        
        # Final Sharpening
        output = ImageEnhance.Sharpness(output).enhance(1.1)
        
        output.save(output_path, "PNG")
        return output_path






