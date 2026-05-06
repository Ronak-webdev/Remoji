import os
import csv
import sys
import urllib.request
import time

# Fix Windows terminal encoding
sys.stdout.reconfigure(encoding='utf-8')


CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "emojis.csv")
OUT_DIR  = os.path.join(os.path.dirname(__file__), "emoji_pngs")

os.makedirs(OUT_DIR, exist_ok=True)

def emoji_to_filename(emoji_char):
    """Convert emoji to Apple-style filename (lower case hex)."""
    result = []
    for ch in emoji_char:
        cp = ord(ch)
        if cp in (0xFE0F, 0xFE0E): continue
        result.append(format(cp, 'x'))
    return '-'.join(result)

def get_apple_emoji_url(filename):
    # Apple 160x160 high quality PNGs from iamcal/emoji-data
    return f"https://raw.githubusercontent.com/iamcal/emoji-data/master/img-apple-160/{filename}.png"

# Read unique emojis from CSV
unique_emojis = set()
if os.path.exists(CSV_PATH):
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            unique_emojis.add(row['emoji'])

print(f"Found {len(unique_emojis)} unique emojis in CSV. Starting High-Res Download...")

success = 0
failed = []

for emoji_char in unique_emojis:
    filename = emoji_to_filename(emoji_char)
    out_path = os.path.join(OUT_DIR, f"{filename}.png")
    
    if os.path.exists(out_path):
        success += 1
        continue
    
    url = get_apple_emoji_url(filename)
    try:
        urllib.request.urlretrieve(url, out_path)
        success += 1
        if success % 50 == 0:
            print(f"  Progress: {success} downloaded...")
    except Exception as e:
        # Some variation selectors or combinations might fail, we try without variation
        failed.append((emoji_char, filename))
    
    time.sleep(0.02) # Fast download

print(f"\n✅ High-Res Downloaded: {success}")
print(f"❌ Failed: {len(failed)}")
