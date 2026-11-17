import os
import warnings
import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

def create_misalignment_plot(val_x, val_y, max_scale, unit, plot_type, title_text, save_path):
    fig, ax = plt.subplots(figsize=(3.4, 3.4), dpi=120)
    for r, c in zip([1.0, 0.75, 0.5, 0.25], ['#e2e8f0', '#cbd5e1', '#94a3b8', '#64748b']):
        radius = max_scale * r
        ax.add_patch(plt.Circle((0, 0), radius, color=c, fill=False, lw=1.2, alpha=0.45 if plot_type != 'total' else 1.0))
        label_x, label_y = radius * np.cos(np.radians(45)), radius * np.sin(np.radians(45))
        ax.text(label_x, label_y, f'{radius:.2g} {unit}', color='#475569', fontsize=6.5, 
                ha='center', va='center', bbox=dict(facecolor='white', edgecolor='none', pad=1.0, alpha=0.75))
    
    ax.axhline(0, color='#94a3b8' if plot_type != 'y' else '#0f172a', linestyle=':' if plot_type != 'y' else '-', lw=1 if plot_type != 'y' else 1.5)
    ax.axvline(0, color='#94a3b8' if plot_type != 'x' else '#0f172a', linestyle=':' if plot_type != 'x' else '-', lw=1 if plot_type != 'x' else 1.5)
    ax.plot(0, 0, marker='o', markersize=4, color='#0f172a')
    
    if plot_type == 'x':
        ax.plot([0, val_x], [0, 0], color='#0891b2', linestyle='-', lw=2.5)
        ax.plot(val_x, 0, marker='|', color='#0891b2', markersize=22, markeredgewidth=3)
        ax.annotate(f'{val_x:+.3f} {unit}', xy=(val_x, 0), xytext=(val_x, max_scale * 0.12 if val_x >= 0 else -max_scale * 0.12), 
                    ha='center', va='bottom' if val_x >= 0 else 'top', fontsize=8, color='#0891b2', fontweight='bold')
    elif plot_type == 'y':
        ax.plot([0, 0], [0, val_y], color='#0891b2', linestyle='-', lw=2.5)
        ax.plot(0, val_y, marker='_', color='#0891b2', markersize=22, markeredgewidth=3)
        ax.annotate(f'{val_y:+.3f} {unit}', xy=(0, val_y), xytext=(max_scale * 0.12 if val_y >= 0 else -max_scale * 0.12, val_y), 
                    va='center', ha='left' if val_y >= 0 else 'right', fontsize=8, color='#0891b2', fontweight='bold')
    elif plot_type == 'total':
        ax.plot([0, val_x], [0, val_y], color='#0891b2', linestyle='--', lw=1.5, alpha=0.7)
        ax.plot(val_x, val_y, marker='+', color='#0891b2', markersize=14, markeredgewidth=2.5)
        ax.add_patch(plt.Circle((val_x, val_y), max_scale * 0.08, color='#0891b2', fill=False, lw=1.5, linestyle='--'))
        
    ax.set_xlim(-max_scale, max_scale)
    ax.set_ylim(-max_scale, max_scale)
    ax.set_aspect('equal')
    ax.axis('off')
    plt.title(title_text, fontsize=8.5, fontweight='bold', color='#1e293b', pad=8)
    plt.tight_layout()
    try:
        plt.savefig(save_path, transparent=True, bbox_inches='tight')
    except PermissionError:
        pass
    plt.close(fig)

