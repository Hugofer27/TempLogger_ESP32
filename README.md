# Temp Logger dashboard

A local dashboard for an ESP32 environmental data logger that records temperature, relative humidity and light. It reads the logger's daily CSV files, joins them into one continuous time series, and shows the latest readings, their history and summary statistics.

Built with Python, pandas, Plotly and Streamlit. Everything runs on your own computer: no database and no cloud service.

> **The data in `data/` is simulated.** The ESP32 hardware has not arrived yet, so the sample files are physically coherent but not measured. They use the exact format the logger will write.

## What it does

- **Latest readings.** The newest value of each variable, its change over the last hour, its class (low, normal, high) and the active alerts.
- **History.** One chart per variable on a shared time axis: zooming or hovering on one chart moves all of them.
- **Period filter.** Last hour, today, last 24 hours, last 7 days, everything, or a custom range.
- **Summary.** Minimum, maximum, mean and number of measurements for the selected period, plus how often each alert was active.
- **Live updating.** The dashboard re-reads the data folder on a timer (every 30 seconds by default) and shows new measurements without reloading the page.
- **Many files, one dataset.** Every `*.csv` in the data folder is combined in time order. Duplicate rows are removed, and rows that cannot be used are counted and reported instead of stopping the load.

## How the data flows

```
sensors → ESP32 → one CSV file per day → this dashboard
```

| Step | What happens | Where |
| --- | --- | --- |
| 1. Discover | list the `*.csv` files in the data folder | `loader.py` |
| 2. Read | each file becomes a table (a pandas DataFrame), read as text | `loader.py` |
| 3. Clean | times become UTC dates, numbers become numbers, empty cells become "no data"; unusable rows are counted | `loader.py` |
| 4. Combine | the daily tables are stacked, duplicate times removed, and everything sorted by time | `loader.py` |
| 5. Filter | keep only the rows inside the chosen period | `filters.py` |
| 6. Summarize | minimum, maximum, mean and count per variable | `stats.py` |
| 7. Draw | Plotly charts, laid out on the page by Streamlit | `charts.py`, `Dashboard.py` |

All calculations use UTC, which is continuous. Local time is applied only when showing the result, so the 23-hour and 25-hour days at the daylight saving changes are handled correctly.

## The data

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
- **An empty cell means the sensor gave no reading.** The chart shows a break in the line there.

The two sample days:

| File | Rows | What happens |
| --- | --- | --- |
| `2026-10-03.csv` | 1440 | A day in a lab: lights on from 8:00 to 18:00, steam from a water bath, and an air-conditioning failure in the afternoon. |
| `2026-10-04.csv` | 1380 | Daylight saving time starts, so the day has 23 hours. Rain from midday, and the light sensor is disconnected for 20 minutes. |

### Adding a sensor

The dashboard is not built around three fixed variables. Any new numeric column in the CSV (for example `ph` or `conductivity_us_cm`) shows up in the **Variables** list automatically. To give it a proper name, unit and colour, add one line to `REGISTRY` in `templogger_dash/variables.py`.

## Install

You need Python 3.12 or newer.

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On Windows, if this folder sits inside a long path, the install can fail with `No such file or directory` because of the 260-character path limit. In that case create the environment in a short path instead, for example `C:\Users\<you>\.venvs\templogger`, and use that path in the commands below.

## Run

```bash
.venv\Scripts\python.exe -m streamlit run Dashboard.py
```

The dashboard opens at `http://localhost:8501`.

### Try the live updating

A small script stands in for the ESP32: it replays the sample rows with the current time and appends one row every 5 seconds to `data_live/`.

```bash
.venv\Scripts\python.exe tools\simulate_live.py
```

While it runs, type `data_live` in the **Data folder** box of the dashboard. The status changes to **Live** and new measurements appear on their own.

### Run the tests

```bash
.venv\Scripts\python.exe -m pytest
```

The expected numbers in the tests were counted independently from the sample files, not with the dashboard's own code.

## Files

| Path | What it is |
| --- | --- |
| `Dashboard.py` | the page: what is shown and where |
| `templogger_dash/variables.py` | name, unit, colour and scale of each variable |
| `templogger_dash/loader.py` | find, read, clean and combine the CSV files |
| `templogger_dash/filters.py` | time periods |
| `templogger_dash/stats.py` | summary statistics and alert counts |
| `templogger_dash/charts.py` | the Plotly charts and their style |
| `tools/simulate_live.py` | stand-in for the ESP32, to try live updating |
| `tests/` | automated tests for the data logic |
| `data/` | the daily CSV files |
