@echo off
rem Abre la interfaz visual del motor SC P-D con el Python de Anaconda.
rem Doble clic y listo. Si Anaconda esta en otra ruta, corrige la linea de abajo.
set PY=%LOCALAPPDATA%\anaconda3\python.exe
if not exist "%PY%" set PY=python
cd /d "%~dp0"
"%PY%" interfaz.py
if errorlevel 1 pause
