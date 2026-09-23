#!/usr/bin/env python3
"""Interfaz visual para correr el motor SC P-D sin editar codigo.

Abrir con F5 en Spyder, o con doble clic en Abrir_Interfaz.bat.

No requiere instalar nada: usa tkinter, que viene con Anaconda. Guarda la
ultima configuracion en interfaz_config.json (misma carpeta) para no tener que
volver a elegir rutas cada mes.

Pestañas:
  Configurar  motor, archivos de entrada, salida y metodos de calculo.
  Resultados  lo que importa de la salida: total, ciclos, empresas, del costo al pago.
  Pagos       prorrateo entre suministradores; llena PAGA en la entrega CEN.
  Registro    la consola del motor.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

CONFIG = CARPETA / "interfaz_config.json"

# ---------------------------------------------------------------------------
# Que archivos pide el motor. (etiqueta, clave RUTA_*, patron para autodetectar,
# obligatorio). Los "mes pasado" son opcionales: vacio = sin empalme.
# ---------------------------------------------------------------------------
ARCHIVOS = [
    ("Reporte 15 min del mes",       "RUTA_REPORTE_15MIN",       "Reporte_PD_15min_*.csv", True),
    ("Reporte 15 min mes anterior",  "RUTA_REPORTE_MES_PASADO",  None,                     False),
    ("RIO del mes",                  "RUTA_RIO",                 "RIO_*.xlsx",             True),
    ("RIO mes anterior",             "RUTA_RIO_MES_PASADO",      None,                     False),
    ("Costos P-D consolidado",       "RUTA_COSTOS_PD",           "Costos_de_P-D_Consolidado.xlsx", True),
    ("Costos P-D mes anterior",      "RUTA_COSTOS_MES_PASADO",   None,                     False),
    ("Diccionario central-config",   "RUTA_DICCIONARIO",         "Diccionario_central_config.xlsx", True),
    ("Diccionario empresa",          "RUTA_DICCIONARIO_EMPRESA", "Diccionario_*empresa.xlsx", True),
]
PATRONES_RETIROS = ("Retiros*.parquet", "Retiros*.csv")

FILTROS_EXCEL = [("Excel", "*.xlsx *.xlsm"), ("Todos", "*.*")]
FILTROS_CSV = [("CSV", "*.csv"), ("Todos", "*.*")]
FILTROS_RETIROS = [("Retiros", "*.parquet *.csv"), ("Todos", "*.*")]

# Paleta
FONDO = "#f3f5f7"
TARJETA = "#ffffff"
BORDE = "#d9dee3"
TEXTO = "#1d2733"
SUAVE = "#66717d"
ACENTO = "#1f5f8b"
BIEN = "#2f6b46"
ALERTA = "#b8720a"
MAL = "#b00020"


def _abrir_en_sistema(ruta: Path):
    if sys.platform.startswith("win"):
        os.startfile(str(ruta))  # noqa: S606 - abre el explorador de Windows
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(ruta)])
    else:
        subprocess.Popen(["xdg-open", str(ruta)])


class Desplazable(ttk.Frame):
    """Marco con barra de desplazamiento vertical (la configuracion no cabe en pantallas chicas)."""

    def __init__(self, padre):
        super().__init__(padre)
        self.lienzo = tk.Canvas(self, highlightthickness=0, background=FONDO)
        barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview)
        self.interior = ttk.Frame(self.lienzo, padding=(12, 10))
        self.interior.bind("<Configure>",
                           lambda e: self.lienzo.configure(scrollregion=self.lienzo.bbox("all")))
        self._ventana = self.lienzo.create_window((0, 0), window=self.interior, anchor="nw")
        self.lienzo.bind("<Configure>", lambda e: self.lienzo.itemconfigure(self._ventana, width=e.width))
        self.lienzo.configure(yscrollcommand=barra.set)
        self.lienzo.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.lienzo.bind("<Enter>", lambda e: self.lienzo.bind_all("<MouseWheel>", self._rueda))
        self.lienzo.bind("<Leave>", lambda e: self.lienzo.unbind_all("<MouseWheel>"))

    def _rueda(self, evento):
        self.lienzo.yview_scroll(int(-evento.delta / 120) or (-1 if evento.delta > 0 else 1), "units")


class Tarjeta(tk.Frame):
    """Indicador grande: titulo, valor y nota."""

    def __init__(self, padre, titulo: str, color: str = TEXTO, grande: bool = False):
        super().__init__(padre, background=TARJETA, highlightthickness=1, highlightbackground=BORDE,
                         padx=14, pady=10)
        tk.Label(self, text=titulo.upper(), background=TARJETA, foreground=SUAVE,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.valor = tk.Label(self, text="—", background=TARJETA, foreground=color,
                              font=("Segoe UI", 20 if grande else 16, "bold"))
        self.valor.pack(anchor="w")
        self.nota = tk.Label(self, text="", background=TARJETA, foreground=SUAVE, font=("Segoe UI", 9))
        self.nota.pack(anchor="w")

    def mostrar(self, valor: str, nota: str = ""):
        self.valor.configure(text=valor)
        self.nota.configure(text=nota)


def _tabla(padre, columnas, alto=8):
    """Treeview con barra. columnas = [(id, titulo, ancho, 'w'|'e')]."""
    marco = ttk.Frame(padre)
    arbol = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings", height=alto)
    for cid, titulo, ancho, lado in columnas:
        arbol.heading(cid, text=titulo, anchor=lado)
        arbol.column(cid, width=ancho, minwidth=36, anchor=lado, stretch=True)
    arbol.tag_configure("par", background="#f7f9fb")
    barra = ttk.Scrollbar(marco, orient="vertical", command=arbol.yview)
    arbol.configure(yscrollcommand=barra.set)
    arbol.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")
    return marco, arbol


def _llenar(arbol, filas):
    arbol.delete(*arbol.get_children())
    for i, fila in enumerate(filas):
        arbol.insert("", "end", values=fila, tags=("par",) if i % 2 else ())


class Interfaz(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Motor SC P-D · 15 minutos")
        self.geometry("1120x780")
        self.minsize(900, 640)
        if sys.platform.startswith("win"):
            self.state("zoomed")  # las tablas de resultados lucen mejor a pantalla completa
        self.configure(background=FONDO)

        self.cola_log: queue.Queue = queue.Queue()
        self.corriendo = False          # cualquier tarea en segundo plano
        self.ultima_entrega: Path | None = None

        self.vars_ruta: dict[str, tk.StringVar] = {}
        self.marcas_ruta: dict[str, ttk.Label] = {}
        self._estilos()
        self._construir()
        self._cargar_config()
        self.after(100, self._vaciar_log)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        # si ya hay una salida de una corrida anterior, mostrarla de inmediato
        if Path(self.var_salida.get()).is_file():
            self.after(300, lambda: self._cargar_resultados(Path(self.var_salida.get())))

    # ------------------------------------------------------------------ estilo
    def _estilos(self):
        s = ttk.Style(self)
        if "clam" in s.theme_names():
            s.theme_use("clam")
        base = ("Segoe UI", 10)
        s.configure(".", background=FONDO, foreground=TEXTO, font=base)
        s.configure("TFrame", background=FONDO)
        s.configure("TLabel", background=FONDO, foreground=TEXTO)
        s.configure("Suave.TLabel", foreground=SUAVE)
        s.configure("Titulo.TLabel", font=("Segoe UI", 15, "bold"))
        s.configure("Seccion.TLabel", font=("Segoe UI", 11, "bold"), foreground=ACENTO)
        s.configure("TLabelframe", background=FONDO, bordercolor=BORDE)
        s.configure("TLabelframe.Label", background=FONDO, foreground=ACENTO, font=("Segoe UI", 10, "bold"))
        s.configure("TRadiobutton", background=FONDO)
        s.configure("TCheckbutton", background=FONDO)
        s.configure("TNotebook", background=FONDO, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(16, 6), font=("Segoe UI", 10))
        s.map("TNotebook.Tab", background=[("selected", TARJETA)], foreground=[("selected", ACENTO)])
        s.configure("Treeview", rowheight=24, fieldbackground=TARJETA, background=TARJETA)
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#e8ecf0")
        s.configure("Accion.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 6),
                    background=ACENTO, foreground="#ffffff")
        s.map("Accion.TButton", background=[("disabled", "#9fb3c4"), ("active", "#184d71")])
        s.configure("TButton", padding=(10, 5))

    # ------------------------------------------------------------------ UI
    def _construir(self):
        # encabezado
        cab = ttk.Frame(self, padding=(16, 12, 16, 4))
        cab.pack(fill="x")
        ttk.Label(cab, text="Motor SC P-D · resolución 15 minutos", style="Titulo.TLabel").pack(side="left")
        self.lbl_estado = ttk.Label(cab, text="Listo.", style="Suave.TLabel")
        self.lbl_estado.pack(side="right")

        # barra de acciones fija abajo
        barra = ttk.Frame(self, padding=(16, 8, 16, 12))
        barra.pack(side="bottom", fill="x")
        self.btn_run = ttk.Button(barra, text="▶  Ejecutar motor", style="Accion.TButton",
                                  command=self._ejecutar)
        self.btn_run.pack(side="left")
        self.btn_prorratear = ttk.Button(barra, text="Prorratear", command=self._prorratear)
        self.btn_prorratear.pack(side="left", padx=(8, 0))
        self.btn_entrega = ttk.Button(barra, text="Generar entrega CEN", command=self._generar_entrega)
        self.btn_entrega.pack(side="left", padx=(8, 0))
        ttk.Label(barra, text="Versión").pack(side="left", padx=(12, 4))
        self.var_version = tk.StringVar(value="Preliminar")
        ttk.Combobox(barra, textvariable=self.var_version, state="readonly", width=11,
                     values=["Preliminar", "Definitivo"]).pack(side="left")
        ttk.Button(barra, text="Abrir carpeta", command=self._abrir_carpeta).pack(side="right")
        # se muestra solo mientras hay una tarea corriendo
        self.progreso = ttk.Progressbar(barra, mode="indeterminate", length=160)

        self.pestanas = ttk.Notebook(self)
        self.pestanas.pack(fill="both", expand=True, padx=16)
        self.tab_config = Desplazable(self.pestanas)
        self.tab_result = ttk.Frame(self.pestanas, padding=12)
        self.tab_pagos = ttk.Frame(self.pestanas, padding=12)
        self.tab_log = ttk.Frame(self.pestanas, padding=8)
        self.pestanas.add(self.tab_config, text="⚙  Configurar")
        self.pestanas.add(self.tab_result, text="📊  Resultados")
        self.pestanas.add(self.tab_pagos, text="💰  Pagos (prorrateo)")
        self.pestanas.add(self.tab_log, text="📜  Registro")

        self._construir_config(self.tab_config.interior)
        self._construir_resultados(self.tab_result)
        self._construir_pagos(self.tab_pagos)
        self._construir_log(self.tab_log)
        self._refrescar_habilitados()

    def _construir_config(self, cuerpo):
        cuerpo.columnconfigure(0, weight=1)

        # -- 1. Motor
        f_motor = ttk.LabelFrame(cuerpo, text="1. Motor", padding=8)
        f_motor.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.var_motor = tk.StringVar(value="v7")
        ttk.Radiobutton(f_motor, text="v7 — ciclo por central relacionada (produccion)",
                        variable=self.var_motor, value="v7",
                        command=self._refrescar_habilitados).pack(anchor="w")
        ttk.Radiobutton(f_motor, text="Turbina — ciclo por UNIDAD GENERADORA (experimental, no pisa al v7)",
                        variable=self.var_motor, value="turbina",
                        command=self._refrescar_habilitados).pack(anchor="w")
        ttk.Radiobutton(f_motor, text="Reglas del Horario — contraste, aplica las reglas del Excel al dato 15 min",
                        variable=self.var_motor, value="reglas_horario",
                        command=self._refrescar_habilitados).pack(anchor="w")

        # -- 2. Archivos
        f_arch = ttk.LabelFrame(cuerpo, text="2. Archivos de entrada", padding=8)
        f_arch.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        f_arch.columnconfigure(2, weight=1)
        for i, (etiqueta, clave, _, obligatorio) in enumerate(ARCHIVOS):
            marca = ttk.Label(f_arch, text="", width=2)
            marca.grid(row=i, column=0, sticky="w")
            self.marcas_ruta[clave] = marca
            texto = etiqueta + (" *" if obligatorio else "")
            ttk.Label(f_arch, text=texto).grid(row=i, column=1, sticky="w", padx=(0, 8), pady=2)
            var = tk.StringVar()
            self.vars_ruta[clave] = var
            var.trace_add("write", lambda *_, c=clave, o=obligatorio: self._marcar_ruta(c, o))
            ttk.Entry(f_arch, textvariable=var).grid(row=i, column=2, sticky="ew", pady=2)
            filtros = FILTROS_CSV if "REPORTE" in clave else FILTROS_EXCEL
            ttk.Button(f_arch, text="Buscar…", width=9,
                       command=lambda v=var, f=filtros: self._elegir(v, f)
                       ).grid(row=i, column=3, padx=(6, 0), pady=2)
            if not obligatorio:
                ttk.Button(f_arch, text="Quitar", width=7,
                           command=lambda v=var: v.set("")
                           ).grid(row=i, column=4, padx=(4, 0), pady=2)
        ttk.Label(f_arch, text="* obligatorio.  ✓ encontrado · ✗ no existe.  Los 'mes anterior' son opcionales: "
                               "vacio = sin empalme de frontera.",
                  style="Suave.TLabel").grid(row=len(ARCHIVOS), column=0, columnspan=5, sticky="w", pady=(6, 0))

        # -- 3. Salida
        f_sal = ttk.LabelFrame(cuerpo, text="3. Archivo de salida", padding=8)
        f_sal.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        f_sal.columnconfigure(0, weight=1)
        self.var_salida = tk.StringVar()
        ttk.Entry(f_sal, textvariable=self.var_salida).grid(row=0, column=0, sticky="ew")
        ttk.Button(f_sal, text="Guardar como…", command=self._elegir_salida
                   ).grid(row=0, column=1, padx=(6, 0))

        # -- 4. Metodos de calculo
        f_met = ttk.LabelFrame(cuerpo, text="4. Metodos de calculo", padding=8)
        f_met.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        f_met.columnconfigure(1, weight=1)

        ttk.Label(f_met, text="Margen unitario").grid(row=0, column=0, sticky="nw", padx=(0, 8))
        self.var_margen = tk.IntVar(value=1)
        fm = ttk.Frame(f_met); fm.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(fm, text="Calcular en el motor: (CMg − CV) × Dolar, todas las filas  [igual que el horario]",
                        variable=self.var_margen, value=1).pack(anchor="w")
        ttk.Radiobutton(fm, text="Usar la columna CMg-CV del reporte tal como viene",
                        variable=self.var_margen, value=0).pack(anchor="w")

        self.lbl_resolucion_margen = ttk.Label(f_met, text="Resolucion del margen (solo motor v7)")
        self.lbl_resolucion_margen.grid(row=1, column=0, sticky="nw", padx=(0, 8), pady=(6, 0))
        self.var_resolucion_margen = tk.StringVar(value="bloque")
        fr = ttk.Frame(f_met); fr.grid(row=1, column=1, sticky="w", pady=(6, 0))
        self.rb_resolucion_margen = [
            ttk.Radiobutton(fr, text="bloque — calcular cada 15 minutos (default)",
                            variable=self.var_resolucion_margen, value="bloque"),
            ttk.Radiobutton(fr, text="hora — agregar por hora-reloj [igual que el horario]",
                            variable=self.var_resolucion_margen, value="hora"),
        ]
        for rb in self.rb_resolucion_margen:
            rb.pack(anchor="w")

        self.var_neteado = tk.IntVar(value=0)
        self.cb_neteado = ttk.Checkbutton(f_met, text="Netear el margen dentro del ciclo antes de truncar  "
                                                      "(CAMBIA EL MONTO: +33,5% en 2606; el horario NO lo hace)",
                                          variable=self.var_neteado)
        self.cb_neteado.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # solo v7: que tarifa cobra un ciclo que paso por varias configuraciones
        self.lbl_tarifa = ttk.Label(f_met, text="Tarifa del ciclo (solo motor v7)")
        self.lbl_tarifa.grid(row=3, column=0, sticky="nw", padx=(0, 8), pady=(6, 0))
        self.var_tarifa = tk.StringVar(value="maxima")
        ft = ttk.Frame(f_met); ft.grid(row=3, column=1, sticky="w", pady=(6, 0))
        self.rb_tarifa = [
            ttk.Radiobutton(ft, text="maxima — la configuracion mas cara que paso por el ciclo  [igual que el horario]",
                            variable=self.var_tarifa, value="maxima"),
            ttk.Radiobutton(ft, text="instruida — la configuracion que instruyo el RIO (spec 15)",
                            variable=self.var_tarifa, value="instruida"),
        ]
        for rb in self.rb_tarifa:
            rb.pack(anchor="w")

        self.lbl_partida_pruebas = ttk.Label(
            f_met, text="Partida sincronizada en pruebas (EP) — solo motor v7")
        self.lbl_partida_pruebas.grid(row=9, column=0, sticky="nw", padx=(0, 8), pady=(6, 0))
        self.var_partida_pruebas = tk.StringVar(value="rechazar")
        fep = ttk.Frame(f_met); fep.grid(row=9, column=1, sticky="w", pady=(6, 0))
        self.rb_partida_pruebas = [
            ttk.Radiobutton(fep, text="Rechazar (vigente)",
                            variable=self.var_partida_pruebas, value="rechazar"),
            ttk.Radiobutton(fep, text="Validar si el CEN la ordenó y la orden falló antes de sincronizar",
                            variable=self.var_partida_pruebas, value="validar_orden_om_fallida"),
            ttk.Radiobutton(fep, text="Validar si queda disponible con motivo válido en el mismo ciclo",
                            variable=self.var_partida_pruebas, value="validar_si_queda_disponible_om"),
        ]
        for rb in self.rb_partida_pruebas:
            rb.pack(anchor="w")

        self.var_diferir = tk.IntVar(value=1)
        self.cb_diferir = ttk.Checkbutton(f_met, text="Diferir ciclos que no terminan en el mes (se cobran el mes que terminan)",
                                          variable=self.var_diferir)
        self.cb_diferir.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.var_baja_gen = tk.IntVar(value=1)
        fb = ttk.Frame(f_met); fb.grid(row=5, column=0, columnspan=2, sticky="w")
        self.cb_baja_gen = ttk.Checkbutton(fb, text="Rechazar ciclos con generacion menor o igual a",
                                           variable=self.var_baja_gen)
        self.cb_baja_gen.pack(side="left")
        self.var_umbral = tk.StringVar(value="1.0")
        self.ent_umbral = ttk.Entry(fb, textvariable=self.var_umbral, width=6)
        self.ent_umbral.pack(side="left", padx=4)
        ttk.Label(fb, text="MWh").pack(side="left")

        self.var_relajada = tk.IntVar(value=1)
        fr = ttk.Frame(f_met); fr.grid(row=6, column=0, columnspan=2, sticky="w")
        self.cb_relajada = ttk.Checkbutton(fr, text="Buscar el registro RIO mas conveniente en una ventana de ±",
                                           variable=self.var_relajada)
        self.cb_relajada.pack(side="left")
        self.var_ventana = tk.StringVar(value="2")
        self.ent_ventana = ttk.Entry(fr, textvariable=self.var_ventana, width=4)
        self.ent_ventana.pack(side="left", padx=4)
        ttk.Label(fr, text="cuartos de hora").pack(side="left")
        fv = ttk.Frame(f_met); fv.grid(row=7, column=0, columnspan=2, sticky="w")
        ttk.Label(fv, text="Aceptar como justificacion una instruccion RIO dada hasta").pack(side="left")
        self.var_vigencia = tk.StringVar(value="30")
        self.ent_vigencia = ttk.Entry(fv, textvariable=self.var_vigencia, width=5)
        self.ent_vigencia.pack(side="left", padx=4)
        ttk.Label(fv, text="min antes del inicio/termino del ciclo (0 = sin limite, hasta 24 h)").pack(side="left")

        self.lbl_horas_sin_historia = ttk.Label(f_met, text="Primer ciclo sin historia (solo motor v7)")
        self.lbl_horas_sin_historia.grid(row=8, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        self.var_horas_sin_historia = tk.StringVar(value="cota_inferior")
        self.cb_horas_sin_historia = ttk.Combobox(
            f_met, textvariable=self.var_horas_sin_historia, state="readonly", width=44,
            values=["cota_inferior", "nulo"])
        self.cb_horas_sin_historia.grid(row=8, column=1, sticky="w", pady=(6, 0))

        # solo turbina
        ttk.Separator(f_met).grid(row=10, column=0, columnspan=2, sticky="ew", pady=6)
        self.lbl_atrib = ttk.Label(f_met, text="Tarifa entre turbinas del mismo evento (solo motor Turbina)")
        self.lbl_atrib.grid(row=11, column=0, sticky="w", padx=(0, 8))
        self.var_atrib = tk.StringVar(value="prorrata")
        self.cb_atrib = ttk.Combobox(f_met, textvariable=self.var_atrib, state="readonly", width=44,
                                     values=["prorrata  — una vez, repartida por generacion",
                                             "primera  — una vez, a la turbina que arranco primero",
                                             "cada_turbina  — cada turbina paga completa"])
        self.cb_atrib.current(0)
        self.cb_atrib.grid(row=11, column=1, sticky="w")

    def _construir_resultados(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)

        arriba = ttk.Frame(tab)
        arriba.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.lbl_resultado = ttk.Label(arriba, text="Aún no hay resultados. Ejecute el motor o cargue una salida.",
                                       style="Seccion.TLabel")
        self.lbl_resultado.pack(side="left")
        ttk.Button(arriba, text="Cargar otra salida…", command=self._elegir_resultado).pack(side="right")
        ttk.Button(arriba, text="Actualizar",
                   command=lambda: self._cargar_resultados(Path(self.var_salida.get()), cambiar=False)
                   ).pack(side="right", padx=(0, 6))

        tarjetas = ttk.Frame(tab)
        tarjetas.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.t_total = Tarjeta(tarjetas, "Sobrecosto P-D a pagar", ACENTO, grande=True)
        self.t_pagados = Tarjeta(tarjetas, "Pagados", BIEN)
        self.t_cubiertos = Tarjeta(tarjetas, "Cubre el margen")
        self.t_rechazados = Tarjeta(tarjetas, "Rechazados")
        self.t_diferidos = Tarjeta(tarjetas, "Diferidos", ALERTA)
        for i, t in enumerate((self.t_total, self.t_pagados, self.t_cubiertos, self.t_rechazados, self.t_diferidos)):
            tarjetas.columnconfigure(i, weight=5 if i == 0 else 3, uniform="t")
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))

        medio = ttk.Frame(tab)
        medio.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        medio.columnconfigure(0, weight=3)
        medio.columnconfigure(1, weight=2)
        f_wf = ttk.LabelFrame(medio, text="Del costo al pago (CLP)", padding=6)
        f_wf.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.lienzo_wf = tk.Canvas(f_wf, height=175, background=TARJETA, highlightthickness=0)
        self.lienzo_wf.pack(fill="both", expand=True)
        self.lienzo_wf.bind("<Configure>", lambda e: self._dibujar_waterfall())
        self._etapas_wf: list[tuple[str, float]] = []
        f_res = ttk.LabelFrame(medio, text="Resultado de los ciclos", padding=6)
        f_res.grid(row=0, column=1, sticky="nsew")
        m, self.tv_resultados = _tabla(f_res, [("r", "Resultado", 190, "w"), ("n", "Ciclos", 60, "e"),
                                               ("c", "Costo P-D", 110, "e"), ("p", "Pagado", 110, "e")], alto=5)
        m.pack(fill="both", expand=True)

        abajo = ttk.Frame(tab)
        abajo.grid(row=3, column=0, sticky="nsew")
        abajo.columnconfigure(0, weight=2)
        abajo.columnconfigure(1, weight=3)
        abajo.rowconfigure(0, weight=1)
        f_emp = ttk.LabelFrame(abajo, text="Quién recibe: sobrecosto por empresa", padding=6)
        f_emp.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        m, self.tv_empresas = _tabla(f_emp, [("e", "Empresa", 120, "w"), ("n", "Ciclos", 50, "e"),
                                             ("sc", "SC P-D (CLP)", 115, "e"), ("p", "%", 45, "e")])
        m.pack(fill="both", expand=True)
        f_top = ttk.LabelFrame(abajo, text="Ciclos con mayor sobrecosto (millones de CLP)", padding=6)
        f_top.grid(row=0, column=1, sticky="nsew")
        m, self.tv_top = _tabla(f_top, [("c", "Ciclo", 95, "w"), ("e", "Empresa", 85, "w"),
                                        ("t", "Tipo", 50, "w"), ("i", "Inicio", 90, "w"),
                                        ("cp", "Partida", 70, "e"), ("cd", "Detención", 70, "e"),
                                        ("m", "Margen", 70, "e"), ("sc", "SC P-D", 75, "e")])
        m.pack(fill="both", expand=True)

        self.lbl_avisos = ttk.Label(tab, text="", foreground=ALERTA, wraplength=1000, justify="left")
        self.lbl_avisos.grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.lbl_parametros = ttk.Label(tab, text="", style="Suave.TLabel", wraplength=1000, justify="left")
        self.lbl_parametros.grid(row=5, column=0, sticky="w")

    def _construir_pagos(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(4, weight=1)
        ttk.Label(tab, text="Prorrateo de pagos entre suministradores", style="Seccion.TLabel"
                  ).grid(row=0, column=0, sticky="w")
        ttk.Label(tab, style="Suave.TLabel", wraplength=1000, justify="left",
                  text="Reparte el sobrecosto de cada ciclo pagado entre los suministradores, en proporción a "
                       "la energía que retiraron en los cuartos de hora del ciclo (spec 11). Con el prorrateo "
                       "hecho, la entrega CEN llena la columna PAGA del RESUMEN y agrega la hoja "
                       "'Cuadro de pagos'.").grid(row=1, column=0, sticky="w", pady=(2, 8))

        f = ttk.Frame(tab)
        f.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        f.columnconfigure(2, weight=1)
        self.marca_retiros = ttk.Label(f, text="", width=2)
        self.marca_retiros.grid(row=0, column=0)
        ttk.Label(f, text="Retiros 15 min (.parquet o .csv)").grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.var_retiros = tk.StringVar()
        self.var_retiros.trace_add("write", lambda *_: self._marcar(self.marca_retiros,
                                                                    self.var_retiros.get(), False))
        ttk.Entry(f, textvariable=self.var_retiros).grid(row=0, column=2, sticky="ew")
        ttk.Button(f, text="Buscar…", width=9,
                   command=lambda: self._elegir(self.var_retiros, FILTROS_RETIROS)).grid(row=0, column=3, padx=(6, 0))
        self.var_incluir_pagos = tk.IntVar(value=0)
        ttk.Checkbutton(f, text="Incluir los pagos (PAGA) en la entrega CEN",
                        variable=self.var_incluir_pagos).grid(row=1, column=1, columnspan=3, sticky="w", pady=(6, 0))

        tarjetas = ttk.Frame(tab)
        tarjetas.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.t_a_repartir = Tarjeta(tarjetas, "Sobrecosto a repartir", ACENTO, grande=True)
        self.t_repartido = Tarjeta(tarjetas, "Repartido", BIEN)
        self.t_delta = Tarjeta(tarjetas, "Diferencia")
        self.t_suministradores = Tarjeta(tarjetas, "Suministradores que pagan")
        for i, t in enumerate((self.t_a_repartir, self.t_repartido, self.t_delta, self.t_suministradores)):
            tarjetas.columnconfigure(i, weight=1, uniform="p")
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))

        f_tab = ttk.LabelFrame(tab, text="Quién paga: monto por suministrador", padding=6)
        f_tab.grid(row=4, column=0, sticky="nsew")
        m, self.tv_pagos = _tabla(f_tab, [("s", "Suministrador", 320, "w"), ("m", "Paga (CLP)", 160, "e"),
                                          ("p", "%", 70, "e")], alto=12)
        m.pack(fill="both", expand=True)
        self.lbl_avisos_pagos = ttk.Label(tab, text="", foreground=ALERTA, wraplength=1000, justify="left")
        self.lbl_avisos_pagos.grid(row=5, column=0, sticky="w", pady=(8, 0))

    def _construir_log(self, tab):
        self.txt = tk.Text(tab, height=12, wrap="none", font=("Consolas", 9),
                           state="disabled", background="#111", foreground="#ddd")
        sb = ttk.Scrollbar(tab, command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        self.txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ------------------------------------------------------------ marcas de archivo
    def _marcar(self, etiqueta: ttk.Label, ruta: str, obligatorio: bool):
        ruta = ruta.strip()
        if not ruta:
            etiqueta.configure(text="•" if obligatorio else "", foreground=MAL if obligatorio else SUAVE)
        elif Path(ruta).exists():
            etiqueta.configure(text="✓", foreground=BIEN)
        else:
            etiqueta.configure(text="✗", foreground=MAL)

    def _marcar_ruta(self, clave: str, obligatorio: bool):
        self._marcar(self.marcas_ruta[clave], self.vars_ruta[clave].get(), obligatorio)

    def _refrescar_habilitados(self):
        es_turbina = self.var_motor.get() == "turbina"
        es_horario = self.var_motor.get() == "reglas_horario"
        estado = "readonly" if es_turbina else "disabled"
        self.cb_atrib.configure(state=estado)
        self.lbl_atrib.configure(foreground=TEXTO if es_turbina else "#999")
        for rb in self.rb_tarifa:
            rb.configure(state="normal" if self.var_motor.get() == "v7" else "disabled")
        self.lbl_tarifa.configure(foreground=TEXTO if self.var_motor.get() == "v7" else "#999")
        for rb in self.rb_partida_pruebas:
            rb.configure(state="normal" if self.var_motor.get() == "v7" else "disabled")
        self.lbl_partida_pruebas.configure(
            foreground=TEXTO if self.var_motor.get() == "v7" else "#999")
        for rb in self.rb_resolucion_margen:
            rb.configure(state="normal" if self.var_motor.get() == "v7" else "disabled")
        self.lbl_resolucion_margen.configure(
            foreground=TEXTO if self.var_motor.get() == "v7" else "#999")
        self.cb_horas_sin_historia.configure(
            state="readonly" if self.var_motor.get() == "v7" else "disabled")
        self.lbl_horas_sin_historia.configure(
            foreground=TEXTO if self.var_motor.get() == "v7" else "#999")
        for control in (self.cb_neteado, self.cb_diferir, self.cb_baja_gen,
                        self.ent_umbral, self.cb_relajada, self.ent_ventana, self.ent_vigencia):
            control.configure(state="disabled" if es_horario else "normal")
        # salida por defecto segun motor, si el usuario no la cambio a mano
        actual = self.var_salida.get()
        defecto_v7 = str(CARPETA / "Reporte_Sobrecostos_PD_Final.xlsx")
        defecto_tb = str(CARPETA / "Reporte_Sobrecostos_PD_Turbina.xlsx")
        defecto_horario = str(CARPETA / "Reporte_Sobrecostos_PD_ReglasHorario.xlsx")
        if actual in ("", defecto_v7, defecto_tb, defecto_horario):
            defecto = defecto_horario if es_horario else (defecto_tb if es_turbina else defecto_v7)
            self.var_salida.set(defecto)

    # ------------------------------------------------------------ acciones
    def _elegir(self, var, filtros):
        inicial = Path(var.get()).parent if var.get() else CARPETA
        ruta = filedialog.askopenfilename(initialdir=inicial, filetypes=filtros)
        if ruta:
            var.set(ruta)

    def _elegir_salida(self):
        inicial = Path(self.var_salida.get()).parent if self.var_salida.get() else CARPETA
        ruta = filedialog.asksaveasfilename(initialdir=inicial, defaultextension=".xlsx",
                                            filetypes=[("Excel", "*.xlsx")],
                                            initialfile=Path(self.var_salida.get() or "salida.xlsx").name)
        if ruta:
            self.var_salida.set(ruta)

    def _elegir_resultado(self):
        inicial = Path(self.var_salida.get()).parent if self.var_salida.get() else CARPETA
        ruta = filedialog.askopenfilename(initialdir=inicial, filetypes=[("Salida del motor", "*.xlsx")])
        if ruta:
            self.var_salida.set(ruta)
            self._cargar_resultados(Path(ruta))

    def _abrir_carpeta(self):
        if self.ultima_entrega and self.ultima_entrega.exists():
            carpeta = self.ultima_entrega
        else:
            carpeta = Path(self.var_salida.get()).parent if self.var_salida.get() else CARPETA
        _abrir_en_sistema(carpeta)

    def _validar(self) -> str | None:
        for etiqueta, clave, _, obligatorio in ARCHIVOS:
            ruta = self.vars_ruta[clave].get().strip()
            if obligatorio and not ruta:
                return f"Falta el archivo obligatorio: {etiqueta}."
            if ruta and not Path(ruta).exists():
                return f"No existe el archivo:\n{ruta}\n({etiqueta})"
        if not self.var_salida.get().strip():
            return "Falta el archivo de salida."
        try:
            float(self.var_umbral.get()); int(self.var_ventana.get()); int(self.var_vigencia.get())
        except ValueError:
            return "El umbral de MWh, la ventana y la vigencia deben ser numeros."
        return None

    def _panel(self) -> dict:
        if self.var_motor.get() == "reglas_horario":
            return {"CALCULAR_MARGEN_EN_EL_MOTOR": self.var_margen.get()}
        panel = {
            "CALCULAR_MARGEN_EN_EL_MOTOR": self.var_margen.get(),
            "MARGEN_NETEADO_POR_CICLO": self.var_neteado.get(),
            "DIFERIR_CICLOS_SIN_TERMINAR": self.var_diferir.get(),
            "FILTRAR_CICLOS_BAJA_GEN": self.var_baja_gen.get(),
            "UMBRAL_RUIDO_MWH": float(self.var_umbral.get()),
            "ACTIVAR_BUSQUEDA_RELAJADA": self.var_relajada.get(),
            "VENTANA_CUARTOS_HORA": int(self.var_ventana.get()),
            "VIGENCIA_INSTRUCCION_RIO_MIN": int(self.var_vigencia.get()),
        }
        if self.var_motor.get() == "turbina":
            panel["ATRIBUCION_TARIFA_TURBINA"] = self.var_atrib.get().split()[0]
        else:
            panel["RESOLUCION_MARGEN"] = self.var_resolucion_margen.get()
            panel["TARIFA_CONFIGURACION"] = self.var_tarifa.get()
            panel["PARTIDA_EN_PRUEBAS"] = self.var_partida_pruebas.get()
            panel["HORAS_SIN_HISTORIA"] = self.var_horas_sin_historia.get()
        return panel

    def _rutas(self) -> dict:
        rutas = {clave: self.vars_ruta[clave].get().strip() for _, clave, _, _ in ARCHIVOS}
        rutas["RUTA_SALIDA"] = self.var_salida.get().strip()
        return rutas

    def _ocupar(self, texto: str):
        """Marca una tarea en curso: bloquea botones y anima la barra."""
        self.corriendo = True
        for b in (self.btn_run, self.btn_prorratear, self.btn_entrega):
            b.configure(state="disabled")
        self.lbl_estado.configure(text=texto, foreground=ALERTA)
        self.progreso.pack(side="right", padx=12)
        self.progreso.start(12)

    def _liberar(self, texto: str, color: str):
        self.corriendo = False
        for b in (self.btn_run, self.btn_prorratear, self.btn_entrega):
            b.configure(state="normal")
        self.lbl_estado.configure(text=texto, foreground=color)
        self.progreso.stop()
        self.progreso.pack_forget()

    def _en_segundo_plano(self, tipo: str, funcion):
        """Corre ``funcion`` en un hilo y devuelve (tipo, resultado|excepcion) por la cola."""
        def correr():
            try:
                self.cola_log.put((tipo, funcion()))
            except Exception as e:  # la UI muestra el error; el detalle va al registro
                self.cola_log.put(traceback.format_exc())
                self.cola_log.put((tipo, e))
        threading.Thread(target=correr, daemon=True).start()

    # --- motor
    def _ejecutar(self):
        if self.corriendo:
            return
        error = self._validar()
        if error:
            messagebox.showerror("Falta algo", error)
            return
        self._guardar_config()
        self._ocupar("Corriendo el motor… (3 a 5 minutos)")
        self._limpiar_log()
        self.pestanas.select(self.tab_log)
        threading.Thread(target=self._correr_motor, daemon=True).start()

    def _correr_motor(self):
        """Corre en un hilo aparte para que la ventana no se congele."""
        rutas, panel, motor_nombre = self._rutas(), self._panel(), self.var_motor.get()

        class Escritor:
            def __init__(s, cola): s.cola = cola
            def write(s, texto):
                if texto:
                    s.cola.put(texto)
            def flush(s): pass

        stdout_original = sys.stdout
        sys.stdout = Escritor(self.cola_log)
        exito = False
        try:
            print(f">>> Motor: {motor_nombre}")
            print(">>> Rutas:")
            for k, v in rutas.items():
                print(f"      {k:<26} {v or '(vacio)'}")
            print(">>> Interruptores:")
            for k, v in panel.items():
                print(f"      {k:<26} {v}")
            print()
            if motor_nombre == "turbina":
                import sc_pd_motor_turbina as motor
            elif motor_nombre == "reglas_horario":
                import sc_pd_motor_reglas_horario as motor
            else:
                import sc_pd_motor_v7 as motor
            motor.main(rutas, panel)
            exito = True
        except SystemExit as e:
            print(f"\n[EL MOTOR SE DETUVO] {e}")
        except Exception:
            print("\n[ERROR INESPERADO]")
            print(traceback.format_exc())
        finally:
            sys.stdout = stdout_original
            self.cola_log.put(("__FIN__", exito))

    def _terminar(self, exito):
        if exito:
            self._liberar(f"Listo → {Path(self.var_salida.get()).name}", BIEN)
            self._cargar_resultados(Path(self.var_salida.get()))
        else:
            self._liberar("Termino con error. Revisa el registro.", MAL)

    # --- resultados
    def _cargar_resultados(self, ruta: Path, cambiar: bool = True):
        if not ruta.is_file() or self.corriendo:
            return
        import resumen_salida
        self._cambiar_a_resultados = cambiar
        self._ocupar(f"Leyendo {ruta.name}…")
        self._en_segundo_plano("__RESUMEN__", lambda: resumen_salida.resumir_salida(ruta))

    def _mostrar_resultados(self, r: dict):
        import pandas as pd
        from resumen_salida import formato_clp, formato_mm
        mes = f"Mes {r['mes']} · " if r["mes"] else ""
        self.lbl_resultado.configure(text=f"{mes}{r['archivo']}")
        pct = (lambda n: f"{100 * n / r['ciclos']:.0f}% de {r['ciclos']} ciclos") if r["ciclos"] else (lambda n: "")
        self.t_total.mostrar(formato_clp(r["total_sc"]),
                             f"{formato_mm(r['total_sc'])} · {r['empresas_con_pago']} empresas reciben")
        self.t_pagados.mostrar(str(r["pagados"]), pct(r["pagados"]))
        self.t_cubiertos.mostrar(str(r["cubiertos"]), "margen ≥ costo")
        self.t_rechazados.mostrar(str(r["rechazados"]), "filtros o costo 0")
        self.t_diferidos.mostrar(str(r["diferidos"]), "al mes de término")

        _llenar(self.tv_resultados, [(f["Resultado"], f["Ciclos"], formato_clp(f["Costo_PD"]),
                                      formato_clp(f["Pagado"])) for _, f in r["resultados"].iterrows()])
        _llenar(self.tv_empresas, [(f["Empresa"], int(f.get("Ciclos", 0) or 0),
                                    formato_clp(f["Total_SC_PD_CLP"]), f"{f['Participacion_%']:.1f}")
                                   for _, f in r["empresas"].iterrows()])

        def celda(f, col, dinero=False):
            v = f.get(col)
            if v is None or v == "" or pd.isna(v):
                return ""
            if dinero:
                return formato_mm(v).replace(" MM", "")
            return v.strftime("%d-%m %H:%M") if hasattr(v, "strftime") else v
        _llenar(self.tv_top, [(celda(f, "Etiqueta_Relacionada"), celda(f, "Empresa"), celda(f, "Tipo_Partida"),
                               celda(f, "Inicio_Ciclo"), celda(f, "Costo_Partida_Efectivo", True),
                               celda(f, "Costo_Detencion_Efectivo", True), celda(f, "Margen_Suma_Ciclo", True),
                               celda(f, "Total SC_PD", True)) for _, f in r["top_ciclos"].iterrows()])
        self._etapas_wf = r["waterfall"]
        self._dibujar_waterfall()
        self.lbl_avisos.configure(text="⚠  " + "   ".join(r["avisos"]) if r["avisos"] else "")
        self.lbl_parametros.configure(
            text="Corrido con: " + ", ".join(f"{k} = {v}" for k, v in r["parametros"].items())
            if r["parametros"] else "")

    def _dibujar_waterfall(self):
        from resumen_salida import formato_mm
        c = self.lienzo_wf
        c.delete("all")
        etapas = self._etapas_wf
        ancho, alto = max(c.winfo_width(), 300), max(c.winfo_height(), 120)
        if not etapas:
            c.create_text(ancho / 2, alto / 2, text="Sin hoja Waterfall_Costos en esta salida.", fill=SUAVE)
            return
        maximo = max(abs(m) for _, m in etapas) or 1
        izq, der = min(320, ancho * 0.45), 80
        fila = min(26, (alto - 8) / len(etapas))
        for i, (etapa, monto) in enumerate(etapas):
            y = 4 + i * fila
            es_total = etapa[:2] in ("1.", "2.", "3.")
            color = BIEN if etapa.startswith("3.") else (ACENTO if es_total else MAL)
            fuente = tkfont.Font(family="Segoe UI", size=9, weight="bold" if es_total else "normal")
            texto = etapa.replace("[-] ", "− ")
            # recorta con "…" para que la etiqueta nunca pise la barra
            while fuente.measure(texto) > izq - 16 and len(texto) > 4:
                texto = texto[:-2] + "…"
            c.create_text(8, y + fila / 2, text=texto, anchor="w", fill=TEXTO if es_total else SUAVE, font=fuente)
            largo = (ancho - izq - der) * abs(monto) / maximo
            if largo > 0:
                c.create_rectangle(izq, y + 4, izq + largo, y + fila - 4, fill=color, width=0)
            c.create_text(izq + largo + 6, y + fila / 2, text=formato_mm(monto).replace("-", "−"),
                          anchor="w", fill=TEXTO, font=("Segoe UI", 9))

    # --- prorrateo
    def _prorratear(self):
        if self.corriendo:
            return
        salida, retiros = Path(self.var_salida.get().strip()), Path(self.var_retiros.get().strip())
        if not salida.is_file():
            messagebox.showerror("Falta la salida", "Ejecute el motor o cargue una salida existente.")
            return
        if not self.var_retiros.get().strip():
            self.pestanas.select(self.tab_pagos)
            self._elegir(self.var_retiros, FILTROS_RETIROS)
            if not self.var_retiros.get().strip():
                return
            retiros = Path(self.var_retiros.get().strip())
        if not retiros.is_file():
            messagebox.showerror("Falta el archivo de retiros", f"No existe:\n{retiros}")
            return
        self._guardar_config()
        import resumen_salida
        self.pestanas.select(self.tab_pagos)
        self._ocupar("Prorrateando entre suministradores… (1 a 2 minutos)")
        self.cola_log.put(f"\n>>> Prorrateo: {salida.name} × {retiros.name}\n")
        self._en_segundo_plano("__PRORRATEO__", lambda: resumen_salida.prorratear_salida(salida, retiros))

    def _mostrar_prorrateo(self, r: dict):
        from resumen_salida import formato_clp
        self.t_a_repartir.mostrar(formato_clp(r["total_original"]), f"{r['ciclos']} ciclos con monto")
        self.t_repartido.mostrar(formato_clp(r["total_repartido"]))
        cuadra = abs(r["delta_total"]) <= 1
        self.t_delta.mostrar(formato_clp(r["delta_total"]), "cuadra ✓" if cuadra else "ciclos sin retiros")
        self.t_delta.valor.configure(foreground=BIEN if cuadra else MAL)
        pagan = r["por_suministrador"]
        self.t_suministradores.mostrar(str(int((pagan["Monetario"] > 0).sum())))
        _llenar(self.tv_pagos, [(f["Suministrador"], formato_clp(f["Monetario"]), f"{f['Participacion_%']:.2f}")
                                for _, f in pagan.iterrows()])
        avisos = list(r["mensajes"]) + [f"Guardado en {r['excel'].name} y {r['csv'].name}."]
        self.lbl_avisos_pagos.configure(text="\n".join(avisos), foreground=ALERTA if r["mensajes"] else SUAVE)
        for m in avisos:
            self.cola_log.put(m + "\n")
        self.var_incluir_pagos.set(1)

    # --- entrega
    def _generar_entrega(self):
        """Genera la entrega sobre la salida seleccionada, sin bloquear la UI."""
        if self.corriendo:
            return
        ruta = Path(self.var_salida.get().strip())
        if not ruta.exists():
            messagebox.showerror("Falta la salida", "Ejecute el motor o seleccione una salida existente.")
            return
        script = RAIZ / "scripts" / "generar_entrega_cen.py"
        comando = [sys.executable, str(script), str(ruta), "--version", self.var_version.get()]
        if self.var_incluir_pagos.get():
            retiros = Path(self.var_retiros.get().strip())
            if not self.var_retiros.get().strip() or not retiros.is_file():
                messagebox.showerror("Falta el archivo de retiros",
                                     "Para incluir los pagos elija el archivo de retiros en la pestaña "
                                     "'Pagos (prorrateo)', o desmarque 'Incluir los pagos'.")
                self.pestanas.select(self.tab_pagos)
                return
            comando += ["--retiros", str(retiros)]
        self._guardar_config()
        con_pagos = " con pagos" if self.var_incluir_pagos.get() else ""
        self._ocupar(f"Generando entrega CEN{con_pagos}…")
        self.cola_log.put(f"\n>>> Entrega CEN ({self.var_version.get()}{con_pagos}): {ruta.name}\n")

        def correr():
            ok, carpeta = False, None
            try:
                proceso = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True, encoding="utf-8", errors="replace")
                for linea in proceso.stdout:
                    self.cola_log.put(linea)
                    if linea.startswith("Entrega creada en:"):
                        carpeta = Path(linea.split(":", 1)[1].strip())
                ok = proceso.wait() == 0
            except Exception:
                self.cola_log.put(traceback.format_exc())
            self.cola_log.put(("__FIN_ENTREGA__", (ok, carpeta)))
        threading.Thread(target=correr, daemon=True).start()

    # --- cola
    def _vaciar_log(self):
        try:
            while True:
                item = self.cola_log.get_nowait()
                if isinstance(item, tuple):
                    self._evento(*item)
                else:
                    self.txt.configure(state="normal")
                    self.txt.insert("end", item)
                    self.txt.see("end")
                    self.txt.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._vaciar_log)

    def _evento(self, tipo, dato):
        if tipo == "__FIN__":
            self._terminar(dato)
        elif tipo == "__RESUMEN__":
            if isinstance(dato, Exception):
                self._liberar(f"No se pudo leer la salida: {dato}", MAL)
                return
            self._liberar(f"Resultados de {dato['archivo']}", BIEN)
            self._mostrar_resultados(dato)
            if getattr(self, "_cambiar_a_resultados", True):
                self.pestanas.select(self.tab_result)
        elif tipo == "__PRORRATEO__":
            if isinstance(dato, Exception):
                self._liberar("Error en el prorrateo. Revisa el registro.", MAL)
                messagebox.showerror("Prorrateo", str(dato))
                return
            self._mostrar_prorrateo(dato)
            self._liberar("Prorrateo listo: la entrega CEN incluirá los pagos.", BIEN)
        elif tipo == "__FIN_ENTREGA__":
            ok, carpeta = dato
            if ok:
                self.ultima_entrega = carpeta
                nombre = carpeta.name if carpeta else "carpeta de salida"
                self._liberar(f"Entrega CEN lista → {nombre}", BIEN)
                if carpeta and messagebox.askyesno("Entrega CEN lista",
                                                   f"Se creó {nombre}.\n\n¿Abrir la carpeta?"):
                    _abrir_en_sistema(carpeta)
            else:
                self._liberar("Error al generar entrega CEN. Revisa el registro.", MAL)
                self.pestanas.select(self.tab_log)

    def _limpiar_log(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")

    # ------------------------------------------------------------- config
    def _cargar_config(self):
        datos = {}
        if CONFIG.exists():
            try:
                datos = json.loads(CONFIG.read_text(encoding="utf-8"))
            except Exception:
                datos = {}
        for _, clave, patron, _ in ARCHIVOS:
            valor = datos.get("rutas", {}).get(clave, "")
            if not valor and patron:
                candidatos = sorted(CARPETA.glob(patron))
                if candidatos:
                    valor = str(candidatos[-1])   # el mas reciente por nombre
            self.vars_ruta[clave].set(valor)
        retiros = datos.get("retiros", "")
        if not retiros:
            candidatos = sorted(r for p in PATRONES_RETIROS for r in CARPETA.glob(p))
            retiros = str(candidatos[-1]) if candidatos else ""
        self.var_retiros.set(retiros)
        self.var_version.set(datos.get("version", "Preliminar"))
        self.var_motor.set(datos.get("motor", "v7"))
        p = datos.get("panel", {})
        self.var_margen.set(p.get("CALCULAR_MARGEN_EN_EL_MOTOR", 1))
        self.var_resolucion_margen.set(p.get("RESOLUCION_MARGEN", "bloque"))
        self.var_neteado.set(p.get("MARGEN_NETEADO_POR_CICLO", 0))
        self.var_tarifa.set(p.get("TARIFA_CONFIGURACION", "maxima"))
        self.var_partida_pruebas.set(p.get("PARTIDA_EN_PRUEBAS", "rechazar"))
        self.var_diferir.set(p.get("DIFERIR_CICLOS_SIN_TERMINAR", 1))
        self.var_baja_gen.set(p.get("FILTRAR_CICLOS_BAJA_GEN", 1))
        self.var_umbral.set(str(p.get("UMBRAL_RUIDO_MWH", 1.0)))
        self.var_relajada.set(p.get("ACTIVAR_BUSQUEDA_RELAJADA", 1))
        self.var_ventana.set(str(p.get("VENTANA_CUARTOS_HORA", 2)))
        self.var_vigencia.set(str(p.get("VIGENCIA_INSTRUCCION_RIO_MIN", 30)))
        self.var_horas_sin_historia.set(p.get("HORAS_SIN_HISTORIA", "cota_inferior"))
        atrib = p.get("ATRIBUCION_TARIFA_TURBINA", "prorrata")
        for i, v in enumerate(self.cb_atrib["values"]):
            if v.startswith(atrib):
                self.cb_atrib.current(i)
        if datos.get("salida"):
            self.var_salida.set(datos["salida"])
        self._refrescar_habilitados()

    def _guardar_config(self):
        try:
            panel = self._panel()
        except ValueError:  # numero mal escrito: se conserva lo guardado antes
            panel = json.loads(CONFIG.read_text(encoding="utf-8")).get("panel", {}) if CONFIG.exists() else {}
        datos = {"motor": self.var_motor.get(), "rutas": self._rutas(),
                 "salida": self.var_salida.get(), "panel": panel,
                 "retiros": self.var_retiros.get().strip(), "version": self.var_version.get()}
        datos["rutas"].pop("RUTA_SALIDA", None)
        try:
            CONFIG.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _cerrar(self):
        if self.corriendo and not messagebox.askyesno(
                "Tarea en curso", "Hay una tarea corriendo. ¿Cerrar de todos modos?"):
            return
        self._guardar_config()
        self.destroy()


if __name__ == "__main__":
    Interfaz().mainloop()
