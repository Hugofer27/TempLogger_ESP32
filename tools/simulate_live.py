"""Sustituto del ESP32 para probar la actualización en vivo.

Repite las filas de los datos de muestra, pero con la hora actual, y las va
añadiendo al CSV del día en una carpeta aparte (data_live/). El dashboard,
apuntando a esa carpeta, las ve llegar igual que verá las del logger.

SON DATOS SIMULADOS: por eso se escriben en data_live/ y no en data/.

Uso, desde la carpeta del dashboard:
    python tools/simulate_live.py                 una fila cada 5 s
    python tools/simulate_live.py --interval 60   al ritmo real del logger
Se detiene con Ctrl+C.
"""

import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

APP_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = APP_DIR / "data"
OUTPUT_DIR = APP_DIR / "data_live"
LOCAL_TZ = ZoneInfo("Australia/Melbourne")
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
NEWLINE = "\r\n"  # el ESP32 escribe con println


def read_sample(folder: Path) -> tuple[str, list[list[str]]]:
    """Encabezado y filas (ya separadas en campos) de los CSV de muestra."""
    header, rows = "", []
    for path in sorted(folder.glob("*.csv")):
        lines = path.read_text(encoding="utf-8").splitlines()
        header = lines[0]
        rows += [line.split(",") for line in lines[1:] if line]
    return header, rows


def append_row(folder: Path, header: str, fields: list[str], when: datetime) -> Path:
    """Añade la fila al archivo del día local, creándolo con encabezado si falta."""
    # El nombre del archivo es el día de Melbourne; la hora de la fila es UTC.
    path = folder / f"{when.astimezone(LOCAL_TZ):%Y-%m-%d}.csv"
    is_new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as file:
        if is_new:
            file.write(header + NEWLINE)
        file.write(",".join(fields) + NEWLINE)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interval", type=float, default=5, help="segundos entre filas")
    parser.add_argument("--history", type=int, default=120,
                        help="minutos de historia que se escriben al empezar")
    args = parser.parse_args()

    header, rows = read_sample(SOURCE_DIR)
    if not rows:
        raise SystemExit(f"No hay CSV de muestra en {SOURCE_DIR}")
    # La carpeta de salida es fija a propósito: cada ejecución borra lo que
    # dejó la anterior, y así nunca puede borrar datos de otra carpeta.
    out = OUTPUT_DIR
    out.mkdir(exist_ok=True)
    for old in out.glob("*.csv"):
        old.unlink()

    start = datetime.now(timezone.utc).replace(microsecond=0)
    seq = 0

    def emit(when: datetime) -> Path:
        nonlocal seq
        fields = list(rows[seq % len(rows)])
        seq += 1
        fields[0] = when.strftime(TIMESTAMP_FORMAT)
        fields[1] = str(int((when - start).total_seconds()) + args.history * 60)
        fields[2] = str(seq)
        return append_row(out, header, fields, when)

    # Un tramo de historia para que la gráfica no empiece vacía. Lleva el
    # mismo intervalo que las filas en vivo: si cambiara, el dashboard
    # tomaría el tramo más espaciado por cortes del registro.
    n_history = int(args.history * 60 / args.interval)
    for steps_ago in range(n_history, 0, -1):
        emit(start - timedelta(seconds=steps_ago * args.interval))
    print(f"Historia escrita: {n_history} filas en {out}")
    print(f"Añadiendo una fila cada {args.interval:g} s. Ctrl+C para detener.")

    try:
        while True:
            now = datetime.now(timezone.utc).replace(microsecond=0)
            path = emit(now)
            print(f"  {now:%H:%M:%S} UTC  ->  {path.name}  (fila {seq})", flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()
