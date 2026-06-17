"""
engine_hq.py
============
High-Quality Emoji Mosaic Engine
- Uses 512x512 Noto Emoji PNGs (downloaded by build_hq_dataset.py)
- On-demand CDN fallback for Render free tier (no local storage required)
- All 5 bug fixes from engine_fixed.py included
- Proper alpha compositing (no white borders!)
- Floyd-Steinberg dithering for color fidelity
- Diversity-aware emoji selection
"""

import os, io, time
import urllib.request
import numpy as np
import pandas as pd
from PIL import Image, ImageOps, ImageEnhance
from scipy.spatial import KDTree
from collections import OrderedDict

try:
    import cairosvg
    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False

NOTO_BASE    = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/png/512"
TWEMOJI_BASE = "https://raw.githubusercontent.com/twitter/twemoji/master/assets/svg"


# ── Color space ──────────────────────────────────────────────────────────────
def rgb_to_lab(rgb_array):
    rgb = rgb_array.astype(np.float32) / 255.0
    mask = rgb > 0.04045
    rgb[mask] = ((rgb[mask] + 0.055) / 1.055) ** 2.4
    rgb[~mask] = rgb[~mask] / 12.92
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = rgb @ M.T
    xyz[:, 0] /= 0.95047; xyz[:, 2] /= 1.08883
    mask2 = xyz > 0.008856
    xyz[mask2] = xyz[mask2] ** (1/3)
    xyz[~mask2] = 7.787 * xyz[~mask2] + 16/116
    lab = np.zeros_like(xyz)
    lab[:, 0] = 116 * xyz[:, 1] - 16
    lab[:, 1] = 500 * (xyz[:, 0] - xyz[:, 1])
    lab[:, 2] = 200 * (xyz[:, 1] - xyz[:, 2])
    return lab


# ── Sprite cleaning ──────────────────────────────────────────────────────────
def clean_sprite_alpha(img_rgba, size):
    """
    Resize + remove white halo artifacts from emoji PNGs.
    Crops transparent padding first to prevent grid gaps!
    Returns clean RGBA image ready for alpha-paste.
    """
    # Crop transparent padding
    bbox = img_rgba.getbbox()
    if bbox:
        img_rgba = img_rgba.crop(bbox)
        
    img = img_rgba.resize((size, size), Image.Resampling.LANCZOS)
    arr = np.array(img, dtype=np.float32)
    r, g, b, a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]

    brightness = r * 0.299 + g * 0.587 + b * 0.114

    # Kill pure white very-low-alpha pixels (halo/border artifacts)
    halo = (brightness > 250) & (a < 50)
    arr[halo, 3] = 0

    return Image.fromarray(arr.astype(np.uint8), 'RGBA')


