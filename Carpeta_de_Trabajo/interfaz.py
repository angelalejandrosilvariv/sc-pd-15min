#!/usr/bin/env python3
"""Interfaz visual para correr el motor SC P-D sin editar codigo.

Abrir con F5 en Spyder, o con doble clic en Abrir_Interfaz.bat.

No requiere instalar nada: usa tkinter, que viene con Anaconda. Guarda la
ultima configuracion en interfaz_config.json (misma carpeta) para no tener que
volver a elegir rutas cada mes.
"""

from __future__ import annotations

import json
import queue
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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

FILTROS_EXCEL = [("Excel", "*.xlsx *.xlsm"), ("Todos", "*.*")]
FILTROS_CSV = [("CSV", "*.csv"), ("Todos", "*.*")]


class Interfaz(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Motor SC P-D")
        self.minsize(820, 640)
        self.resizable(True, True)

        self.cola_log: queue.Queue[str] = queue.Queue()
        self.corriendo = False

        self.vars_ruta: dict[str, tk.StringVar] = {}
        self._construir()
        self._cargar_config()
        self.after(100, self._vaciar_log)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    # ------------------------------------------------------------------ UI
    def _construir(self):
        cuerpo = ttk.Frame(self, padding=12)
        cuerpo.pack(fill="both", expand=True)
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

        # -- 2. Archivos
        f_arch = ttk.LabelFrame(cuerpo, text="2. Archivos de entrada", padding=8)
        f_arch.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        f_arch.columnconfigure(1, weight=1)
        for i, (etiqueta, clave, _, obligatorio) in enumerate(ARCHIVOS):
            texto = etiqueta + (" *" if obligatorio else "")
            ttk.Label(f_arch, text=texto).grid(row=i, column=0, sticky="w", padx=(0, 8), pady=2)
            var = tk.StringVar()
            self.vars_ruta[clave] = var
            ttk.Entry(f_arch, textvariable=var).grid(row=i, column=1, sticky="ew", pady=2)
            filtros = FILTROS_CSV if "REPORTE" in clave else FILTROS_EXCEL
            ttk.Button(f_arch, text="Buscar…", width=9,
                       command=lambda v=var, f=filtros: self._elegir(v, f)
                       ).grid(row=i, column=2, padx=(6, 0), pady=2)
            if not obligatorio:
                ttk.Button(f_arch, text="Quitar", width=7,
                           command=lambda v=var: v.set("")
                           ).grid(row=i, column=3, padx=(4, 0), pady=2)
        ttk.Label(f_arch, text="* obligatorio.  Los 'mes anterior' son opcionales: vacio = sin empalme de frontera.",
                  foreground="#666").grid(row=len(ARCHIVOS), column=0, columnspan=4, sticky="w", pady=(6, 0))

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

        ttk.Label(f_met, text="Margen unitario").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.var_margen = tk.IntVar(value=1)
        fm = ttk.Frame(f_met); fm.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(fm, text="Calcular en el motor: (CMg − CV) × Dolar, todas las filas  [igual que el horario]",
                        variable=self.var_margen, value=1).pack(anchor="w")
        ttk.Radiobutton(fm, text="Usar la columna CMg-CV del reporte tal como viene",
                        variable=self.var_margen, value=0).pack(anchor="w")

        self.var_neteado = tk.IntVar(value=0)
        ttk.Checkbutton(f_met, text="Netear el margen dentro del ciclo antes de truncar  "
                                    "(CAMBIA EL MONTO: +33,5% en 2606; el horario NO lo hace)",
                        variable=self.var_neteado).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # solo v7: que tarifa cobra un ciclo que paso por varias configuraciones
        self.lbl_tarifa = ttk.Label(f_met, text="Tarifa del ciclo (solo motor v7)")
        self.lbl_tarifa.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        self.var_tarifa = tk.StringVar(value="maxima")
        ft = ttk.Frame(f_met); ft.grid(row=2, column=1, sticky="w", pady=(6, 0))
        self.rb_tarifa = [
            ttk.Radiobutton(ft, text="maxima — la configuracion mas cara que paso por el ciclo  [igual que el horario]",
                            variable=self.var_tarifa, value="maxima"),
            ttk.Radiobutton(ft, text="instruida — la configuracion que instruyo el RIO (spec 15)",
                            variable=self.var_tarifa, value="instruida"),
        ]
        for rb in self.rb_tarifa:
            rb.pack(anchor="w")

        self.var_diferir = tk.IntVar(value=1)
        ttk.Checkbutton(f_met, text="Diferir ciclos que no terminan en el mes (se cobran el mes que terminan)",
                        variable=self.var_diferir).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.var_baja_gen = tk.IntVar(value=1)
        fb = ttk.Frame(f_met); fb.grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(fb, text="Rechazar ciclos con generacion menor o igual a",
                        variable=self.var_baja_gen).pack(side="left")
        self.var_umbral = tk.StringVar(value="1.0")
        ttk.Entry(fb, textvariable=self.var_umbral, width=6).pack(side="left", padx=4)
        ttk.Label(fb, text="MWh").pack(side="left")

        self.var_relajada = tk.IntVar(value=1)
        fr = ttk.Frame(f_met); fr.grid(row=5, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(fr, text="Buscar el registro RIO mas conveniente en una ventana de ±",
                        variable=self.var_relajada).pack(side="left")
        self.var_ventana = tk.StringVar(value="2")
        ttk.Entry(fr, textvariable=self.var_ventana, width=4).pack(side="left", padx=4)
        ttk.Label(fr, text="cuartos de hora").pack(side="left")

        # solo turbina
        ttk.Separator(f_met).grid(row=6, column=0, columnspan=2, sticky="ew", pady=6)
        self.lbl_atrib = ttk.Label(f_met, text="Tarifa entre turbinas del mismo evento (solo motor Turbina)")
        self.lbl_atrib.grid(row=7, column=0, sticky="w", padx=(0, 8))
        self.var_atrib = tk.StringVar(value="prorrata")
        self.cb_atrib = ttk.Combobox(f_met, textvariable=self.var_atrib, state="readonly", width=44,
                                     values=["prorrata  — una vez, repartida por generacion",
                                             "primera  — una vez, a la turbina que arranco primero",
                                             "cada_turbina  — cada turbina paga completa"])
        self.cb_atrib.current(0)
        self.cb_atrib.grid(row=7, column=1, sticky="w")

        # -- 5. Ejecutar + log
        f_run = ttk.Frame(cuerpo)
        f_run.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        self.btn_run = ttk.Button(f_run, text="▶  Ejecutar", command=self._ejecutar)
        self.btn_run.pack(side="left")
        self.lbl_estado = ttk.Label(f_run, text="Listo.", foreground="#666")
        self.lbl_estado.pack(side="left", padx=12)
        ttk.Button(f_run, text="Abrir carpeta de salida", command=self._abrir_carpeta).pack(side="right")

        f_log = ttk.LabelFrame(cuerpo, text="Salida del motor", padding=4)
        f_log.grid(row=5, column=0, sticky="nsew")
        cuerpo.rowconfigure(5, weight=1)
        self.txt = tk.Text(f_log, height=12, wrap="none", font=("Consolas", 9),
                           state="disabled", background="#111", foreground="#ddd")
        sb = ttk.Scrollbar(f_log, command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        self.txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._refrescar_habilitados()

    def _refrescar_habilitados(self):
        es_turbina = self.var_motor.get() == "turbina"
        estado = "readonly" if es_turbina else "disabled"
        self.cb_atrib.configure(state=estado)
        self.lbl_atrib.configure(foreground="#000" if es_turbina else "#999")
        for rb in self.rb_tarifa:
            rb.configure(state="disabled" if es_turbina else "normal")
        self.lbl_tarifa.configure(foreground="#999" if es_turbina else "#000")
        # salida por defecto segun motor, si el usuario no la cambio a mano
        actual = self.var_salida.get()
        defecto_v7 = str(CARPETA / "Reporte_Sobrecostos_PD_Final.xlsx")
        defecto_tb = str(CARPETA / "Reporte_Sobrecostos_PD_Turbina.xlsx")
        if actual in ("", defecto_v7, defecto_tb):
            self.var_salida.set(defecto_tb if es_turbina else defecto_v7)

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

    def _abrir_carpeta(self):
        import os
        carpeta = Path(self.var_salida.get()).parent if self.var_salida.get() else CARPETA
        os.startfile(str(carpeta))

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
            float(self.var_umbral.get()); int(self.var_ventana.get())
        except ValueError:
            return "El umbral de MWh y la ventana deben ser numeros."
        return None

    def _panel(self) -> dict:
        panel = {
            "CALCULAR_MARGEN_EN_EL_MOTOR": self.var_margen.get(),
            "MARGEN_NETEADO_POR_CICLO": self.var_neteado.get(),
            "DIFERIR_CICLOS_SIN_TERMINAR": self.var_diferir.get(),
            "FILTRAR_CICLOS_BAJA_GEN": self.var_baja_gen.get(),
            "UMBRAL_RUIDO_MWH": float(self.var_umbral.get()),
            "ACTIVAR_BUSQUEDA_RELAJADA": self.var_relajada.get(),
            "VENTANA_CUARTOS_HORA": int(self.var_ventana.get()),
        }
        if self.var_motor.get() == "turbina":
            panel["ATRIBUCION_TARIFA_TURBINA"] = self.var_atrib.get().split()[0]
        else:
            panel["TARIFA_CONFIGURACION"] = self.var_tarifa.get()
        return panel

    def _rutas(self) -> dict:
        rutas = {clave: self.vars_ruta[clave].get().strip() for _, clave, _, _ in ARCHIVOS}
        rutas["RUTA_SALIDA"] = self.var_salida.get().strip()
        return rutas

    def _ejecutar(self):
        if self.corriendo:
            return
        error = self._validar()
        if error:
            messagebox.showerror("Falta algo", error)
            return
        self._guardar_config()
        self.corriendo = True
        self.btn_run.configure(state="disabled")
        self.lbl_estado.configure(text="Corriendo… (3 a 5 minutos)", foreground="#b8720a")
        self._limpiar_log()
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

    def _vaciar_log(self):
        try:
            while True:
                item = self.cola_log.get_nowait()
                if isinstance(item, tuple) and item[0] == "__FIN__":
                    self._terminar(item[1])
                else:
                    self.txt.configure(state="normal")
                    self.txt.insert("end", item)
                    self.txt.see("end")
                    self.txt.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._vaciar_log)

    def _terminar(self, exito):
        self.corriendo = False
        self.btn_run.configure(state="normal")
        if exito:
            self.lbl_estado.configure(text=f"Listo → {Path(self.var_salida.get()).name}",
                                      foreground="#2f6b46")
        else:
            self.lbl_estado.configure(text="Termino con error. Revisa el log.", foreground="#b00020")

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
        self.var_motor.set(datos.get("motor", "v7"))
        p = datos.get("panel", {})
        self.var_margen.set(p.get("CALCULAR_MARGEN_EN_EL_MOTOR", 1))
        self.var_neteado.set(p.get("MARGEN_NETEADO_POR_CICLO", 0))
        self.var_tarifa.set(p.get("TARIFA_CONFIGURACION", "maxima"))
        self.var_diferir.set(p.get("DIFERIR_CICLOS_SIN_TERMINAR", 1))
        self.var_baja_gen.set(p.get("FILTRAR_CICLOS_BAJA_GEN", 1))
        self.var_umbral.set(str(p.get("UMBRAL_RUIDO_MWH", 1.0)))
        self.var_relajada.set(p.get("ACTIVAR_BUSQUEDA_RELAJADA", 1))
        self.var_ventana.set(str(p.get("VENTANA_CUARTOS_HORA", 2)))
        atrib = p.get("ATRIBUCION_TARIFA_TURBINA", "prorrata")
        for i, v in enumerate(self.cb_atrib["values"]):
            if v.startswith(atrib):
                self.cb_atrib.current(i)
        if datos.get("salida"):
            self.var_salida.set(datos["salida"])
        self._refrescar_habilitados()

    def _guardar_config(self):
        datos = {"motor": self.var_motor.get(), "rutas": self._rutas(),
                 "salida": self.var_salida.get(), "panel": self._panel()}
        datos["rutas"].pop("RUTA_SALIDA", None)
        try:
            CONFIG.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _cerrar(self):
        if self.corriendo and not messagebox.askyesno(
                "Motor corriendo", "El motor sigue corriendo. ¿Cerrar de todos modos?"):
            return
        self._guardar_config()
        self.destroy()


if __name__ == "__main__":
    Interfaz().mainloop()
