import pandas as pd

def process_batch_results(intersection_data: list):
    """Converts the raw list of dictionaries into a sorted Pandas DataFrame."""
    df_final = pd.DataFrame(intersection_data)
    if not df_final.empty and "Subfolder ID" in df_final.columns:
        df_final["Subfolder ID"] = df_final["Subfolder ID"].astype(str).str.zfill(3)
        df_final = df_final.sort_values("Subfolder ID")
    return df_final

def prepare_table_data(df: pd.DataFrame):
    """Extracts headers and formats rows as raw Python strings for the UI Table."""
    if df is None or df.empty:
        return [], []
    df_clean = df.copy()
    df_clean.fillna("", inplace=True)
    headers = df_clean.columns.astype(str).tolist()
    rows = df_clean.astype(str).values.tolist()
    return headers, rows

def has_active_data(df: pd.DataFrame, active_systems: list) -> bool:
    """Checks if the dataframe contains any data for the currently queued systems."""
    if df is None or df.empty:
        return False
    df_filtered = df[df["Subfolder ID"].isin(active_systems)]
    return not df_filtered.empty