"""Lectura liviana de la salida del motor para mostrarla en la interfaz.

Solo lee las hojas chicas del reporte (``Resumen_Ciclos_PD``, ``SC_por_Empresa``,
``Waterfall_Costos``, ``Parametros_Motor``); no toca ``Detalle_15Min`` salvo para
prorratear. Sirve para los tres motores: las columnas que falten se omiten.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cache_reporte import leer_hoja_cache
from prorrateo_15min import leer_retiros, prorratear_ciclos_motor, resumir_por_suministrador

DIFERIDOS = ("Continua proximo mes", "Continua todo el mes")
# Interruptores que se muestran junto al resultado para saber con que se corrio.
PARAMETROS_CLAVE = ("CALCULAR_MARGEN_EN_EL_MOTOR", "RESOLUCION_MARGEN", "MARGEN_NETEADO_POR_CICLO",
                    "TARIFA_CONFIGURACION", "PARTIDA_EN_PRUEBAS", "HORAS_SIN_HISTORIA",
                    "DIFERIR_CICLOS_SIN_TERMINAR", "VIGENCIA_INSTRUCCION_RIO_MIN",
                    "ATRIBUCION_TARIFA_TURBINA")


def _libro(ruta: Path) -> pd.ExcelFile:
    # calamine lee el reporte en segundos; openpyxl tarda minutos en Detalle_15Min
    try:
        return pd.ExcelFile(ruta, engine="calamine")
    except (ImportError, ValueError):
        return pd.ExcelFile(ruta)


def _hoja(xl: pd.ExcelFile, nombre: str, **kw) -> pd.DataFrame | None:
    return pd.read_excel(xl, sheet_name=nombre, **kw) if nombre in xl.sheet_names else None


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def normalizar_etiqueta_ciclo(df: pd.DataFrame, hoja: str) -> pd.DataFrame:
    """Uniforma la llave de ciclo exportada por los tres motores.

    El v7 ya usa ``Etiqueta_Relacionada``; Turbina publica
    ``Etiqueta_Turbina`` y Reglas del Horario publica ``Etiqueta`` solamente
    en el resumen. En el detalle de este ultimo la llave se reconstruye con
    las dos columnas con que el propio motor define sus ciclos.
    """
    normalizado = df.copy()
    if "Etiqueta_Relacionada" in normalizado:
        return normalizado
    if "Etiqueta_Turbina" in normalizado:
        return normalizado.rename(columns={"Etiqueta_Turbina": "Etiqueta_Relacionada"})
    if hoja == "Resumen_Ciclos_PD" and "Etiqueta" in normalizado:
        return normalizado.rename(columns={"Etiqueta": "Etiqueta_Relacionada"})
    if hoja == "Detalle_15Min" and {"Central_Relacionada", "Ciclo_ID"} <= set(normalizado.columns):
        ids = pd.to_numeric(normalizado["Ciclo_ID"], errors="raise").astype(int).astype(str)
        normalizado["Etiqueta_Relacionada"] = normalizado["Central_Relacionada"].astype(str) + "&" + ids
        return normalizado
    raise ValueError(
        f"{hoja} no tiene la etiqueta esperada de una salida del motor "
        "v7, Turbina o Reglas del Horario."
    )


def formato_clp(valor: float) -> str:
    """1234567.8 -> '$ 1.234.568' (separador de miles chileno)."""
    entero = round(float(valor)) or 0  # sin "-0"
    return "$ " + f"{entero:,}".replace(",", ".")


def formato_mm(valor: float) -> str:
    """1234567.8 -> '1,2 MM' (millones, coma decimal)."""
    return f"{float(valor) / 1e6:,.1f} MM".replace(",", "X").replace(".", ",").replace("X", ".")


def clasificar_ciclos(ciclos: pd.DataFrame) -> pd.Series:
    """Resultado de cada ciclo en palabras simples, a partir de sus montos."""
    total = _num(ciclos, "Total SC_PD")
    costos = _num(ciclos, "Costos_Totales_PD")
    estado = ciclos.get("Estado_Ciclo_Mes", pd.Series("", index=ciclos.index)).astype(str)
    return pd.Series(
        [
            "Diferido al próximo mes" if e in DIFERIDOS and t == 0 else
            "Pagado" if t > 0 else
            "Cubierto por el margen" if c > 0 else
            "Sin costo o rechazado por filtros"
            for e, t, c in zip(estado, total, costos)
        ],
        index=ciclos.index,
    )


def resumir_salida(ruta: str | Path, top: int = 15) -> dict:
    """Indicadores, tablas y avisos de un reporte del motor."""
    ruta = Path(ruta)
    xl = _libro(ruta)
    ciclos = _hoja(xl, "Resumen_Ciclos_PD")
    if ciclos is None:
        raise ValueError(f"{ruta.name} no tiene la hoja Resumen_Ciclos_PD: ¿es una salida del motor?")
    empresas = _hoja(xl, "SC_por_Empresa")
    waterfall = _hoja(xl, "Waterfall_Costos")
    parametros = _hoja(xl, "Parametros_Motor")

    ciclos = normalizar_etiqueta_ciclo(ciclos, "Resumen_Ciclos_PD")
    ciclos["Resultado"] = clasificar_ciclos(ciclos)
    total = float(_num(ciclos, "Total SC_PD").sum())
    conteo = ciclos["Resultado"].value_counts()

    if empresas is None or "Total_SC_PD_CLP" not in empresas:
        empresas = (ciclos.assign(_t=_num(ciclos, "Total SC_PD"))
                    .groupby("Empresa", as_index=False)
                    .agg(Ciclos=("_t", "size"), Total_SC_PD_CLP=("_t", "sum")))
    empresas = empresas.sort_values("Total_SC_PD_CLP", ascending=False, ignore_index=True)
    empresas["Participacion_%"] = (100 * empresas["Total_SC_PD_CLP"] / total).round(1) if total else 0.0

    columnas_top = [c for c in ("Etiqueta_Relacionada", "Empresa", "Tipo_Partida", "Inicio_Ciclo",
                                "Costo_Partida_Efectivo", "Costo_Detencion_Efectivo",
                                "Margen_Suma_Ciclo", "Total SC_PD") if c in ciclos]
    top_ciclos = (ciclos.assign(_t=_num(ciclos, "Total SC_PD"))
                  .sort_values("_t", ascending=False).head(top)[columnas_top].reset_index(drop=True))

    resultados = (ciclos.assign(_c=_num(ciclos, "Costos_Totales_PD"), _t=_num(ciclos, "Total SC_PD"))
                  .groupby("Resultado", as_index=False)
                  .agg(Ciclos=("Resultado", "size"), Costo_PD=("_c", "sum"), Pagado=("_t", "sum"))
                  .sort_values("Ciclos", ascending=False, ignore_index=True))

    etapas = []
    if waterfall is not None and {"Etapa_Financiera", "Monto (CLP)"} <= set(waterfall.columns):
        etapas = [(str(e).strip(), float(m)) for e, m in
                  zip(waterfall["Etapa_Financiera"], pd.to_numeric(waterfall["Monto (CLP)"], errors="coerce").fillna(0))]

    params = {}
    if parametros is not None and {"interruptor", "valor"} <= set(parametros.columns):
        todos = dict(zip(parametros["interruptor"].astype(str), parametros["valor"]))
        params = {k: todos[k] for k in PARAMETROS_CLAVE if k in todos}

    avisos = []
    if "Obs_Partida" in ciclos:
        revisar = ciclos["Obs_Partida"].astype(str).str.contains("Revisar", case=False, na=False)
        if revisar.any():
            avisos.append(f"{int(revisar.sum())} ciclo(s) con 'Revisar' en Obs_Partida.")
    sin_empresa = ciclos.get("Empresa", pd.Series(dtype=str)).astype(str).isin(["Sin_Empresa", "nan", ""])
    if sin_empresa.any():
        avisos.append(f"{int(sin_empresa.sum())} ciclo(s) sin empresa asignada.")
    if "Etiqueta_Relacionada" in ciclos and ciclos["Etiqueta_Relacionada"].duplicated().any():
        avisos.append("Hay etiquetas de ciclo repetidas en Resumen_Ciclos_PD.")

    mes = ""
    if "Inicio_Ciclo" in ciclos:
        inicios = pd.to_datetime(ciclos["Inicio_Ciclo"], errors="coerce").dropna()
        if not inicios.empty:
            mes = inicios.max().strftime("%y%m")

    return {
        "archivo": ruta.name,
        "mes": mes,
        "total_sc": total,
        "ciclos": int(len(ciclos)),
        "pagados": int(conteo.get("Pagado", 0)),
        "diferidos": int(conteo.get("Diferido al próximo mes", 0)),
        "cubiertos": int(conteo.get("Cubierto por el margen", 0)),
        "rechazados": int(conteo.get("Sin costo o rechazado por filtros", 0)),
        "empresas_con_pago": int((empresas["Total_SC_PD_CLP"] > 0).sum()),
        "empresas": empresas,
        "top_ciclos": top_ciclos,
        "resultados": resultados,
        "waterfall": etapas,
        "parametros": params,
        "avisos": avisos,
    }


def prorratear_salida(ruta_salida: str | Path, ruta_retiros: str | Path,
                      carpeta: str | Path | None = None) -> dict:
    """Prorratea la salida del motor y deja Prorrateo_15Min.xlsx/CSV junto a ella.

    Solo reparte ciclos con monto (los diferidos y amortizados no tienen nada que pagar),
    igual que la entrega CEN.
    """
    ruta_salida = Path(ruta_salida)
    ciclos = leer_hoja_cache(ruta_salida, "Resumen_Ciclos_PD")
    detalle = leer_hoja_cache(ruta_salida, "Detalle_15Min")
    if ciclos is None or detalle is None:
        xl = _libro(ruta_salida)
        ciclos = _hoja(xl, "Resumen_Ciclos_PD")
        detalle = _hoja(xl, "Detalle_15Min")
    if ciclos is None or detalle is None:
        raise ValueError(f"{ruta_salida.name} no trae Resumen_Ciclos_PD y Detalle_15Min.")
    ciclos = normalizar_etiqueta_ciclo(ciclos, "Resumen_Ciclos_PD")
    detalle = normalizar_etiqueta_ciclo(detalle, "Detalle_15Min")[["Etiqueta_Relacionada", "FECHA_HORA"]]
    con_monto = ciclos[_num(ciclos, "Total SC_PD") != 0]
    detalle_p, auditoria = prorratear_ciclos_motor(detalle, con_monto, leer_retiros(ruta_retiros))
    por_suministrador = resumir_por_suministrador(detalle_p)
    total = float(por_suministrador["Monetario"].sum())
    por_suministrador["Participacion_%"] = (100 * por_suministrador["Monetario"] / total).round(2) if total else 0.0

    carpeta = Path(carpeta) if carpeta else ruta_salida.parent
    carpeta.mkdir(parents=True, exist_ok=True)
    excel = carpeta / "Prorrateo_15Min.xlsx"
    csv = carpeta / "Prorrateo_15Min_Detalle.csv"
    with pd.ExcelWriter(excel) as w:
        por_suministrador.to_excel(w, sheet_name="Pagos_por_Suministrador", index=False)
        auditoria["por_ciclo"].to_excel(w, sheet_name="Cuadratura_por_Ciclo", index=False)
    detalle_p.to_csv(csv, index=False, sep=";", decimal=",")
    return {
        "por_suministrador": por_suministrador,
        "total_original": auditoria["total_original"],
        "total_repartido": auditoria["total_repartido"],
        "delta_total": auditoria["delta_total"],
        "ciclos": int(len(auditoria["por_ciclo"])),
        "ciclos_sin_retiros": auditoria["ciclos_sin_retiros"],
        "mensajes": auditoria["mensajes"],
        "excel": excel,
        "csv": csv,
    }
