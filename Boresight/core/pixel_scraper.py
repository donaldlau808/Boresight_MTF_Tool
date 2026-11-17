import os
import cv2
import glob
import warnings
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def create_crosshair_masks(bgr_img: np.ndarray, active_colors: dict, stroke_dil: int, line_dil: int) -> tuple[np.ndarray, np.ndarray]:
    b = bgr_img[:, :, 0].astype(int); g = bgr_img[:, :, 1].astype(int); r = bgr_img[:, :, 2].astype(int)
    orange_mask = np.zeros(bgr_img.shape[:2], dtype=np.uint8)
    green_mask = np.zeros(bgr_img.shape[:2], dtype=np.uint8)
    white_mask = np.zeros(bgr_img.shape[:2], dtype=np.uint8)

    if active_colors.get('orange'): orange_mask = ((r > 140) & (b < 100) & ((r - b) > 50)).astype(np.uint8)
    if active_colors.get('green'): green_mask = ((g > 140) & (r < 100) & (b < 100) & ((g - r) > 40)).astype(np.uint8)
    if active_colors.get('white'): white_mask = ((r > 220) & (g > 220) & (b > 220) & (np.abs(r - g) < 20) & (np.abs(g - b) < 20)).astype(np.uint8)
    
    raw_mask = orange_mask | green_mask | white_mask
    kernel_stroke = np.ones((int(stroke_dil), int(stroke_dil)), np.uint8)
    kernel_line = np.ones((int(line_dil), int(line_dil)), np.uint8)
    
    safe_green_white = cv2.dilate(green_mask | white_mask, kernel_stroke, iterations=1)
    safe_orange = cv2.dilate(orange_mask, kernel_line, iterations=1)
    return raw_mask, safe_green_white | safe_orange

def get_clean_profile(img_gray: np.ndarray, safe_mask: np.ndarray, y1: int, y2: int, x1: int, x2: int, axis: int = 0) -> np.ndarray:
    roi_gray = img_gray[y1:y2, x1:x2].astype(float)
    roi_mask = safe_mask[y1:y2, x1:x2]
    roi_gray[roi_mask > 0] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmean(roi_gray, axis=axis)

def extract_mast_center_edges(profile: np.ndarray, offset_x: int, mode: str, min_prominence: float) -> tuple:
    nans = np.isnan(profile)
    if np.all(nans): return None, None, None
    x_vals = np.arange(len(profile))
    if np.any(nans): profile[nans] = np.interp(x_vals[nans], x_vals[~nans], profile[~nans])
    kernel = np.ones(3) / 3.0
    smoothed = np.convolve(profile, kernel, mode='same')
    smoothed[0], smoothed[-1] = profile[0], profile[-1]
    bg = np.median(smoothed)
    if mode == 'max': 
        peak_idx = np.argmax(smoothed)
        prominence = smoothed[peak_idx] - bg
        thresh = bg + 0.5 * prominence
    else:            
        peak_idx = np.argmin(smoothed)
        prominence = bg - smoothed[peak_idx]
        thresh = bg - 0.5 * prominence
    if prominence < min_prominence: return None, None, None
    left_idx, right_idx = peak_idx, peak_idx
    while left_idx > 0 and ((mode == 'max' and smoothed[left_idx] > thresh) or (mode == 'min' and smoothed[left_idx] < thresh)): left_idx -= 1
    while right_idx < len(smoothed) - 1 and ((mode == 'max' and smoothed[right_idx] > thresh) or (mode == 'min' and smoothed[right_idx] < thresh)): right_idx += 1
    def get_crossing(x_in, x_out):
        y_in, y_out = smoothed[x_in], smoothed[x_out]
        return x_in if y_in == y_out else x_in + (thresh - y_in) / (y_out - y_in)
    left_edge = get_crossing(left_idx + 1, left_idx) if left_idx < peak_idx else float(left_idx)
    right_edge = get_crossing(right_idx - 1, right_idx) if right_idx > peak_idx else float(right_idx)
    return float(offset_x + (left_edge + right_edge) / 2.0), float(offset_x + left_edge), float(offset_x + right_edge)

