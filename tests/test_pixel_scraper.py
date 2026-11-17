import os
import cv2
import numpy as np
import pytest
import tracemalloc
import gc
from boresight.core import pixel_scraper

def test_missing_images_failure_mode(tmp_path):
    """Verifies graceful handling and error reporting when input image paths do not exist."""
    out_dir = str(tmp_path / "outputs")
    colors = {'orange': False, 'green': False, 'white': False}
    
    result, success = pixel_scraper.process_pair(
        "nonexistent_eon.png", "nonexistent_mwir.png", "001", out_dir, colors, colors
    )
    assert success is False
    assert isinstance(result, dict)
    assert result["Subfolder ID"] == "001"
    assert "ERROR" in result["Status"].upper()

def test_manual_override_processing(tmp_path):
    """Verifies end-to-end image pair processing with synthetic images and manual coordinates."""
    eon_path = str(tmp_path / "eon.png")
    mwir_path = str(tmp_path / "mwir.png")
    out_dir = str(tmp_path / "outputs")

    blank_img = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.imwrite(eon_path, blank_img)
    cv2.imwrite(mwir_path, blank_img)

    colors = {'orange': False, 'green': False, 'white': False}
    manual_coords = {'eon_x': 100, 'eon_y': 100, 'mwir_x': 105, 'mwir_y': 98}

    result, success = pixel_scraper.process_pair(
        eon_path, mwir_path, "017", out_dir, colors, colors, manual_coords=manual_coords
    )

    assert success is True
    assert str(result["Subfolder ID"]).zfill(3) == "017"
    assert os.path.exists(out_dir)

def test_corrupt_image_handling(tmp_path):
    """Verifies that non-image files disguised as images do not cause a hard crash."""
    eon_path = str(tmp_path / "corrupt_eon.png")
    mwir_path = str(tmp_path / "corrupt_mwir.png")
    out_dir = str(tmp_path / "outputs")
    
    # Write corrupt data instead of a valid PNG header
    with open(eon_path, "w") as f: f.write("This is not a real PNG file")
    with open(mwir_path, "w") as f: f.write("This is not a real PNG file")

    colors = {'orange': False, 'green': False, 'white': False}
    result, success = pixel_scraper.process_pair(eon_path, mwir_path, "099", out_dir, colors, colors)
    
    assert success is False
    assert "ERROR" in result["Status"].upper()

def test_extreme_coordinates_overflow(tmp_path):
    """Verifies handling of integer overflows, wraparounds, or massively out-of-bounds clicks."""
    eon_path = str(tmp_path / "eon.png")
    mwir_path = str(tmp_path / "mwir.png")
    out_dir = str(tmp_path / "outputs")

    blank_img = np.zeros((50, 50, 3), dtype=np.uint8)
    cv2.imwrite(eon_path, blank_img)
    cv2.imwrite(mwir_path, blank_img)

    colors = {'orange': False, 'green': False, 'white': False}
    
    # Coordinates that trigger Python -> C++ OverflowErrors or IndexErrors
    extreme_coords = {'eon_x': 2**31 - 1, 'eon_y': -999999, 'mwir_x': 10000000000000, 'mwir_y': 0}

    try:
        result, success = pixel_scraper.process_pair(
            eon_path, mwir_path, "100", out_dir, colors, colors, manual_coords=extreme_coords
        )
        assert isinstance(result, dict)
    except Exception as e:
        pytest.fail(f"Extreme coordinates caused an unhandled C++ exception: {e}")

def test_pure_black_auto_detect(tmp_path):
    """Verifies cv2.moments divide-by-zero protection on pure black/empty images."""
    eon_path = str(tmp_path / "eon.png")
    mwir_path = str(tmp_path / "mwir.png")
    out_dir = str(tmp_path / "outputs")

    blank_img = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.imwrite(eon_path, blank_img)
    cv2.imwrite(mwir_path, blank_img)

    colors = {'orange': True, 'green': True, 'white': True}
    
    try:
        result, success = pixel_scraper.process_pair(eon_path, mwir_path, "101", out_dir, colors, colors)
        assert success is False
        assert "REJECTED" in result["Status"].upper()
    except ZeroDivisionError:
        pytest.fail("cv2.moments triggered an unhandled ZeroDivisionError.")

