import numpy as np
import pandas as pd
from skimage.color import rgb2lab, deltaE_ciede2000

def filter_diverse_emojis(df, min_delta_e=8.0):
    """
    From the full emoji dataset, keep only emojis that are perceptually
    distinct from each other by at least min_delta_e CIEDE2000 units.
    
    Also remove emojis that are near-black or near-white with delta_e < 3
    from (0,0,0) or (255,255,255) UNLESS there are fewer than 10 such emojis
    (we still want some dark/light ones, just not 200 of them).
    
    Algorithm: Greedy farthest-point selection
    1. Start with the emoji closest to pure red (arbitrary seed)
    2. At each step, add the emoji that is farthest (in CIEDE2000) from
       all already-selected emojis
    3. Stop when remaining emojis are all within min_delta_e of some selected one
    
    Returns filtered DataFrame.
    """
    rgb_values = df[['r', 'g', 'b']].values.astype(np.float32) / 255.0
    # Convert to LAB
    lab_values = rgb2lab(rgb_values.reshape(-1, 1, 3)).reshape(-1, 3)
    
    n = len(df)
    selected = []
    remaining = list(range(n))
    
    # Seed: pick emoji closest to middle gray (128, 128, 128) as neutral start
    gray_lab = rgb2lab(np.array([[[0.5, 0.5, 0.5]]])).reshape(3)
    dists_to_gray = np.array([
        deltaE_ciede2000(gray_lab.reshape(1,1,3), lab_values[i].reshape(1,1,3))[0,0]
        for i in remaining
    ])
    seed = remaining[np.argmin(dists_to_gray)]
    selected.append(seed)
    remaining.remove(seed)
    
    # Greedy farthest point
    min_dist_to_selected = np.full(n, np.inf)
    
    while remaining:
        last = selected[-1]
        for i in remaining:
            d = deltaE_ciede2000(
                lab_values[last].reshape(1,1,3),
                lab_values[i].reshape(1,1,3)
            )[0,0]
            if d < min_dist_to_selected[i]:
                min_dist_to_selected[i] = d
        
        # Find remaining emoji farthest from all selected
        best_i = max(remaining, key=lambda i: min_dist_to_selected[i])
        
        # Stop if even the farthest is too close
        if min_dist_to_selected[best_i] < min_delta_e:
            break
            
        selected.append(best_i)
        remaining.remove(best_i)
    
    print(f"Filtered: {n} emojis → {len(selected)} diverse emojis (min ΔE={min_delta_e})")
    return df.iloc[selected].reset_index(drop=True)