def extract_horizon_elevation(profile: np.ndarray, offset_y: int, mode: str, min_grad: float):
    nans = np.isnan(profile)
    if np.all(nans): return None
    y_vals = np.arange(len(profile))
    if np.any(nans): profile[nans] = np.interp(y_vals[nans], y_vals[~nans], profile[~nans])
    kernel = np.ones(5) / 5.0
    smoothed = np.convolve(profile, kernel, mode='same')
    smoothed[:2], smoothed[-2:] = profile[:2], profile[-2:]
    grad = np.gradient(smoothed)
    peak_idx = np.argmax(grad) if mode == 'max' else np.argmin(grad)
    if abs(grad[peak_idx]) < min_grad: return None
    if 1 <= peak_idx < len(grad) - 1:
        xs = np.array([peak_idx - 1, peak_idx, peak_idx + 1])
        poly = np.polyfit(xs, grad[xs], 2)
        if (mode == 'max' and poly[0] < 0) or (mode == 'min' and poly[0] > 0): return float(offset_y + (-poly[1] / (2.0 * poly[0])))
    return float(offset_y + peak_idx)

def extract_eon_features(bgr_img: np.ndarray, gray_img: np.ndarray, active_colors: dict, cfg: dict):
    raw_mask, safe_mask = create_crosshair_masks(bgr_img, active_colors, cfg['stroke_dilation'], cfg['line_dilation'])
    profile_x = get_clean_profile(gray_img, safe_mask, cfg['search_y_min_eon'], cfg['search_y_max_eon'], cfg['roi_x_min'], cfg['roi_x_max'], axis=0)
    mast_x, left_edge, right_edge = extract_mast_center_edges(profile_x, cfg['roi_x_min'], 'min', cfg['min_mast_prominence'])
    if mast_x is None: return None, None, None, None, safe_mask
    profile_y = get_clean_profile(gray_img, safe_mask, cfg['horizon_y_min'], cfg['horizon_y_max'], cfg['horizon_x_min'], cfg['horizon_x_max'], axis=1)
    horizon_y = extract_horizon_elevation(profile_y, cfg['horizon_y_min'], 'min', cfg['min_horizon_gradient'])
    if horizon_y is None: return None, None, None, None, safe_mask
    return float(mast_x), float(left_edge), float(right_edge), float(horizon_y), safe_mask

def extract_mwir_features(bgr_img: np.ndarray, gray_img: np.ndarray, active_colors: dict, cfg: dict):
    raw_mask, safe_mask = create_crosshair_masks(bgr_img, active_colors, cfg['stroke_dilation'], cfg['line_dilation'])
    profile_x = get_clean_profile(gray_img, safe_mask, cfg['search_y_min_mwir'], cfg['search_y_max_mwir'], cfg['roi_x_min'], cfg['roi_x_max'], axis=0)
    mast_x, left_edge, right_edge = extract_mast_center_edges(profile_x, cfg['roi_x_min'], 'max', cfg['min_mast_prominence'])
    if mast_x is None: return None, None, None, None, safe_mask
    profile_y = get_clean_profile(gray_img, safe_mask, cfg['horizon_y_min'], cfg['horizon_y_max'], cfg['horizon_x_min'], cfg['horizon_x_max'], axis=1)
    horizon_y = extract_horizon_elevation(profile_y, cfg['horizon_y_min'], 'max', cfg['min_horizon_gradient'])
    if horizon_y is None: return None, None, None, None, safe_mask
    return float(mast_x), float(left_edge), float(right_edge), float(horizon_y), safe_mask

def _clip_box(box, img_w, img_h):
    x_min, x_max, y_min, y_max = box
    x_min_c = max(0, min(x_min, img_w - 2))
    x_max_c = max(x_min_c + 1, min(x_max, img_w))
    y_min_c = max(0, min(y_min, img_h - 2))
    y_max_c = max(y_min_c + 1, min(y_max, img_h))
    return (x_min_c, x_max_c, y_min_c, y_max_c)

