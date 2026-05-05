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
    """Convert emoji character to Twemoji filename (hex codepoints joined by -)."""
    codepoints = []
    i = 0
    chars = list(emoji_char)
    result = []
    # Walk through codepoints, skip variation selectors (FE0F) and ZWJ
    for ch in emoji_char:
        cp = ord(ch)
        if cp == 0xFE0F:   # variation selector - skip
            continue
        result.append(format(cp, 'x'))
    return '-'.join(result)

def get_twemoji_url(filename):
    return f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{filename}.png"

# Read unique emojis from CSV
unique_emojis = set()
with open(CSV_PATH, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        unique_emojis.add(row['emoji'])

print(f"Found {len(unique_emojis)} unique emojis in CSV. Starting download...")

success = 0
failed = []

for emoji_char in unique_emojis:
    filename = emoji_to_filename(emoji_char)
    out_path = os.path.join(OUT_DIR, f"{filename}.png")
    
    if os.path.exists(out_path):
        success += 1
        continue  # Already downloaded
    
    url = get_twemoji_url(filename)
    try:
        urllib.request.urlretrieve(url, out_path)
        success += 1
        print(f"  ✓ {emoji_char} -> {filename}.png")
    except Exception as e:
        failed.append((emoji_char, filename, str(e)))
        print(f"  ✗ {emoji_char} -> {filename}.png  ({e})")
    
    time.sleep(0.05)  # Be polite to CDN

print(f"\n✅ Downloaded: {success}")
print(f"❌ Failed: {len(failed)}")
if failed:
    print("\nFailed emojis (will use color-fill fallback):")
    for emoji_char, filename, err in failed:
        print(f"  {emoji_char}  ({filename})  -> {err}")
