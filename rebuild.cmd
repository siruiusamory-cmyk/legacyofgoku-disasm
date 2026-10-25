@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
if "%ADS%"=="" set "ADS=%~dp0..\toolchains\ads12-build805"
set "PATH=%ADS%\Bin;%PATH%"
set "ARMHOME=%ADS%"
set "ARMINC=%ADS%\Include"
set "ARMLIB=%ADS%\Lib"
cd /d "%ROOT%"
if not exist build mkdir build
echo === code generator ===
python tools\code\emit_code.py --write
echo code_generate_exit=%ERRORLEVEL%
echo === stream generator ===
python tools\compress\f1_streams.py --write
echo stream_generate_exit=%ERRORLEVEL%
echo === bios stream generator ===
python tools\compress\bios_streams.py --write
echo bios_generate_exit=%ERRORLEVEL%
echo === script stream generator ===
python tools\scripts\script_streams.py --write
echo script_generate_exit=%ERRORLEVEL%
echo === actor row generator ===
python tools\research\actor_rows.py --write
echo actor_rows_exit=%ERRORLEVEL%
echo === credits generator ===
python tools\research\credits_rows.py --write
echo credits_rows_exit=%ERRORLEVEL%
echo === dialogue generator ===
python tools\research\dialogue_rows.py --write
echo dialogue_rows_exit=%ERRORLEVEL%
echo === message generator ===
python tools\research\message_rows.py --write
echo message_rows_exit=%ERRORLEVEL%
echo === pointer generator ===
python tools\research\pointer_rows.py --write
echo pointer_rows_exit=%ERRORLEVEL%
echo === text generator ===
python tools\research\text_rows.py --write
echo text_rows_exit=%ERRORLEVEL%
echo === fill generator ===
python tools\code\fill_runs.py --write
echo fill_generate_exit=%ERRORLEVEL%
echo === incbin slices ===
call tools\incbin.bat baserom.gba 0x0 0xc0
echo incbin_header_exit=%ERRORLEVEL%
echo === compressor ===
if not exist "%ROOT%\tools\compress\compress.exe" call "%ROOT%\tools\compress\build.cmd"
if errorlevel 1 exit /b 1
echo === building asm files ===
armasm asm\log1.s -o build/log1.o
echo armasm_log1_exit=%ERRORLEVEL%
echo === linking and converting ===
armlink build/log1.o -noremove -scatter scatter.ld -map -symbols -o build/log1.axf 2> build/log1.map
echo armlink_exit=%ERRORLEVEL%
if errorlevel 1 findstr /i /c:"error:" build/log1.map
fromelf build/log1.axf -bin -o build\ROM_START
echo fromelf_exit=%ERRORLEVEL%
dir /b build\ROM_START
echo DONE
