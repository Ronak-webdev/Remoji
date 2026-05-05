import os
import pandas as pd
import numpy as np
from PIL import Image

# Paths
RAW_CSV_PATH = os.path.join("data", "openmoji_raw.csv")
PNG_DIR = os.path.join("backend", "emoji_pngs")
OUTPUT_CSV_PATH = os.path.join("data", "emojis.csv")

def get_average_color(base_png_path):
    try:
        # The base_png_path uses lowercase and _ as requested by the user
        # But the actual files on disk use uppercase and -
        # We'll try various combinations to be robust
        
        filename = os.path.basename(base_png_path)
        hex_part = os.path.splitext(filename)[0]
        
        variants = [
            hex_part,                   # 1f600
            hex_part.upper(),           # 1F600
            hex_part.replace('_', '-'), # 1f600-200d...
            hex_part.upper().replace('_', '-') # 1F600-200D...
        ]
        
        actual_path = None
        for v in variants:
            p = os.path.join(PNG_DIR, f"{v}.png")
            if os.path.exists(p):
                actual_path = p
                break
        
        if not actual_path:
            return (128, 128, 128), False
        
        with Image.open(actual_path) as img:
            img = img.convert("RGBA")
            data = np.array(img)
            
            # Reshape to (N, 4)
            pixels = data.reshape(-1, 4)
            
            # Use RGB channels
            rgb = pixels[:, :3]
            # Drop near-black/transparent pixels
            mask = np.all(rgb >= 10, axis=1)
            
            if not np.any(mask):
                # If all pixels are dark, just take the mean of everything
                mean_color = rgb.mean(axis=0)
            else:
                mean_color = rgb[mask].mean(axis=0)
                
            return tuple(mean_color.astype(int)), True
    except Exception as e:
        # print(f"Error processing {base_png_path}: {e}")
        return (128, 128, 128), False

def generate():
    if not os.path.exists(RAW_CSV_PATH):
        print(f"Error: {RAW_CSV_PATH} not found!")
        return

    print(f"Reading {RAW_CSV_PATH}...")
    # OpenMoji CSV downloaded via curl in Step 1 was comma-separated
    df_raw = pd.read_csv(RAW_CSV_PATH, sep=',', encoding='utf-8')
    
    if 'emoji' not in df_raw.columns:
        print(f"Columns found: {list(df_raw.columns)}")
        print("Error: 'emoji' column not found! Check the CSV format.")
        return

    # Ensure emoji column is string and not empty
    df_raw = df_raw[df_raw['emoji'].notna() & (df_raw['emoji'] != "")]
    
    results = []
    real_png_count = 0
    fallback_count = 0
    
    total = len(df_raw)
    print(f"Processing {total} emojis...")
    
    for i, (idx, row) in enumerate(df_raw.iterrows()):
        emoji_char = row['emoji']
        hexcode_raw = str(row['hexcode']).lower()
        # OpenMoji naming rule: use _ as separator for sequences
        hexcode_norm = hexcode_raw.replace('-', '_')
        name = row['annotation']
        
        png_path = os.path.join(PNG_DIR, f"{hexcode_norm}.png")
        
        color, is_real = get_average_color(png_path)
        
        if is_real:
            real_png_count += 1
        else:
            fallback_count += 1
            
        results.append({
            'emoji': emoji_char,
            'hexcode': hexcode_norm,
            'r': color[0],
            'g': color[1],
            'b': color[2],
            'name': name
        })
        
        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{total}...")

    df_out = pd.DataFrame(results)
    df_out.to_csv(OUTPUT_CSV_PATH, index=False)
    
    print("\nSummary:")
    print(f"Total rows: {len(df_out)}")
    print(f"Real PNGs found: {real_png_count}")
    print(f"Fallbacks used: {fallback_count}")
    print(f"Output saved to: {OUTPUT_CSV_PATH}")

if __name__ == "__main__":
    generate()
