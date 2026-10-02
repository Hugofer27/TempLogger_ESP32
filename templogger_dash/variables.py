"""Registro de variables: qué significa cada columna numérica del CSV.

El dashboard no tiene "temperatura, humedad y luz" escritas en su lógica.
Recorre las columnas numéricas que encuentra en los datos y pregunta aquí
cómo mostrarlas. Una columna nueva (pH, conductividad, turbidez) aparece
sola con una etiqueta genérica; añadir una línea a REGISTRY le da nombre,
unidad y color.
"""

from dataclasses import dataclass

import pandas as pd

# Columnas numéricas que son contabilidad del logger, no mediciones.
BOOKKEEPING_COLUMNS = ("uptime_s", "seq")


@dataclass(frozen=True)
class Variable:
    column: str  # nombre de la columna en el CSV
    label: str  # nombre que ve el usuario
    unit: str
    decimals: int = 2  # resolución con la que se muestra
    color_light: str = "#898781"  # color de la línea en tema claro
    color_dark: str = "#898781"  # color de la línea en tema oscuro
    log_scale: bool = False  # ¿abarca varios órdenes de magnitud?
    primary: bool = False  # ¿se muestra al abrir el dashboard?
    class_column: str | None = None  # columna con la clase bajo/normal/alto

    def color(self, dark: bool) -> str:
        return self.color_dark if dark else self.color_light

    def format(self, value: float) -> str:
        if pd.isna(value):
            return "—"
        return f"{value:.{self.decimals}f} {self.unit}".strip()


# El orden fija el color de cada variable (el color sigue a la variable, no a
# su posición en pantalla). Esta secuencia de tonos pasa las pruebas de
# separación para daltonismo entre vecinos, en tema claro y en oscuro.
REGISTRY: tuple[Variable, ...] = (
    Variable("t_aht_c", "Temperature", "°C", 2, "#eb6834", "#d95926",
             primary=True, class_column="clase_t"),
    Variable("hr_pct", "Relative humidity", "%", 1, "#2a78d6", "#3987e5",
             primary=True, class_column="clase_hr"),
    # La luz va de ~1 lx (noche) a cientos de lx: en escala lineal la noche
    # quedaría aplastada contra el cero, por eso se propone la logarítmica.
    Variable("lux", "Light", "lx", 1, "#eda100", "#c98500",
             log_scale=True, primary=True, class_column="clase_luz"),
    Variable("p_hpa", "Pressure", "hPa", 2, "#1baf7a", "#199e70"),
    Variable("punto_rocio_c", "Dew point", "°C", 2, "#4a3aa7", "#9085e9"),
    Variable("indice_calor_c", "Heat index", "°C", 2, "#e87ba4", "#d55181"),
    Variable("t_bmp_c", "Sensor temperature (BMP280)", "°C", 2, "#008300", "#008300"),
    Variable("p_mar_hpa", "Sea-level pressure", "hPa", 2, "#e34948", "#e66767"),
)

_BY_COLUMN = {v.column: v for v in REGISTRY}


def describe(column: str) -> Variable:
    """Devuelve la variable registrada o una genérica para columnas nuevas."""
    return _BY_COLUMN.get(column) or Variable(column, column, "")


def measurement_columns(df: pd.DataFrame) -> list[str]:
    """Columnas numéricas con al menos un dato, primero las del registro."""
    candidates = [
        c for c in df.columns
        if c not in BOOKKEEPING_COLUMNS
        and pd.api.types.is_numeric_dtype(df[c])
        and df[c].notna().any()
    ]
    known = [v.column for v in REGISTRY if v.column in candidates]
    unknown = sorted(c for c in candidates if c not in _BY_COLUMN)
    return known + unknown


def default_columns(df: pd.DataFrame) -> list[str]:
    """Las variables principales presentes; si no hay ninguna, las tres primeras."""
    available = measurement_columns(df)
    primary = [c for c in available if describe(c).primary]
    return primary or available[:3]
