import os
import warnings
import cv2
import matplotlib.pyplot as plt
import numpy as np
from openpyxl import load_workbook
from openpyxl.drawing.image import Image
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment
import pandas as pd

HEADER_FILL = PatternFill(start_color="F47D30", end_color="F47D30", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
INPUT_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
REF_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
BOLD_FONT = Font(bold=True)

def create_misalignment_plot(val_x, val_y, max_scale, unit, plot_type, title_text, save_path):
    fig, ax = plt.subplots(figsize=(3.4, 3.4), dpi=120)
    for r, c in zip([1.0, 0.75, 0.5, 0.25], ['#e2e8f0', '#cbd5e1', '#94a3b8', '#64748b']):
        radius = max_scale * r
        ax.add_patch(plt.Circle((0, 0), radius, color=c, fill=False, lw=1.2, alpha=0.45 if plot_type != 'total' else 1.0))
        label_x = radius * np.cos(np.radians(45))
        label_y = radius * np.sin(np.radians(45))
        ax.text(label_x, label_y, f'{radius:.2g} {unit}', color='#475569', fontsize=6.5, 
                ha='center', va='center', rotation=0, bbox=dict(facecolor='white', edgecolor='none', pad=1.0, alpha=0.75))
    ax.axhline(0, color='#94a3b8' if plot_type != 'y' else '#0f172a', linestyle=':' if plot_type != 'y' else '-', lw=1 if plot_type != 'y' else 1.5)
    ax.axvline(0, color='#94a3b8' if plot_type != 'x' else '#0f172a', linestyle=':' if plot_type != 'x' else '-', lw=1 if plot_type != 'x' else 1.5)
    ax.plot(0, 0, marker='o', markersize=4, color='#0f172a')
    
    if plot_type == 'x':
        ax.plot([0, val_x], [0, 0], color='#0891b2', linestyle='-', lw=2.5)
        ax.plot(val_x, 0, marker='|', color='#0891b2', markersize=22, markeredgewidth=3)
        ax.plot(val_x, 0, marker='o', color='#0891b2', markersize=5)
        offset_y = max_scale * 0.12 if val_x >= 0 else -max_scale * 0.12
        ax.annotate(f'{val_x:+.3f} {unit}', xy=(val_x, 0), xytext=(val_x, offset_y), ha='center', va='bottom' if val_x >= 0 else 'top', fontsize=8, color='#0891b2', fontweight='bold')
    elif plot_type == 'y':
        ax.plot([0, 0], [0, val_y], color='#0891b2', linestyle='-', lw=2.5)
        ax.plot(0, val_y, marker='_', color='#0891b2', markersize=22, markeredgewidth=3)
        ax.plot(0, val_y, marker='o', color='#0891b2', markersize=5)
        offset_x = max_scale * 0.12 if val_y >= 0 else -max_scale * 0.12
        ax.annotate(f'{val_y:+.3f} {unit}', xy=(0, val_y), xytext=(offset_x, val_y), va='center', ha='left' if val_y >= 0 else 'right', fontsize=8, color='#0891b2', fontweight='bold')
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
    
    # Strictly filter Excel data to ONLY the system numbers currently loaded in the UI queue
    if active_systems is not None:
        df = df[df["Subfolder ID"].isin(active_systems)]
        
    if df.empty:
        return False, "No relevant data found for the systems currently in the queue.", None
    
    expected_cols = ["Subfolder ID", "EON Mast Center X", "EON Horizon Y", "MWIR Mast Center X", "MWIR Horizon Y", "Status"]
    if not set(expected_cols).issubset(df.columns): return False, "Input Excel is missing required columns.", None

    df = df[expected_cols]
    cols_to_clean = ['EON Mast Center X', 'EON Horizon Y', 'MWIR Mast Center X', 'MWIR Horizon Y']
    for col in cols_to_clean:
        df[col] = df[col].replace(r'^\s*$', np.nan, regex=True)
        df[col] = pd.to_numeric(df[col], errors='coerce')

    plot_records = []
    DATA_START_ROW = 17
    out_px_x, out_px_y, out_miss_x, out_miss_y, out_tot_miss, out_mrad_x, out_mrad_y, out_tot_mrad = [], [], [], [], [], [], [], []
    num_px_x, num_px_y, num_miss_x, num_miss_y, num_tot_miss, num_mrad_x, num_mrad_y, num_tot_mrad = [], [], [], [], [], [], [], []

    for i, row in df.iterrows():
        subfolder = str(row['Subfolder ID']).zfill(3)
        if pd.isna(row.get('EON Mast Center X')) or pd.isna(row.get('MWIR Mast Center X')) or pd.isna(row.get('EON Horizon Y')) or pd.isna(row.get('MWIR Horizon Y')):
            out_px_x.append("REJECTED"); out_px_y.append("REJECTED"); out_miss_x.append("REJECTED"); out_miss_y.append("REJECTED")
            out_tot_miss.append("REJECTED"); out_mrad_x.append("REJECTED"); out_mrad_y.append("REJECTED"); out_tot_mrad.append("REJECTED")
            num_px_x.append("REJECTED"); num_px_y.append("REJECTED"); num_miss_x.append("REJECTED"); num_miss_y.append("REJECTED")
            num_tot_miss.append("REJECTED"); num_mrad_x.append("REJECTED"); num_mrad_y.append("REJECTED"); num_tot_mrad.append("REJECTED")
            plot_records.append((None, None, None, None, None, None))
            continue

        delta_px_x = row['MWIR Mast Center X'] - row['EON Mast Center X']
        delta_px_y = row['MWIR Horizon Y'] - row['EON Horizon Y']
        eff_pitch_mm = MWIR_NATIVE_PITCH_MM * (MWIR_NATIVE_W_PX / CANVAS_W_PX)
        canvas_gsd_m_px = (eff_pitch_mm / MWIR_FOCAL_LEN_MM) * RANGE_M
        delta_m_x = delta_px_x * canvas_gsd_m_px
        delta_m_y = delta_px_y * canvas_gsd_m_px
        mrad_x = (delta_m_x / RANGE_M) * 1000.0
        mrad_y = (delta_m_y / RANGE_M) * 1000.0
        
        num_px_x.append(round(delta_px_x, 2)); num_px_y.append(round(delta_px_y, 2))
        num_miss_x.append(round(delta_m_x, 3)); num_miss_y.append(round(delta_m_y, 3))
        num_tot_miss.append(round(np.sqrt(delta_m_x**2 + delta_m_y**2), 3))
        num_mrad_x.append(round(mrad_x, 3)); num_mrad_y.append(round(mrad_y, 3))
        num_tot_mrad.append(round(np.sqrt(mrad_x**2 + mrad_y**2), 3))

        p_trans_x = os.path.join(plot_dir, f'{subfolder}_1_trans_x.png')
        p_trans_y = os.path.join(plot_dir, f'{subfolder}_2_trans_y.png')
        p_trans_tot = os.path.join(plot_dir, f'{subfolder}_3_trans_total.png')
        p_ang_x = os.path.join(plot_dir, f'{subfolder}_4_ang_x.png')
        p_ang_y = os.path.join(plot_dir, f'{subfolder}_5_ang_y.png')
        p_ang_tot = os.path.join(plot_dir, f'{subfolder}_6_ang_total.png')

        create_misalignment_plot(delta_m_x, 0, PLOT_MAX_SCALE_M, 'm', 'x', f'[{subfolder}] Trans X: {delta_m_x:+.3f} m', p_trans_x)
        create_misalignment_plot(0, delta_m_y, PLOT_MAX_SCALE_M, 'm', 'y', f'[{subfolder}] Trans Y: {delta_m_y:+.3f} m', p_trans_y)
        create_misalignment_plot(delta_m_x, delta_m_y, PLOT_MAX_SCALE_M, 'm', 'total', f'[{subfolder}] Trans Tot: {np.sqrt(delta_m_x**2 + delta_m_y**2):.3f} m', p_trans_tot)
        create_misalignment_plot(mrad_x, 0, PLOT_MAX_SCALE_MRAD, 'mrad', 'x', f'[{subfolder}] Ang X: {mrad_x:+.3f} mrad', p_ang_x)
        create_misalignment_plot(0, mrad_y, PLOT_MAX_SCALE_MRAD, 'mrad', 'y', f'[{subfolder}] Ang Y: {mrad_y:+.3f} mrad', p_ang_y)
        create_misalignment_plot(mrad_x, mrad_y, PLOT_MAX_SCALE_MRAD, 'mrad', 'total', f'[{subfolder}] Ang Tot: {np.sqrt(mrad_x**2 + mrad_y**2):.3f} mrad', p_ang_tot)
        plot_records.append((p_trans_x, p_trans_y, p_trans_tot, p_ang_x, p_ang_y, p_ang_tot))

        r = DATA_START_ROW + 2 + i 
        out_px_x.append(f'=D{r}-B{r}')
        out_px_y.append(f'=E{r}-C{r}')
        out_miss_x.append(f'=G{r} * ((($B$5 * ($B$6/$B$7)) / $B$4) * $B$3)')
        out_miss_y.append(f'=H{r} * ((($B$5 * ($B$6/$B$7)) / $B$4) * $B$3)')
        out_tot_miss.append(f'=SQRT((I{r}*I{r}) + (J{r}*J{r}))')
        out_mrad_x.append(f'=(I{r}/$B$3)*1000')
        out_mrad_y.append(f'=(J{r}/$B$3)*1000')
        out_tot_mrad.append(f'=SQRT((L{r}*L{r}) + (M{r}*M{r}))')

    df['Pixel Offset X (px)'] = out_px_x; df['Pixel Offset Y (px)'] = out_px_y
    df['Target Misalignment X (m)'] = out_miss_x; df['Target Misalignment Y (m)'] = out_miss_y
    df['Total Target Misalignment (m)'] = out_tot_miss; df['Co-Boresight Error X (mrad)'] = out_mrad_x
    df['Co-Boresight Error Y (mrad)'] = out_mrad_y; df['Total Co-Boresight Error (mrad)'] = out_tot_mrad

    with pd.ExcelWriter(excel_output_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='CoBoresight', startrow=DATA_START_ROW)

    wb = load_workbook(excel_output_path)
    ws = wb.active

    ws['A1'] = "CO-BORESIGHT MISALIGNMENT EXECUTION SHEET (PHYSICAL METERS-FIRST)"
    ws['A1'].fill = HEADER_FILL; ws['A1'].font = HEADER_FONT; ws.merge_cells('A1:T1')  

    ws['A2'] = "1. SYSTEM CONSTANTS"; ws['A2'].font = BOLD_FONT
    constants = [
        ("Target Range", RANGE_M, "m", "Distance to target"),
        ("MWIR Focal Length", MWIR_FOCAL_LEN_MM, "mm", "Physical Lens Focal Length"),
        ("MWIR Native Pixel Pitch", MWIR_NATIVE_PITCH_MM, "mm", "Physical Sensor Pixel Size"),
        ("MWIR Native Width", MWIR_NATIVE_W_PX, "px", "Native sensor width from Spec Table"),
        ("Screenshot Canvas Width", CANVAS_W_PX, "px", "Scaled width of diagnostic images")
    ]
    for r_idx, (param, val, unit, desc) in enumerate(constants, start=3):
        ws[f'A{r_idx}'] = param; ws[f'B{r_idx}'] = val; ws[f'B{r_idx}'].fill = INPUT_FILL; ws[f'B{r_idx}'].font = BOLD_FONT
        ws[f'C{r_idx}'] = unit; ws[f'D{r_idx}'] = desc

    ws['A9'] = "2. CALCULATED PROFILE REDUCTION PARAMETERS"; ws['A9'].font = BOLD_FONT
    ws['A10'], ws['B10'], ws['C10'], ws['D10'] = "Parameter", "Ref Code", "Units", "Math Equation (Live Excel Cells)"
    for col in ['A', 'B', 'C', 'D']: ws[f'{col}10'].font = BOLD_FONT
    
    formulas = [
        ("Pixel Offset", "Delta px", "px", "Delta px = MWIR_Coord - EON_Coord"),
        ("Canvas GSD", "GSD", "m/px", "GSD = ((Pitch * (NativeW / CanvasW)) / FocalLength) * Range"),
        ("Target Misalignment", "Delta m", "m", "Delta m = Delta px * GSD"),
        ("Co-Boresight Angle", "mrad_err", "mrad", "mrad_err = (Delta m / Range) * 1000")
    ]
    for r_idx, (param, ref, unit, eq) in enumerate(formulas, start=11):
        ws[f'A{r_idx}'] = param; ws[f'B{r_idx}'] = ref; ws[f'B{r_idx}'].fill = REF_FILL
        ws[f'C{r_idx}'] = unit; ws[f'D{r_idx}'] = eq

    ws['A17'] = "3. CO-BORESIGHT DATA EXPORT"; ws['A17'].font = BOLD_FONT
    df_header_row = DATA_START_ROW + 1
    for col in range(1, len(df.columns) + 1):
        cell = ws.cell(row=df_header_row, column=col)
        cell.fill = HEADER_FILL; cell.font = HEADER_FONT; cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        ws.column_dimensions[get_column_letter(col)].width = 18

    ws.column_dimensions[get_column_letter(6)].width = 30 

    start_img_col = len(df.columns) + 1
    plot_column_headers = ['Translation Misalignment X', 'Translation Misalignment Y', 'Total Translation Misalignment', 'Angular Misalignment X', 'Angular Misalignment Y', 'Total Angular Misalignment']
    for offset, header in enumerate(plot_column_headers):
        col_letter = get_column_letter(start_img_col + offset)
        cell = ws.cell(row=df_header_row, column=start_img_col + offset, value=header)
        cell.fill = HEADER_FILL; cell.font = HEADER_FONT; ws.column_dimensions[col_letter].width = 38

    for row_idx, paths in enumerate(plot_records, start=df_header_row + 1):
        ws.row_dimensions[row_idx].height = 180
        if paths[0] is None:
            for offset in range(6):
                col_letter = get_column_letter(start_img_col + offset)
                cell = ws.cell(row=row_idx, column=start_img_col + offset, value="IMAGE REJECTED DUE TO NOISE")
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); cell.font = Font(color="FF0000", bold=True)
            continue
        for offset, img_path in enumerate(paths):
            if not os.path.exists(img_path): continue
            img = Image(img_path)
            img.width, img.height = 210, 210
            col_letter = get_column_letter(start_img_col + offset)
            ws.add_image(img, f'{col_letter}{row_idx}')

    wb.save(excel_output_path)
    
    df_display = df.copy()
    df_display['Pixel Offset X (px)'] = num_px_x; df_display['Pixel Offset Y (px)'] = num_px_y
    df_display['Target Misalignment X (m)'] = num_miss_x; df_display['Target Misalignment Y (m)'] = num_miss_y
    df_display['Total Target Misalignment (m)'] = num_tot_miss; df_display['Co-Boresight Error X (mrad)'] = num_mrad_x
    df_display['Co-Boresight Error Y (mrad)'] = num_mrad_y; df_display['Total Co-Boresight Error (mrad)'] = num_tot_mrad
    
    return True, f"Successfully generated report: {excel_output_path}", df_display