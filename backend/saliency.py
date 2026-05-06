def compute_saliency_map(pil_image):
    import cv2
    import numpy as np
    img_np = np.array(pil_image.convert('RGB'))
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(gx**2 + gy**2)
    blurred = cv2.GaussianBlur(magnitude, (31, 31), 0)
    if blurred.max() > 0:
        blurred = blurred / blurred.max()
    return blurred.astype(np.float32)
