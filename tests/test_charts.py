"""Pruebas de la preparación de las gráficas y del registro de variables."""

import pandas as pd

from templogger_dash import charts, variables
from templogger_dash.loader import TIME_COLUMN


def test_display_time_is_melbourne_clock_time(sample):
    local = charts.to_display_time(sample.data[TIME_COLUMN], "Australia/Melbourne")
    assert local.iloc[0] == pd.Timestamp("2026-10-03 00:00")  # UTC+10
    assert local.iloc[-1] == pd.Timestamp("2026-10-04 23:59")  # UTC+11, horario de verano


def test_no_gap_at_the_daylight_saving_jump(sample):
    # El reloj local salta una hora, pero en tiempo real no falta ningún minuto.
    assert charts.count_gaps(sample.data) == 0
    assert len(charts.insert_gaps(sample.data)) == len(sample.data)


def test_a_pause_in_the_record_breaks_the_line(sample):
    df = sample.data.drop(index=range(100, 130)).reset_index(drop=True)
    assert charts.count_gaps(df) == 1
    with_gaps = charts.insert_gaps(df)
    assert len(with_gaps) == len(df) + 1
    assert pd.isna(with_gaps["t_aht_c"].iloc[100])


def test_figure_has_one_axis_per_variable(sample):
    fig = charts.timeseries_figure(
        sample.data, ["t_aht_c", "hr_pct", "lux"], "Australia/Melbourne", "Melbourne",
        log_columns=("lux",),
    )
    assert [t.name for t in fig.data] == ["Temperature", "Relative humidity", "Light"]
    assert [t.yaxis for t in fig.data] == ["y", "y2", "y3"]
    assert fig.layout.yaxis3.type == "log"
    assert fig.layout.yaxis.type == "linear"


def test_zero_on_a_log_axis_is_drawn_at_the_floor(sample):
    df = sample.data.head(5).copy()
    df.loc[2, "lux"] = 0.0
    fig = charts.timeseries_figure(df, ["lux"], "UTC", "UTC", log_columns=("lux",))
    assert fig.data[0].y[2] == charts.LOG_FLOOR
    assert fig.data[0].customdata[2] == 0.0  # el cuadro del ratón muestra el valor real


def test_measurement_columns_skip_bookkeeping(sample):
    assert variables.measurement_columns(sample.data) == [
        "t_aht_c", "hr_pct", "lux", "p_hpa", "punto_rocio_c", "indice_calor_c",
        "t_bmp_c", "p_mar_hpa",
    ]
    assert variables.default_columns(sample.data) == ["t_aht_c", "hr_pct", "lux"]


def test_unknown_column_gets_a_generic_variable(sample):
    df = sample.data.assign(ph=7.0)
    assert variables.measurement_columns(df)[-1] == "ph"
    assert variables.describe("ph").label == "ph"
    assert variables.describe("ph").format(7.0) == "7.00"
