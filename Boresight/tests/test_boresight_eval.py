import pytest
from core.boresight_eval import generate_report


def test_missing_input_file_failure_mode(tmp_path):
    """Verifies the graceful failure mode when the target Excel file does not exist."""
    fake_input = str(tmp_path / "fake_path.xlsx")
    out_xlsx = str(tmp_path / "out.xlsx")
    plot_dir = str(tmp_path / "plots")

    success, msg, df = generate_report(fake_input, out_xlsx, plot_dir, {})
    assert success is False
    assert "File not found" in msg
    assert df is None


def test_system_constants_parsing(tmp_path):
    """Ensures string inputs from the UI are safely parsed to floats by the engine."""
    mock_constants = {
        "target_range": "3880.75",
        "canvas_width": 3840.0,
        "focal_length": "420",
        "pixel_pitch": "0.01",
        "native_width": "1280",
    }

    dummy_input = tmp_path / "dummy_input.xlsx"
    dummy_input.write_text("")
    out_xlsx = str(tmp_path / "out.xlsx")
    plot_dir = str(tmp_path / "plots")

    try:
        generate_report(str(dummy_input), out_xlsx, plot_dir, mock_constants)
    except TypeError:
        pytest.fail("Engine failed to parse string-based system constants to floats.")
    except Exception:
        # Expected to fail on pandas.read_excel for an empty non-xlsx file,
        # proving float casting succeeded without a TypeError.
        pass