def plot_mask_diagnostic_original(bgr_img, safe_mask, mast_x, left_edge, right_edge, horizon_y, channel_name, subfolder_name, save_path, roi_box):
    img_h, img_w = bgr_img.shape[:2]
    x_min, x_max, y_min, y_max = _clip_box(roi_box, img_w, img_h)
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), dpi=150)
    crop_rgb = cv2.cvtColor(bgr_img[y_min:y_max, x_min:x_max], cv2.COLOR_BGR2RGB)
    crop_mask = safe_mask[y_min:y_max, x_min:x_max]
    masked_vis = crop_rgb.copy(); masked_vis[crop_mask > 0] = [255, 0, 0] 
    axes[0].imshow(crop_rgb, extent=[x_min, x_max, y_max, y_min])
    axes[0].axvline(left_edge, color='magenta', linestyle=':', lw=2)
    axes[0].axvline(right_edge, color='magenta', linestyle=':', lw=2)
    axes[0].axvline(mast_x, color='cyan', linestyle='--', lw=2)
    axes[0].axhline(horizon_y, color='lime', linestyle='-.', lw=2)
    axes[0].set_title(f"[{subfolder_name}] {channel_name} Original ROI with Edges")
    axes[1].imshow(crop_mask, cmap='gray', extent=[x_min, x_max, y_max, y_min])
    axes[1].set_title(f"[{subfolder_name}] {channel_name} Binary Mask")
    axes[2].imshow(masked_vis, extent=[x_min, x_max, y_max, y_min])
    axes[2].axvline(left_edge, color='magenta', linestyle=':', lw=2)
    axes[2].axvline(right_edge, color='magenta', linestyle=':', lw=2)
    axes[2].axvline(mast_x, color='cyan', linestyle='--', lw=2)
    axes[2].axhline(horizon_y, color='lime', linestyle='-.', lw=2)
    axes[2].set_title(f"[{subfolder_name}] {channel_name} Pixels Ignored (Red = NaN)")
    for ax in axes: ax.set_xlabel("Pixel X"); ax.set_ylabel("Pixel Y"); ax.grid(True, linestyle=":", alpha=0.5)
    plt.tight_layout()
    try: plt.savefig(save_path, bbox_inches="tight")
    except PermissionError: pass
    plt.close()

def plot_and_save_side_by_side_original(rgb_eon, rgb_mwir, eon_mast, eon_horizon, mwir_mast, mwir_horizon, subfolder_name, save_path, eon_box, mwir_box):
    img_h, img_w = rgb_eon.shape[:2]
    e_x_min, e_x_max, e_y_min, e_y_max = _clip_box(eon_box, img_w, img_h)
    m_x_min, m_x_max, m_y_min, m_y_max = _clip_box(mwir_box, img_w, img_h)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8), dpi=150)
    crop_eon = rgb_eon[e_y_min:e_y_max, e_x_min:e_x_max]
    ax1.imshow(crop_eon, extent=[e_x_min, e_x_max, e_y_max, e_y_min], interpolation='nearest')
    ax1.axvline(x=eon_mast, color="cyan", linestyle="--", linewidth=2)
    ax1.axhline(y=eon_horizon, color="lime", linestyle="-.", linewidth=2)
    ax1.plot(eon_mast, eon_horizon, "ro", markersize=8) 
    ax1.set_xlim(e_x_min, e_x_max); ax1.set_ylim(e_y_max, e_y_min); ax1.set_title("EON Channel (Visible)", fontsize=12, fontweight="bold")
    ax1.grid(True, linestyle=":", alpha=0.6)
    crop_mwir = rgb_mwir[m_y_min:m_y_max, m_x_min:m_x_max]
    ax2.imshow(crop_mwir, extent=[m_x_min, m_x_max, m_y_max, m_y_min], interpolation='nearest')
    ax2.axvline(x=mwir_mast, color="yellow", linestyle="--", linewidth=2)
    ax2.axhline(y=mwir_horizon, color="lime", linestyle="-.", linewidth=2)
    ax2.plot(mwir_mast, mwir_horizon, "ro", markersize=8) 
    ax2.set_xlim(m_x_min, m_x_max); ax2.set_ylim(m_y_max, m_y_min); ax2.set_title("MWIR Channel (Thermal)", fontsize=12, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.6)
    plt.suptitle(f"[{subfolder_name}] Side-by-Side Pixel Alignment", fontsize=13, fontweight="bold")
    plt.tight_layout()
    try: plt.savefig(save_path, bbox_inches="tight")
    except PermissionError: pass
    plt.close()

