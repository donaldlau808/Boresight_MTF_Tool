import pytest
import os
import pandas as pd
from boresight.core.boresight_eval import generate_report

def test_empty_dataframe_failure_mode():
    """Verifies the graceful failure mode when the input dataframe is empty."""
    empty_df = pd.DataFrame()
    success, msg, df_out = generate_report(empty_df, "out.xlsx", {})
    assert success is False
    assert "No relevant data" in msg
    assert df_out is None

def test_system_constants_parsing(tmp_path):
    """Ensures string inputs from the UI are safely parsed to floats by the engine."""
    mock_constants = {
        'target_range': "3880.75",
        'canvas_width': 3840.0,
        'focal_length': "420",
        'pixel_pitch': "0.01",
        'native_width': "1280"
    }
    
    valid_df = pd.DataFrame({
        "Subfolder ID": ["001"], 
        "EON Mast Center X": [100], 
        "EON Horizon Y": [100], 
        "MWIR Mast Center X": [100], 
        "MWIR Horizon Y": [100], 
        "Status": ["SUCCESS"]
    })
    
    out_file = str(tmp_path / "out.xlsx")
        
    try:
        generate_report(valid_df, out_file, mock_constants)
    except TypeError:
        pytest.fail("Engine failed to parse string-based system constants to floats.")

def test_divide_by_zero_constants(tmp_path):
    """Verifies math engine doesn't crash on ZeroDivisionError if constants are 0."""
    valid_df = pd.DataFrame({
        "Subfolder ID": ["001"], 
        "EON Mast Center X": [100], 
        "EON Horizon Y": [100], 
        "MWIR Mast Center X": [100], 
        "MWIR Horizon Y": [100], 
        "Status": ["SUCCESS"]
    })
    
    mock_constants = {
        'target_range': 0.0, 
        'canvas_width': 3840.0,
        'focal_length': 0.0,   # Will cause divide-by-zero in DO-160 math
        'pixel_pitch': 0.0,
        'native_width': 1280.0
    }
    
    out_file = str(tmp_path / "out.xlsx")
    
    try:
        success, msg, df_out = generate_report(valid_df, out_file, mock_constants)
        assert isinstance(success, bool)
    except ZeroDivisionError:
        pytest.fail("Math engine crashed with an unhandled ZeroDivisionError.")

def test_corrupted_dataframe_data(tmp_path):
    """Verifies engine handles DataFrames missing required columns."""
    
    # Missing the required X/Y intersection columns
    corrupt_df = pd.DataFrame({"Subfolder ID": ["001"], "RandomData": [123], "Notes": ["corrupt"]})
    
    mock_constants = {
        'target_range': 4000.0, 'canvas_width': 3840.0,
        'focal_length': 420.0, 'pixel_pitch': 0.01, 'native_width': 1280.0
    }
    
    out_file = str(tmp_path / "out.xlsx")
    
    try:
        success, msg, df_out = generate_report(corrupt_df, out_file, mock_constants)
        assert success is False
        assert "missing required columns" in msg.lower()
    except KeyError as e:
        pytest.fail(f"Engine crashed with an unhandled KeyError on corrupted data: {e}")