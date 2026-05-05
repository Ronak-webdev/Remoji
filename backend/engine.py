import os
import numpy as np
import pandas as pd
from PIL import Image, ImageEnhance
import pillow_avif
from scipy.spatial import KDTree
import random

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        print(f"--- Initializing Premium PNG Emoji Engine with {dataset_path} ---")
        self.df = pd.read_csv(dataset_path)
        
        # We use 'hex' column if available to map to filenames
        if 'hex' in self.df.columns:
            self.emoji_filenames = self.df['hex'].values.tolist()
        else:
            # Fallback if hex is missing (shouldn't happen with our updated script)
            self.emoji_filenames = [self._emoji_to_filename(e) for e in self.df['emoji'].values]
            
        # Normalize colors to 0-1
        self.emoji_rgb = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        
        # Build KDTree for ultra-fast color matching
        self.tree = KDTree(self.emoji_rgb)
        
        # Directory of pre-downloaded emoji PNGs (OpenMoji 72x72)
        self.png_dir = os.path.join(os.path.dirname(__file__), "emoji_pngs")
        
        # LRU-style image cache
        self._sprite_cache = {}
        self._cache_limit = 2048

    @staticmethod
    def _emoji_to_filename(emoji_char):
        parts = []
        for ch in emoji_char:
            cp = ord(ch)
            if cp in (0xFE0F, 0xFE0E): continue
            parts.append(format(cp, 'X'))
        return '-'.join(parts)

    def _find_png(self, filename_base):
        """Robust lookup for PNG files (handles case)."""
        variants = [
            filename_base,
            filename_base.lower(),
            filename_base.upper()
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
                    self._sprite_cache.pop(next(iter(self._sprite_cache)))
                
                self._sprite_cache[key] = img
                return img
            except Exception as e:
                print(f"Error loading {png_path}: {e}")

        # Fallback: solid-color RGBA square using the emoji's mean RGB from CSV
        r = int(self.df.iloc[emoji_index]['r'])
        g = int(self.df.iloc[emoji_index]['g'])
        b = int(self.df.iloc[emoji_index]['b'])
        img = Image.new('RGBA', (size, size), (r, g, b, 255))
        
        self._sprite_cache[key] = img
        return img

    def get_best_emoji_index(self, rgb):
        """Find the closest emoji index using KDTree with a bit of variety"""
        rgb_norm = rgb / 255.0
        # Query top 3 to add realistic variety
        distances, indices = self.tree.query(rgb_norm, k=3)
        
        # Pick one of the top 3 (weighted towards the best match: 70%, 20%, 10%)
        choice_idx = random.choices([0, 1, 2], weights=[0.7, 0.2, 0.1])[0]
        return int(indices[choice_idx])

    def create_mosaic(self, input_path, output_path, config):
        """
        Generates a premium, realistic emoji mosaic using PNG sprites.
        """
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        
        print(f"--- Starting Realistic PNG Mosaic: quality={quality}, size={emoji_size} ---")
        
        # Load image
        img = Image.open(input_path).convert('RGB')
        w, h = img.size
        
        # Calculate grid based on quality
        target_cols = 20 + (quality * 20)
        analysis_window = max(1, w // target_cols)
        
        cols = w // analysis_window
        rows = h // analysis_window
        
        # Image Enhancement for Realistic Mosaic
        # Boost saturation slightly
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.2)
        
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        # Boost contrast for punchier emoji matches
        img_small = ImageEnhance.Contrast(img_small).enhance(1.1)
        pixels = np.array(img_small)
        
        # High-Res Canvas (2x scale for crisp detail)
        base_size = emoji_size * 2
        out_w = cols * base_size
        out_h = rows * base_size
        
        # Using a dark-gray background
        output = Image.new('RGBA', (out_w, out_h), (30, 30, 30, 255))
        
        # Overlap Scaling (1.3x)
        # The 1.3x multiplier makes emojis bleed into each other slightly.
        # It creates that "hand-made" mosaic look instead of a perfect grid.
        sprite_size = int(base_size * 1.3)

        # Generate Mosaic with Jitter
        for r in range(rows):
            for c in range(cols):
                rgb = pixels[r, c]
                idx = self.get_best_emoji_index(rgb)
                
                # Load the sprite using our PNG pipeline
                sprite = self._get_sprite(idx, sprite_size)
                
                # Base position (adjusted for overlapping center)
                # Since sprite is 1.3x larger, we offset it slightly so it stays centered
                offset = (sprite_size - base_size) // 2
                base_x = (c * base_size) - offset
                base_y = (r * base_size) - offset
                
                # Add 5% random jitter to placement
                jitter_range = int(base_size * 0.1)
                x = base_x + random.randint(-jitter_range, jitter_range)
                y = base_y + random.randint(-jitter_range, jitter_range)
                
                # Paste the transparent PNG sprite
                output.paste(sprite, (x, y), sprite)
            
            # Progress Logging
            if (r + 1) % max(1, rows // 10) == 0:
                print(f"  Progress: {(r + 1) * 100 // rows}%")

        print(f"--- Saving Premium Output to {output_path} ---")
        # Save as high-quality PNG
        output.convert('RGB').save(output_path, "PNG", compress_level=2)
        return output_path
