$PythonPaths = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    (Get-Command python, py, python3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
)

$PythonExe = $PythonPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($PythonExe) {
    Write-Host "Python tespit edildi: $PythonExe" -ForegroundColor Green
    Write-Host "Lisans Takip Uygulaması Başlatılıyor (http://localhost:$Port)..." -ForegroundColor Cyan
    & $PythonExe app.py
} else {
    Write-Host "Python bulunamadı." -ForegroundColor Red
}
