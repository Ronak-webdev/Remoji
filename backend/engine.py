import os
import numpy as np
import pandas as pd
from PIL import Image, ImageEnhance
from scipy.spatial import KDTree

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        print(f"--- Initializing EmojiMosaicEngine with {dataset_path} ---")
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        self.emoji_rgb = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        self.tree = KDTree(self.emoji_rgb)
        
        self.png_dir = os.path.join(os.path.dirname(__file__), "emoji_pngs")
        # Prefer the hexcode column we generated in Step 2, fallback to the rule
        if 'hexcode' in self.df.columns:
            self.emoji_filenames = self.df['hexcode'].values.tolist()
        else:
            self.emoji_filenames = [self._emoji_to_filename(e) for e in self.emojis]
        
        self._sprite_cache = {}
        self._cache_limit = 2048
        
        # Diagnostics
        png_exists = os.path.exists(self.png_dir)
        png_count = len([f for f in os.listdir(self.png_dir) if f.endswith('.png')]) if png_exists else 0
        csv_count = len(self.df)
        
        # Quick check for coverage using the same logic as _get_sprite but without loading
        found_count = 0
        for fname in self.emoji_filenames:
            if self._find_png(fname):
                found_count += 1
        
        coverage = (found_count / csv_count * 100) if csv_count > 0 else 0
        
        print(f"  PNG directory: {self.png_dir} | exists: {png_exists}")
        print(f"  PNG files: {png_count}")
        print(f"  Total emojis in CSV: {csv_count}")
        print(f"  PNG coverage: {coverage:.1f}%")

    @staticmethod
    def _emoji_to_filename(emoji_char):
        """OpenMoji naming rule: lowercase hex, skip FE0F/FE0E, join with _."""
        parts = []
        for ch in emoji_char:
            cp = ord(ch)
            if cp in (0xFE0F, 0xFE0E):
                continue
            parts.append(format(cp, 'x'))
        return '_'.join(parts)

    def _find_png(self, filename_base):
        """Robust lookup for PNG files (handles case and separator differences)."""
        # Variants to try (since actual OpenMoji package uses uppercase and -)
        variants = [
            filename_base,                           # 1f600
            filename_base.upper(),                   # 1F600
            filename_base.replace('_', '-'),         # 1f600-200d...
            filename_base.upper().replace('_', '-')  # 1F600-200D...
        ]
        for v in variants:
            path = os.path.join(self.png_dir, f"{v}.png")
            if os.path.exists(path):
                return path
        return None

    def _get_sprite(self, emoji_index, size):
        """Return a PIL Image (RGBA) for the emoji at `size`×`size` with caching."""
        key = (emoji_index, size)
        if key in self._sprite_cache:
            return self._sprite_cache[key]

        filename = self.emoji_filenames[emoji_index]
        png_path = self._find_png(filename)
        
        if png_path:
            try:
                img = Image.open(png_path).convert("RGBA")
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                
                # LRU cache eviction
                if len(self._sprite_cache) >= self._cache_limit:
                    # Pop the first key (oldest inserted)
                    self._sprite_cache.pop(next(iter(self._sprite_cache)))
                
                self._sprite_cache[key] = img
                return img
            except Exception as e:
                print(f"  Sprite load error {filename}: {e}")

        # Fallback: solid-color RGBA square using the emoji's mean RGB from CSV
        r = int(self.df.iloc[emoji_index]['r'])
        g = int(self.df.iloc[emoji_index]['g'])
        b = int(self.df.iloc[emoji_index]['b'])
        img = Image.new('RGBA', (size, size), (r, g, b, 255))
        
        self._sprite_cache[key] = img
        return img

    def get_best_emoji_index(self, rgb):
        """Query KDTree for the nearest emoji color."""
        rgb_norm = np.array(rgb, dtype=np.float32) / 255.0
        _, index = self.tree.query(rgb_norm)
        return int(index)

    def create_mosaic(self, input_path, output_path, config):
        quality    = int(config.get('quality', 3))     # 1-5
        emoji_size = int(config.get('emoji_size', 16)) # px
        
        print(f"--- Creating mosaic: quality={quality}, emoji_size={emoji_size} ---")
        
        img = Image.open(input_path).convert('RGB')
        w, h = img.size
        
        # Grid calculation
        target_cols = 20 + quality * 20        # 40 / 60 / 80 / 100 / 120
        analysis_window = max(1, w // target_cols)
        cols = w // analysis_window
        rows = h // analysis_window
        
        print(f"  Grid: {cols}x{rows} (analysis window: {analysis_window}px)")
        
        # Image analysis
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        # Apply contrast enhancement 1.15 (vivid colors)
        img_small = ImageEnhance.Contrast(img_small).enhance(1.15)
        pixels = np.array(img_small)
        
        # Canvas
        out_w = cols * emoji_size
        out_h = rows * emoji_size
        # Dark bg as requested
        output = Image.new('RGBA', (out_w, out_h), (30, 30, 30, 255))
        
        # Render loop
        for r in range(rows):
            for c in range(cols):
                idx    = self.get_best_emoji_index(pixels[r, c])
                sprite = self._get_sprite(idx, emoji_size)
                output.paste(sprite, (c * emoji_size, r * emoji_size), sprite)
            
            # Progress print
            if rows >= 20 and (r + 1) % max(1, rows // 10) == 0:
                print(f"  {(r+1)*100//rows}% done")
        
        print(f"  Saving output to {output_path}...")
        # Save as RGB with compress_level=2
        output.convert('RGB').save(output_path, 'PNG', compress_level=2)
        
        return output_path
