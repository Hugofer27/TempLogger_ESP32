"""Dashboard local del Temp Logger (versión mínima v0.1).

Ejecutar desde esta carpeta:  streamlit run Dashboard.py
"""

from pathlib import Path

import plotly.express as px
import streamlit as st

from templogger_dash.loader import load_folder

DATA_DIR = Path(__file__).parent / "data"
LOCAL_TZ = "Australia/Melbourne"

# Variables que se muestran: columna del CSV → (etiqueta, unidad).
VARIABLES = {
    "t_aht_c": ("Temperature", "°C"),
    "hr_pct": ("Relative humidity", "%"),
    "lux": ("Light", "lx"),
}

st.set_page_config(page_title="Temp Logger", layout="wide")
st.title("Unit  Logger")

df = load_folder(DATA_DIR)
if df.empty:
    st.warning(f"No CSV files found in {DATA_DIR}")
    st.stop()

# El CSV va en UTC; la hora de Melbourne solo se usa para mostrar.
df["time_local"] = df["timestamp_utc"].dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)

latest = df.iloc[-1]
st.caption(f"Last measurement: {latest['time_local']:%Y-%m-%d %H:%M} (Melbourne) · {len(df)} rows")

for col, (column, (label, unit)) in zip(st.columns(len(VARIABLES)), VARIABLES.items()):
    col.metric(label, f"{latest[column]:.1f} {unit}")

for column, (label, unit) in VARIABLES.items():
    fig = px.line(df, x="time_local", y=column, title=label,
                  labels={"time_local": "Time (Melbourne)", column: f"{label} ({unit})"})
    st.plotly_chart(fig)
