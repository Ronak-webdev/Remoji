import os
import numpy as np
import pandas as pd
from PIL import Image, ImageOps, ImageEnhance
from scipy.spatial import KDTree
from skimage import color

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        # Load dataset
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        self.base_count = len(self.emojis)
        
        # Load RGB and Mirroring (Double the dataset by horizontally flipping emojis)
        # First half: Original, Second half: Mirrored
        rgb_orig = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        self.emoji_rgb = np.tile(rgb_orig, (2, 1))
        
        # Convert to LAB for perceptually accurate matching
        # Input shape (N, 3) -> reshape to (N, 1, 3) for rgb2lab -> (N, 3)
        self.emoji_lab = color.rgb2lab(self.emoji_rgb.reshape(-1, 1, 3)).reshape(-1, 3)
        
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
        # Check if this is a mirrored version
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
                
        # Fallback transparent image
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        self._sprite_cache[key] = img
        return img

    def get_best_emoji_index(self, rgb):
        """Find the closest emoji using KDTree in LAB space"""
        # Normalize input RGB (0-1)
        rgb_norm = rgb.astype(np.float32) / 255.0
        # Convert to LAB
        lab = color.rgb2lab(rgb_norm.reshape(1, 1, 3)).reshape(3)
        # Query KDTree
        _, index = self.tree.query(lab)
        return index

    def create_mosaic(self, input_path, output_path, config):
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        contrast_val = float(config.get('contrast', 1.1))
        saturation_val = float(config.get('saturation', 1.0))
        # Overlay factor (The "Masterpiece Secret Sauce")
        overlay_factor = float(config.get('overlay', 0.15)) 
        
        # Load image and fix orientation
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img).convert('RGB')
        
        # Apply Contrast and Saturation to the source
        if contrast_val != 1.0:
            img = ImageEnhance.Contrast(img).enhance(contrast_val)
        if saturation_val != 1.0:
            img = ImageEnhance.Color(img).enhance(saturation_val)
            
        w, h = img.size
        
        # Fidelity Scale
        target_cols = 60 + (quality * 20)
        
        # Calculate grid
        analysis_window = max(1, w // target_cols)
        cols = w // analysis_window
        rows = h // analysis_window
        
        # Resize for pixel data
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        pixels = np.array(img_small, dtype=np.float32)
        
        # Output dimensions
        out_w = cols * emoji_size
        out_h = rows * emoji_size
        
        # Cap dimensions for Render memory
        MAX_DIM = 8000
        if out_w > MAX_DIM or out_h > MAX_DIM:
            scale_down = MAX_DIM / max(out_w, out_h)
            emoji_size = max(4, int(emoji_size * scale_down))
            out_w = cols * emoji_size
            out_h = rows * emoji_size

        # Create output canvas
        output = Image.new('RGBA', (out_w, out_h), (255, 255, 255, 0))
        sprite_size = int(emoji_size * 1.1) # Slight overlap to prevent gaps

        # Floyd-Steinberg Dithering
        print("DEBUG: Applying Masterpiece Dithering & LAB Matching...")
        for y in range(rows):
            for x in range(cols):
                old_pixel = pixels[y, x].copy()
                
                # Get best emoji for current pixel
                idx = self.get_best_emoji_index(old_pixel)
                
                # Calculate error (Original Color - Emoji Color)
                # Use RGB for error diffusion as it's simpler and more stable than LAB error
                emoji_rgb = self.emoji_rgb[idx] * 255.0
                error = old_pixel - emoji_rgb
                
                # Distribute error to neighbors
                if x + 1 < cols:
                    pixels[y, x + 1] += error * 7 / 16
                if y + 1 < rows:
                    if x > 0:
                        pixels[y + 1, x - 1] += error * 3 / 16
                    pixels[y + 1, x] += error * 5 / 16
                    if x + 1 < cols:
                        pixels[y + 1, x + 1] += error * 1 / 16
                
                # Paste emoji
                px = x * emoji_size
                py = y * emoji_size
                sprite = self._get_sprite(idx, sprite_size)
                output.paste(sprite, (px, py), sprite)
        
        # Apply the "Masterpiece Overlay" (The honest version of the cheating trick)
        if overlay_factor > 0:
            print(f"DEBUG: Applying Masterpiece Overlay (Factor: {overlay_factor})")
            # Create a high-res version of the original image to blend
            original_high_res = img.resize((out_w, out_h), Image.Resampling.LANCZOS).convert("RGBA")
            # Use the original image as a blend layer
            output = Image.blend(output, original_high_res, overlay_factor)

        output.save(output_path, "PNG")
        return output_path


