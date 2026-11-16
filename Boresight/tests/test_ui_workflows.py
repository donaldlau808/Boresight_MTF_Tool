import os
import cv2
import numpy as np
import pytest
from PySide6.QtCore import Qt, QMimeData, QUrl, QPointF
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensures a single QApplication instance exists for headless UI testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_win(qapp, tmp_path, monkeypatch):
    """Creates a clean MainWindow instance with all modal dialogs mocked so CI never blocks."""
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warnings.append(("warning", args)))
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: warnings.append(("critical", args)))
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: warnings.append(("info", args)))

    win = MainWindow()
    win._test_warnings = warnings
    out_dir = tmp_path / "Test_Outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    win.dir_output_base.setText(str(out_dir))

    yield win
    win.close()


def _make_solid_image(path, bgr_color=(50, 100, 150), size=(80, 80)):
    """Writes a valid synthetic PNG with a distinct BGR color to verify image identity."""
    img = np.full((size[1], size[0], 3), bgr_color, dtype=np.uint8)
    cv2.imwrite(str(path), img)
    return str(path)


def _simulate_widget_drop(widget, file_path):
    """Fires an authentic Qt QDropEvent onto ClickableLabel."""
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(file_path))])
    event = QDropEvent(
        QPointF(10, 10),
        Qt.CopyAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    widget.dropEvent(event)


def _get_queue_items(win):
    return [win.folder_list.item(i).text() for i in range(win.folder_list.count())]


def _remove_all_from_queue(win):
    while win.folder_list.count() > 0:
        win.folder_list.setCurrentRow(0)
        win.remove_selected_system()


# ==============================================================================
# 1. BROWSE -> REMOVE ALL -> DRAG & DROP SAME SYSTEM NUMBER (NO STALE LEAKAGE)
# ==============================================================================
def test_browse_remove_all_then_drop_same_system_id(main_win, tmp_path, monkeypatch):
    """
    Reproduces: Browse directory (017, 018) -> Remove all -> Drag & drop new EON for 017.
    Verifies old browsed 017 EON/MWIR images do NOT pop back up, and MWIR stays empty until dropped.
    """
    input_dir = tmp_path / "Input_Dataset"
    for sys_id in ("017", "018"):
        (input_dir / "EON" / sys_id).mkdir(parents=True)
        (input_dir / "MWIR" / sys_id).mkdir(parents=True)
        _make_solid_image(input_dir / "EON" / sys_id / "old_eon.png", bgr_color=(10, 10, 10))
        _make_solid_image(input_dir / "MWIR" / sys_id / "old_mwir.png", bgr_color=(20, 20, 20))

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **kw: str(input_dir))
    main_win.browse_input_directory()

    assert _get_queue_items(main_win) == ["017", "018"]
    assert main_win.eon_label.current_pixmap is not None
    assert main_win.mwir_label.current_pixmap is not None

    # Remove all systems via UI button action
    _remove_all_from_queue(main_win)
    assert _get_queue_items(main_win) == []
    assert main_win.system_image_paths == {}
    assert main_win.eon_label.current_pixmap is None
    assert main_win.mwir_label.current_pixmap is None

    # Drag and drop a brand-new EON image and enter "17" (unpadded)
    new_eon = _make_solid_image(tmp_path / "external_new_eon.png", bgr_color=(0, 255, 0))
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("17", True))
    _simulate_widget_drop(main_win.eon_label, new_eon)

    assert _get_queue_items(main_win) == ["017"]
    assert main_win.eon_label.current_pixmap is not None
    # MWIR must remain completely empty (must NOT load old_mwir.png from input_dir)
    assert main_win.system_image_paths["017"]["MWIR"] is None
    assert main_win.mwir_label.current_pixmap is None
    assert "old_eon.png" not in main_win.system_image_paths["017"]["EON"]

    # Now drop the matching new MWIR image for 017
    new_mwir = _make_solid_image(tmp_path / "external_new_mwir.png", bgr_color=(255, 0, 0))
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("017", True))
    _simulate_widget_drop(main_win.mwir_label, new_mwir)

    assert main_win.mwir_label.current_pixmap is not None
    assert "old_mwir.png" not in main_win.system_image_paths["017"]["MWIR"]


# ==============================================================================
# 2. BROWSE (017-020) -> REMOVE -> DROP OUT-OF-RANGE (025) -> REMOVE -> RE-BROWSE
# ==============================================================================
def test_browse_remove_drop_out_of_range_remove_and_rebrowse(main_win, tmp_path, monkeypatch):
    """
    Reproduces: Browse (017..020) -> Remove all -> Drop 025 -> Remove all -> Re-browse.
    Verifies 025 never pollutes the browsed input directory or reappears at the end of the list.
    """
    input_dir = tmp_path / "Batch_Source"
    for sys_id in ("017", "018", "019", "020"):
        (input_dir / "EON" / sys_id).mkdir(parents=True)
        (input_dir / "MWIR" / sys_id).mkdir(parents=True)
        _make_solid_image(input_dir / "EON" / sys_id / "eon.png")
        _make_solid_image(input_dir / "MWIR" / sys_id / "mwir.png")

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **kw: str(input_dir))
    main_win.browse_input_directory()
    assert _get_queue_items(main_win) == ["017", "018", "019", "020"]

    # Clear all
    _remove_all_from_queue(main_win)
    assert _get_queue_items(main_win) == []

    # Drop out-of-range system 025
    drop_eon = _make_solid_image(tmp_path / "drop_025_eon.png")
    drop_mwir = _make_solid_image(tmp_path / "drop_025_mwir.png")
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("025", True))
    _simulate_widget_drop(main_win.eon_label, drop_eon)
    _simulate_widget_drop(main_win.mwir_label, drop_mwir)
    assert _get_queue_items(main_win) == ["025"]

    # Remove 025 again
    _remove_all_from_queue(main_win)
    assert _get_queue_items(main_win) == []
    assert not (input_dir / "EON" / "025").exists()

    # Re-browse original input directory
    main_win.browse_input_directory()
    assert _get_queue_items(main_win) == ["017", "018", "019", "020"]


