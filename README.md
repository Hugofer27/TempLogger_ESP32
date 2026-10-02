# Temp Logger dashboard

A local dashboard for an ESP32 environmental data logger that records temperature, relative humidity and light. It reads the logger's daily CSV files, joins them into one continuous time series, and shows the latest readings and their history.

Built with Python, pandas, Plotly and Streamlit. Everything runs on your own computer: no database and no cloud service.

> **Status: v0.1.** The ESP32 hardware has not arrived yet, so the files in `data/` are **simulated**: physically coherent, but not measured. They use the exact format the logger will write.

## What it does

- Finds every `*.csv` file in `data/` (one file per day).
- Combines them in chronological order.
- Shows the latest temperature, relative humidity and light readings.
- Plots each variable against time, in Melbourne local time.

## The data

```
sensors → ESP32 → one CSV file per day → this dashboard
```

Each row is one measurement. The sample files have one row per minute.

| Column | Unit | Meaning |
| --- | --- | --- |
| `timestamp_utc` | ISO 8601, UTC | time of the measurement |
| `t_aht_c` | °C | air temperature (AHT20 sensor) |
| `hr_pct` | % | relative humidity (AHT20 sensor) |
| `lux` | lx | illuminance (BH1750 sensor) |
| `p_hpa`, `p_mar_hpa` | hPa | absolute and sea-level pressure (BMP280 sensor) |
| `punto_rocio_c`, `indice_calor_c` | °C | dew point and heat index, calculated by the logger |
| `clase_t`, `clase_hr`, `clase_luz` | — | class of each reading: `bajo` (low), `normal` or `alto` (high) |
| `alertas` | — | alert flags, separated by `\|` |

Two details matter when reading the files:

- **Timestamps are in UTC, but each file is named after the local day in Melbourne.** `2026-10-03.csv` starts at `2026-10-02T14:00:00Z`, which is midnight in Melbourne.
- **An empty cell means the sensor gave no reading.**

The two sample days:

| File | Rows | What happens |
| --- | --- | --- |
| `2026-10-03.csv` | 1440 | A day in a lab: lights on from 8:00 to 18:00, steam from a water bath, and an air-conditioning failure in the afternoon. |
| `2026-10-04.csv` | 1380 | Daylight saving time starts, so the day has 23 hours. Rain from midday, and the light sensor is disconnected for 20 minutes. |

## Install

You need Python 3.12 or newer.

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On Windows, if this folder sits inside a long path, the install can fail with `No such file or directory` because of the 260-character path limit. In that case create the environment in a short path instead, for example `C:\Users\<you>\.venvs\templogger`, and use that path in the commands.

## Run

```bash
.venv\Scripts\python.exe -m streamlit run Dashboard.py
```

The dashboard opens at `http://localhost:8501`.

## Files

| Path | What it is |
| --- | --- |
| `Dashboard.py` | the page: everything you see |
| `templogger_dash/loader.py` | data loading: find the files, read them, combine and sort |
| `data/` | the daily CSV files |
| `requirements.txt` | the Python packages the dashboard needs |