def test_read_only_remnant_files(tmp_path):
    """Simulates remnant locked files by writing to a read-only destination."""
    eon_path = str(tmp_path / "eon.png")
    mwir_path = str(tmp_path / "mwir.png")
    out_dir = str(tmp_path / "outputs")
    
    blank_img = np.zeros((50, 50, 3), dtype=np.uint8)
    cv2.imwrite(eon_path, blank_img)
    cv2.imwrite(mwir_path, blank_img)
    
    os.makedirs(out_dir, exist_ok=True)
    
    # Create a conflicting locked output image simulating a remnant file
    conflict_file = os.path.join(out_dir, "102_side_by_side_zoomed.png")
    with open(conflict_file, "w") as f: f.write("locked")
    os.chmod(conflict_file, 0o444) # Make it strict Read-Only
    
    colors = {'orange': False, 'green': False, 'white': False}
    manual_coords = {'eon_x': 25, 'eon_y': 25, 'mwir_x': 25, 'mwir_y': 25}
    
    try:
        result, success = pixel_scraper.process_pair(
            eon_path, mwir_path, "102", out_dir, colors, colors, manual_coords=manual_coords
        )
        assert isinstance(result, dict)
    except PermissionError as e:
        pytest.fail(f"Image exporter crashed on remnant file instead of handling the OS lock: {e}")
    finally:
        os.chmod(conflict_file, 0o777) # Cleanup so pytest can purge the temp dir

def test_memory_leak_on_batch_processing(tmp_path):
    """Processes a heavy batch of synthetic systems to guarantee images and plots are safely garbage collected."""
    eon_path = str(tmp_path / "mem_eon.png")
    mwir_path = str(tmp_path / "mem_mwir.png")
    out_dir = str(tmp_path / "outputs")

    # Creating reasonably sized images to ensure memory footprint is measurable
    blank_img = np.zeros((800, 800, 3), dtype=np.uint8)
    cv2.imwrite(eon_path, blank_img)
    cv2.imwrite(mwir_path, blank_img)

    colors = {'orange': False, 'green': False, 'white': False}
    manual_coords = {'eon_x': 400, 'eon_y': 400, 'mwir_x': 405, 'mwir_y': 405}

    # 1. WARM UP: Run once to load heavy libraries (Matplotlib, pandas, etc.) into baseline memory
    pixel_scraper.process_pair(eon_path, mwir_path, "warmup", out_dir, colors, colors, manual_coords=manual_coords)
    gc.collect()

    # 2. START TRACING: Take a snapshot of memory usage before the loop
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    # 3. EXECUTE BATCH: Run 50 system pairs (enough to heavily spike memory if a leak exists)
    for i in range(50):
        sys_name = str(i).zfill(3)
        pixel_scraper.process_pair(eon_path, mwir_path, sys_name, out_dir, colors, colors, manual_coords=manual_coords)

    # 4. END TRACING: Force garbage collection and take a final snapshot
    gc.collect()
    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # 5. COMPARE: Calculate total memory differential in Megabytes
    stats = snapshot_after.compare_to(snapshot_before, 'lineno')
    total_diff_b = sum(stat.size_diff for stat in stats)
    total_diff_mb = total_diff_b / (1024 * 1024)

    # Allow up to 10MB of variance for dynamic Python cache scaling.
    # An unclosed Matplotlib figure or OpenCV frame over 50 iterations would leak > 100MB.
    assert total_diff_mb < 10.0, f"Memory leak detected! Engine retained {total_diff_mb:.2f} MB after processing."