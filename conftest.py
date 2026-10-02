"""Configuración de pytest.

Que este archivo exista en la raíz hace que pytest añada esta carpeta a la
ruta de importación: así las pruebas pueden hacer `import templogger_dash`.
"""

from pathlib import Path

import pytest

from templogger_dash import loader

DATA_DIR = Path(__file__).parent / "data"

HEADER = (
    "timestamp_utc,uptime_s,seq,t_aht_c,hr_pct,t_bmp_c,p_hpa,p_mar_hpa,lux,"
    "punto_rocio_c,indice_calor_c,clase_t,clase_hr,clase_luz,alertas"
)


def make_row(minute: int, t: str = "19.22", lux: str = "1.7") -> str:
    """Una fila con el formato del logger, en el minuto indicado."""
    return (
        f"2026-10-02T14:{minute:02d}:00Z,{minute * 60},{minute + 1},{t},51.6,19.83,"
        f"1004.00,1011.06,{lux},9.01,18.54,normal,normal,bajo,OSCURO"
    )


def write_csv(path: Path, lines: list[str], *, final_newline: bool = True) -> Path:
    """Escribe un CSV con fin de línea CRLF, como el ESP32."""
    text = "\r\n".join(lines) + ("\r\n" if final_newline else "")
    path.write_bytes(text.encode("utf-8"))
    return path


@pytest.fixture(scope="session")
def sample():
    """Los dos días simulados de data/, ya unidos."""
    return loader.load_folder(DATA_DIR)
