import os
import sys
# Add backend dir to path
sys.path.append(os.path.join(os.getcwd(), "backend"))
from engine import EmojiMosaicEngine

DATA_DIR = os.path.join(os.getcwd(), "data")
CSV_PATH = os.path.join(DATA_DIR, "emojis.csv")

if not os.path.exists(CSV_PATH):
    print(f"Error: {CSV_PATH} not found!")
    sys.exit(1)

try:
    engine = EmojiMosaicEngine(CSV_PATH)
    print("\n--- Test Results ---")
    print("Engine initialization successful!")
    # Test a lookup
    idx = engine.get_best_emoji_index((255, 0, 0))
    print(f"Best emoji for Red (255,0,0): {engine.emojis[idx]} (index {idx})")
    
    # Test sprite load
    sprite = engine._get_sprite(idx, 16)
    print(f"Sprite loaded: {sprite.size} {sprite.mode}")
    
except Exception as e:
    print(f"Engine test failed: {e}")
    import traceback
    traceback.print_exc()
