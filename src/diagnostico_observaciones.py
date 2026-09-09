"""Consultas puras para trazar observaciones sobre el cálculo SC P-D."""

from __future__ import annotations

from difflib import get_close_matches

import pandas as pd


def _normalizar(serie: pd.Series) -> pd.Series:
    """Normaliza nombres sin convertir valores nulos en la cadena ``nan``."""
    return serie.astype("string").str.strip().str.casefold()


def coincide_central(
    df: pd.DataFrame,
    consulta: str,
    columna_central: str = "Central",
    columna_relacionada: str = "Central_Relacionada",
) -> pd.Series:
    """Indica si la central o su central relacionada igualan la consulta."""
    buscada = str(consulta).strip().casefold()
    mascara = pd.Series(False, index=df.index, dtype=bool)
    for columna in dict.fromkeys((columna_central, columna_relacionada)):
        if columna in df.columns:
            mascara |= _normalizar(df[columna]).eq(buscada).fillna(False)
    return mascara


def filtrar_ventana(
    df: pd.DataFrame,
    columna_fecha: str,
    inicio,
    fin,
    margen: pd.Timedelta = pd.Timedelta("1h"),
) -> pd.DataFrame:
    """Recorta a la ventana cerrada indicada, incluyendo contexto temporal."""
    if columna_fecha not in df.columns:
        raise ValueError(f"El DataFrame no contiene la columna de fecha '{columna_fecha}'.")
    inicio_ts, fin_ts = pd.Timestamp(inicio), pd.Timestamp(fin)
    if inicio_ts > fin_ts:
        raise ValueError("La fecha de inicio no puede ser posterior a la fecha de fin.")
    margen = pd.Timedelta(margen)
    fechas = pd.to_datetime(df[columna_fecha], errors="coerce")
    return df.loc[fechas.between(inicio_ts - margen, fin_ts + margen, inclusive="both")].copy()


def centrales_disponibles(
    *dfs: pd.DataFrame,
    columnas=("Central", "Central_Relacionada"),
) -> set[str]:
    """Reúne los nombres no vacíos presentes en las columnas solicitadas."""
    resultado: set[str] = set()
    for df in dfs:
        if df is None:
            continue
        for columna in columnas:
            if columna in df.columns:
                valores = df[columna].dropna().astype(str).str.strip()
                resultado.update(v for v in valores if v)
    return resultado


def _filtrar_insumo(df, consulta, fecha, central, relacionada, inicio, fin, margen):
    if df is None:
        return pd.DataFrame()
    coincidentes = df.loc[coincide_central(df, consulta, central, relacionada)]
    return filtrar_ventana(coincidentes, fecha, inicio, fin, margen)


def _diagnostico_ciclos(resumen: pd.DataFrame) -> pd.DataFrame:
    """Presenta exclusivamente campos explicativos ya calculados por el motor."""
    prefijos = (
        "Etiqueta_Relacionada", "Inicio_Ciclo", "Fin_Ciclo", "Tipo_Partida",
        "Obs_Partida", "Obs_Detencion", "Obs_Liquidacion_Final",
    )
    columnas = [
        c for c in resumen.columns
        if c in prefijos or c.startswith("Filtro_")
    ]
    diagnostico = resumen.loc[:, columnas].copy()
    diagnostico.insert(0, "Diagnostico", "Ciclo encontrado en Detalle_15Min; revisar evidencia del motor.")
    return diagnostico


def armar_trazado(
    rio: pd.DataFrame,
    reporte_crudo: pd.DataFrame,
    detalle_15min: pd.DataFrame,
    resumen_ciclos_pd: pd.DataFrame,
    consulta: str,
    inicio,
    fin,
    margen: pd.Timedelta = pd.Timedelta("1h"),
) -> dict[str, pd.DataFrame]:
    """Arma las cinco hojas de evidencia para una central y una ventana."""
    fuentes = (
        (rio, "Central_Relacionada_RIO", "Central_Relacionada_RIO"),
        (reporte_crudo, "Central", "Central_Relacionada"),
        (detalle_15min, "Central", "Central_Relacionada"),
        (resumen_ciclos_pd, "Central", "Central_Relacionada"),
    )
    existe = any(
        coincide_central(df, consulta, central, relacionada).any()
        for df, central, relacionada in fuentes if df is not None
    )
    if not existe:
        columnas = ("Central", "Central_Relacionada", "Central_Relacionada_RIO")
        opciones = centrales_disponibles(
            rio, reporte_crudo, detalle_15min, resumen_ciclos_pd, columnas=columnas
        )
        sugerencias = get_close_matches(str(consulta).strip(), sorted(opciones), n=5, cutoff=0.3)
        texto = ", ".join(sugerencias) if sugerencias else ", ".join(sorted(opciones)[:5])
        raise ValueError(
            f"La central '{consulta}' no aparece en los insumos. "
            f"Opciones similares: {texto or 'no hay centrales disponibles'}."
        )

    rio_f = _filtrar_insumo(
        rio, consulta, "FECHA_HORA_RIO", "Central_Relacionada_RIO",
        "Central_Relacionada_RIO", inicio, fin, margen,
    )
    reporte_f = _filtrar_insumo(
        reporte_crudo, consulta, "FECHA_HORA", "Central", "Central_Relacionada",
        inicio, fin, margen,
    )
    detalle_f = _filtrar_insumo(
        detalle_15min, consulta, "FECHA_HORA", "Central", "Central_Relacionada",
        inicio, fin, margen,
    )

    if "Etiqueta_Relacionada" in detalle_f.columns and "Etiqueta_Relacionada" in resumen_ciclos_pd.columns:
        etiquetas = set(detalle_f["Etiqueta_Relacionada"].dropna())
        resumen_f = resumen_ciclos_pd.loc[
            resumen_ciclos_pd["Etiqueta_Relacionada"].isin(etiquetas)
        ].copy()
    else:
        resumen_f = resumen_ciclos_pd.iloc[0:0].copy()

    if detalle_f.empty:
        diagnostico = pd.DataFrame({
            "Diagnostico": [
                "No aparece en Detalle_15Min: no fue considerada en ningún ciclo de este cálculo."
            ]
        })
    else:
        diagnostico = _diagnostico_ciclos(resumen_f)
        if diagnostico.empty:
            diagnostico = pd.DataFrame({
                "Diagnostico": [
                    "Hay filas en Detalle_15Min, pero sus etiquetas no aparecen en Resumen_Ciclos_PD."
                ]
            })

    return {
        "RIO": rio_f,
        "Reporte_Crudo": reporte_f,
        "Detalle_15Min": detalle_f,
        "Resumen_Ciclos_PD": resumen_f,
        "Diagnostico": diagnostico,
    }
