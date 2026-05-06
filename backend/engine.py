import os
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
from scipy.spatial import KDTree
from skimage.color import rgb2lab, deltaE_ciede2000
from collections import defaultdict
import cv2
from saliency import compute_saliency_map

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        self.emoji_rgb = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        
        # Convert to LAB for perceptual matching
        self.emoji_lab = rgb2lab(
            self.emoji_rgb.reshape(-1, 1, 3)
        ).reshape(-1, 3).astype(np.float32)
        
        # KDTree in LAB space
        self.tree = KDTree(self.emoji_lab)
        
        # Load variance if available (for texture-aware matching)
        if 'variance' in self.df.columns:
            self.emoji_variance = self.df['variance'].values.astype(np.float32)
        else:
            self.emoji_variance = np.ones(len(self.df), dtype=np.float32) * 50.0
        
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

    def get_best_emoji_index(self, rgb, local_usage=None, region_variance=None):
        """
        Find best emoji using CIEDE2000 with diversity penalty.
        NO tinting. The emoji must naturally match the target color.
        
        local_usage: dict {emoji_idx: count} of recently used emojis nearby
        region_variance: float — how complex/textured the source region is
        """
        rgb_01 = np.clip(np.array(rgb, dtype=np.float32), 0, 255) / 255.0
        lab_input = rgb2lab(rgb_01.reshape(1, 1, 3)).reshape(3)
        
        # Get top-20 candidates (more candidates = better diversity options)
        K = 20
        distances, indices = self.tree.query(lab_input, k=min(K, len(self.emoji_lab)))
        
        best_idx = indices[0]
        best_score = float('inf')
        
        for idx in indices:
            # CIEDE2000 perceptual distance (primary score)
            delta_e = deltaE_ciede2000(
                lab_input.reshape(1, 1, 3),
                self.emoji_lab[idx].reshape(1, 1, 3)
            )[0, 0]
            
            # Diversity penalty: strongly penalize recently used emojis
            # This is the KEY fix for the "all black circles" problem
            diversity_penalty = 0.0
            if local_usage and idx in local_usage:
                # Exponential penalty: 1 use = +5, 2 uses = +12, 3+ uses = +25
                count = local_usage[idx]
                diversity_penalty = min(5.0 * (2 ** (count - 1)), 30.0)
            
            # Texture match bonus: if region is complex, prefer complex emojis
            # If region is smooth, prefer simple emojis
            texture_score = 0.0
            if region_variance is not None:
                emoji_var = self.emoji_variance[idx]
                texture_diff = abs(region_variance - emoji_var)
                texture_score = texture_diff * 0.05  # small weight, don't override color
            
            score = delta_e + diversity_penalty + texture_score
            
            if score < best_score:
                best_score = score
                best_idx = idx
        
        return best_idx

    def create_mosaic(self, input_path, output_path, config):
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img).convert('RGB')
        w, h = img.size
        
        # Grid resolution & Fidelity Scale
        # q=5 corresponds to 60 columns (fast but detailed)
        # q=10 corresponds to 110 columns (max detail)
        target_cols = 10 + (quality * 10)
        cols = min(target_cols, w)
        
        # Fix Hexagonal Aspect Ratio: 
        # Since hex rows are squashed vertically by 0.866, we must sample more rows 
        # from the original image to compensate, preventing a squashed output.
        analysis_window_x = w / cols
        analysis_window_y = analysis_window_x * 0.866
        rows = max(1, int(h / analysis_window_y))
        
        # Saliency map for adaptive detail
        sal_map = compute_saliency_map(img)
        sal_small = cv2.resize(sal_map, (cols, rows))
        
        # Resize image to grid
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        pixels = np.array(img_small).astype(np.float32)
        
        # Compute per-cell variance (for texture matching)
        # Use a slightly larger window for variance calculation
        img_np = np.array(img).astype(np.float32)
        
        def get_region_variance(r, c):
            y1 = int(r * h / rows)
            y2 = int((r+1) * h / rows)
            x1 = int(c * w / cols)
            x2 = int((c+1) * w / cols)
            region = img_np[y1:y2, x1:x2]
            if region.size == 0:
                return 50.0
            return float(region.std())
        
        # ── PHASE 1: Floyd-Steinberg Error Diffusion (determines WHICH emoji goes where)
        # This propagates color quantization error to neighbors,
        # so the overall color average across the mosaic matches the original.
        # This is how we get color fidelity WITHOUT cheating.
        
        error_buffer = np.zeros((rows, cols, 3), dtype=np.float32)
        placed_indices = np.full((rows, cols), -1, dtype=np.int32)
        
        for r in range(rows):
            # Serpentine scanning (alternates direction each row) — better dithering
            col_range = range(cols) if r % 2 == 0 else range(cols - 1, -1, -1)
            
            for c in col_range:
                # Target = original color + accumulated error from neighbors
                target = np.clip(pixels[r, c] + error_buffer[r, c], 0, 255)
                
                # Local diversity map: look at a 5×5 neighborhood
                local_usage = defaultdict(int)
                for dr in range(-2, 1):
                    for dc in range(-3, 4):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            prev = placed_indices[nr, nc]
                            if prev >= 0:
                                local_usage[prev] += 1
                
                # Texture of this region
                region_var = get_region_variance(r, c)
                
                # Get best emoji (NO tinting will be applied later)
                idx = self.get_best_emoji_index(
                    target,
                    local_usage=local_usage,
                    region_variance=region_var
                )
                placed_indices[r, c] = idx
                
                # Quantization error = target color - actual emoji color
                emoji_rgb_actual = self.emoji_rgb[idx] * 255.0
                quant_error = target - emoji_rgb_actual
                
                # Floyd-Steinberg error diffusion
                # Direction-aware (serpentine)
                direction = 1 if r % 2 == 0 else -1
                nc_right = c + direction
                
                if 0 <= nc_right < cols:
                    error_buffer[r, nc_right] += quant_error * (7/16)
                if r + 1 < rows:
                    nc_left = c - direction
                    if 0 <= nc_left < cols:
                        error_buffer[r+1, nc_left] += quant_error * (3/16)
                    error_buffer[r+1, c] += quant_error * (5/16)
                    if 0 <= nc_right < cols:
                        error_buffer[r+1, nc_right] += quant_error * (1/16)
        
        # ── PHASE 2: Render (place UNMODIFIED emoji PNGs on canvas)
        # Hexagonal offset grid: odd rows are shifted right by half emoji width
        # This breaks the rigid square grid look naturally
        
        sprite_size = emoji_size * 2  # base render size
        
        # Hex grid parameters
        hex_x_spacing = sprite_size          # horizontal spacing
        hex_y_spacing = int(sprite_size * 0.866)  # vertical spacing (√3/2 for hex)
        hex_offset = sprite_size // 2        # horizontal offset for odd rows
        
        # Canvas size with hex grid
        out_w = cols * hex_x_spacing + hex_offset + sprite_size
        out_h = rows * hex_y_spacing + sprite_size
        
        # Transparent canvas
        output = Image.new('RGBA', (out_w, out_h), (255, 255, 255, 0))
        
        for r in range(rows):
            for c in range(cols):
                idx = placed_indices[r, c]
                if idx < 0:
                    continue
                
                # Hex grid position
                x = c * hex_x_spacing + (hex_offset if r % 2 == 1 else 0)
                y = r * hex_y_spacing
                
                # Saliency-adaptive size: important regions get slightly larger emojis
                # so they are more recognizable (NOT for color — only for size)
                sal_val = sal_small[r, c]
                if sal_val > 0.7:
                    actual_size = int(sprite_size * 1.15)
                elif sal_val < 0.2:
                    actual_size = int(sprite_size * 0.9)
                else:
                    actual_size = sprite_size
                
                # Get UNMODIFIED emoji sprite — no tinting, no color overlay
                sprite = self._get_sprite(idx, actual_size)
                
                # Center the sprite on its grid position
                cx = x - (actual_size - sprite_size) // 2
                cy = y - (actual_size - sprite_size) // 2
                
                output.paste(sprite, (cx, cy), sprite)
        
        # SAVE — pure emoji mosaic, no post-processing color changes
        output.save(output_path, "PNG")
        return output_path

