@echo off
rem Atalho para rodar o pipeline de extracao de OCs (modo demo) sem precisar
rem abrir terminal e digitar comando - so dar duplo-clique neste arquivo.
setlocal
cd /d "%~dp0"

set PYTHON_EXE=.venv\Scripts\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=python

echo ============================================
echo  Rodando pipeline de extracao de OCs (modo demo)
echo ============================================
echo.

"%PYTHON_EXE%" src\pipeline.py

echo.
echo ============================================
echo  Pipeline finalizado.
echo  Confira o resultado no site ou em output\logs\pipeline.log
echo ============================================
pause
