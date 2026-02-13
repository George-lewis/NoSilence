# build.ps1
# This script automates the process of building the SpotifyAutoResume executable.

# Stop the script if any command fails
$ErrorActionPreference = "Stop"

# Get the directory of the current script, which is assumed to be the project root.
$ProjectRoot = $PSScriptRoot

# Define important paths
$VenvPath = Join-Path $ProjectRoot ".venv"
$PyInstallerPath = Join-Path $VenvPath "Scripts\pyinstaller.exe"
$DistPath = Join-Path $ProjectRoot "dist"
$SrcPath = Join-Path $ProjectRoot "src"

# --- 1. Verify PyInstaller Exists ---
if (-not (Test-Path $PyInstallerPath)) {
    Write-Error "PyInstaller not found at '$PyInstallerPath'."
    Write-Error "Please ensure it is installed in your virtual environment by running: .\.venv\Scripts\python.exe -m pip install pyinstaller"
    exit 1
}

# --- 2. Run PyInstaller ---
Write-Host "Building executable with PyInstaller..."
$PyInstallerArgs = @(
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--name", "SpotifyAutoResume",
    "--add-data", "secrets.json;.",
    "--hidden-import=pycaw.pycaw",
    "--hidden-import=pythoncom",
    "--hidden-import=pywintypes",
    (Join-Path $SrcPath "main.py")
)

& $PyInstallerPath $PyInstallerArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed. Please review the output above."
    exit 1
}

Write-Host "Executable built successfully."

Write-Host ""
Write-Host "Build complete!"
Write-Host "The executable is available in the 'dist' folder." -ForegroundColor Green
