"""Pruebas de las estadísticas, contra valores calculados aparte con awk."""

import pandas as pd
import pytest

from templogger_dash import filters, stats
from templogger_dash.loader import TIME_COLUMN


def test_summary_of_the_second_day(sample):
    df = sample.data
    window = filters.preset_window(filters.TODAY, df[TIME_COLUMN].iloc[-1], "Australia/Melbourne")
    summary = stats.summarize(filters.apply_window(df, window), ["t_aht_c", "hr_pct", "lux"])

    assert summary.loc["t_aht_c", "min"] == 18.27
    assert summary.loc["t_aht_c", "max"] == 22.89
    assert summary.loc["t_aht_c", "mean"] == pytest.approx(20.451167, abs=1e-6)
    assert summary.loc["t_aht_c", "count"] == 1380
    assert summary.loc["hr_pct", "mean"] == pytest.approx(53.766377, abs=1e-6)
    # El sensor de luz estuvo 20 minutos sin dato: n es menor.
    assert summary.loc["lux", "count"] == 1360
    assert summary.loc["lux", "mean"] == pytest.approx(57.806176, abs=1e-6)


def test_alert_counts(sample):
    assert stats.alert_counts(sample.data).to_dict() == {
        "OSCURO": 1305,
        "PRESION_BAJANDO": 506,
        "CALOR_HUMEDO": 102,
        "CONDENSACION": 23,
        "FALLA_SENSOR": 20,
    }


def test_split_alerts():
    assert stats.split_alerts("FALLA_SENSOR|PRESION_BAJANDO") == ["FALLA_SENSOR", "PRESION_BAJANDO"]
    assert stats.split_alerts("") == []


def test_median_interval(sample):
    assert stats.median_interval(sample.data) == pd.Timedelta(minutes=1)
    assert stats.median_interval(sample.data.head(1)) is None


def test_value_before(sample):
    df = sample.data
    assert stats.value_before(df, "t_aht_c", pd.Timestamp("2026-10-02T14:00:30Z")) == 19.22
    assert stats.value_before(df, "t_aht_c", pd.Timestamp("2026-10-01T00:00:00Z")) is None
