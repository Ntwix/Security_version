@echo off
chcp 65001 >nul
echo ======================================================================
echo   CHU Security Analyzer - Build et Installation Plugin Revit 2023
echo ======================================================================
echo.


:: === 1. Vérifier MSBuild ===
set MSBUILD=
for /f "delims=" %%i in ('where MSBuild.exe 2^>nul') do set MSBUILD=%%i
if "%MSBUILD%"=="" (
    if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin\MSBuild.exe" (
        set "MSBUILD=C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
    )
)
if "%MSBUILD%"=="" (
    echo [ERREUR] MSBuild.exe introuvable.
    echo          Installez Visual Studio 2019/2022 ou Build Tools.
    pause
    exit /b 1
)
echo [OK] MSBuild: %MSBUILD%

:: === 2. Vérifier Revit API ===
if not exist "C:\Program Files\Autodesk\Revit 2023\RevitAPI.dll" (
    echo [ERREUR] RevitAPI.dll introuvable dans Revit 2023.
    echo          Vérifiez que Revit 2023 est installé.
    pause
    exit /b 1
)
echo [OK] Revit 2023 API trouvée

:: === 3. Vérifier .NET 4.8 Developer Pack ===
if not exist "C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.8" (
    echo.
    echo [ATTENTION] .NET Framework 4.8 Developer Pack non installé !
    echo.
    echo   Vous devez l'installer pour compiler le plugin.
    echo   Téléchargez-le ici :
    echo   https://dotnet.microsoft.com/download/dotnet-framework/net48
    echo   (Choisissez "Developer Pack" pas juste "Runtime")
    echo.
    echo   Après installation, relancez ce script.
    echo.
    pause
    exit /b 1
)
echo [OK] .NET 4.8 Developer Pack trouvé

:: === 4. Build ===
echo.
echo [BUILD] Compilation en cours...
cd /d "%~dp0CHU_SecurityAnalyzer"
"%MSBUILD%" CHU_SecurityAnalyzer.csproj -p:Configuration=Release -verbosity:minimal
if errorlevel 1 (
    echo.
    echo [ERREUR] La compilation a échoué. Voir les erreurs ci-dessus.
    pause
    exit /b 1
)
echo [OK] Compilation réussie !

:: === 5. Installation dans Revit ===
echo.
echo [INSTALL] Copie des fichiers dans Revit 2023...

set ADDIN_DIR=%APPDATA%\Autodesk\Revit\Addins\2023
if not exist "%ADDIN_DIR%" mkdir "%ADDIN_DIR%"

:: Créer un sous-dossier pour le plugin
set PLUGIN_DIR=%ADDIN_DIR%\CHU_SecurityAnalyzer
if not exist "%PLUGIN_DIR%" mkdir "%PLUGIN_DIR%"

:: Copier la DLL
copy /Y "bin\Release\CHU_SecurityAnalyzer.dll" "%PLUGIN_DIR%\" >nul
echo   - DLL copiée

:: Copier le .addin (avec chemin mis à jour)
(
echo ^<?xml version="1.0" encoding="utf-8"?^>
echo ^<RevitAddIns^>
echo   ^<AddIn Type="Application"^>
echo     ^<Name^>CHU Security Analyzer^</Name^>
echo     ^<Assembly^>%PLUGIN_DIR%\CHU_SecurityAnalyzer.dll^</Assembly^>
echo     ^<FullClassName^>CHU_SecurityAnalyzer.App^</FullClassName^>
echo     ^<AddInId^>B1C2D3E4-F5A6-7890-1234-567890ABCDEF^</AddInId^>
echo     ^<VendorId^>CHU_IBN_SINA^</VendorId^>
echo     ^<VendorDescription^>CHU Ibn Sina - Analyse Conformité Sécurité^</VendorDescription^>
echo   ^</AddIn^>
echo ^</RevitAddIns^>
) > "%ADDIN_DIR%\CHU_SecurityAnalyzer.addin"
echo   - Manifeste .addin créé

echo.
echo ======================================================================
echo   INSTALLATION TERMINÉE !
echo ======================================================================
echo.
echo   Fichiers installés :
echo   - %PLUGIN_DIR%\CHU_SecurityAnalyzer.dll
echo   - %ADDIN_DIR%\CHU_SecurityAnalyzer.addin
echo.
echo   PROCHAINE ÉTAPE :
echo   1. Fermez Revit s'il est ouvert
echo   2. Lancez Revit 2023
echo   3. Ouvrez votre maquette ARCHI (avec le lien ELEC)
echo   4. Allez dans l'onglet "CHU Sécurité"
echo   5. Cliquez sur "Analyser Zone"
echo.
pause
