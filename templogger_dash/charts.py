"""Gráficas de la serie de tiempo (Plotly).

Aquí vive el estilo de las gráficas: alturas, grosor de línea, escala
logarítmica y el cuadro que aparece al pasar el ratón. Los colores, nombres
y unidades de cada variable están en variables.py.
"""

import math

import pandas as pd
import plotly.graph_objects as go

from .loader import TIME_COLUMN
from .stats import median_interval
from .variables import describe

ROW_HEIGHT = 200  # alto de cada gráfica, en píxeles
ROW_GAP = 54  # espacio entre gráficas (ahí va el título de la siguiente)
MARGIN_TOP = 34
MARGIN_BOTTOM = 56
LINE_WIDTH = 2

# Un hueco es una pausa mayor que este número de intervalos normales.
GAP_FACTOR = 3

# En un eje logarítmico no existe el cero. Las lecturas de 0 (oscuridad
# total) se dibujan en este piso, por debajo de la resolución del sensor
# (1 lx en el BH1750); el cuadro del ratón sigue mostrando el valor real.
LOG_FLOOR = 0.1


def to_display_time(time_utc: pd.Series, tz: str) -> pd.Series:
    """Hora UTC → hora de reloj de la zona elegida, solo para mostrar.

    Plotly no maneja zonas horarias: se le entrega la hora local ya
    convertida y sin zona.
    """
    return time_utc.dt.tz_convert(tz).dt.tz_localize(None)


def insert_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Añade una fila vacía después de cada corte del registro.

    Plotly une con una recta dos puntos seguidos aunque entre ellos pasen
    horas, y eso inventa datos que nadie midió. Una fila con NaN en medio
    le hace levantar el lápiz.
    """
    step = median_interval(df)
    if step is None:
        return df
    pause_after = df[TIME_COLUMN].diff().shift(-1) > step * GAP_FACTOR
    if not pause_after.any():
        return df
    markers = pd.DataFrame({TIME_COLUMN: df.loc[pause_after, TIME_COLUMN] + step})
    with_gaps = pd.concat([df, markers], ignore_index=True)
    return with_gaps.sort_values(TIME_COLUMN, kind="stable").reset_index(drop=True)


def count_gaps(df: pd.DataFrame) -> int:
    """Número de cortes del registro en el tramo."""
    step = median_interval(df)
    if step is None:
        return 0
    return int((df[TIME_COLUMN].diff() > step * GAP_FACTOR).sum())


def log_ticks(values: pd.Series) -> dict:
    """Marcas de un eje logarítmico, escritas con el número completo.

    Por defecto Plotly rotula "2, 5, 10, 2, 5, 100", que se lee mal. Si los
    datos abarcan pocas décadas se marcan 1-2-5 de cada una; si abarcan
    muchas, solo las potencias de 10.
    """
    positive = values[values > 0]
    if positive.empty:
        return {}
    low = math.floor(math.log10(positive.min()))
    high = math.ceil(math.log10(positive.max()))
    if high - low > 3:
        return {"dtick": 1}
    ticks = [m * 10.0**e for e in range(low, high + 1) for m in (1, 2, 5)]
    return {"tickmode": "array", "tickvals": ticks, "ticktext": [f"{t:g}" for t in ticks]}


def figure_height(n_rows: int) -> int:
    plot = n_rows * ROW_HEIGHT + (n_rows - 1) * ROW_GAP
    return plot + MARGIN_TOP + MARGIN_BOTTOM


def timeseries_figure(
    df: pd.DataFrame,
    columns: list[str],
    tz: str,
    tz_label: str,
    *,
    dark: bool = False,
    log_columns: tuple[str, ...] = (),
    view_key: str = "",
) -> go.Figure:
    """Una gráfica por variable, apiladas y con el eje de tiempo compartido.

    Cada variable tiene su propio eje Y (nunca dos escalas en la misma
    gráfica). Todas cuelgan del mismo eje X: el zoom y el cursor recorren
    las gráficas a la vez.
    """
    plot_df = insert_gaps(df)
    x = to_display_time(plot_df[TIME_COLUMN], tz)

    n = len(columns)
    plot_height = n * ROW_HEIGHT + (n - 1) * ROW_GAP
    row = ROW_HEIGHT / plot_height
    gap = ROW_GAP / plot_height

    fig = go.Figure()
    layout: dict = {}
    annotations = []
    for i, column in enumerate(columns):
        var = describe(column)
        axis = "" if i == 0 else str(i + 1)
        top = 1 - i * (row + gap)
        use_log = column in log_columns

        values = plot_df[column]
        drawn = values.mask(values <= 0, LOG_FLOOR) if use_log else values
        unit = f" {var.unit}" if var.unit else ""
        fig.add_trace(
            go.Scatter(
                x=x,
                y=drawn,
                customdata=values,
                mode="lines",
                name=var.label,
                line={"color": var.color(dark), "width": LINE_WIDTH},
                connectgaps=False,
                xaxis="x",
                yaxis=f"y{axis}",
                hovertemplate=f"%{{customdata:.{var.decimals}f}}{unit}<extra>{var.label}</extra>",
            )
        )
        layout[f"yaxis{axis}"] = {
            "domain": [max(top - row, 0), top],
            "type": "log" if use_log else "linear",
            "zeroline": False,
            "automargin": True,
            **(log_ticks(drawn) if use_log else {}),
        }
        title = f"<b>{var.label}</b>" + (f" ({var.unit})" if var.unit else "")
        if use_log:
            title += " · log scale"
        annotations.append(
            {
                "text": title, "showarrow": False,
                "xref": "paper", "x": 0, "xanchor": "left",
                "yref": "paper", "y": top, "yanchor": "bottom", "yshift": 6,
            }
        )

    last_axis = "y" if n == 1 else f"y{n}"
    fig.update_layout(
        **layout,
        xaxis={
            "anchor": last_axis,
            "title": {"text": f"Time ({tz_label})"},
            "hoverformat": "%a %d %b %Y, %H:%M",
            "showspikes": True,
            "spikemode": "across",
            "spikethickness": 1,
            "spikedash": "solid",
            "spikesnap": "cursor",
        },
        annotations=annotations,
        height=figure_height(n),
        margin={"l": 8, "r": 8, "t": MARGIN_TOP, "b": MARGIN_BOTTOM},
        showlegend=False,
        # Un solo cuadro con el valor de todas las variables en ese instante.
        hovermode="x unified",
        hoversubplots="axis",
        # Mientras esta clave no cambie, Plotly conserva el zoom aunque
        # lleguen datos nuevos.
        uirevision=view_key,
    )
    return fig
