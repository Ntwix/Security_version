@echo off
set SRC=c:\Users\nouha\Desktop\CHU_Ibn Sina\4-CODE\zone1_locaux_electriques_v2\zone1_locaux_electriques\RevitPlugin\CHU_SecurityAnalyzer\bin\Release\CHU_SecurityAnalyzer.dll
set DST=%APPDATA%\Autodesk\Revit\Addins\2023\CHU_SecurityAnalyzer\
if not exist "%DST%" mkdir "%DST%"
copy /Y "%SRC%" "%DST%"
echo DLL copiee vers %DST%
pause
