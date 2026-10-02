"""Dashboard local del Temp Logger.

Ejecutar desde esta carpeta:  streamlit run Dashboard.py

Este archivo es solo la interfaz: qué se muestra y dónde. La lógica de
datos está en templogger_dash/ (loader, filters, stats, charts, variables).
"""

from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from templogger_dash import charts, filters, loader, stats, variables
from templogger_dash.loader import TIME_COLUMN

APP_DIR = Path(__file__).parent
DEFAULT_DATA_FOLDER = "data"

TIMEZONES = {"Melbourne": "Australia/Melbourne", "UTC": "UTC"}
REFRESH_SECONDS = {"10 s": 10, "30 s": 30, "1 min": 60, "5 min": 300}

# El CSV guarda las clases y las alertas en español (es el contrato con el
# firmware). Aquí solo se traducen para mostrarlas.
CLASS_BADGES = {
    "bajo": ("Low", "orange", ":material/arrow_downward:"),
    "normal": ("Normal", "gray", ":material/check:"),
    "alto": ("High", "orange", ":material/arrow_upward:"),
    "?": ("No reading", "red", ":material/error:"),
}
ALERT_BADGES = {
    "FALLA_SENSOR": ("Sensor fault", "red", ":material/error:"),
    "VALOR_IMPOSIBLE": ("Impossible value", "red", ":material/error:"),
    "CALOR_HUMEDO": ("Hot and humid", "orange", ":material/warning:"),
    "CONDENSACION": ("Condensation risk", "orange", ":material/warning:"),
    "T_NO_COINCIDE": ("Temperature sensors disagree", "orange", ":material/warning:"),
    "PRESION_BAJANDO": ("Pressure falling", "orange", ":material/warning:"),
    "OSCURO": ("Dark", "gray", ":material/dark_mode:"),
}
METRICS_PER_ROW = 4


# ----------------------------------------------------------------------------
# Datos
# ----------------------------------------------------------------------------

@st.cache_data(show_spinner=False, max_entries=400)
def read_file_cached(path: str, mtime_ns: int, size: int) -> tuple[pd.DataFrame, dict]:
    """Lee un archivo una sola vez mientras no cambien su fecha ni su tamaño.

    El informe se guarda como diccionario: la caché serializa lo que guarda,
    y un diccionario sobrevive a que Streamlit recargue el código tras
    editarlo, cosa que un objeto de una clase propia no siempre hace.
    """
    df, report = loader.read_csv_file(path)
    return df, asdict(report)


def load_data(folder: Path) -> loader.LoadResult:
    frames, reports = [], []
    for path in loader.discover_csv_files(folder):
        try:
            signature = loader.file_signature(path)
        except OSError:
            continue  # el archivo desapareció entre listar y leer
        df, report = read_file_cached(*signature)
        frames.append(df)
        reports.append(loader.FileReport(**report))
    data, duplicates = loader.combine(frames)
    return loader.LoadResult(data, tuple(reports), duplicates)


def format_age(age: pd.Timedelta) -> str:
    seconds = abs(age.total_seconds())
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 90 * 60:
        return f"{seconds / 60:.0f} min"
    if seconds < 48 * 3600:
        return f"{seconds / 3600:.0f} h"
    return f"{seconds / 86400:.0f} days"


# ----------------------------------------------------------------------------
# Secciones de la página
# ----------------------------------------------------------------------------

def show_status(df: pd.DataFrame, tz: str, tz_label: str) -> None:
    """Hora de la última medición y si el logger sigue enviando datos."""
    last_time = df[TIME_COLUMN].iloc[-1]
    age = pd.Timestamp.now(tz="UTC") - last_time
    step = stats.median_interval(df) or pd.Timedelta(minutes=1)
    live_limit = max(step * 3, pd.Timedelta(minutes=2))

    with st.container(horizontal=True, vertical_alignment="center"):
        if age < -live_limit:
            st.badge("Dated ahead of this computer's clock", icon=":material/schedule:", color="gray")
        elif age <= live_limit:
            st.badge("Live", icon=":material/sensors:", color="green")
        else:
            st.badge(f"No new data for {format_age(age)}", icon=":material/sensors_off:", color="gray")
        local = last_time.tz_convert(tz)
        st.caption(f"Last measurement: {local:%a %d %b %Y, %H:%M:%S} ({tz_label})")