def plot_mask_diagnostic_zoomed(bgr_img, safe_mask, mast_x, left_edge, right_edge, horizon_y, channel_name, subfolder_name, save_path, roi_box):
    img_h, img_w = bgr_img.shape[:2]
    x_min, x_max, y_min, y_max = _clip_box(roi_box, img_w, img_h)
    dpi = 100 
    fig_w, fig_h = img_w / dpi, img_h / dpi
    fig, axes = plt.subplots(1, 3, figsize=(fig_w, fig_h), dpi=dpi)
    crop_rgb = cv2.cvtColor(bgr_img[y_min:y_max, x_min:x_max], cv2.COLOR_BGR2RGB)
    crop_mask = safe_mask[y_min:y_max, x_min:x_max]
    masked_vis = crop_rgb.copy(); masked_vis[crop_mask > 0] = [255, 0, 0] 
    axes[0].imshow(crop_rgb, extent=[x_min, x_max, y_max, y_min], interpolation='nearest')
    axes[0].axvline(left_edge, color='magenta', linestyle=':', lw=2)
    axes[0].axvline(right_edge, color='magenta', linestyle=':', lw=2)
    axes[0].axvline(mast_x, color='cyan', linestyle='--', lw=2)
    axes[0].axhline(horizon_y, color='lime', linestyle='-.', lw=2)
    axes[0].set_title(f"[{subfolder_name}] {channel_name} Original ROI", fontsize=14)
    axes[1].imshow(crop_mask, cmap='gray', extent=[x_min, x_max, y_max, y_min], interpolation='nearest')
    axes[1].set_title(f"[{subfolder_name}] {channel_name} Binary Mask", fontsize=14)
    axes[2].imshow(masked_vis, extent=[x_min, x_max, y_max, y_min], interpolation='nearest')
    axes[2].axvline(left_edge, color='magenta', linestyle=':', lw=2)
    axes[2].axvline(right_edge, color='magenta', linestyle=':', lw=2)
    axes[2].axvline(mast_x, color='cyan', linestyle='--', lw=2)
    axes[2].axhline(horizon_y, color='lime', linestyle='-.', lw=2)
    axes[2].set_title(f"[{subfolder_name}] {channel_name} Pixels Ignored (Red)", fontsize=14)
    for ax in axes: ax.set_xlabel("Pixel X", fontsize=12); ax.set_ylabel("Pixel Y", fontsize=12); ax.tick_params(axis='both', which='major', labelsize=10); ax.grid(True, linestyle=":", alpha=0.5)
    plt.tight_layout()
    try: plt.savefig(save_path, dpi=dpi)
    except PermissionError: pass
    plt.close()