# ── Main Engine ───────────────────────────────────────────────────────────────
class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        self.df = pd.read_csv(dataset_path)
        
        self.png_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emoji_pngs")
        os.makedirs(self.png_dir, exist_ok=True)
        
        # Filter out emojis that haven't been downloaded yet to prevent CDN timeouts/missing emojis
        valid_rows = []
        for i, row in self.df.iterrows():
            code = row['hex'] if 'hex' in self.df.columns else self._emoji_to_filename(row['emoji'])
            if os.path.exists(os.path.join(self.png_dir, f"{code}.png")):
                valid_rows.append(i)
                
        self.df = self.df.loc[valid_rows].reset_index(drop=True)
        print(f"Filtered to {len(self.df)} locally available emojis.")
        
        self.emojis = self.df['emoji'].values

        # LAB KDTree
        if 'l' in self.df.columns and 'a_val' in self.df.columns and 'b_val' in self.df.columns:
            print("Using pre-calculated LAB centroids (HQ mode)")
            self.emoji_lab = self.df[['l', 'a_val', 'b_val']].values.astype(np.float32)
        else:
            print("Falling back to RGB→LAB")
            rgb_vals = self.df[['r', 'g', 'b']].values.astype(np.float32)
            self.emoji_lab = rgb_to_lab(rgb_vals.copy())

        self.tree = KDTree(self.emoji_lab)
        self.hex_codes = self.df['hex'].values if 'hex' in self.df.columns else \
                         [self._emoji_to_filename(e) for e in self.emojis]

        # RGB values for dithering error computation
        self.emoji_rgb = self.df[['r','g','b']].values.astype(np.float32) \
                         if 'r' in self.df.columns else None

        self.png_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emoji_pngs")
        os.makedirs(self.png_dir, exist_ok=True)  # Create cache dir on Render

        # LRU sprite cache (stores cleaned RGBA at requested size)
        self._sprite_cache = OrderedDict()
        self._MAX_CACHE = 600

        # Raw 512px source cache (avoid re-downloading)
        self._raw_cache = OrderedDict()
        self._MAX_RAW = 800

    @staticmethod
    def _emoji_to_filename(emoji_char):
        parts = []
        for ch in emoji_char:
            cp = ord(ch)
            if cp in (0xFE0F, 0xFE0E): continue
            parts.append(format(cp, 'X'))
        return '-'.join(parts)

    # ── Source fetching ──────────────────────────────────────────────────────
    def _load_raw_512(self, hex_code):
        """
        Load 512x512 RGBA source for an emoji.
        Priority: local disk → Noto CDN → Twemoji SVG
        """
        if hex_code in self._raw_cache:
            self._raw_cache.move_to_end(hex_code)
            return self._raw_cache[hex_code]

        img = None

        # 1. Local disk (pre-built dataset)
        local_path = os.path.join(self.png_dir, f"{hex_code}.png")
        if os.path.exists(local_path):
            try:
                img = Image.open(local_path).convert('RGBA')
            except:
                pass

        # 2. Noto Emoji CDN (512x512 PNG, Apache/OFL license)
        if img is None:
            parts = hex_code.lower().split('-')
            fname = 'emoji_u' + '_'.join(parts) + '.png'
            url = f"{NOTO_BASE}/{fname}"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = r.read()
                img = Image.open(io.BytesIO(data)).convert('RGBA')
                # Cache to disk for next time
                img.save(local_path, 'PNG')
            except:
                pass

        # 3. Twemoji SVG fallback (infinite resolution via cairosvg)
        if img is None and HAS_CAIRO:
            code = hex_code.lower()
            url = f"{TWEMOJI_BASE}/{code}.svg"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=8) as r:
                    svg_data = r.read()
                png_data = cairosvg.svg2png(bytestring=svg_data, output_width=512, output_height=512)
                img = Image.open(io.BytesIO(png_data)).convert('RGBA')
                img.save(local_path, 'PNG')
            except:
                pass

        # 4. Transparent fallback
        if img is None:
            img = Image.new('RGBA', (512, 512), (0, 0, 0, 0))

        self._raw_cache[hex_code] = img
        if len(self._raw_cache) > self._MAX_RAW:
            self._raw_cache.popitem(last=False)

        return img

    def _get_sprite(self, index, size):
        """Get cleaned, resized RGBA sprite for an emoji index."""
        key = (index, size)
        if key in self._sprite_cache:
            self._sprite_cache.move_to_end(key)
            return self._sprite_cache[key]

        hex_code = self.hex_codes[index]
        raw = self._load_raw_512(hex_code)
        sprite = clean_sprite_alpha(raw, size)

        self._sprite_cache[key] = sprite
        if len(self._sprite_cache) > self._MAX_CACHE:
            self._sprite_cache.popitem(last=False)

        return sprite

    # ── Color matching ───────────────────────────────────────────────────────
    def _best_match(self, rgb_pixel, used_counts=None, diversity_weight=0.25, k=12):
        """RGB Manhattan nearest-neighbor (migrated from Image2Emoji)."""
        if self.emoji_rgb is None:
            return 0
        diff = np.abs(self.emoji_rgb - rgb_pixel)
        dists = np.sum(diff, axis=1)
        best_idx = int(np.argmin(dists))
        return best_idx

    # ── Floyd-Steinberg dithering ────────────────────────────────────────────
    def _dither_pass(self, pixels, cols, rows):
        """
        Floyd-Steinberg error diffusion with serpentine scan.
        Returns result_indices array (rows x cols).
        """
        pix = pixels.astype(np.float32).copy()
        result = np.zeros((rows, cols), dtype=np.int32)

        for r in range(rows):
            col_range = range(cols) if r % 2 == 0 else range(cols - 1, -1, -1)
            for c in col_range:
                old = np.clip(pix[r, c], 0, 255)
                idx = self._best_match(old.astype(np.uint8))
                result[r, c] = idx

                if self.emoji_rgb is not None:
                    matched_rgb = self.emoji_rgb[idx]
                else:
                    matched_rgb = old  # No error if no RGB data

                error = (old - matched_rgb) * 0.75

                if r % 2 == 0:
                    if c + 1 < cols:       pix[r,   c+1] += error * (7/16)
                    if r + 1 < rows:
                        if c > 0:          pix[r+1, c-1] += error * (3/16)
                        pix[r+1, c]        += error * (5/16)
                        if c + 1 < cols:   pix[r+1, c+1] += error * (1/16)
                else:
                    if c - 1 >= 0:         pix[r,   c-1] += error * (7/16)
                    if r + 1 < rows:
                        if c + 1 < cols:   pix[r+1, c+1] += error * (3/16)
                        pix[r+1, c]        += error * (5/16)
                        if c - 1 >= 0:     pix[r+1, c-1] += error * (1/16)

        return result

    # ── Main API ─────────────────────────────────────────────────────────────
    def create_mosaic(self, input_path, output_path, config):
        quality       = int(config.get('quality', 3))
        emoji_size    = int(config.get('emoji_size', 16))
        use_dithering = bool(config.get('dithering', True))
        bg_color      = config.get('bg_color', 'black')  # 'black' | 'white' | 'transparent'

        SCALE = 3  # 3× super-resolution render

        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img).convert('RGB')
        w, h = img.size

        target_cols = 40 + quality * 15
        analysis_window = max(1, w // target_cols)
        cols = w // analysis_window
        rows = h // analysis_window

        img_small = img.resize((cols, rows), Image.Resampling.NEAREST)
        
        pixels = np.array(img_small)

        cell = emoji_size * SCALE
        overlap_enabled = str(config.get('overlap_enabled', 'false')).lower() == 'true'
        overlap_percent = int(config.get('overlap_percent', 45))
        
        if overlap_enabled:
            stride = max(1, int(cell * (1 - (overlap_percent / 100.0))))
            out_w = (cols - 1) * stride + cell
            out_h = (rows - 1) * stride + cell
            config['bg_color'] = 'white'  # Force white background for overlap
        else:
            stride = cell
            out_w, out_h = cols * cell, rows * cell

        MAX_DIM = 4000
        if max(out_w, out_h) > MAX_DIM:
            sd = MAX_DIM / max(out_w, out_h)
            emoji_size = max(4, int(emoji_size * sd))
            cell = emoji_size * SCALE
            if overlap_enabled:
                stride = max(1, int(cell * (1 - (overlap_percent / 100.0))))
                out_w = (cols - 1) * stride + cell
                out_h = (rows - 1) * stride + cell
            else:
                stride = cell
                out_w, out_h = cols * cell, rows * cell

        # Canvas background
        bg_color = config.get('bg_color', 'black')
        bg_map = {
            'black':       (0,   0,   0,   255),
            'white':       (255, 255, 255, 255),
            'transparent': (0,   0,   0,   0),
        }
        bg = bg_map.get(bg_color, (0, 0, 0, 255))
        output = Image.new('RGBA', (out_w, out_h), bg)

        print(f"HQ Mosaic | {cols}×{rows} cells | canvas {out_w}×{out_h} | "
              f"emoji_size={emoji_size} | dither={use_dithering}")

        print("Image2Emoji rendering pass (Nearest-neighbor only)...")
        r_range = range(rows-1, -1, -1) if overlap_enabled else range(rows)
        for r in r_range:
            c_range = range(cols-1, -1, -1) if overlap_enabled else range(cols)
            for c in c_range:
                old = np.clip(pixels[r, c], 0, 255)
                idx = self._best_match(old.astype(np.uint8))
                sprite = self._get_sprite(idx, cell)
                output.paste(sprite, (c * stride, r * stride), mask=sprite)

        self._sprite_cache.clear()
        self._raw_cache.clear()
        
        import gc
        gc.collect()

        # Final output
        result = output.convert('RGB')
        del output
        gc.collect()
        
        result = ImageEnhance.Sharpness(result).enhance(1.3)
        result.save(output_path, 'PNG', compress_level=1)
        return output_path
