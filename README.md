# Motor SC P-D — Resolución 15 minutos

Motor en Python para calcular sobrecostos de partida y detención (SC P-D) del mercado eléctrico chileno, migrando desde un cálculo horario a una resolución de 15 minutos.

## Estado

Esta primera versión del repositorio **preserva el código final v7 entregado en la conversación**. No se cambiaron las reglas de negocio ni se reinterpretaron datos fuente.

El código incorpora, entre otras, las correcciones documentadas en su encabezado: detección de ciclos, mapeo explícito del RIO, saneamiento del empalme mensual, reconstrucción de políticas PO, renumeración de ciclos, selección de configuración dominante y empalme del RIO del mes anterior.

## Datos de entrada

El motor espera archivos como:

- `Reporte_PD_15min_YYMM.csv`
- `RIO_MM_YYYY.xlsx`
- `Costos_de_P-D_Consolidado.xlsx`
- `Diccionario_central_config.xlsx`
- opcionalmente `Diccionario_configuracion_empresa.xlsx`
- archivo de costos del mes anterior, cuando corresponda
- RIO y reporte de 15 minutos del mes anterior, cuando corresponda

**Los archivos fuente no se incluyen en este repositorio** por contener datos operacionales.

## Estructura

```text
sc-pd-15min/
├── .github/
│   └── workflows/
│       └── tests.yml
├── src/
│   └── sc_pd_motor_v7.py
├── tests/
│   ├── test_cycle_detection.py
│   └── test_source_regressions.py
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Instalación

Python 3.11+ recomendado.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Configuración

La v7 conserva el **panel de control de rutas** dentro de `src/sc_pd_motor_v7.py`.

Antes de ejecutar, revisa especialmente:

- `RUTA_REPORTE_15MIN`
- `RUTA_REPORTE_MES_PASADO`
- `RUTA_RIO`
- `RUTA_RIO_MES_PASADO`
- `RUTA_COSTOS_PD`
- `RUTA_COSTOS_MES_PASADO`
- `RUTA_DICCIONARIO`
- `RUTA_DICCIONARIO_EMPRESA`
- `RUTA_SALIDA`

También deben validarse contra la regla de negocio vigente los parámetros `CODIGOS_EO_VALIDOS`, `USAR_TARIFA_RIO_INSTRUIDA`, `REGLA_EXENCION` y los demás interruptores del panel.

## Ejecución

Desde la raíz del repositorio:

```bash
python src/sc_pd_motor_v7.py
```

El resultado se escribe en la ruta definida en `RUTA_SALIDA`.

## Auditoría

El flujo exporta hojas de auditoría y conciliación, incluyendo:

- `Waterfall_Costos`
- `SC_por_Empresa`
- `Resumen_Ciclos_PD`
- `Detalle_15Min`
- `Auditoria_Pasos`
- `Cobertura_Instruccion_RIO` cuando está habilitada

## Pruebas

Las pruebas no ejecutan el pipeline completo contra datos productivos. Se concentran en:

1. validar sintácticamente el script;
2. extraer y probar la función real de detección de ciclos;
3. proteger regresiones de los fixes críticos descritos en la v7.

Ejecuta:

```bash
pytest -q
```

## Decisiones y pendientes conocidos

El propio código deja explícitos asuntos que todavía requieren validación de negocio o regulatoria, por ejemplo:

- `CODIGOS_EO_VALIDOS = ['PDO']` está marcado como pendiente de confirmar;
- la tolerancia de corte de ciclo queda en `0`, de acuerdo con la definición entregada para el proyecto;
- la regla de margen usa solo margen positivo;
- no se debe sustituir la regla física de ciclo por un puente heurístico de horas de cero;
- el repositorio no contiene los Excel/CSV operacionales.

## Principio de cambios

Los cambios posteriores deberían separarse en:

- correcciones de integridad de datos;
- reglas de negocio aprobadas;
- refactor técnico sin cambio funcional;
- auditoría y trazabilidad.

Toda modificación que pueda alterar el monto liquidado debería acompañarse de una prueba o evidencia reproducible.