# ==============================================================================
# 3. ORPHAN/EMPTY FOLDERS & ACCIDENTAL EON/MWIR SUBFOLDER SELECTION
# ==============================================================================
def test_browse_ignores_orphan_folders_and_auto_steps_up_from_channel(main_win, tmp_path, monkeypatch):
    """
    Verifies that leftover single-channel folders (025) and empty folders (030) are ignored,
    and selecting .../Input/EON automatically resolves to .../Input.
    """
    input_dir = tmp_path / "Messy_Input"
    # Complete pair: 017
    (input_dir / "EON" / "017").mkdir(parents=True)
    (input_dir / "MWIR" / "017").mkdir(parents=True)
    _make_solid_image(input_dir / "EON" / "017" / "eon.png")
    _make_solid_image(input_dir / "MWIR" / "017" / "mwir.png")

    # Leftover single-channel orphan: 025 (only EON exists)
    (input_dir / "EON" / "025").mkdir(parents=True)
    _make_solid_image(input_dir / "EON" / "025" / "stray.png")

    # Empty folders: 030
    (input_dir / "EON" / "030").mkdir(parents=True)
    (input_dir / "MWIR" / "030").mkdir(parents=True)

    # User accidentally clicks inside .../Messy_Input/EON
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **kw: str(input_dir / "EON"))
    main_win.browse_input_directory()

    assert main_win.dir_input_base.text() == os.path.normpath(str(input_dir))
    assert _get_queue_items(main_win) == ["017"]


# ==============================================================================
# 4. OVERWRITE DROPPED CHANNEL, MANUAL CLICK RESET, INVALID FILES & CANCELLED PROMPTS
# ==============================================================================
def test_chaotic_drop_overwrite_cancel_and_manual_coords_reset(main_win, tmp_path, monkeypatch):
    """
    Tests rapid sequences: drop -> click manual coords -> overwrite channel (resets click) ->
    cancel prompt (no-op) -> drop 0-byte/non-image file (rejected) -> remove from empty queue.
    """
    img_a = _make_solid_image(tmp_path / "a.png")
    img_b = _make_solid_image(tmp_path / "b.png")
    img_c = _make_solid_image(tmp_path / "c.png")

    # 1. Drop EON & MWIR for system 042
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("42", True))
    _simulate_widget_drop(main_win.eon_label, img_a)
    _simulate_widget_drop(main_win.mwir_label, img_b)
    assert _get_queue_items(main_win) == ["042"]

    # 2. Register manual coordinates on both channels
    main_win.register_click("EON", 30, 40)
    main_win.register_click("MWIR", 50, 60)
    assert main_win.system_manual_coords["042"] == {"eon_x": 30, "eon_y": 40, "mwir_x": 50, "mwir_y": 60}

    # 3. Overwrite EON with a new image -> EON manual click must reset, MWIR click must stay
    _simulate_widget_drop(main_win.eon_label, img_c)
    assert main_win.system_manual_coords["042"]["eon_x"] is None
    assert main_win.system_manual_coords["042"]["eon_y"] is None
    assert main_win.system_manual_coords["042"]["mwir_x"] == 50
    assert main_win.system_manual_coords["042"]["mwir_y"] == 60

    # 4. User drops an image but clicks Cancel on System Number prompt -> state unchanged
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("", False))
    _simulate_widget_drop(main_win.eon_label, img_a)
    assert _get_queue_items(main_win) == ["042"]

    # 5. User drops a 0-byte corrupt file and a .txt file -> both rejected safely
    zero_byte = tmp_path / "empty.png"
    zero_byte.write_bytes(b"")
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("not an image")

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("099", True))
    _simulate_widget_drop(main_win.eon_label, zero_byte)
    _simulate_widget_drop(main_win.eon_label, txt_file)
    assert _get_queue_items(main_win) == ["042"]

    # 6. Remove 042, then click Remove again on an empty queue -> warns cleanly without crash
    _remove_all_from_queue(main_win)
    assert _get_queue_items(main_win) == []
    main_win.remove_selected_system()
    assert len(main_win._test_warnings) >= 1


# ==============================================================================
# 5. PRE-FLIGHT VALIDATION GUARDS & SHUTDOWN CLEANUP
# ==============================================================================
def test_preflight_validation_and_shutdown_cleanup(main_win, tmp_path, monkeypatch):
    """
    Verifies batch processing refuses incomplete single-channel items or missing color selections,
    and closing the window purges the OS temp drop cache.
    """
    img_eon = _make_solid_image(tmp_path / "only_eon.png")
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("055", True))
    _simulate_widget_drop(main_win.eon_label, img_eon)

    # Attempt batch run with no crosshair color checked -> blocked with warning
    main_win.run_batch_processing()
    assert len(main_win._test_warnings) >= 1

    # Check a color, attempt batch run with missing MWIR -> blocked with warning
    main_win.chk_orange.setChecked(True)
    main_win.run_batch_processing()
    assert len(main_win._test_warnings) >= 2

    # Temp cache exists while window is open, then disappears upon close()
    cache_dir = main_win.drop_cache_dir
    assert os.path.isdir(cache_dir)
    main_win.close()
    assert not os.path.exists(cache_dir)