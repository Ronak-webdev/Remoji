import os
import pandas as pd
import numpy as np
from PIL import Image
import sys

# Set encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PNG_DIR = os.path.join(BACKEND_DIR, "emoji_pngs")
CSV_PATH = os.path.join(BACKEND_DIR, "data", "openmoji_raw.csv")
OUTPUT_CSV = os.path.join(BACKEND_DIR, "data", "emojis.csv")

def get_average_color(image_path):
    try:
        with Image.open(image_path) as img:
            img = img.convert('RGBA')
            pixels = np.array(img)  # shape H×W×4
            mask = pixels[:, :, 3] > 10  # non-transparent pixels
            if mask.sum() == 0:
                return None
            rgb_pixels = pixels[mask][:, :3]  # only RGB of visible pixels
            return rgb_pixels.mean(axis=0).astype(int)
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None

def main():
    print(f"Loading metadata from {CSV_PATH}...")
    # OpenMoji CSV is tab-separated or comma? 
    # Based on previous 'type' output, it looks like comma-separated but can have quoted strings.
    df = pd.read_csv(CSV_PATH, sep=',', encoding='utf-8')
    
    # Filter to only rows that have a corresponding PNG
    # Filenames in PNG_DIR are uppercase hexcode + .png
    # But some hexcodes in CSV are lowercase? Or have different hyphenation?
    # Let's check a few.
    
    processed_data = []
    
    print("Processing images...")
    count = 0
    for _, row in df.iterrows():
        emoji_char = row['emoji']
        hex_code = str(row['hexcode']).upper()
        
        # Try finding the file
        # 1. Direct match
        png_path = os.path.join(PNG_DIR, f"{hex_code}.png")
        
        # 2. Match with FE0F if missing in hex_code but present in filename
        # (Some OpenMoji files use the full emoji representation)
        if not os.path.exists(png_path):
            # Try lowercase just in case
            png_path = os.path.join(PNG_DIR, f"{hex_code.lower()}.png")
            
        if not os.path.exists(png_path):
            continue
            
        avg_rgb = get_average_color(png_path)
        if avg_rgb is not None:
            processed_data.append({
                'emoji': emoji_char,
                'r': avg_rgb[0],
                'g': avg_rgb[1],
                'b': avg_rgb[2],
                'hex': hex_code # Keep hex for later if needed
            })
            count += 1
            if count % 500 == 0:
                print(f"  Processed {count} emojis...")

    print(f"Total processed: {count}")
    
    if not processed_data:
        print("ERROR: No data processed!")
        return
        
    out_df = pd.DataFrame(processed_data)
    # Reorder to match engine expectations: emoji, r, g, b, hex
    out_df[['emoji', 'r', 'g', 'b', 'hex']].to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
    print(f"Saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
