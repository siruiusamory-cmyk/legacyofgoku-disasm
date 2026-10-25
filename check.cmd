@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
python tools\check_links.py
if errorlevel 1 exit /b 1
python tools\lint\lints.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\test_check_links.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\gate\test_gate.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\lint\test_lint.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\extract\test_slice_rom.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\compress\test_jcalg1.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\compress\test_f1_streams.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\compress\test_bios_streams.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\research\test_startup_writes.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\split\test_census.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\code\test_emit_code.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\recomp\test_export_inputs.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\recomp\test_runtime_labels.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\scripts\test_script_streams.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\research\test_actor_rows.py
python -m pytest -q tools\research\test_credits_rows.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\research\test_dialogue_rows.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\research\test_message_rows.py
if errorlevel 1 exit /b 1
python -m pytest -q tools\research\test_text_rows.py
if errorlevel 1 exit /b 1
echo check done
