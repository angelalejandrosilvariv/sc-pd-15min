"""Agosto 2026 con empalme de julio, motor main actual (specs 25, 27, 28), archivos locales."""
import sys, time
from pathlib import Path
RAIZ = Path(r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main"); W = RAIZ / "Carpeta_de_Trabajo"; S = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
import sc_pd_motor_v7 as motor
VIG = int(sys.argv[1]) if len(sys.argv) > 1 else 30
HIST = sys.argv[2] if len(sys.argv) > 2 else "cota_inferior"
rutas = {"RUTA_REPORTE_15MIN": str(W / "Reporte_PD_15min_2608_v2.csv"), "RUTA_REPORTE_MES_PASADO": str(W / "Reporte_PD_15min_2607_v2.csv"),
         "RUTA_RIO": str(W / "RIO_08_2026.xlsx"), "RUTA_RIO_MES_PASADO": str(W / "RIO_07_2026.xlsx"),
         "RUTA_COSTOS_PD": str(W / "Costos_de_P-D_Consolidado_2608.xlsx"), "RUTA_COSTOS_MES_PASADO": str(W / "Costos_de_P-D_Consolidado_2607.xlsx"),
         "RUTA_DICCIONARIO": str(W / "Diccionario_central_config.xlsx"), "RUTA_DICCIONARIO_EMPRESA": str(W / "Diccionario_central_empresa.xlsx"),
         "RUTA_SALIDA": str(S / f"Motor_2608_julio_vig{VIG}_{HIST}.xlsx")}
t0 = time.time()
motor.main(rutas, {"CALCULAR_MARGEN_EN_EL_MOTOR": 1, "MARGEN_NETEADO_POR_CICLO": 0, "TARIFA_CONFIGURACION": "maxima",
                   "VIGENCIA_INSTRUCCION_RIO_MIN": VIG, "HORAS_SIN_HISTORIA": HIST})
print(f"\n[OK] 2608 con julio vig={VIG} hist={HIST} en {time.time()-t0:,.1f} s")
