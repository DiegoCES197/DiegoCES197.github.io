@echo off
REM RadiAPP v2.0 - Shortcuts para Windows
REM Guarda este archivo como: radiapp.bat
REM Uso: Haz doble-click o ejecuta desde cmd

cd /d d:\RadiAPP

echo.
echo ========================================
echo    RadiAPP v2.0 - Launcher Menu
echo ========================================
echo.

:menu
echo.
echo 1. Instalar dependencias
echo 2. Ejecutar tests
echo 3. Lanzar UI (Gradio)
echo 4. Ver documentacion - README
echo 5. Ver documentacion - QUICK_START
echo 6. Ver documentacion - OPTIMIZACIONES
echo 7. Activar virtual environment
echo 8. Salir
echo.

set /p choice="Selecciona opcion (1-8): "

if "%choice%"=="1" goto install
if "%choice%"=="2" goto test
if "%choice%"=="3" goto run
if "%choice%"=="4" goto readme
if "%choice%"=="5" goto quickstart
if "%choice%"=="6" goto optimizations
if "%choice%"=="7" goto venv
if "%choice%"=="8" goto exit

echo Opcion invalida
goto menu

:install
echo.
echo === INSTALANDO DEPENDENCIAS ===
D:\rocm711\Scripts\python.exe -m pip install torch transformers gradio pillow numpy python-docx
echo.
echo Instalacion completada!
pause
goto menu

:test
echo.
echo === EJECUTANDO TESTS ===
D:\rocm711\Scripts\python.exe test_optimizations.py
echo.
pause
goto menu

:run
echo.
echo === LANZANDO RADIAPP v2.0 ===
echo Accede a: http://127.0.0.1:7860
echo Presiona Ctrl+C para detener
echo.
D:\rocm711\Scripts\python.exe -m gradio app.py
pause
goto menu

:readme
echo.
echo === MOSTRANDO README_IMPLEMENTACION ===
start README_IMPLEMENTACION.md
goto menu

:quickstart
echo.
echo === MOSTRANDO QUICK_START ===
start QUICK_START.md
goto menu

:optimizations
echo.
echo === MOSTRANDO OPTIMIZACIONES ===
start OPTIMIZACIONES.md
goto menu

:venv
echo.
echo === ACTIVANDO VIRTUAL ENVIRONMENT ===
call D:\rocm711\Scripts\activate.bat
echo Virtual environment activado!
pause
goto menu

:exit
echo.
echo Adios!
echo.
exit
