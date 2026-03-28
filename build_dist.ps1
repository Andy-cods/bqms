# build_dist.ps1 — Tao goi phan phoi BSMQ Tool
# Chay: .\build_dist.ps1
# Ket qua: BSMQ_Tool_v6_YYYYMMDD.zip (trong thu muc cha)

$ErrorActionPreference = "Stop"

$srcDir   = $PSScriptRoot
$version  = (Get-Content "$srcDir\version.txt" -ErrorAction SilentlyContinue) -replace '\s',''
if (-not $version) { $version = "6.0.0" }
$datestamp = Get-Date -Format "yyyyMMdd"
$folderName = "BSMQ_Tool_v${version}"
$zipName    = "${folderName}_${datestamp}.zip"
$parentDir  = Split-Path $srcDir -Parent
$stagingDir = Join-Path $parentDir $folderName
$zipPath    = Join-Path $parentDir $zipName

Write-Host "================================================"
Write-Host "  BSMQ Build Distribution v$version"
Write-Host "================================================"
Write-Host "  Source : $srcDir"
Write-Host "  Output : $zipPath"
Write-Host ""

# ── Download _setup assets if missing ─────────────────────────────────────
$setupDir = Join-Path $srcDir "_setup"
$pyZip    = Join-Path $setupDir "python-3.11.9-embed-amd64.zip"
$getPip   = Join-Path $setupDir "get-pip.py"

if (-not (Test-Path $pyZip)) {
    Write-Host "[1/4] Downloading Python 3.11 embeddable..."
    Invoke-WebRequest "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" `
        -OutFile $pyZip -UseBasicParsing
    Write-Host "      OK ($([math]::Round((Get-Item $pyZip).Length/1MB,1)) MB)"
} else {
    Write-Host "[1/4] Python zip already present."
}

if (-not (Test-Path $getPip)) {
    Write-Host "      Downloading get-pip.py..."
    Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" `
        -OutFile $getPip -UseBasicParsing
    Write-Host "      OK"
}

# ── Create staging directory ──────────────────────────────────────────────
Write-Host "[2/4] Creating staging directory..."
if (Test-Path $stagingDir) { Remove-Item $stagingDir -Recurse -Force }
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

# Files/dirs to exclude from distribution
$excludeDirNames = @(
    ".git", "__pycache__", "python", "tests", "plans", "Claude-Kit",
    ".pytest_cache", "node_modules", "Lan bao gia L2", "Lan bao gia L2_v2", "Lan bao gia L2_v3"
)
$excludeFileNames = @(
    "bsmq.db", "bsmq_monitor.db", "bsmq_monitor_old.db",
    "app_v1_backup.py", "BSMQ_Dashboard_v5.html",
    "excel_state.json", ".env", "credentials.json",
    "pytest.ini", "README.md", "app.py"
)
$excludeExtensions = @(".pyc", ".pyo", ".pyd")
$stagingFolderName = Split-Path $stagingDir -Leaf

# Copy files
Get-ChildItem -Path $srcDir -Recurse | ForEach-Object {
    $rel = $_.FullName.Substring($srcDir.Length).TrimStart('\','/')

    # Skip staging dir itself
    if ($rel.StartsWith($stagingFolderName)) { return }

    # Skip excluded dirs
    $parts = $rel.Split([IO.Path]::DirectorySeparatorChar)
    foreach ($d in $excludeDirNames) {
        if ($parts -contains $d) { return }
    }

    # Skip excluded files
    if ($excludeFileNames -contains $_.Name) { return }

    # Skip excluded extensions
    if ($excludeExtensions -contains $_.Extension) { return }

    # Skip log files but keep logs/ dir
    if ($rel -match '^logs[/\\].+') { return }
    if ($rel -match '^outputs[/\\].+') { return }
    if ($rel -match '^cache[/\\].+') { return }
    if ($rel -match '^backups[/\\].+') { return }

    $dest = Join-Path $stagingDir $rel
    if ($_.PSIsContainer) {
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
    } else {
        Copy-Item $_.FullName -Destination $dest -Force
    }
}

# ── Create empty placeholder dirs ─────────────────────────────────────────
foreach ($d in @("logs", "outputs", "cache", "backups")) {
    $p = Join-Path $stagingDir $d
    New-Item -ItemType Directory -Path $p -Force | Out-Null
    "" | Out-File -FilePath (Join-Path $p ".gitkeep") -Encoding utf8
}

Write-Host "      OK (staged $(([array](Get-ChildItem $stagingDir -Recurse -File)).Count) files)"

# ── Compress ──────────────────────────────────────────────────────────────
Write-Host "[3/4] Compressing to ZIP..."
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path $stagingDir -DestinationPath $zipPath -CompressionLevel Optimal
$sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "      OK"

# ── Cleanup staging ───────────────────────────────────────────────────────
Write-Host "[4/4] Cleaning up staging directory..."
Remove-Item $stagingDir -Recurse -Force
Write-Host "      OK"

Write-Host ""
Write-Host "================================================"
Write-Host "  BUILD COMPLETE"
Write-Host "  File : $zipName"
Write-Host "  Size : $sizeMB MB"
Write-Host "================================================"
Write-Host ""
Write-Host "Gui file nay cho nguoi dung:"
Write-Host "  1. Giai nen → double-click install.bat"
Write-Host "  2. Sau khi cai xong → double-click run.bat"
