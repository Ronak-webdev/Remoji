import os
import pandas as pd
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

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

def fix_colors():
    df = pd.read_csv('../data/emojis.csv')
    png_dir = 'emoji_pngs'
    
    for idx, row in df.iterrows():
        code = row['hex']
        png_path = os.path.join(png_dir, f"{code}.png")
        if not os.path.exists(png_path):
            continue
            
        try:
            img = Image.open(png_path).convert('RGBA')
            img = img.resize((32, 32), Image.Resampling.NEAREST)
            arr = np.array(img, dtype=np.float32)
            alpha = arr[:, :, 3]
            mask = alpha > 128
            
            pixels = arr[mask][:, :3]
            if len(pixels) > 10:
                kmeans = KMeans(n_clusters=2, n_init=1).fit(pixels)
                counts = np.bincount(kmeans.labels_)
                dom = kmeans.cluster_centers_[np.argmax(counts)]
                
                r_dom, g_dom, b_dom = dom[0], dom[1], dom[2]
                L, a_val, b_val = rgb_to_lab_single(r_dom, g_dom, b_dom)
                
                df.at[idx, 'r'] = round(r_dom)
                df.at[idx, 'g'] = round(g_dom)
                df.at[idx, 'b'] = round(b_dom)
                df.at[idx, 'l'] = round(L, 2)
                df.at[idx, 'a_val'] = round(a_val, 2)
                df.at[idx, 'b_val'] = round(b_val, 2)
        except Exception as e:
            pass
            
    df.to_csv('../data/emojis.csv', index=False)
    print("Fixed CSV colors using KMeans Dominant Color!")

if __name__ == '__main__':
    fix_colors()
