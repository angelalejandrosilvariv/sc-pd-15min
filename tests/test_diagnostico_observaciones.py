import pandas as pd
import pytest

from src.diagnostico_observaciones import (
    armar_trazado,
    centrales_disponibles,
    coincide_central,
    filtrar_ventana,
)


def test_coincide_central_por_ambos_niveles_normaliza_texto():
    df = pd.DataFrame({
        "Central": [" CANDELARIA-1 ", "OTRA", "DISTINTA"],
        "Central_Relacionada": ["SUR", "Coronel", "NORTE"],
    })
    assert coincide_central(df, "candelaria-1").tolist() == [True, False, False]
    assert coincide_central(df, " CORONEL ").tolist() == [False, True, False]


def test_filtrar_ventana_incluye_limites_del_margen():
    df = pd.DataFrame({
        "fecha": pd.to_datetime([
            "2026-07-21 06:59", "2026-07-21 07:00", "2026-07-21 09:30",
            "2026-07-21 10:30", "2026-07-21 10:31",
        ])
    })
    resultado = filtrar_ventana(
        df, "fecha", "2026-07-21 08:00", "2026-07-21 09:30"
    )
    assert resultado["fecha"].dt.strftime("%H:%M").tolist() == ["07:00", "09:30", "10:30"]


def _insumos():
    rio = pd.DataFrame({
        "FECHA_HORA_RIO": pd.to_datetime(["2026-07-21 08:00"]),
        "Central_Relacionada_RIO": ["CORONEL"],
        "CONSIGNAS": ["CTF(+)"],
    })
    reporte = pd.DataFrame({
        "FECHA_HORA": pd.to_datetime(["2026-07-21 08:15"]),
        "Central": ["CANDELARIA-1"],
        "GENERACION": [2.5],
    })
    detalle = pd.DataFrame({
        "FECHA_HORA": pd.to_datetime(["2026-07-21 08:15"]),
        "Central": ["CANDELARIA-1"],
        "Central_Relacionada": ["CORONEL"],
        "Etiqueta_Relacionada": ["CORONEL&8"],
        "GENERACION": [2.5],
    })
    resumen = pd.DataFrame({
        "Etiqueta_Relacionada": ["CORONEL&8"],
        "Central_Relacionada": ["CORONEL"],
        "Filtro_Conf_Partida": [0],
        "Filtro_Op_Partida": [1],
        "Obs_Partida": ["Configuración RIO distinta"],
        "Obs_Detencion": ["Costo reconocido"],
        "Obs_Liquidacion_Final": ["Costo nulo o anulado por filtros RIO/EP"],
    })
    return rio, reporte, detalle, resumen


def test_armar_trazado_conserva_ciclo_mal_atribuido_y_resumen_exacto():
    rio, reporte, detalle, resumen = _insumos()
    trazado = armar_trazado(
        rio, reporte, detalle, resumen, "CANDELARIA-1",
        "2026-07-21 08:00", "2026-07-21 09:30",
    )
    assert trazado["Detalle_15Min"].iloc[0]["Central_Relacionada"] == "CORONEL"
    assert trazado["Detalle_15Min"].iloc[0]["Etiqueta_Relacionada"] == "CORONEL&8"
    pd.testing.assert_frame_equal(
        trazado["Resumen_Ciclos_PD"].reset_index(drop=True), resumen
    )
    assert trazado["Diagnostico"].iloc[0]["Filtro_Conf_Partida"] == 0


def test_armar_trazado_muestra_termino_y_evidencia_rio_sin_modificarlos():
    rio, reporte, detalle, resumen = _insumos()
    resumen = resumen.assign(
        Inicio_Ciclo=pd.Timestamp("2026-07-21 08:15"),
        Termino_Ciclo=pd.Timestamp("2026-07-21 09:15"),
        Tipo_Partida_RIO="Tibia_2",
        Config_RIO_Usada_Partida="CORONEL_GNL",
    )
    diagnostico = armar_trazado(
        rio, reporte, detalle, resumen, "CANDELARIA-1",
        "2026-07-21 08:00", "2026-07-21 09:30",
    )["Diagnostico"]

    assert diagnostico.loc[0, "Termino_Ciclo"] == pd.Timestamp("2026-07-21 09:15")
    assert diagnostico.loc[0, "Tipo_Partida_RIO"] == "Tibia_2"
    assert diagnostico.loc[0, "Config_RIO_Usada_Partida"] == "CORONEL_GNL"


def test_armar_trazado_explica_ausencia_en_detalle():
    rio, reporte, detalle, resumen = _insumos()
    trazado = armar_trazado(
        rio, reporte, detalle, resumen, "CANDELARIA-1",
        "2026-07-25 08:00", "2026-07-25 09:30", margen=pd.Timedelta(0),
    )
    assert trazado["Detalle_15Min"].empty
    assert "No aparece en Detalle_15Min" in trazado["Diagnostico"].iloc[0]["Diagnostico"]


def test_central_no_encontrada_incluye_sugerencias():
    rio, reporte, detalle, resumen = _insumos()
    assert "CANDELARIA-1" in centrales_disponibles(reporte, detalle)
    with pytest.raises(ValueError, match="CANDELARIA-1"):
        armar_trazado(
            rio, reporte, detalle, resumen, "CANDELARIA-2",
            "2026-07-21 08:00", "2026-07-21 09:30",
        )
