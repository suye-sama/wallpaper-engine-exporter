param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$BuildDir = Join-Path $Root "build"
$DistDir = Join-Path $Root "dist"
$EntryPoint = Join-Path $Root "wallpaper_exporter\pyinstaller_entry.py"
$RePKG = Join-Path $Root "tools\RePKG\RePKG.exe"

function Remove-WorkspacePath {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $ResolvedRoot = (Resolve-Path -LiteralPath $Root).Path
    $ResolvedPath = (Resolve-Path -LiteralPath $Path).Path
    if (-not $ResolvedPath.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside workspace: $ResolvedPath"
    }

    Remove-Item -LiteralPath $ResolvedPath -Recurse -Force
}

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Creating virtual environment..."
    python -m venv (Join-Path $Root ".venv")
}

if (-not (Test-Path -LiteralPath $RePKG)) {
    throw "RePKG.exe not found: $RePKG"
}

Write-Host "Installing build dependencies..."
& $Python -m pip install -r (Join-Path $Root "requirements.txt") -r (Join-Path $Root "requirements-build.txt")
if ($LASTEXITCODE -ne 0) {
    throw "pip install failed"
}

Remove-WorkspacePath $BuildDir
Remove-WorkspacePath $DistDir

$ModeArgs = @("--onedir")
if ($OneFile) {
    $ModeArgs = @("--onefile")
}

$PyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name",
    "WallpaperExporter",
    "--distpath",
    $DistDir,
    "--workpath",
    $BuildDir,
    "--specpath",
    $BuildDir
) + $ModeArgs + @(
    "--add-data",
    "$RePKG;tools\RePKG",
    $EntryPoint
)

Write-Host "Running PyInstaller..."
& $Python -m PyInstaller @PyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed"
}

if ($OneFile) {
    $Exe = Join-Path $DistDir "WallpaperExporter.exe"
} else {
    $Exe = Join-Path $DistDir "WallpaperExporter\WallpaperExporter.exe"
}

Write-Host "Built: $Exe"
