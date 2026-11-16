import os
import cv2
import numpy as np
from core import pixel_scraper

def test_missing_images_failure_mode(tmp_path):
    """Verifies graceful handling when input image paths do not exist."""
    out_dir = str(tmp_path / "outputs")
    colors = {'orange': False, 'green': False, 'white': False}
    
    result, success = pixel_scraper.process_pair(
        "nonexistent_eon.png",
        "nonexistent_mwir.png",
        "001",
        out_dir,
        colors,
        colors
    )
    assert success is False
    assert result is None

def test_manual_override_processing(tmp_path):
    """Verifies end-to-end image pair processing with synthetic images and manual coordinates."""
    eon_path = str(tmp_path / "eon.png")
    mwir_path = str(tmp_path / "mwir.png")
    out_dir = str(tmp_path / "outputs")

    # Generate synthetic 200x200 test images
    blank_img = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.imwrite(eon_path, blank_img)
    cv2.imwrite(mwir_path, blank_img)

    colors = {'orange': False, 'green': False, 'white': False}
    manual_coords = {'eon_x': 100, 'eon_y': 100, 'mwir_x': 105, 'mwir_y': 98}

    result, success = pixel_scraper.process_pair(
        eon_path,
        mwir_path,
        "017",
        out_dir,
        colors,
        colors,
        manual_coords=manual_coords
    )

    assert success is True
    assert isinstance(result, dict)
    assert str(result["Subfolder ID"]).zfill(3) == "017"
    assert os.path.exists(out_dir)