def plot_and_save_side_by_side_zoomed(rgb_eon, rgb_mwir, eon_mast, eon_horizon, mwir_mast, mwir_horizon, subfolder_name, save_path, eon_box, mwir_box):
    img_h, img_w = rgb_eon.shape[:2]
    e_x_min, e_x_max, e_y_min, e_y_max = _clip_box(eon_box, img_w, img_h)
    m_x_min, m_x_max, m_y_min, m_y_max = _clip_box(mwir_box, img_w, img_h)
    dpi = 100 
    fig_w, fig_h = img_w / dpi, img_h / dpi
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(fig_w, fig_h), dpi=dpi)
    crop_eon = rgb_eon[e_y_min:e_y_max, e_x_min:e_x_max]
    ax1.imshow(crop_eon, extent=[e_x_min, e_x_max, e_y_max, e_y_min], interpolation='nearest')
    ax1.axvline(x=eon_mast, color="cyan", linestyle="--", linewidth=2)
    ax1.axhline(y=eon_horizon, color="lime", linestyle="-.", linewidth=2)
    ax1.plot(eon_mast, eon_horizon, "ro", markersize=8) 
    ax1.set_xlim(e_x_min, e_x_max); ax1.set_ylim(e_y_max, e_y_min); ax1.set_title("EON Channel (Visible)", fontsize=16, fontweight="bold")
    ax1.grid(True, linestyle=":", alpha=0.6)
    crop_mwir = rgb_mwir[m_y_min:m_y_max, m_x_min:m_x_max]
    ax2.imshow(crop_mwir, extent=[m_x_min, m_x_max, m_y_max, m_y_min], interpolation='nearest')
    ax2.axvline(x=mwir_mast, color="yellow", linestyle="--", linewidth=2)
    ax2.axhline(y=mwir_horizon, color="lime", linestyle="-.", linewidth=2)
    ax2.plot(mwir_mast, mwir_horizon, "ro", markersize=8) 
    ax2.set_xlim(m_x_min, m_x_max); ax2.set_ylim(m_y_max, m_y_min); ax2.set_title("MWIR Channel (Thermal)", fontsize=16, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.6)
    plt.suptitle(f"[{subfolder_name}] Side-by-Side Pixel Alignment", fontsize=20, fontweight="bold")
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    try: plt.savefig(save_path, dpi=dpi)
    except PermissionError: pass
    plt.close()

