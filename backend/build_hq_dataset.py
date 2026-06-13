"""
build_hq_dataset.py
===================
ONE-TIME script — run this LOCALLY (not on Render) to:
  1. Download all Noto Emoji 512x512 PNGs from Google's GitHub
  2. Fallback to Twemoji SVG (rasterized to 512px) for missing ones
  3. Compute LAB centroid for each emoji
  4. Save emoji_pngs/ folder + data/emojis.csv

Run: python build_hq_dataset.py
Then commit emoji_pngs/ + data/emojis.csv to your repo (or upload to Render disk)

Requirements: pip install pillow cairosvg requests pandas scipy numpy
"""

import os, io, time, json, unicodedata
import urllib.request
import numpy as np
import pandas as pd
from PIL import Image
from scipy.spatial import KDTree

try:
    import cairosvg
    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False
    print("WARNING: cairosvg not installed. Twemoji SVG fallback disabled.")
    print("Install: pip install cairosvg")

# ── Config ──────────────────────────────────────────────────────────────────
EMOJI_SIZE    = 512          # Store at 512x512 (engine resizes down as needed)
OUTPUT_DIR    = "emoji_pngs" # Where PNGs are saved
CSV_PATH      = os.path.join("data", "emojis.csv")
DELAY         = 0.05         # Seconds between requests (be nice to GitHub CDN)
MAX_EMOJIS    = None         # None = download all; set to 200 to test quickly

NOTO_BASE  = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/png/512"
TWEMOJI_BASE = "https://raw.githubusercontent.com/twitter/twemoji/master/assets/svg"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)

# ── Unicode emoji list ───────────────────────────────────────────────────────
def get_emoji_list():
    """
    Return list of (emoji_char, hex_code) tuples.
    Uses Unicode emoji data — covers ~3600 standard emojis.
    Hex code matches our CSV format: '1F600' or '1F1EE-1F1F3'
    """
    emojis = []
    
    # Core emoji ranges (Unicode 15.0)
    ranges = [
        (0x1F600, 0x1F64F),  # Emoticons
        (0x1F300, 0x1F5FF),  # Misc symbols & pictographs
        (0x1F680, 0x1F6FF),  # Transport & map
        (0x1F700, 0x1F77F),  # Alchemical symbols
        (0x1F780, 0x1F7FF),  # Geometric shapes extended
        (0x1F800, 0x1F8FF),  # Supplemental arrows-C
        (0x1F900, 0x1F9FF),  # Supplemental symbols
        (0x1FA00, 0x1FA6F),  # Chess symbols
        (0x1FA70, 0x1FAFF),  # Symbols and pictographs extended-A
        (0x2600,  0x26FF),   # Misc symbols
        (0x2700,  0x27BF),   # Dingbats
        (0x231A,  0x231B),   # Watch, hourglass
        (0x23E9,  0x23F3),   # Various clocks/arrows
        (0x23F8,  0x23FA),   # Pause/stop buttons
        (0x25AA,  0x25AB),   # Small squares
        (0x25B6,  0x25B6),   # Play button
        (0x25C0,  0x25C0),   # Reverse button
        (0x25FB,  0x25FE),   # Medium squares
        (0x2614,  0x2615),   # Umbrella, hot beverage
        (0x2648,  0x2653),   # Zodiac signs
        (0x267F,  0x267F),   # Wheelchair
        (0x2693,  0x2693),   # Anchor
        (0x26A1,  0x26A1),   # Lightning
        (0x26AA,  0x26AB),   # Circles
        (0x26BD,  0x26BE),   # Football, baseball
        (0x26C4,  0x26C5),   # Snowman, sun
        (0x26CE,  0x26CF),   # Ophiuchus, pick
        (0x26D4,  0x26D4),   # No entry
        (0x26EA,  0x26EA),   # Church
        (0x26F2,  0x26F3),   # Fountain, golf
        (0x26F5,  0x26F5),   # Sailboat
        (0x26FA,  0x26FA),   # Tent
        (0x26FD,  0x26FD),   # Fuel pump
        (0x2702,  0x2702),   # Scissors
        (0x2705,  0x2705),   # Check mark
        (0x2708,  0x270D),   # Airplane→writing hand
        (0x270F,  0x270F),   # Pencil
        (0x2712,  0x2712),   # Black nib
        (0x2714,  0x2714),   # Heavy check
        (0x2716,  0x2716),   # Heavy multiplication
        (0x271D,  0x271D),   # Latin cross
        (0x2721,  0x2721),   # Star of David
        (0x2728,  0x2728),   # Sparkles
        (0x2733,  0x2734),   # Spoked asterisk
        (0x2744,  0x2744),   # Snowflake
        (0x2747,  0x2747),   # Sparkle
        (0x274C,  0x274C),   # Cross mark
        (0x274E,  0x274E),   # Cross mark button
        (0x2753,  0x2755),   # Question marks
        (0x2757,  0x2757),   # Exclamation
        (0x2763,  0x2764),   # Exclamation ornament, heart
        (0x2795,  0x2797),   # Plus/minus/division signs
        (0x27A1,  0x27A1),   # Right arrow
        (0x27B0,  0x27B0),   # Curly loop
        (0x27BF,  0x27BF),   # Double curly loop
        (0x2934,  0x2935),   # Arrows
        (0x2B05,  0x2B07),   # Arrows
        (0x2B1B,  0x2B1C),   # Squares
        (0x2B50,  0x2B50),   # Star
        (0x2B55,  0x2B55),   # Circle
        (0x3030,  0x3030),   # Wavy dash
        (0x303D,  0x303D),   # Part alternation mark
        (0x3297,  0x3297),   # Circled ideograph congratulation
        (0x3299,  0x3299),   # Circled ideograph secret
    ]
    
    seen = set()
    for start, end in ranges:
        for cp in range(start, end + 1):
            try:
                char = chr(cp)
                # Check if it's actually an emoji (has category So, Sm, or is in emoji range)
                hex_code = format(cp, 'X')
                if hex_code not in seen:
                    seen.add(hex_code)
                    emojis.append((char, hex_code))
            except:
                pass
    
    # Add flag emojis (regional indicators A-Z pairs)
    flag_base = 0x1F1E6  # 🇦
    country_codes = [
        ('US', 0x1F1FA, 0x1F1F8), ('IN', 0x1F1EE, 0x1F1F3),
        ('GB', 0x1F1EC, 0x1F1E7), ('DE', 0x1F1E9, 0x1F1EA),
        ('FR', 0x1F1EB, 0x1F1F7), ('JP', 0x1F1EF, 0x1F1F5),
        ('CN', 0x1F1E8, 0x1F1F3), ('KR', 0x1F1F0, 0x1F1F7),
        ('CA', 0x1F1E8, 0x1F1E6), ('AU', 0x1F1E6, 0x1F1FA),
        ('BR', 0x1F1E7, 0x1F1F7), ('IT', 0x1F1EE, 0x1F1F9),
        ('ES', 0x1F1EA, 0x1F1F8), ('MX', 0x1F1F2, 0x1F1FD),
        ('RU', 0x1F1F7, 0x1F1FA), ('NG', 0x1F1F3, 0x1F1EC),
    ]
    for name, cp1, cp2 in country_codes:
        char = chr(cp1) + chr(cp2)
        hex_code = f"{format(cp1, 'X')}-{format(cp2, 'X')}"
        emojis.append((char, hex_code))
    
    return emojis