def show_latest(df: pd.DataFrame, columns: list[str]) -> None:
    """Un recuadro por variable con el último valor, su cambio y su clase."""
    latest = df.iloc[-1]
    hour_before = latest[TIME_COLUMN] - pd.Timedelta(hours=1)

    per_row = min(len(columns), METRICS_PER_ROW)
    for start in range(0, len(columns), per_row):
        row = columns[start:start + per_row]
        for slot, column in zip(st.columns(per_row), row):
            var = variables.describe(column)
            value = latest[column]
            before = stats.value_before(df, column, hour_before)
            delta, arrow = None, "auto"
            if pd.notna(value) and before is not None:
                change = round(value - before, var.decimals)
                if change == 0:
                    delta, arrow = "No change in the last hour", "off"
                else:
                    delta = f"{change:+.{var.decimals}f} {var.unit} in the last hour"
            with slot.container(border=True):
                # delta_color="off": subir o bajar no es bueno ni malo aquí.
                st.metric(var.label, var.format(value), delta, delta_color="off", delta_arrow=arrow)
                if var.class_column in df.columns:
                    label, color, icon = CLASS_BADGES.get(
                        latest[var.class_column], (str(latest[var.class_column]), "gray", None)
                    )
                    st.badge(label, icon=icon, color=color)

    alerts = stats.split_alerts(latest.get(stats.ALERT_COLUMN, ""))
    with st.container(horizontal=True, vertical_alignment="center"):
        st.caption("Active alerts:" if alerts else "No active alerts.", width="content")
        for alert in alerts:
            label, color, icon = ALERT_BADGES.get(alert, (alert, "orange", ":material/warning:"))
            st.badge(label, icon=icon, color=color)


def choose_window(df: pd.DataFrame, tz: str, tz_label: str) -> tuple[filters.TimeWindow, str]:
    """Selector del periodo. Devuelve la ventana y una clave que la identifica."""
    anchor = df[TIME_COLUMN].iloc[-1]
    period = st.segmented_control(
        "Period", [*filters.PRESETS, filters.CUSTOM],
        default=filters.LAST_24_HOURS, required=True, key="period",
    )
    if period != filters.CUSTOM:
        return filters.preset_window(period, anchor, tz), period

    first_local = df[TIME_COLUMN].iloc[0].tz_convert(tz).tz_localize(None)
    last_local = anchor.tz_convert(tz).tz_localize(None)
    left, right = st.columns(2)
    start = left.datetime_input(
        f"From ({tz_label})", value=max(first_local, last_local - pd.Timedelta(hours=24)),
        step=timedelta(minutes=15), format="YYYY-MM-DD", key="custom_from",
    )
    end = right.datetime_input(
        f"To ({tz_label})", value=last_local,
        step=timedelta(minutes=15), format="YYYY-MM-DD", key="custom_to",
    )
    if start > end:
        st.warning("'From' is later than 'To', so the period is empty.")
    return filters.custom_window(start, end, tz), f"{period}|{start}|{end}"


def show_summary(view: pd.DataFrame, columns: list[str]) -> None:
    summary = stats.summarize(view, columns)
    table = pd.DataFrame({
        "Variable": [variables.describe(c).label for c in summary.index],
        "Unit": [variables.describe(c).unit for c in summary.index],
        "Minimum": summary["min"].to_numpy(),
        "Maximum": summary["max"].to_numpy(),
        "Mean": summary["mean"].to_numpy(),
        "Measurements": summary["count"].to_numpy(),
    })
    number = st.column_config.NumberColumn(format="%.2f")
    st.dataframe(
        table, hide_index=True,
        column_config={"Minimum": number, "Maximum": number, "Mean": number},
    )


def show_alerts(view: pd.DataFrame) -> None:
    counts = stats.alert_counts(view)
    with st.expander(f"Alerts in this period ({len(counts)})"):
        if counts.empty:
            st.caption("No alerts in this period.")
            return
        table = pd.DataFrame({
            "Alert": [ALERT_BADGES.get(a, (a,))[0] for a in counts.index],
            "Code in the CSV": counts.index,
            "Measurements": counts.to_numpy(),
            "Share of the period (%)": (100 * counts / len(view)).to_numpy(),
        })
        st.dataframe(
            table, hide_index=True,
            column_config={"Share of the period (%)": st.column_config.NumberColumn(format="%.1f")},
        )


def show_table(view: pd.DataFrame, tz: str, tz_label: str) -> None:
    with st.expander("Measurements table"):
        table = view.drop(columns=TIME_COLUMN)
        table.insert(0, f"Time ({tz_label})", charts.to_display_time(view[TIME_COLUMN], tz))
        st.dataframe(table, hide_index=True)
        # El archivo descargado conserva el formato del logger (hora en UTC).
        export = view.assign(**{TIME_COLUMN: view[TIME_COLUMN].dt.strftime(loader.TIMESTAMP_FORMAT)})
        st.download_button(
            "Download this period as CSV", export.to_csv(index=False),
            file_name="templogger_period.csv", mime="text/csv", on_click="ignore",
            icon=":material/download:",
        )