def process_pair(eon_path: str, mwir_path: str, subfolder_name: str, output_dir: str, 
                 eon_colors: dict, mwir_colors: dict, manual_coords: dict = None, roi_config: dict = None) -> tuple:
    if roi_config is None:
        roi_config = {
            'roi_x_min': 940, 'roi_x_max': 980, 'roi_y_min': 420, 'roi_y_max': 560,
            'search_y_min_eon': 460, 'search_y_max_eon': 510, 'search_y_min_mwir': 460, 'search_y_max_mwir': 510,
            'horizon_x_min': 800, 'horizon_x_max': 1120, 'horizon_y_min': 520, 'horizon_y_max': 570,
            'stroke_dilation': 7, 'line_dilation': 3, 'min_mast_prominence': 0.0, 'min_horizon_gradient': 0.0
        }

    os.makedirs(output_dir, exist_ok=True)
    img_eon = cv2.imread(eon_path)
    img_mwir = cv2.imread(mwir_path)

    if img_eon is None or img_mwir is None:
        return {"Subfolder ID": subfolder_name, "Status": "ERROR: Image Read Failed"}, False

    rgb_eon = cv2.cvtColor(img_eon, cv2.COLOR_BGR2RGB); rgb_mwir = cv2.cvtColor(img_mwir, cv2.COLOR_BGR2RGB)
    gray_eon = cv2.cvtColor(img_eon, cv2.COLOR_BGR2GRAY); gray_mwir = cv2.cvtColor(img_mwir, cv2.COLOR_BGR2GRAY)
    img_h, img_w = img_eon.shape[:2]
    
    view_w, view_h = 600, 400
    orig_w, orig_h = roi_config['roi_x_max'] - roi_config['roi_x_min'], roi_config['roi_y_max'] - roi_config['roi_y_min']

    if manual_coords:
        _, mask_eon = create_crosshair_masks(img_eon, eon_colors, roi_config['stroke_dilation'], roi_config['line_dilation'])
        _, mask_mwir = create_crosshair_masks(img_mwir, mwir_colors, roi_config['stroke_dilation'], roi_config['line_dilation'])
        mast_x_eon, horizon_eon = manual_coords['eon_x'], manual_coords['eon_y']
        mast_x_mwir, horizon_mwir = manual_coords['mwir_x'], manual_coords['mwir_y']
        left_eon, right_eon, left_mwir, right_mwir = mast_x_eon, mast_x_eon, mast_x_mwir, mast_x_mwir
    else:
        mast_x_eon, left_eon, right_eon, horizon_eon, mask_eon = extract_eon_features(img_eon, gray_eon, eon_colors, roi_config)
        if mast_x_eon is None or horizon_eon is None:
            return {"Subfolder ID": subfolder_name, "EON Mast Center X": np.nan, "EON Horizon Y": np.nan, "MWIR Mast Center X": np.nan, "MWIR Horizon Y": np.nan, "Status": "REJECTED: EON Low Contrast / Noise"}, False
        mast_x_mwir, left_mwir, right_mwir, horizon_mwir, mask_mwir = extract_mwir_features(img_mwir, gray_mwir, mwir_colors, roi_config)
        if mast_x_mwir is None or horizon_mwir is None:
            return {"Subfolder ID": subfolder_name, "EON Mast Center X": mast_x_eon, "EON Horizon Y": horizon_eon, "MWIR Mast Center X": np.nan, "MWIR Horizon Y": np.nan, "Status": "REJECTED: MWIR Low Contrast / Noise"}, False
        
    eon_box_zoomed = (max(0, int(mast_x_eon - view_w / 2)), min(img_w, int(mast_x_eon + view_w / 2)), max(0, int(horizon_eon - view_h / 2)), min(img_h, int(horizon_eon + view_h / 2)))
    mwir_box_zoomed = (max(0, int(mast_x_mwir - view_w / 2)), min(img_w, int(mast_x_mwir + view_w / 2)), max(0, int(horizon_mwir - view_h / 2)), min(img_h, int(horizon_mwir + view_h / 2)))
    eon_box_orig = (max(0, int(mast_x_eon - orig_w / 2)), min(img_w, int(mast_x_eon + orig_w / 2)), max(0, int(horizon_eon - orig_h / 2)), min(img_h, int(horizon_eon + orig_h / 2)))
    mwir_box_orig = (max(0, int(mast_x_mwir - orig_w / 2)), min(img_w, int(mast_x_mwir + orig_w / 2)), max(0, int(horizon_mwir - orig_h / 2)), min(img_h, int(horizon_mwir + orig_h / 2)))

    plot_mask_diagnostic_original(img_eon, mask_eon, mast_x_eon, left_eon, right_eon, horizon_eon, "EON", subfolder_name, os.path.join(output_dir, f"{subfolder_name}_eon_mask_diagnostic_original.png"), eon_box_orig)
    plot_mask_diagnostic_original(img_mwir, mask_mwir, mast_x_mwir, left_mwir, right_mwir, horizon_mwir, "MWIR", subfolder_name, os.path.join(output_dir, f"{subfolder_name}_mwir_mask_diagnostic_original.png"), mwir_box_orig)
    plot_and_save_side_by_side_original(rgb_eon, rgb_mwir, mast_x_eon, horizon_eon, mast_x_mwir, horizon_mwir, subfolder_name, os.path.join(output_dir, f"{subfolder_name}_side_by_side_original.png"), eon_box_orig, mwir_box_orig)
    plot_mask_diagnostic_zoomed(img_eon, mask_eon, mast_x_eon, left_eon, right_eon, horizon_eon, "EON", subfolder_name, os.path.join(output_dir, f"{subfolder_name}_eon_mask_diagnostic_zoomed.png"), eon_box_zoomed)
    plot_mask_diagnostic_zoomed(img_mwir, mask_mwir, mast_x_mwir, left_mwir, right_mwir, horizon_mwir, "MWIR", subfolder_name, os.path.join(output_dir, f"{subfolder_name}_mwir_mask_diagnostic_zoomed.png"), mwir_box_zoomed)
    plot_and_save_side_by_side_zoomed(rgb_eon, rgb_mwir, mast_x_eon, horizon_eon, mast_x_mwir, horizon_mwir, subfolder_name, os.path.join(output_dir, f"{subfolder_name}_side_by_side_zoomed.png"), eon_box_zoomed, mwir_box_zoomed)

    return {
        "Subfolder ID": subfolder_name, "EON Mast Center X": mast_x_eon, "EON Horizon Y": horizon_eon,
        "MWIR Mast Center X": mast_x_mwir, "MWIR Horizon Y": horizon_mwir, "Status": "SUCCESS"
    }, True