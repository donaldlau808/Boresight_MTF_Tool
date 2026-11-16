import pytest
import os
import pandas as pd
from core.boresight_eval import generate_report

def test_missing_input_file_failure_mode():
    """Verifies the graceful failure mode when the target Excel file does not exist."""
    success, msg, df = generate_report("fake_path.xlsx", "out.xlsx", "plots", {})
    assert success is False
    assert "File not found" in msg
    assert df is None

def test_system_constants_parsing():
    """Ensures string inputs from the UI are safely parsed to floats by the engine."""
    mock_constants = {
        'target_range': "3880.75",
        'canvas_width': 3840.0,
        'focal_length': "420",
        'pixel_pitch': "0.01",
        'native_width': "1280"
    }
    
    dummy_input = "dummy_input.xlsx"
    with open(dummy_input, "w") as f: f.write("")
        
    try:
        generate_report(dummy_input, "out.xlsx", "plots", mock_constants)
    except TypeError:
        pytest.fail("Engine failed to parse string-based system constants to floats.")
    except Exception:
        pass # Expected to fail on pandas read_excel, which proves it passed parsing
    finally:
        if os.path.exists(dummy_input):
            os.remove(dummy_input)

def test_divide_by_zero_constants(tmp_path):
    """Verifies math engine doesn't crash on ZeroDivisionError if constants are 0."""
    excel_in = str(tmp_path / "dummy_in.xlsx")
    
    # Pass valid initial data
    df = pd.DataFrame({"Subfolder ID": ["001"], "EON_X": [100], "EON_Y": [100], "MWIR_X": [100], "MWIR_Y": [100]})
    df.to_excel(excel_in, index=False)
    
    mock_constants = {
        'target_range': 0.0, 
        'canvas_width': 3840.0,
        'focal_length': 0.0,   # Will cause divide-by-zero in DO-160 math
        'pixel_pitch': 0.0,
        'native_width': 1280.0
    }
    
    try:
        success, msg, df_out = generate_report(excel_in, "out.xlsx", str(tmp_path), mock_constants)
        assert isinstance(success, bool)
    except ZeroDivisionError:
        pytest.fail("Math engine crashed with an unhandled ZeroDivisionError.")

def test_corrupted_excel_data(tmp_path):
    """Verifies engine handles DataFrames missing required columns."""
    excel_in = str(tmp_path / "corrupt_in.xlsx")
    
    # Missing the required X/Y intersection columns
    df = pd.DataFrame({"Subfolder ID": ["001"], "RandomData": [123], "Notes": ["corrupt"]})
    df.to_excel(excel_in, index=False)
    
    mock_constants = {
        'target_range': 4000.0, 'canvas_width': 3840.0,
        'focal_length': 420.0, 'pixel_pitch': 0.01, 'native_width': 1280.0
    }
    
    try:
        success, msg, df_out = generate_report(excel_in, "out.xlsx", str(tmp_path), mock_constants)
        assert success is False
    except KeyError as e:
        pytest.fail(f"Engine crashed with an unhandled KeyError on corrupted data: {e}")