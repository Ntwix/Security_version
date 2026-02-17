$src = "c:\Users\nouha\Desktop\CHU_Ibn Sina\4-CODE\zone1_locaux_electriques_v2\zone1_locaux_electriques\RevitPlugin\CHU_SecurityAnalyzer\bin\Release\CHU_SecurityAnalyzer.dll"
$dst = Join-Path $env:APPDATA "Autodesk\Revit\Addins\2023\CHU_SecurityAnalyzer"
if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Path $dst -Force }
$dstFile = Join-Path $dst "CHU_SecurityAnalyzer.dll"
Copy-Item -Path $src -Destination $dstFile -Force
Write-Host "DLL copiee avec succes"
Get-Item $dstFile | Format-List Name, Length, LastWriteTime
