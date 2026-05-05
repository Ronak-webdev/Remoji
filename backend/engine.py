import os
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import pillow_avif
from scipy.spatial import KDTree

class EmojiMosaicEngine:
    def __init__(self, dataset_path):
        # Load dataset
        self.df = pd.read_csv(dataset_path)
        self.emojis = self.df['emoji'].values
        # Normalize colors to 0-1
        self.emoji_rgb = self.df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
        
        # Build KDTree for ultra-fast color matching
        self.tree = KDTree(self.emoji_rgb)
        
        # Smart Font Handling for Cross-Platform (Windows/Linux/Cloud)
        self.font_path = self._find_emoji_font()
        self.cache = {}

    def _find_emoji_font(self):
        """Finds the best available emoji font on the current system"""
        # Always use the bundled font file we just downloaded
        local_font = os.path.join(os.path.dirname(__file__), "NotoColorEmoji.ttf")
        if os.path.exists(local_font):
            return local_font
            
        return None # Fallback just in case



    def get_best_emoji(self, rgb):
        """Find the closest emoji using KDTree (Euclidean distance in RGB)"""
        # Normalize input RGB
        rgb_norm = rgb / 255.0
        _, index = self.tree.query(rgb_norm)
        return self.emojis[index]

    def create_mosaic(self, input_path, output_path, config):
        """
        Generates a high-fidelity emoji mosaic with minimum, smart parameters.
        - quality: 1 (Draft) to 5 (Masterpiece)
        - emoji_size: Final size of emojis in px
        """
        quality = int(config.get('quality', 3))
        emoji_size = int(config.get('emoji_size', 16))
        
        print(f"--- Starting mosaic creation: quality={quality}, size={emoji_size} ---")
        
        # Load image
        img = Image.open(input_path).convert('RGB')
        w, h = img.size
        
        # Fidelity Scale (1-10):
        # q=1 -> 40 columns (Draft)
        # q=3 -> 80 columns (High Detail - NEW DEFAULT)
        # q=10 -> 220 columns (Extreme Masterpiece)
        target_cols = 20 + (quality * 20)
        
        # Calculate window size to hit our target columns
        analysis_window = max(1, w // target_cols)
        
        cols = w // analysis_window
        rows = h // analysis_window
        
        # Resize image to the grid size for bulk processing
        img_small = img.resize((cols, rows), Image.Resampling.LANCZOS)
        # Enhance contrast slightly to make colors pop
        img_small = ImageEnhance.Contrast(img_small).enhance(1.1)
        pixels = np.array(img_small)
        
        # Free up memory from small image after getting pixels
        del img_small
        
        # Output canvas dimensions (2x scale for high-quality zoom)
        out_w = cols * emoji_size * 2
        out_h = rows * emoji_size * 2
        
        # Create high-res canvas (Opaque background to prevent invisible images if emojis fail to load)
        output = Image.new('RGBA', (out_w, out_h), (245, 245, 245, 255))
        draw = ImageDraw.Draw(output)
        
        # Load font - scaled to fit emoji_size (with 2x scaling)
        try:
            # Overlap emojis slightly (1.2x) to prevent gaps and create a rich texture
            font = ImageFont.truetype(self.font_path, int(emoji_size * 2 * 1.2))
        except:
            font = ImageFont.load_default()

        # Generate mosaic
        for r in range(rows):
            for c in range(cols):
                rgb = pixels[r, c]
                
                # Process every pixel for full coverage
                emoji = self.get_best_emoji(rgb)
                
                x = c * emoji_size * 2
                y = r * emoji_size * 2
                
                # Draw the emoji with embedded color support
                draw.text((x, y), emoji, font=font, embedded_color=True)
        
        # Convert back to RGB or keep RGBA if needed
        print(f"--- Saving final output to {output_path} ---")
        output.save(output_path, "PNG")
        return output_path
