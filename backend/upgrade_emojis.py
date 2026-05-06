import sys
import os
import json
import urllib.request
import time
from PIL import Image
import pandas as pd
import numpy as np

# Fix Windows terminal encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FULL_PATH = os.path.join(BASE_DIR, "emoji_data_full.json")
OUT_DIR = os.path.join(BASE_DIR, "emoji_pngs")
CSV_OUT = os.path.join(BASE_DIR, "..", "data", "emojis.csv")

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)

def get_avg_color(img_path):
    try:
        # If file is too small, it's likely corrupt
        if os.path.getsize(img_path) < 100:
            return None
            
        img = Image.open(img_path).convert('RGBA')
        np_img = np.array(img)
        alpha = np_img[:, :, 3]
        rgb = np_img[:, :, :3]
        
        mask = alpha > 100
        if not np.any(mask):
            return (200, 200, 200)
            
        avg_color = rgb[mask].mean(axis=0)
        return tuple(avg_color.astype(int))
    except Exception:
        return None

def download_file(url, out_path, retries=2):
    for i in range(retries):
        try:
            urllib.request.urlretrieve(url, out_path)
            # Basic check if it's a valid PNG
            with Image.open(out_path) as img:
                img.verify()
            return True
        except:
            if os.path.exists(out_path):
                os.remove(out_path)
            time.sleep(0.5)
    return False

def main():
    print("🚀 Starting ULTIMATE Master Emoji Upgrade (Skin Tones + Multi-Source)...")
    
    if not os.path.exists(DATA_FULL_PATH):
        print("Error: emoji_data_full.json not found!")
        return

    with open(DATA_FULL_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    emoji_list = []
    processed_hex = set()
    success = 0

    # Expand data to include skin variations
    expanded_data = []
    for item in data:
        expanded_data.append(item)
        if 'skin_variations' in item:
            for skin_key, skin_item in item['skin_variations'].items():
                expanded_data.append(skin_item)

    print(f"Total entries to process (including skin variations): {len(expanded_data)}")

    # Sources in order of preference
    # 1. Google Noto (512x512) - BEST QUALITY
    # 2. JoyPixels (512x512 / fallback 128)
    # 3. Apple (160x160)
    # 4. Twemoji (72x72)
    sources = [
        ("https://fonts.gstatic.com/s/e/notoemoji/latest/{}/512.png", lambda x: x.lower().replace("-fe0f", "")),
        ("https://raw.githubusercontent.com/joypixels/emoji-assets/master/png/512/{}.png", lambda x: x.lower()),
        ("https://raw.githubusercontent.com/iamcal/emoji-data/master/img-apple-160/{}.png", lambda x: x.lower()),
        ("https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72/{}.png", lambda x: x.lower())
    ]
    
    for item in expanded_data:
        unified = item['unified'].upper()
        if unified in processed_hex: continue
        
        char = "".join([chr(int(x, 16)) for x in unified.split('-')])
        out_path = os.path.join(OUT_DIR, f"{unified}.png")
        
        # If file exists and is valid, skip
        if os.path.exists(out_path):
            avg = get_avg_color(out_path)
            if avg is not None:
                emoji_list.append({'emoji': char, 'r': avg[0], 'g': avg[1], 'b': avg[2], 'hex': unified})
                processed_hex.add(unified)
                continue
            else:
                os.remove(out_path)

        # Try to download
        downloaded = False
        # Try both with and without FE0F if primary fails
        variants = [unified]
        if "FE0F" in unified:
            variants.append(unified.replace("-FE0F", ""))
            
        for v in variants:
            for source_tpl, formatter in sources:
                url = source_tpl.format(formatter(v))
                if download_file(url, out_path):
                    downloaded = True
                    break
            if downloaded: break
            
        if downloaded:
            avg = get_avg_color(out_path)
            if avg:
                emoji_list.append({'emoji': char, 'r': avg[0], 'g': avg[1], 'b': avg[2], 'hex': unified})
                processed_hex.add(unified)
                success += 1
                if len(emoji_list) % 100 == 0:
                    print(f"  Progress: {len(emoji_list)} emojis... (New: {success})")

    # Save to CSV
    df = pd.DataFrame(emoji_list)
    df.to_csv(CSV_OUT, index=False)
    print(f"\n✅ COMPLETE! Final High-Res Dataset Size: {len(emoji_list)}")
    print(f"📁 PNGs: {OUT_DIR}")
    print(f"📁 CSV: {CSV_OUT}")

if __name__ == "__main__":
    main()