def generate_report(excel_input_path: str, excel_output_path: str, plot_dir: str, sys_constants: dict, active_systems: list = None):
    if not os.path.exists(excel_input_path): return False, f"File not found: {excel_input_path}", None
        
    RANGE_M = float(sys_constants.get('target_range', 3880.75))
    CANVAS_W_PX = float(sys_constants.get('canvas_width', 3840.0))
    MWIR_FOCAL_LEN_MM = float(sys_constants.get('focal_length', 420.0))
    MWIR_NATIVE_PITCH_MM = float(sys_constants.get('pixel_pitch', 0.010))
    MWIR_NATIVE_W_PX = float(sys_constants.get('native_width', 1280.0))

    if RANGE_M <= 0 or MWIR_FOCAL_LEN_MM <= 0:
        return False, "Target Range and Focal Length must be greater than zero.", None

    PLOT_MAX_SCALE_M = 1.0     
    PLOT_MAX_SCALE_MRAD = (PLOT_MAX_SCALE_M / RANGE_M) * 1000.0  

    os.makedirs(plot_dir, exist_ok=True)
    df = pd.read_excel(excel_input_path)
    df["Subfolder ID"] = df["Subfolder ID"].astype(str).str.zfill(3)
    
    if active_systems is not None:
        df = df[df["Subfolder ID"].isin(active_systems)]
        
    if df.empty:
        return False, "No relevant data found for the systems currently in the queue.", None
    
    expected_cols = ["Subfolder ID", "EON Mast Center X", "EON Horizon Y", "MWIR Mast Center X", "MWIR Horizon Y", "Status"]
    if not set(expected_cols).issubset(df.columns): return False, "Input Excel is missing required columns.", None

    df = df[expected_cols]
    for col in ['EON Mast Center X', 'EON Horizon Y', 'MWIR Mast Center X', 'MWIR Horizon Y']:
        df[col] = pd.to_numeric(df[col].replace(r'^\s*$', np.nan, regex=True), errors='coerce')

    plot_records = []
    DATA_START_ROW = 17 # 0-indexed row 16 for xlsxwriter
    num_px_x, num_px_y, num_miss_x, num_miss_y, num_tot_miss, num_mrad_x, num_mrad_y, num_tot_mrad = [], [], [], [], [], [], [], []
    
    eff_pitch_mm = MWIR_NATIVE_PITCH_MM * (MWIR_NATIVE_W_PX / CANVAS_W_PX)
    canvas_gsd_m_px = (eff_pitch_mm / MWIR_FOCAL_LEN_MM) * RANGE_M

    for i, row in df.iterrows():
        subfolder = str(row['Subfolder ID']).zfill(3)
        if pd.isna(row.get('EON Mast Center X')) or pd.isna(row.get('MWIR Mast Center X')):
            for lst in [num_px_x, num_px_y, num_miss_x, num_miss_y, num_tot_miss, num_mrad_x, num_mrad_y, num_tot_mrad]:
                lst.append("REJECTED")
            plot_records.append((None, None, None, None, None, None))
            continue

        delta_px_x = row['MWIR Mast Center X'] - row['EON Mast Center X']
        delta_px_y = row['MWIR Horizon Y'] - row['EON Horizon Y']
        delta_m_x = delta_px_x * canvas_gsd_m_px
        delta_m_y = delta_px_y * canvas_gsd_m_px
        mrad_x = (delta_m_x / RANGE_M) * 1000.0
        mrad_y = (delta_m_y / RANGE_M) * 1000.0
        
        num_px_x.append(round(delta_px_x, 2)); num_px_y.append(round(delta_px_y, 2))
        num_miss_x.append(round(delta_m_x, 3)); num_miss_y.append(round(delta_m_y, 3))
        num_tot_miss.append(round(np.sqrt(delta_m_x**2 + delta_m_y**2), 3))
        num_mrad_x.append(round(mrad_x, 3)); num_mrad_y.append(round(mrad_y, 3))
        num_tot_mrad.append(round(np.sqrt(mrad_x**2 + mrad_y**2), 3))

        paths = [os.path.join(plot_dir, f'{subfolder}_{n}.png') for n in ['1_trans_x', '2_trans_y', '3_trans_total', '4_ang_x', '5_ang_y', '6_ang_total']]
        create_misalignment_plot(delta_m_x, 0, PLOT_MAX_SCALE_M, 'm', 'x', f'[{subfolder}] Trans X: {delta_m_x:+.3f} m', paths[0])
        create_misalignment_plot(0, delta_m_y, PLOT_MAX_SCALE_M, 'm', 'y', f'[{subfolder}] Trans Y: {delta_m_y:+.3f} m', paths[1])
        create_misalignment_plot(delta_m_x, delta_m_y, PLOT_MAX_SCALE_M, 'm', 'total', f'[{subfolder}] Trans Tot: {np.sqrt(delta_m_x**2 + delta_m_y**2):.3f} m', paths[2])
        create_misalignment_plot(mrad_x, 0, PLOT_MAX_SCALE_MRAD, 'mrad', 'x', f'[{subfolder}] Ang X: {mrad_x:+.3f} mrad', paths[3])
        create_misalignment_plot(0, mrad_y, PLOT_MAX_SCALE_MRAD, 'mrad', 'y', f'[{subfolder}] Ang Y: {mrad_y:+.3f} mrad', paths[4])
        create_misalignment_plot(mrad_x, mrad_y, PLOT_MAX_SCALE_MRAD, 'mrad', 'total', f'[{subfolder}] Ang Tot: {np.sqrt(mrad_x**2 + mrad_y**2):.3f} mrad', paths[5])
        plot_records.append(tuple(paths))

    df['Pixel Offset X (px)'] = num_px_x; df['Pixel Offset Y (px)'] = num_px_y
    df['Target Misalignment X (m)'] = num_miss_x; df['Target Misalignment Y (m)'] = num_miss_y
    df['Total Target Misalignment (m)'] = num_tot_miss; df['Co-Boresight Error X (mrad)'] = num_mrad_x
    df['Co-Boresight Error Y (mrad)'] = num_mrad_y; df['Total Co-Boresight Error (mrad)'] = num_tot_mrad

    # High-leverage XlsxWriter Engine Integration
    with pd.ExcelWriter(excel_output_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='CoBoresight', startrow=DATA_START_ROW-1)
        workbook = writer.book
        worksheet = writer.sheets['CoBoresight']

        # Formats
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#F47D30', 'font_color': 'white', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        input_fmt = workbook.add_format({'bold': True, 'bg_color': '#FFF2CC'})
        ref_fmt = workbook.add_format({'bg_color': '#F2F2F2'})
        bold_fmt = workbook.add_format({'bold': True})
        reject_fmt = workbook.add_format({'bold': True, 'font_color': 'red', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        # Columns
        worksheet.set_column('A:E', 18)
        worksheet.set_column('F:F', 30)
        worksheet.set_column('G:Z', 38)
        
        # Headers & Meta
        worksheet.merge_range('A1:T1', "CO-BORESIGHT MISALIGNMENT EXECUTION SHEET (PHYSICAL METERS-FIRST)", header_fmt)
        worksheet.write('A2', "1. SYSTEM CONSTANTS", bold_fmt)
        
        constants = [
            ("Target Range", RANGE_M, "m", "Distance to target"),
            ("MWIR Focal Length", MWIR_FOCAL_LEN_MM, "mm", "Physical Lens Focal Length"),
            ("MWIR Native Pixel Pitch", MWIR_NATIVE_PITCH_MM, "mm", "Physical Sensor Pixel Size"),
            ("MWIR Native Width", MWIR_NATIVE_W_PX, "px", "Native sensor width from Spec Table"),
            ("Screenshot Canvas Width", CANVAS_W_PX, "px", "Scaled width of diagnostic images")
        ]
        for r_idx, (param, val, unit, desc) in enumerate(constants, start=2):
            worksheet.write(r_idx, 0, param); worksheet.write(r_idx, 1, val, input_fmt)
            worksheet.write(r_idx, 2, unit); worksheet.write(r_idx, 3, desc)

        worksheet.write('A9', "2. CALCULATED PROFILE REDUCTION PARAMETERS", bold_fmt)
        worksheet.write_row('A10', ["Parameter", "Ref Code", "Units", "Math Equation (Live Excel Cells)"], bold_fmt)
        
        formulas = [
            ("Pixel Offset", "Delta px", "px", "Delta px = MWIR_Coord - EON_Coord"),
            ("Canvas GSD", "GSD", "m/px", "GSD = ((Pitch * (NativeW / CanvasW)) / FocalLength) * Range"),
            ("Target Misalignment", "Delta m", "m", "Delta m = Delta px * GSD"),
            ("Co-Boresight Angle", "mrad_err", "mrad", "mrad_err = (Delta m / Range) * 1000")
        ]
        for r_idx, (param, ref, unit, eq) in enumerate(formulas, start=10):
            worksheet.write(r_idx, 0, param); worksheet.write(r_idx, 1, ref, ref_fmt)
            worksheet.write(r_idx, 2, unit); worksheet.write(r_idx, 3, eq)

        worksheet.write('A17', "3. CO-BORESIGHT DATA EXPORT", bold_fmt)

        # Plot headers and images
        start_img_col = len(df.columns)
        plot_headers = ['Translation Misalignment X', 'Translation Misalignment Y', 'Total Translation Misalignment', 'Angular Misalignment X', 'Angular Misalignment Y', 'Total Angular Misalignment']
        for col_idx, header in enumerate(plot_headers, start=start_img_col):
            worksheet.write(DATA_START_ROW-1, col_idx, header, header_fmt)

        for row_idx, paths in enumerate(plot_records, start=DATA_START_ROW):
            worksheet.set_row(row_idx, 180)
            if paths[0] is None:
                for col_idx in range(6):
                    worksheet.write(row_idx, start_img_col + col_idx, "IMAGE REJECTED DUE TO NOISE", reject_fmt)
                continue
            for offset, img_path in enumerate(paths):
                if os.path.exists(img_path):
                    worksheet.insert_image(row_idx, start_img_col + offset, img_path, {'x_scale': 0.75, 'y_scale': 0.75, 'positioning': 1})

    return True, f"Successfully generated report: {excel_output_path}", df
