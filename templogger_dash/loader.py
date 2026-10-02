"""Lectura de los CSV diarios del logger (versión mínima).

Flujo: carpeta con un CSV por día → un DataFrame por archivo → concatenar
→ convertir la hora → ordenar en el tiempo.
"""

from pathlib import Path

import pandas as pd

# Formato de la hora que escribe el firmware (record.cpp): ISO 8601 en UTC.
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def discover_csv_files(folder: str | Path) -> list[Path]:
    """Lista los CSV de la carpeta ordenados por nombre (AAAA-MM-DD.csv)."""
    return sorted(Path(folder).glob("*.csv"))


def read_csv_file(path: str | Path) -> pd.DataFrame:
    """Lee un CSV diario y convierte timestamp_utc en fecha con zona UTC.

    errors="coerce" convierte lo que no es una fecha (p. ej. "sin_hora")
    en NaT ("not a time") en lugar de detener el programa.
    """
    df = pd.read_csv(path)
    df["timestamp_utc"] = pd.to_datetime(
        df["timestamp_utc"], format=TIMESTAMP_FORMAT, utc=True, errors="coerce"
    )
    return df


def load_folder(folder: str | Path) -> pd.DataFrame:
    """Une todos los CSV de la carpeta en un solo DataFrame cronológico."""
    frames = [read_csv_file(p) for p in discover_csv_files(folder)]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    # Sin hora válida no se puede ubicar la fila en el eje del tiempo.
    df = df.dropna(subset=["timestamp_utc"])
    return df.sort_values("timestamp_utc").reset_index(drop=True)
