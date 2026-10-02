"""Lectura de los CSV diarios del logger.

Flujo: carpeta con un CSV por día → un DataFrame por archivo → limpiar
→ concatenar → quitar duplicados → ordenar en el tiempo.

Cada paso anota lo que descarta: en un sistema de adquisición, un dato
rechazado en silencio es peor que un dato rechazado y contado.
"""

import io
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

TIME_COLUMN = "timestamp_utc"

# Formato de la hora que escribe el firmware (record.cpp): ISO 8601 en UTC.
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Columnas de texto del contrato. Todas las demás se tratan como números.
TEXT_COLUMNS = ("alertas",)
TEXT_PREFIXES = ("clase_",)


@dataclass(frozen=True)
class FileReport:
    """Qué pasó al leer un archivo: lo aceptado y lo descartado."""

    name: str
    rows_read: int = 0  # líneas de datos del archivo
    rows_valid: int = 0  # filas con hora válida
    no_timestamp: int = 0  # "sin_hora" o una hora ilegible
    repeated_headers: int = 0  # encabezado escrito otra vez tras un reinicio
    malformed: int = 0  # líneas con más campos que el encabezado
    incomplete_last_line: bool = False  # línea que el logger aún escribía
    error: str = ""


@dataclass(frozen=True)
class LoadResult:
    data: pd.DataFrame
    files: tuple[FileReport, ...]
    duplicates_removed: int


def is_text_column(column: str) -> bool:
    return column in TEXT_COLUMNS or column.startswith(TEXT_PREFIXES)


def discover_csv_files(folder: str | Path) -> list[Path]:
    """Lista los CSV de la carpeta ordenados por nombre (AAAA-MM-DD.csv)."""
    return sorted(Path(folder).glob("*.csv"))


def file_signature(path: Path) -> tuple[str, int, int]:
    """Ruta, fecha de modificación y tamaño: si no cambian, el archivo tampoco.

    Sirve de clave de caché: los días pasados se leen una vez y solo se
    vuelve a leer el archivo al que el logger sigue añadiendo filas.
    """
    stat = path.stat()
    return (str(path), stat.st_mtime_ns, stat.st_size)


def read_csv_file(path: str | Path) -> tuple[pd.DataFrame, FileReport]:
    """Lee un CSV diario y devuelve sus filas válidas más un informe."""
    path = Path(path)
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        return pd.DataFrame(), FileReport(path.name, error=str(exc))

    # Si el archivo no termina en salto de línea, el logger estaba a mitad de
    # una fila. Se deja fuera: en la siguiente lectura llegará completa.
    incomplete = bool(text) and not text.endswith("\n")
    if incomplete:
        text = text[: text.rfind("\n") + 1]
    if not text.strip():
        return pd.DataFrame(), FileReport(
            path.name, incomplete_last_line=incomplete, error="empty file"
        )

    # Todo entra como texto. Convertir es un paso aparte y explícito, así un
    # valor raro se convierte en "sin dato" en lugar de detener la lectura.
    raw = pd.read_csv(
        io.StringIO(text), dtype=str, keep_default_na=False, on_bad_lines="skip"
    )
    if TIME_COLUMN not in raw.columns:
        return pd.DataFrame(), FileReport(
            path.name, error=f"no '{TIME_COLUMN}' column in the header"
        )

    lines_of_data = sum(1 for line in text.splitlines() if line.strip()) - 1
    malformed = lines_of_data - len(raw)

    is_header = raw[TIME_COLUMN] == TIME_COLUMN
    raw = raw[~is_header]

    # errors="coerce": lo que no es una fecha (p. ej. "sin_hora") pasa a NaT.
    timestamps = pd.to_datetime(
        raw[TIME_COLUMN], format=TIMESTAMP_FORMAT, utc=True, errors="coerce"
    )
    has_time = timestamps.notna()

    df = raw[has_time].copy()
    df[TIME_COLUMN] = timestamps[has_time]
    for column in df.columns:
        if column == TIME_COLUMN:
            continue
        if is_text_column(column):
            df[column] = df[column].fillna("").astype(str)
        else:
            # Celda vacía = sensor sin dato → NaN ("not a number").
            df[column] = pd.to_numeric(df[column], errors="coerce")

    report = FileReport(
        name=path.name,
        rows_read=lines_of_data,
        rows_valid=len(df),
        no_timestamp=int((~has_time).sum()),
        repeated_headers=int(is_header.sum()),
        malformed=malformed,
        incomplete_last_line=incomplete,
    )
    return df.reset_index(drop=True), report


def combine(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    """Une los DataFrames en una sola serie cronológica sin horas repetidas.

    Devuelve la serie y cuántas filas duplicadas se quitaron.
    """
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame({TIME_COLUMN: pd.Series(dtype="datetime64[us, UTC]")}), 0

    # concat apila las tablas. Si un archivo trae una columna que otro no
    # tiene (un sensor nuevo), las filas antiguas quedan con NaN en ella.
    df = pd.concat(frames, ignore_index=True)

    # kind="stable" conserva el orden de llegada entre filas con la misma
    # hora, así keep="last" se queda con la del archivo más reciente.
    df = df.sort_values(TIME_COLUMN, kind="stable")
    before = len(df)
    df = df.drop_duplicates(subset=TIME_COLUMN, keep="last")
    return df.reset_index(drop=True), before - len(df)


def load_folder(folder: str | Path) -> LoadResult:
    """Lee y une todos los CSV de la carpeta."""
    frames, reports = [], []
    for path in discover_csv_files(folder):
        df, report = read_csv_file(path)
        frames.append(df)
        reports.append(report)
    data, duplicates = combine(frames)
    return LoadResult(data, tuple(reports), duplicates)
