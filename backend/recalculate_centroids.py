import os
import csv
import numpy as np
from PIL import Image

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "emojis.csv")
OUT_DIR = os.path.join(os.path.dirname(__file__), "emoji_pngs")

def rgb_to_lab(r, g, b):
    """Accurate sRGB to CIELAB conversion."""
    # Normalize RGB
    r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
    
    # Inverse gamma
    r_l = ((r_n + 0.055) / 1.055) ** 2.4 if r_n > 0.04045 else r_n / 12.92
    g_l = ((g_n + 0.055) / 1.055) ** 2.4 if g_n > 0.04045 else g_n / 12.92
    b_l = ((b_n + 0.055) / 1.055) ** 2.4 if b_n > 0.04045 else b_n / 12.92
    
    # Matrix mult for XYZ (D65)
    x = (r_l * 0.4124 + g_l * 0.3576 + b_l * 0.1805) * 100
    y = (r_l * 0.2126 + g_l * 0.7152 + b_l * 0.0722) * 100
    z = (r_l * 0.0193 + g_l * 0.1192 + b_l * 0.9505) * 100
    
    # XYZ to LAB (D65 reference white)
    x_n, y_n, z_n = 95.047, 100.000, 108.883
    x_r, y_r, z_r = x / x_n, y / y_n, z / z_n
    
    epsilon = 0.008856
    kappa = 903.3
    
    f_x = x_r ** (1/3) if x_r > epsilon else (kappa * x_r + 16) / 116
    f_y = y_r ** (1/3) if y_r > epsilon else (kappa * y_r + 16) / 116
    f_z = z_r ** (1/3) if z_r > epsilon else (kappa * z_r + 16) / 116
    
    l = max(0, 116 * f_y - 16)
    a = 500 * (f_x - f_y)
    b_val = 200 * (f_y - f_z)
    
    return l, a, b_val

def get_average_rgb(img_path):
    """Calculates the average RGB color of an image blended on a white background.
       This accurately represents what the emoji looks like when pasted in the mosaic."""
    try:
        with Image.open(img_path) as img:
            img = img.convert("RGBA")
            
            # Create a white background
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            
            # Paste the emoji onto the white background using its own alpha as a mask
            bg.paste(img, (0, 0), img)
            
            # Convert to RGB (dropping the now-useless alpha channel)
            blended = bg.convert("RGB")
            data = np.array(blended)
            
            # Calculate the true average of the entire square
            avg_r, avg_g, avg_b = np.mean(data, axis=(0, 1))
            
            return int(avg_r), int(avg_g), int(avg_b)
    except Exception as e:
        print(f"Error processing {img_path}: {e}")
        return None, None, None

def emoji_to_filename(emoji_char):
    result = []
    for ch in emoji_char:
        cp = ord(ch)
        if cp in (0xFE0F, 0xFE0E): continue
        result.append(format(cp, 'x'))
    return '-'.join(result)

def recalculate():
    if not os.path.exists(CSV_PATH):
        print(f"CSV not found at {CSV_PATH}")
        return

    updated_rows = []
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if 'l' not in fieldnames:
            fieldnames.extend(['l', 'a_val', 'b_val']) # Adding LAB columns explicitly to CSV
            
        for row in reader:
            filename = emoji_to_filename(row['emoji'])
            img_path = os.path.join(OUT_DIR, f"{filename}.png")
            
            if os.path.exists(img_path):
                avg_r, avg_g, avg_b = get_average_rgb(img_path)
                if avg_r is not None:
                    row['r'] = str(avg_r)
                    row['g'] = str(avg_g)
                    row['b'] = str(avg_b)
                    
                    l, a, b = rgb_to_lab(avg_r, avg_g, avg_b)
                    row['l'] = str(round(l, 4))
                    row['a_val'] = str(round(a, 4))
                    row['b_val'] = str(round(b, 4))
            
            # If image doesn't exist, we keep the original RGB, but still calculate LAB
            else:
                r, g, b = int(row['r']), int(row['g']), int(row['b'])
                l, a, b_val = rgb_to_lab(r, g, b)
                row['l'] = str(round(l, 4))
                row['a_val'] = str(round(a, 4))
                row['b_val'] = str(round(b_val, 4))

            updated_rows.append(row)

    # Write back to CSV
    with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
        
    print(f"Recalculated centroids for {len(updated_rows)} emojis and updated emojis.csv")

if __name__ == "__main__":
    recalculate()