# ── LAB conversion ───────────────────────────────────────────────────────────
def rgb_to_lab_single(r, g, b):
    rgb = np.array([[r, g, b]], dtype=np.float32) / 255.0
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
    L = 116 * xyz[0,1] - 16
    a = 500 * (xyz[0,0] - xyz[0,1])
    bv = 200 * (xyz[0,1] - xyz[0,2])
    return float(L), float(a), float(bv)


def compute_lab_centroid(img_rgba):
    """
    Compute LAB centroid of an emoji, ignoring transparent pixels.
    Returns (r, g, b, L, a, b_val) or None if emoji is mostly transparent.
    """
    arr = np.array(img_rgba, dtype=np.float32)
    alpha = arr[:, :, 3]
    mask = alpha > 30  # Only consider pixels with >30/255 opacity
    
    if mask.sum() < 10:
        return None  # Mostly empty
    
    # Weighted RGB centroid (alpha-weighted)
    weights = alpha[mask] / 255.0
    r_vals = arr[:, :, 0][mask]
    g_vals = arr[:, :, 1][mask]
    b_vals = arr[:, :, 2][mask]
    
    r_mean = float(np.average(r_vals, weights=weights))
    g_mean = float(np.average(g_vals, weights=weights))
    b_mean = float(np.average(b_vals, weights=weights))
    
    L, a_val, b_val = rgb_to_lab_single(r_mean, g_mean, b_mean)
    return r_mean, g_mean, b_mean, L, a_val, b_val


