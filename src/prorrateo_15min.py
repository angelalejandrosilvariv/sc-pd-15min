"""Funciones para repartir costos de ciclos SC P-D en intervalos de 15 minutos."""

from __future__ import annotations

import pandas as pd


COLUMNAS_DETALLE = [
    "Suministrador", "Cuarto_Hora_Mensual", "Medida_kWh_Cuarto",
    "Total_kWh_Ciclo", "Prorrata_Respecto_Ciclo", "Ciclo",
    "Precio_Ciclo", "Monetario_Cuarto",
]


def _requerir_columnas(df: pd.DataFrame, columnas: set[str], nombre: str) -> None:
    faltantes = columnas.difference(df.columns)
    if faltantes:
        raise ValueError(f"{nombre} no contiene columna(s): {', '.join(sorted(faltantes))}")


def calcular_cuarto_hora_mensual(fecha_hora: pd.Series) -> pd.Series:
    """Calcula el cuarto 1-indexado del mes; cada marca representa su inicio."""
    fechas = pd.to_datetime(fecha_hora, errors="raise")
    minuto_del_dia = fechas.dt.hour * 60 + fechas.dt.minute
    return ((fechas.dt.day - 1) * 96 + minuto_del_dia // 15 + 1).astype("Int64")


def construir_membresia_ciclos(detalle_15min: pd.DataFrame) -> pd.DataFrame:
    """Construye pares ciclo-cuarto, sin duplicarlos por centrales relacionadas."""
    _requerir_columnas(
        detalle_15min, {"Etiqueta_Relacionada", "FECHA_HORA"}, "Detalle_15Min"
    )
    membresia = detalle_15min[["Etiqueta_Relacionada", "FECHA_HORA"]].drop_duplicates().copy()
    membresia["Cuarto_Hora_Mensual"] = calcular_cuarto_hora_mensual(
        membresia["FECHA_HORA"]
    )
    membresia = membresia.rename(columns={"Etiqueta_Relacionada": "Ciclo"})
    return membresia[["Ciclo", "Cuarto_Hora_Mensual"]].drop_duplicates(ignore_index=True)


def agrupar_retiros(retiros: pd.DataFrame) -> pd.DataFrame:
    """Agrupa retiros por cuarto y suministrador, conservando su signo."""
    _requerir_columnas(
        retiros, {"Cuarto de Hora", "Suministrador", "Medida_kWh"}, "retiros"
    )
    datos = retiros[["Cuarto de Hora", "Suministrador", "Medida_kWh"]].copy()
    datos["Cuarto de Hora"] = pd.to_numeric(datos["Cuarto de Hora"], errors="raise")
    datos["Medida_kWh"] = pd.to_numeric(datos["Medida_kWh"], errors="raise")
    agrupados = (
        datos.groupby(["Cuarto de Hora", "Suministrador"], as_index=False, dropna=False)[
            "Medida_kWh"
        ].sum()
    )
    return agrupados.rename(columns={"Cuarto de Hora": "Cuarto_Hora_Mensual"})


def prorratear_retiros(
    membresia_ciclos: pd.DataFrame,
    retiros_agrupados: pd.DataFrame,
    precios_ciclo: pd.DataFrame,
) -> pd.DataFrame:
    """Reparte cada precio entre los retiros de la ventana temporal del ciclo.

    Los ciclos sin detalle se omiten. Los que sí tienen detalle pero totalizan
    cero kWh se excluyen de las filas y quedan registrados en ``DataFrame.attrs``
    para que :func:`auditar_cuadratura` los reporte explícitamente.
    """
    _requerir_columnas(membresia_ciclos, {"Ciclo", "Cuarto_Hora_Mensual"}, "membresía")
    _requerir_columnas(
        retiros_agrupados,
        {"Cuarto_Hora_Mensual", "Suministrador", "Medida_kWh"},
        "retiros agrupados",
    )
    _requerir_columnas(precios_ciclo, {"Ciclo", "Precio_Ciclo"}, "precios")

    precios = precios_ciclo[["Ciclo", "Precio_Ciclo"]].copy()
    if precios["Ciclo"].duplicated().any():
        repetidos = precios.loc[precios["Ciclo"].duplicated(False), "Ciclo"].unique()
        raise ValueError(f"Precio_Ciclo duplicado para ciclo(s): {list(repetidos)}")
    precios["Precio_Ciclo"] = pd.to_numeric(precios["Precio_Ciclo"], errors="raise")

    membresia = membresia_ciclos[["Ciclo", "Cuarto_Hora_Mensual"]].drop_duplicates()
    membresia = membresia.merge(precios, on="Ciclo", how="inner", validate="many_to_one")
    ciclos_incluidos = membresia[["Ciclo", "Precio_Ciclo"]].drop_duplicates()
    cruce = membresia.merge(retiros_agrupados, on="Cuarto_Hora_Mensual", how="left")
    cruce["Medida_kWh"] = pd.to_numeric(cruce["Medida_kWh"], errors="coerce")
    totales = cruce.groupby("Ciclo", as_index=False)["Medida_kWh"].sum(min_count=1)
    totales = totales.rename(columns={"Medida_kWh": "Total_kWh_Ciclo"})
    totales["Total_kWh_Ciclo"] = totales["Total_kWh_Ciclo"].fillna(0.0)
    sin_retiros = totales.loc[
        totales["Total_kWh_Ciclo"].abs() <= 1e-12, "Ciclo"
    ].tolist()

    detalle = cruce.dropna(subset=["Suministrador", "Medida_kWh"]).merge(
        totales, on="Ciclo", how="left", validate="many_to_one"
    )
    detalle = detalle[detalle["Total_kWh_Ciclo"].abs() > 1e-12].copy()
    detalle["Prorrata_Respecto_Ciclo"] = (
        detalle["Medida_kWh"] / detalle["Total_kWh_Ciclo"]
    )
    detalle["Monetario_Cuarto"] = (
        detalle["Prorrata_Respecto_Ciclo"] * detalle["Precio_Ciclo"]
    )
    detalle = detalle.rename(columns={"Medida_kWh": "Medida_kWh_Cuarto"})
    detalle = detalle[COLUMNAS_DETALLE].reset_index(drop=True)
    detalle.attrs["ciclos_sin_retiros"] = sin_retiros
    detalle.attrs["ciclos_incluidos"] = ciclos_incluidos.to_dict("records")
    return detalle


def auditar_cuadratura(detalle: pd.DataFrame, tolerancia: float = 0.01) -> dict:
    """Entrega totales, cuadratura por ciclo y mensajes de alerta."""
    _requerir_columnas(detalle, set(COLUMNAS_DETALLE), "detalle prorrateado")
    incluidos = pd.DataFrame(detalle.attrs.get("ciclos_incluidos", []))
    if incluidos.empty:
        incluidos = detalle[["Ciclo", "Precio_Ciclo"]].drop_duplicates()
    repartido = (
        detalle.groupby("Ciclo", as_index=False)["Monetario_Cuarto"].sum()
        .rename(columns={"Monetario_Cuarto": "Monetario_Repartido"})
    )
    por_ciclo = incluidos.merge(repartido, on="Ciclo", how="left")
    por_ciclo["Monetario_Repartido"] = por_ciclo["Monetario_Repartido"].fillna(0.0)
    por_ciclo["Delta_Ciclo"] = por_ciclo["Precio_Ciclo"] - por_ciclo["Monetario_Repartido"]
    sin_retiros = list(detalle.attrs.get("ciclos_sin_retiros", []))
    con_diferencia = por_ciclo[
        (por_ciclo["Delta_Ciclo"].abs() > tolerancia)
        & ~por_ciclo["Ciclo"].isin(sin_retiros)
    ].copy()
    total_original = float(por_ciclo["Precio_Ciclo"].sum())
    total_repartido = float(detalle["Monetario_Cuarto"].sum())
    mensajes = []
    if sin_retiros:
        mensajes.append(
            f"[!] {len(sin_retiros)} ciclo(s) sin retiros para prorratear "
            f"(no se pudo repartir su costo): {', '.join(map(str, sin_retiros))}"
        )
    if not con_diferencia.empty:
        mensajes.append(
            f"[!] {len(con_diferencia)} ciclo(s) con diferencia de cuadratura "
            f"mayor a {tolerancia:.2f}."
        )
    return {
        "total_original": total_original,
        "total_repartido": total_repartido,
        "delta_total": total_original - total_repartido,
        "por_ciclo": por_ciclo,
        "ciclos_sin_retiros": sin_retiros,
        "ciclos_con_diferencia": con_diferencia,
        "mensajes": mensajes,
    }
