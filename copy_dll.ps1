$src = Join-Path $env:USERPROFILE "Desktop\CHU_Ibn Sina\4-CODE\zone1_locaux_electriques_v2\zone1_locaux_electriques\RevitPlugin\CHU_SecurityAnalyzer\bin\Release\CHU_SecurityAnalyzer.dll"
$dst = Join-Path $env:APPDATA "Autodesk\Revit\Addins\2023\CHU_SecurityAnalyzer\CHU_SecurityAnalyzer.dll"

Write-Host "Source: $src"
Write-Host "Destination: $dst"

if (Test-Path -LiteralPath $src) {
    Copy-Item -LiteralPath $src -Destination $dst -Force
    Write-Host "COPIE REUSSIE"
    Get-Item -LiteralPath $dst | Format-List FullName, Length, LastWriteTime
} else {
    Write-Host "ERREUR: Fichier source introuvable"
}
