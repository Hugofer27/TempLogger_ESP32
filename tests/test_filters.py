"""Pruebas de las ventanas de tiempo."""

import pandas as pd
import pytest

from templogger_dash import filters
from templogger_dash.loader import TIME_COLUMN

MELBOURNE = "Australia/Melbourne"


def rows_in(sample, preset, anchor=None, tz=MELBOURNE):
    df = sample.data
    anchor = anchor or df[TIME_COLUMN].iloc[-1]
    return len(filters.apply_window(df, filters.preset_window(preset, anchor, tz)))


@pytest.mark.parametrize("preset, expected", [
    (filters.LAST_HOUR, 60),
    (filters.LAST_24_HOURS, 1440),
    (filters.LAST_7_DAYS, 2820),
    (filters.ALL, 2820),
])
def test_relative_presets(sample, preset, expected):
    assert rows_in(sample, preset) == expected


def test_today_on_the_23_hour_day(sample):
    # 4 de octubre de 2026: empieza el horario de verano en Melbourne.
    assert rows_in(sample, filters.TODAY) == 1380


def test_today_on_a_normal_day(sample):
    anchor = pd.Timestamp("2026-10-03T13:59:00Z")  # 23:59 del 3 de octubre
    assert rows_in(sample, filters.TODAY, anchor) == 1440


def test_today_lasts_25_hours_when_daylight_saving_ends():
    # 5 de abril de 2026: a las 03:00 el reloj vuelve a las 02:00.
    anchor = pd.Timestamp("2026-04-05T05:00:00Z")
    window = filters.preset_window(filters.TODAY, anchor, MELBOURNE)
    assert window.end - window.start == pd.Timedelta(hours=25)
    assert window.start == pd.Timestamp("2026-04-04T13:00:00Z")  # 00:00 con UTC+11


def test_today_in_utc(sample):
    # Del 4 de octubre 00:00Z a 12:59Z hay 13 h de datos.
    assert rows_in(sample, filters.TODAY, tz="UTC") == 13 * 60


def test_custom_window_matches_the_documented_sensor_fault(sample):
    # El LEEME de los datos dice: GY-302 desconectado de 13:01 a 13:20, hora
    # local del 4 de octubre.
    window = filters.custom_window("2026-10-04 13:01", "2026-10-04 13:20", MELBOURNE)
    view = filters.apply_window(sample.data, window)
    assert len(view) == 20
    assert view["lux"].isna().all()


def test_local_hour_that_does_not_exist_moves_forward():
    # A las 02:00 el reloj salta a las 03:00: las 02:30 no existen.
    stamp = filters.local_to_utc("2026-10-04 02:30", MELBOURNE, first_if_ambiguous=True)
    assert stamp == pd.Timestamp("2026-10-03T16:00:00Z")
