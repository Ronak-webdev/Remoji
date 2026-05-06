import sys
import os
import json
import urllib.request
import time
import concurrent.futures
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

def download_file(url, out_path, retries=1):
    for i in range(retries):
        try:
            # Add User-Agent to prevent 403
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                with open(out_path, 'wb') as f:
                    f.write(response.read())
            
            # Basic check if it's a valid PNG
            with Image.open(out_path) as img:
                img.verify()
            return True
        except:
            if os.path.exists(out_path):
                os.remove(out_path)
    return False

def process_single_emoji(item, sources, processed_hex):
    unified = item['unified'].upper()
    if unified in processed_hex: return None
    
    char = "".join([chr(int(x, 16)) for x in unified.split('-')])
    out_path = os.path.join(OUT_DIR, f"{unified}.png")
    
    # FORCE UPGRADE Check
    if os.path.exists(out_path):
        try:
            with Image.open(out_path) as img:
                if img.width >= 512:
                    avg = get_avg_color(out_path)
                    if avg:
                        return {'emoji': char, 'r': avg[0], 'g': avg[1], 'b': avg[2], 'hex': unified}
            os.remove(out_path)
        except:
            os.remove(out_path)

    # Download with variants
    variants = [unified]
    if "FE0F" in unified:
        variants.append(unified.replace("-FE0F", ""))
        
    for v in variants:
        for source_tpl, formatter in sources:
            url = source_tpl.format(formatter(v))
            if download_file(url, out_path):
                avg = get_avg_color(out_path)
                if avg:
                    return {'emoji': char, 'r': avg[0], 'g': avg[1], 'b': avg[2], 'hex': unified}
                break
    return None

def main():
    print("🚀 Starting TURBO Multithreaded Emoji Upgrade (512px Focus)...")
    
    if not os.path.exists(DATA_FULL_PATH):
        print("Error: emoji_data_full.json not found!")
        return

    with open(DATA_FULL_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Expand data
    expanded_data = []
    for item in data:
        expanded_data.append(item)
        if 'skin_variations' in item:
            for skin_key, skin_item in item['skin_variations'].items():
                expanded_data.append(skin_item)

    print(f"Total entries to process: {len(expanded_data)}")
    
    sources = [
        ("https://fonts.gstatic.com/s/e/notoemoji/latest/{}/512.png", lambda x: x.lower().replace("-fe0f", "")),
        ("https://raw.githubusercontent.com/gauravghongde/fluent-emoji/main/fluentui-emoji/assets/{}/Default/512.png", lambda x: x.lower()),
        ("https://raw.githubusercontent.com/iamcal/emoji-data/master/img-apple-160/{}.png", lambda x: x.lower()),
        ("https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72/{}.png", lambda x: x.lower())
    ]
    
    processed_hex = set()
    final_list = []
    
    # Using ThreadPoolExecutor for parallel downloads
    print("🔥 Downloading in parallel (15 threads)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        future_to_emoji = {executor.submit(process_single_emoji, item, sources, processed_hex): item for item in expanded_data}
        
        count = 0
        for future in concurrent.futures.as_completed(future_to_emoji):
            try:
                result = future.result()
                if result:
                    final_list.append(result)
                    count += 1
                    if count % 100 == 0:
                        print(f"  Progress: {count} emojis processed...")
            except Exception as e:
                pass

    # Save to CSV
    df = pd.DataFrame(final_list)
    df.to_csv(CSV_OUT, index=False)
    print(f"\n✅ TURBO COMPLETE! Total High-Res Emojis: {len(final_list)}")
    print(f"📁 PNGs: {OUT_DIR}")
    print(f"📁 CSV: {CSV_OUT}")

if __name__ == "__main__":
    main()
