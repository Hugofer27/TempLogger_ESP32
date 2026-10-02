"""Resúmenes numéricos de un tramo de la serie."""

import pandas as pd

from .loader import TIME_COLUMN

ALERT_COLUMN = "alertas"
ALERT_SEPARATOR = "|"


def summarize(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Mínimo, máximo, media y número de mediciones de cada columna.

    `count` cuenta solo los valores presentes: si un sensor estuvo caído,
    su n es menor que el número de filas del periodo.
    """
    columns = [c for c in columns if c in df.columns]
    summary = df[columns].agg(["min", "max", "mean", "count"]).T
    summary["count"] = summary["count"].astype(int)
    return summary


def median_interval(df: pd.DataFrame) -> pd.Timedelta | None:
    """Tiempo típico entre dos mediciones seguidas.

    Se usa la mediana y no la media porque un solo corte largo movería
    mucho la media y casi nada la mediana.
    """
    steps = df[TIME_COLUMN].diff().dropna()
    return steps.median() if len(steps) else None


def split_alerts(cell: str) -> list[str]:
    """'A|B' → ['A', 'B']; una celda vacía → []."""
    return [a for a in str(cell).split(ALERT_SEPARATOR) if a]


def alert_counts(df: pd.DataFrame) -> pd.Series:
    """Número de mediciones en las que estuvo activa cada alerta."""
    if ALERT_COLUMN not in df.columns or df.empty:
        return pd.Series(dtype=int)
    # explode convierte una fila con dos alertas en dos filas de una alerta.
    alerts = df[ALERT_COLUMN].map(split_alerts).explode().dropna()
    return alerts.value_counts()


def value_before(df: pd.DataFrame, column: str, when: pd.Timestamp) -> float | None:
    """Último valor disponible de la columna en `when` o antes."""
    earlier = df.loc[df[TIME_COLUMN] <= when, column].dropna()
    return float(earlier.iloc[-1]) if len(earlier) else None
