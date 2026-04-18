"""
Image difference detection using SSIM (Structural Similarity Index).
Computes similarity scores and identifies bounding boxes for changed regions.
"""

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from PIL import Image
import io


def compute_ssim_and_mask(old_bytes, new_bytes):
    """
    Compute SSIM score and difference mask between two images.
    
    Args:
        old_bytes: bytes of the original image
        new_bytes: bytes of the new image
    
    Returns:
        tuple: (ssim_score, bounding_boxes, old_image, new_image)
            - ssim_score: float between 0 and 1 (1 = identical)
            - bounding_boxes: list of dicts with changed region coordinates
            - old_image: numpy array of old image (grayscale)
            - new_image: numpy array of new image (grayscale)
    """
    # Load images from bytes
    old_img = Image.open(io.BytesIO(old_bytes))
    new_img = Image.open(io.BytesIO(new_bytes))
    
    # Convert to grayscale numpy arrays
    old_gray = np.array(old_img.convert('L'))
    new_gray = np.array(new_img.convert('L'))
    
    # Resize images to match if dimensions differ
    if old_gray.shape != new_gray.shape:
        new_img_resized = new_img.resize(old_img.size, Image.Resampling.LANCZOS)
        new_gray = np.array(new_img_resized.convert('L'))
    
    # Compute SSIM
    score, diff = ssim(old_gray, new_gray, full=True)
    
    # Convert difference image to uint8
    diff = (diff * 255).astype("uint8")
    
    # Threshold the difference image to create binary mask
    thresh = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    
    # Find bounding boxes
    boxes = find_changed_regions(thresh, min_area=100)
    
    return score, boxes, old_gray, new_gray


def find_changed_regions(diff_mask, min_area=100):
    """
    Find bounding boxes around changed regions in the difference mask.
    
    Args:
        diff_mask: binary difference mask
        min_area: minimum contour area to consider (filters noise)
    
    Returns:
        list: bounding boxes as dicts with x, y, width, height, area
    """
    # Find contours in the difference mask
    contours, _ = cv2.findContours(diff_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    boxes = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area >= min_area:
            x, y, w, h = cv2.boundingRect(contour)
            boxes.append({
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "area": int(area)
            })
    
    return boxes


def summarize_change(score, boxes):
    """
    Generate a human-readable summary of the detected changes.
    
    Args:
        score: SSIM score (0-1)
        boxes: list of bounding box dicts
    
    Returns:
        str: human-readable summary
    """
    # Determine change level based on SSIM score
    if score >= 0.95:
        change_level = "minimal"
    elif score >= 0.85:
        change_level = "minor"
    elif score >= 0.70:
        change_level = "moderate"
    else:
        change_level = "significant"
    
    summary = f"Detected {change_level} changes (SSIM: {score:.4f}). "
    summary += f"Found {len(boxes)} changed region(s). "
    
    if boxes:
        total_area = sum(b["area"] for b in boxes)
        summary += f"Total changed area: {total_area} pixels."
    
    return summary
