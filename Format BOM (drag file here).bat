@echo off
rem Drag an exported InvenTree BOM .xlsx file onto this .bat to add the colours,
rem the Ordered tick column, Est. Delivery and the tidy formatting.
setlocal
if "%~1"=="" (
  echo.
  echo   Drag an exported .xlsx file onto this file to format it.
  echo.
  pause
  exit /b 0
)
python "%~dp0format_bom_excel.py" "%~1"
echo.
pause
