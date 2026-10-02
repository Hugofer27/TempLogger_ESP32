"""Pruebas de la lectura de los CSV.

Los números esperados de los datos de muestra se contaron por separado con
awk sobre los archivos, no con este mismo código.
"""

import pandas as pd

from conftest import HEADER, make_row, write_csv
from templogger_dash import loader
from templogger_dash.loader import TIME_COLUMN


# --- Datos de muestra -------------------------------------------------------

def test_sample_row_counts(sample):
    assert len(sample.data) == 2820
    assert [(r.name, r.rows_valid) for r in sample.files] == [
        ("2026-10-03.csv", 1440),
        ("2026-10-04.csv", 1380),  # día de 23 h: empieza el horario de verano
    ]
    assert sample.duplicates_removed == 0


def test_sample_time_range_is_utc_and_sorted(sample):
    time = sample.data[TIME_COLUMN]
    assert str(time.dt.tz) == "UTC"
    assert time.iloc[0] == pd.Timestamp("2026-10-02T14:00:00Z")
    assert time.iloc[-1] == pd.Timestamp("2026-10-04T12:59:00Z")
    assert time.is_monotonic_increasing
    assert time.is_unique


def test_sample_empty_cells_become_nan(sample):
    lux = sample.data["lux"]
    assert lux.isna().sum() == 20  # GY-302 desconectado 20 minutos
    assert lux.min() == 1.7
    assert lux.max() == 710.8


def test_sample_column_types(sample):
    df = sample.data
    assert pd.api.types.is_numeric_dtype(df["t_aht_c"])
    assert pd.api.types.is_numeric_dtype(df["seq"])
    assert set(df["clase_luz"].unique()) == {"bajo", "normal", "?"}
    assert not sample.files[0].incomplete_last_line


# --- Casos que el contrato permite ------------------------------------------

def test_duplicate_times_keep_the_latest_file(tmp_path):
    write_csv(tmp_path / "a.csv", [HEADER, make_row(0), make_row(1, t="20.00")])
    write_csv(tmp_path / "b.csv", [HEADER, make_row(1, t="25.00"), make_row(2)])
    result = loader.load_folder(tmp_path)
    assert len(result.data) == 3
    assert result.duplicates_removed == 1
    assert result.data["t_aht_c"].tolist() == [19.22, 25.00, 19.22]


def test_line_still_being_written_is_left_out(tmp_path):
    partial = "2026-10-02T14:02:00Z,120,3,19.2"
    path = write_csv(tmp_path / "a.csv", [HEADER, make_row(0), make_row(1), partial],
                     final_newline=False)
    df, report = loader.read_csv_file(path)
    assert len(df) == 2
    assert report.incomplete_last_line


def test_repeated_header_is_dropped(tmp_path):
    path = write_csv(tmp_path / "a.csv", [HEADER, make_row(0), HEADER, make_row(1)])
    df, report = loader.read_csv_file(path)
    assert len(df) == 2
    assert report.repeated_headers == 1
    assert report.no_timestamp == 0


def test_rows_without_time_are_counted(tmp_path):
    no_time = make_row(1).replace("2026-10-02T14:01:00Z", "sin_hora")
    path = write_csv(tmp_path / "a.csv", [HEADER, make_row(0), no_time])
    df, report = loader.read_csv_file(path)
    assert len(df) == 1
    assert report.no_timestamp == 1
    assert report.rows_read == 2


def test_malformed_values_do_not_stop_the_load(tmp_path):
    too_many_fields = make_row(1) + ",extra,extra"
    bad_number = make_row(2, t="abc")
    path = write_csv(tmp_path / "a.csv", [HEADER, make_row(0), too_many_fields, bad_number])
    df, report = loader.read_csv_file(path)
    assert len(df) == 2
    assert report.malformed == 1
    assert pd.isna(df["t_aht_c"].iloc[1])


def test_new_sensor_column_is_kept(tmp_path):
    write_csv(tmp_path / "a.csv", [HEADER, make_row(0)])
    write_csv(tmp_path / "b.csv", [HEADER + ",ph", make_row(1) + ",7.02"])
    df = loader.load_folder(tmp_path).data
    assert pd.isna(df["ph"].iloc[0])  # el día anterior no tenía ese sensor
    assert df["ph"].iloc[1] == 7.02


def test_file_that_is_not_a_logger_csv_is_reported(tmp_path):
    write_csv(tmp_path / "notes.csv", ["a,b", "1,2"])
    write_csv(tmp_path / "empty.csv", [])
    result = loader.load_folder(tmp_path)
    assert result.data.empty
    assert all(r.error for r in result.files)


def test_empty_folder(tmp_path):
    result = loader.load_folder(tmp_path)
    assert result.data.empty
    assert TIME_COLUMN in result.data.columns
    assert result.files == ()