def show_quality(result: loader.LoadResult, view: pd.DataFrame) -> None:
    """Qué archivos se leyeron y qué se descartó al leerlos."""
    problems = sum(
        r.no_timestamp + r.malformed + bool(r.error) for r in result.files
    ) + result.duplicates_removed
    title = f"Data files and quality ({len(result.files)} files"
    title += ", some rows set aside)" if problems else ")"
    with st.expander(title):
        table = pd.DataFrame({
            "File": [r.name for r in result.files],
            "Rows read": [r.rows_read for r in result.files],
            "Valid rows": [r.rows_valid for r in result.files],
            "No valid time": [r.no_timestamp for r in result.files],
            "Malformed": [r.malformed for r in result.files],
            "Repeated headers": [r.repeated_headers for r in result.files],
            "Line still being written": [r.incomplete_last_line for r in result.files],
            "Problem": [r.error for r in result.files],
        })
        st.dataframe(table, hide_index=True)
        st.caption(
            f"Duplicate times removed: {result.duplicates_removed}. "
            f"Gaps in the selected period: {charts.count_gaps(view)}. "
            "Rows without a valid time cannot be placed on the time axis, so they are left out."
        )


# ----------------------------------------------------------------------------
# Página
# ----------------------------------------------------------------------------

def render(folder: Path, columns: list[str], tz_label: str, log_columns: tuple[str, ...]) -> None:
    """Cuerpo de la página. Se vuelve a ejecutar solo, cada cierto tiempo."""
    tz = TIMEZONES[tz_label]
    result = load_data(folder)
    df = result.data

    if not result.files:
        st.info(
            f"No CSV files found in `{folder}`. "
            "The logger writes one file per day, named `YYYY-MM-DD.csv`."
        )
        return
    if df.empty:
        st.warning("The files were read, but none of their rows has a valid time.")
        show_quality(result, df)
        return

    show_status(df, tz, tz_label)

    st.subheader("Latest readings")
    if columns:
        show_latest(df, columns)

    st.subheader("History")
    window, window_key = choose_window(df, tz, tz_label)
    view = filters.apply_window(df, window)

    if view.empty:
        st.info("No measurements in this period.")
    elif not columns:
        st.info("Choose at least one variable in the sidebar.")
    else:
        first = view[TIME_COLUMN].iloc[0].tz_convert(tz)
        last = view[TIME_COLUMN].iloc[-1].tz_convert(tz)
        gaps = charts.count_gaps(view)
        st.caption(
            f"{len(view):,} measurements, from {first:%a %d %b %H:%M} to {last:%a %d %b %H:%M} ({tz_label})"
            + (f" · {gaps} gap{'s' if gaps != 1 else ''} in the record" if gaps else "")
        )
        dark = getattr(st.context.theme, "type", "light") == "dark"
        fig = charts.timeseries_figure(
            view, columns, tz, tz_label, dark=dark, log_columns=log_columns,
            view_key=f"{window_key}|{tz_label}|{','.join(columns)}",
        )
        st.plotly_chart(fig, key="timeseries", config={"displaylogo": False})

        st.subheader("Summary of the period")
        show_summary(view, columns)
        show_alerts(view)
        show_table(view, tz, tz_label)

    show_quality(result, view)


st.set_page_config(page_title="Temp Logger", page_icon=":material/thermostat:", layout="wide")
st.title("Temp Logger")

with st.sidebar:
    st.header("Settings")
    folder_text = st.text_input(
        "Data folder", DEFAULT_DATA_FOLDER,
        help="Folder with the logger's daily CSV files. A relative path starts at the dashboard's folder.",
    )
    data_folder = Path(folder_text) if Path(folder_text).is_absolute() else APP_DIR / folder_text

    loaded = load_data(data_folder).data
    selected = st.multiselect(
        "Variables", variables.measurement_columns(loaded),
        default=variables.default_columns(loaded),
        format_func=lambda c: variables.describe(c).label,
    )
    log_selected = tuple(
        c for c in selected
        if variables.describe(c).log_scale
        and st.toggle(f"Log scale for {variables.describe(c).label.lower()}", True, key=f"log_{c}")
    )
    tz_choice = st.radio("Time zone", list(TIMEZONES), horizontal=True)

    st.divider()
    auto_refresh = st.toggle("Auto-refresh", True, help="Re-read the data folder to pick up new measurements.")
    refresh_label = st.selectbox(
        "Check for new data every", list(REFRESH_SECONDS), index=1, disabled=not auto_refresh,
    )

# Un fragmento es una parte de la página que Streamlit puede volver a ejecutar
# sola. Con run_every se repite cada N segundos: vuelve a mirar la carpeta y,
# gracias a la caché, solo lee de nuevo los archivos que cambiaron.
st.fragment(render, run_every=REFRESH_SECONDS[refresh_label] if auto_refresh else None)(
    data_folder, selected, tz_choice, log_selected
)
