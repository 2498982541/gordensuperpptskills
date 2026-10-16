#Requires -Version 5.1
<#
.SYNOPSIS
Render every slide of a .pptx to PNG through Microsoft PowerPoint.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File render_pptx.ps1 -InputPptx page.pptx -OutputDir qa\render

.NOTES
Opens the file read-only without a window. Renders are serialized with a
mutex so parallel workers can share one PowerPoint. PowerPoint is only quit
if nothing else (user documents or windows) is open in it.
#>
param(
    [Parameter(Mandatory = $true)][string]$InputPptx,
    [Parameter(Mandatory = $true)][string]$OutputDir,
    [int]$Width = 1920,
    [int]$TimeoutMinutes = 15
)
$ErrorActionPreference = 'Stop'

$inputPath = (Resolve-Path -LiteralPath $InputPptx).Path
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$outputPath = (Resolve-Path -LiteralPath $OutputDir).Path

$mutex = New-Object System.Threading.Mutex($false, 'Local\PptSkillsPowerPointRender')
$held = $false
try { $held = $mutex.WaitOne([TimeSpan]::FromMinutes($TimeoutMinutes)) }
catch [System.Threading.AbandonedMutexException] { $held = $true }
if (-not $held) { throw "Timed out waiting for another PowerPoint render to finish." }

$app = $null
$pres = $null
try {
    $app = New-Object -ComObject PowerPoint.Application
    # ReadOnly = msoTrue, Untitled = msoFalse, WithWindow = msoFalse
    $pres = $app.Presentations.Open($inputPath, -1, 0, 0)
    $height = [int][Math]::Round($Width * $pres.PageSetup.SlideHeight / $pres.PageSetup.SlideWidth)
    $count = $pres.Slides.Count
    for ($i = 1; $i -le $count; $i++) {
        $file = Join-Path $outputPath ('slide_{0:D2}.png' -f $i)
        $pres.Slides.Item($i).Export($file, 'PNG', $Width, $height)
    }
    Write-Output "Rendered $count slide(s) to $outputPath"
}
finally {
    if ($null -ne $pres) {
        $pres.Close()
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($pres)
    }
    if ($null -ne $app) {
        try {
            if ($app.Presentations.Count -eq 0 -and $app.Windows.Count -eq 0 -and $app.Visible -eq 0) { $app.Quit() }
        } catch { }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
