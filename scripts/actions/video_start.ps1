# video_start.ps1 - Devuelve al inicio (0:00) el video que se reproduce en Chrome.
#
# Pensado como accion `script` de Recognizer; no requiere dependencias externas.
# Estrategia:
#   1. Detectar la sesion de media en reproduccion de Chrome (WinRT GSMTC).
#   2. Elegir su ventana (por titulo o la mas reciente) y traerla al frente.
#   3. Pulsar la tecla `0` (no se hace clic en el video: el clic lo pausaria).
#   4. Si tras el salto el video quedo en pausa, reanudarlo con la tecla multimedia.
# Registrar el resultado en scripts/actions/video_start.log.

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logPath = Join-Path $scriptDir 'video_start.log'
$keyZeroVirtualKey = 0x30
$mediaPlayPauseVirtualKey = 0xB3
$winrtTimeoutMilliseconds = 2000
$focusWaitMilliseconds = 350
$resumeWaitMilliseconds = 500
$keyEventKeyUp = 0x0002

function Write-Log {
    param([string] $Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $logPath -Value "$timestamp $Message"
}

function Await-WinRtOperation {
    param(
        [Parameter(Mandatory = $true)] $Operation,
        [Parameter(Mandatory = $true)] [Type] $ResultType
    )
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and
        $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
    $netTask = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    [void] $netTask.Wait($winrtTimeoutMilliseconds)
    if (-not $netTask.IsCompleted) {
        throw 'La operacion WinRT no termino a tiempo.'
    }
    $netTask.Result
}

function Get-PlayingChromeVideoTitle {
    try {
        Add-Type -AssemblyName System.Runtime.WindowsRuntime -ErrorAction Stop
        $managerType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime]
        $manager = Await-WinRtOperation -Operation ($managerType::RequestAsync()) -ResultType ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
        foreach ($session in $manager.GetSessions()) {
            if ($session.SourceAppUserModelId -notmatch 'chrome') { continue }
            $playback = $session.GetPlaybackInfo()
            if ($playback.PlaybackStatus.ToString() -ne 'Playing') { continue }
            $properties = Await-WinRtOperation -Operation ($session.TryGetMediaPropertiesAsync()) -ResultType ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
            if ($properties.Title) { return $properties.Title }
        }
    }
    catch {
        Write-Log "Aviso: no se pudo leer la sesion de media ($($_.Exception.Message))."
    }
    return $null
}

function Get-ChromePlaybackStatus {
    try {
        Add-Type -AssemblyName System.Runtime.WindowsRuntime -ErrorAction Stop
        $managerType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime]
        $manager = Await-WinRtOperation -Operation ($managerType::RequestAsync()) -ResultType ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
        foreach ($session in $manager.GetSessions()) {
            if ($session.SourceAppUserModelId -notmatch 'chrome') { continue }
            return $session.GetPlaybackInfo().PlaybackStatus.ToString()
        }
    }
    catch {
        Write-Log "Aviso: no se pudo leer el estado de reproduccion ($($_.Exception.Message))."
    }
    return $null
}

if (-not ('NativeMethods' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class NativeMethods
{
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
}
'@
}

try {
    Write-Log 'Inicio de video_start.ps1.'

    $videoTitle = Get-PlayingChromeVideoTitle
    if ($videoTitle) {
        Write-Log "Video en reproduccion detectado: $videoTitle"
    }
    else {
        Write-Log 'Aviso: sin sesion de Chrome en reproduccion; se usa la ventana mas reciente.'
    }

    $chromeWindows = @(Get-Process chrome -ErrorAction SilentlyContinue | Where-Object {
            $_.MainWindowHandle -ne 0 -and
            $_.MainWindowTitle -and
            $_.MainWindowTitle.Trim().Length -gt 0
        })
    if ($chromeWindows.Count -eq 0) {
        Write-Log 'Aviso: no hay ventanas de Chrome con titulo; nada que hacer.'
        exit 0
    }

    $target = $null
    if ($videoTitle) {
        $target = $chromeWindows |
            Where-Object { $_.MainWindowTitle -like "*$videoTitle*" } |
            Select-Object -First 1
    }
    if (-not $target) {
        $target = $chromeWindows | Sort-Object -Property StartTime -Descending | Select-Object -First 1
    }
    if (-not $target) {
        Write-Log 'Aviso: no se pudo elegir una ventana de Chrome.'
        exit 0
    }
    Write-Log "Ventana elegida: [$($target.Id)] $($target.MainWindowTitle)"

    $wshShell = New-Object -ComObject WScript.Shell
    $activated = $wshShell.AppActivate($target.Id)
    if (-not $activated) {
        [void][NativeMethods]::SetForegroundWindow($target.MainWindowHandle)
    }
    Start-Sleep -Milliseconds $focusWaitMilliseconds

    if ([NativeMethods]::GetForegroundWindow() -ne $target.MainWindowHandle) {
        Write-Log 'Aviso: no se pudo poner Chrome al frente; se omite el envio de la tecla.'
        exit 0
    }

    [NativeMethods]::keybd_event([byte] $keyZeroVirtualKey, 0, 0, [UIntPtr]::Zero)
    [NativeMethods]::keybd_event([byte] $keyZeroVirtualKey, 0, $keyEventKeyUp, [UIntPtr]::Zero)
    Write-Log 'Tecla 0 enviada; el video deberia volver al inicio.'
    Start-Sleep -Milliseconds $resumeWaitMilliseconds

    if ((Get-ChromePlaybackStatus) -eq 'Paused') {
        [NativeMethods]::keybd_event([byte] $mediaPlayPauseVirtualKey, 0, 0, [UIntPtr]::Zero)
        [NativeMethods]::keybd_event([byte] $mediaPlayPauseVirtualKey, 0, $keyEventKeyUp, [UIntPtr]::Zero)
        Write-Log 'El video estaba en pausa; se reanudo la reproduccion.'
    }
    else {
        Write-Log 'El video sigue reproduciendose.'
    }
    exit 0
}
catch {
    Write-Log "Error: $($_.Exception.Message)"
    exit 1
}