# ── Downloader ───────────────────────────────────────────────────────────────
def download_noto(hex_code):
    """Download from Noto Emoji 512px. Returns PIL Image or None."""
    parts = hex_code.lower().split('-')
    fname = 'emoji_u' + '_'.join(parts) + '.png'
    url = f"{NOTO_BASE}/{fname}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            return Image.open(io.BytesIO(r.read())).convert('RGBA')
    except:
        return None


def download_twemoji_svg(hex_code):
    """Download Twemoji SVG and rasterize to EMOJI_SIZE. Returns PIL Image or None."""
    if not HAS_CAIRO:
        return None
    code = hex_code.lower()
    url = f"{TWEMOJI_BASE}/{code}.svg"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            svg_data = r.read()
        png_data = cairosvg.svg2png(
            bytestring=svg_data,
            output_width=EMOJI_SIZE,
            output_height=EMOJI_SIZE
        )
        return Image.open(io.BytesIO(png_data)).convert('RGBA')
    except:
        return None


# ── Main ─────────────────────────────────────────────────────────────────────
def build_dataset():
    print("============================================================")
    print("Emoji HQ Dataset Builder")
    print("Target resolution: 512x512px")
    print(f"Sources: Noto Emoji (primary) -> Twemoji SVG (fallback)")
    print("============================================================")
    
    emojis = get_emoji_list()
    if MAX_EMOJIS:
        emojis = emojis[:MAX_EMOJIS]
    
    print(f"Total emojis to process: {len(emojis)}")
    
    rows = []
    ok_noto = 0
    ok_twemoji = 0
    failed = 0
    
    for i, (emoji_char, hex_code) in enumerate(emojis):
        png_path = os.path.join(OUTPUT_DIR, f"{hex_code}.png")
        
        # Skip if already downloaded
        if os.path.exists(png_path):
            try:
                img = Image.open(png_path).convert('RGBA')
                centroid = compute_lab_centroid(img)
                if centroid:
                    r, g, b, L, a_val, b_val = centroid
                    rows.append({
                        'emoji': emoji_char, 'hex': hex_code,
                        'r': round(r), 'g': round(g), 'b': round(b),
                        'l': round(L, 2), 'a_val': round(a_val, 2), 'b_val': round(b_val, 2)
                    })
                continue
            except:
                pass
        
        # Try Noto first
        img = download_noto(hex_code)
        source = 'noto'
        
        if img is None:
            # Fallback to Twemoji SVG
            img = download_twemoji_svg(hex_code)
            source = 'twemoji'
        
        if img is None:
            failed += 1
            if i % 50 == 0:
                print(f"  [{i}/{len(emojis)}] SKIP {hex_code} (not found in either source)")
            time.sleep(DELAY)
            continue
        
        # Resize to standard size
        if img.size != (EMOJI_SIZE, EMOJI_SIZE):
            img = img.resize((EMOJI_SIZE, EMOJI_SIZE), Image.Resampling.LANCZOS)
        
        # Compute LAB centroid
        centroid = compute_lab_centroid(img)
        if centroid is None:
            failed += 1
            time.sleep(DELAY)
            continue
        
        r, g, b, L, a_val, b_val = centroid
        
        # Save PNG
        img.save(png_path, 'PNG', optimize=False)
        
        rows.append({
            'emoji': emoji_char, 'hex': hex_code,
            'r': round(r), 'g': round(g), 'b': round(b),
            'l': round(L, 2), 'a_val': round(a_val, 2), 'b_val': round(b_val, 2)
        })
        
        if source == 'noto': ok_noto += 1
        else: ok_twemoji += 1
        
        if i % 10 == 0:
            print(f"  [{i}/{len(emojis)}] OK {emoji_char} ({hex_code}) via {source} | noto={ok_noto} twemoji={ok_twemoji} failed={failed}")
        
        time.sleep(DELAY)
    
    # Save CSV
    df = pd.DataFrame(rows)
    df.to_csv(CSV_PATH, index=False)
    
    print()
    print("=" * 60)
    print(f"✅ DONE!")
    print(f"  Noto Emoji downloaded: {ok_noto}")
    print(f"  Twemoji SVG rasterized: {ok_twemoji}")
    print(f"  Failed/skipped: {failed}")
    print(f"  Total in CSV: {len(rows)}")
    print(f"  PNGs saved to: {OUTPUT_DIR}/")
    print(f"  CSV saved to: {CSV_PATH}")
    print()
    print("Next steps:")
    print("  1. Copy emoji_pngs/ and data/emojis.csv to your backend")
    print("  2. Deploy — engine will use these 512x512 HQ emojis automatically")


if __name__ == '__main__':
    build_dataset()
