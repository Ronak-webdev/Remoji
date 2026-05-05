import os
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import pillow_avif
from scipy.spatial import KDTree
import random

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        print(f"--- Initializing Realistic Emoji Engine with {dataset_path} ---")
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        # Normalize colors to 0-1
        self.emoji_rgb = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        
        # Build KDTree for ultra-fast color matching
        self.tree = KDTree(self.emoji_rgb)
        
        # Smart Font Path Selection
        self.font_path = self._find_emoji_font()
        print(f"  Selected Font: {self.font_path}")

    def _find_emoji_font(self):
        """Finds the best available emoji font (prefers bundled NotoColorEmoji)"""
        # 1. Bundled Font (Highest priority for Render compatibility)
        local_font = os.path.join(os.path.dirname(__file__), "NotoColorEmoji.ttf")
        if os.path.exists(local_font):
            return local_font
            
        # 2. Windows Path (Fallback for local dev)
        win_font = "C:\\Windows\\Fonts\\seguiemj.ttf"
        if os.path.exists(win_font):
            return win_font
            
        return None

    def get_best_emoji(self, rgb):
        """Find the closest emoji using KDTree with a bit of variety"""
        rgb_norm = rgb / 255.0
        # Query top 3 to add realistic variety
        distances, indices = self.tree.query(rgb_norm, k=3)
        
        # Pick one of the top 3 (weighted towards the best)
        # We use a power distribution to prefer the closest match
        choice_idx = random.choices([0, 1, 2], weights=[0.7, 0.2, 0.1])[0]
        return self.emojis[indices[choice_idx]]

    def create_mosaic(self, input_path, output_path, config):
        """
        Generates a premium, realistic emoji mosaic.
        - quality: 1 to 5
        - emoji_size: Base size (will be scaled 2x)
        """
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        
        print(f"--- Starting Realistic Mosaic Creation: quality={quality}, size={emoji_size} ---")
        
        # Load image
        img = Image.open(input_path).convert('RGB')
        w, h = img.size
        
        # Calculate grid based on quality
        target_cols = 20 + (quality * 20)
        analysis_window = max(1, w // target_cols)
        
        cols = w // analysis_window
        rows = h // analysis_window
        
        # Image Enhancement for Realistic Mosaic
        # We boost saturation slightly so emojis don't look washed out
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.2)
        
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        # Boost contrast for punchier emoji matches
        img_small = ImageEnhance.Contrast(img_small).enhance(1.1)
        pixels = np.array(img_small)
        
        # High-Res Canvas (2x scale for crisp detail)
        # This makes the emojis look sharp even when zoomed in
        out_w = cols * emoji_size * 2
        out_h = rows * emoji_size * 2
        
        # Using a dark-gray background (30,30,30) looks more premium than pure black
        output = Image.new('RGBA', (out_w, out_h), (30, 30, 30, 255))
        draw = ImageDraw.Draw(output)
        
        # Load Font with Overlap Scaling (1.3x)
        # The 1.3x multiplier makes emojis bleed into each other slightly,
        # creating that "hand-made" mosaic look instead of a perfect grid.
        try:
            font_size = int(emoji_size * 2 * 1.3)
            font = ImageFont.truetype(self.font_path, font_size)
        except Exception as e:
            print(f"  Font load error: {e}. Using default.")
            font = ImageFont.load_default()

        # Generate Mosaic with Jitter
        # Adding a small random offset (jitter) makes it look much more realistic
        for r in range(rows):
            for c in range(cols):
                rgb = pixels[r, c]
                emoji = self.get_best_emoji(rgb)
                
                # Base position
                base_x = c * emoji_size * 2
                base_y = r * emoji_size * 2
                
                # Add 5% random jitter to placement
                jitter_range = int(emoji_size * 0.1)
                x = base_x + random.randint(-jitter_range, jitter_range)
                y = base_y + random.randint(-jitter_range, jitter_range)
                
                # Draw the emoji
                try:
                    # embedded_color=True is crucial for NotoColorEmoji/SegoeUI
                    draw.text((x, y), emoji, font=font, embedded_color=True)
                except:
                    # Fallback for systems without color support
                    draw.text((x, y), emoji, font=font)
            
            # Progress Logging
            if (r + 1) % max(1, rows // 10) == 0:
                print(f"  Progress: {(r + 1) * 100 // rows}%")

        print(f"--- Saving Premium Output to {output_path} ---")
        # Save as high-quality PNG
        output.convert('RGB').save(output_path, "PNG", optimize=True)
        return output_path
