"""Ventanas de tiempo: qué tramo de la serie se muestra.

Todo el cálculo se hace en UTC, que es tiempo real y continuo. La zona
horaria local solo interviene para decidir dónde empieza y termina "hoy".
"""

from dataclasses import dataclass

import pandas as pd

from .loader import TIME_COLUMN

LAST_HOUR = "Last hour"
TODAY = "Today"
LAST_24_HOURS = "Last 24 hours"
LAST_7_DAYS = "Last 7 days"
ALL = "All"
CUSTOM = "Custom"

PRESETS = (LAST_HOUR, TODAY, LAST_24_HOURS, LAST_7_DAYS, ALL)

_DURATIONS = {
    LAST_HOUR: pd.Timedelta(hours=1),
    LAST_24_HOURS: pd.Timedelta(hours=24),
    LAST_7_DAYS: pd.Timedelta(days=7),
}


@dataclass(frozen=True)
class TimeWindow:
    """Intervalo de tiempo en UTC. None significa sin límite por ese lado."""

    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None
    start_inclusive: bool = True
    end_inclusive: bool = True


def preset_window(preset: str, anchor: pd.Timestamp, tz: str) -> TimeWindow:
    """Ventana de un rango predefinido, contada desde `anchor`.

    `anchor` es la última medición, no el reloj del PC: así "última hora"
    sigue mostrando datos aunque el logger lleve un rato apagado.
    """
    if preset == ALL:
        return TimeWindow()
    if preset == TODAY:
        # Día local de la última medición. DateOffset suma un día de
        # calendario, no 24 h: los días de 23 h y 25 h del cambio de horario
        # terminan en la medianoche correcta.
        midnight = anchor.tz_convert(tz).normalize()
        next_midnight = midnight + pd.DateOffset(days=1)
        return TimeWindow(
            midnight.tz_convert("UTC"), next_midnight.tz_convert("UTC"),
            end_inclusive=False,
        )
    # Intervalo (anchor - duración, anchor]: con una fila por minuto,
    # "última hora" son 60 filas y no 61.
    return TimeWindow(anchor - _DURATIONS[preset], anchor, start_inclusive=False)


def local_to_utc(naive_local, tz: str, *, first_if_ambiguous: bool) -> pd.Timestamp:
    """Convierte una fecha y hora local sin zona a UTC.

    En el cambio de horario hay horas locales que no existen (se saltan en
    octubre) u ocurren dos veces (se repiten en abril).
    """
    stamp = pd.Timestamp(naive_local).tz_localize(
        tz, ambiguous=first_if_ambiguous, nonexistent="shift_forward"
    )
    return stamp.tz_convert("UTC")


def custom_window(start_local, end_local, tz: str) -> TimeWindow:
    """Ventana elegida por el usuario en hora local, ambos extremos incluidos."""
    return TimeWindow(
        local_to_utc(start_local, tz, first_if_ambiguous=True),
        local_to_utc(end_local, tz, first_if_ambiguous=False),
    )


def apply_window(df: pd.DataFrame, window: TimeWindow) -> pd.DataFrame:
    """Devuelve las filas cuya hora cae dentro de la ventana."""
    time = df[TIME_COLUMN]
    # Una máscara booleana marca con True las filas que se conservan.
    mask = pd.Series(True, index=df.index)
    if window.start is not None:
        mask &= time >= window.start if window.start_inclusive else time > window.start
    if window.end is not None:
        mask &= time <= window.end if window.end_inclusive else time < window.end
    return df[mask]
