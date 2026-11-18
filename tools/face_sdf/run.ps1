param(
    [string]$Blender = $(if ($env:BLENDER_EXE) { $env:BLENDER_EXE } else { "blender" }),
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$taskRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
& $Python "$taskRoot\run_pipeline.py" --blender $Blender
exit $LASTEXITCODE
