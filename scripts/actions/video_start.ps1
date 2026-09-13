# video_start.ps1 - Devuelve al inicio (0:00) el video que se reproduce en Chrome.
#
# Pensado como accion `script` de Recognizer; no requiere dependencias externas.
# Estrategia:
#   1. Detectar la sesion de media en reproduccion de Chrome (WinRT GSMTC).
#   2. Elegir su ventana (por titulo o la mas reciente).
#   3. Traerla al frente y hacer clic en el centro del video para darle foco.
#   4. Pulsar la tecla `0`.
# Registrar el resultado en scripts/actions/video_start.log.

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logPath = Join-Path $scriptDir 'video_start.log'
$keyZeroVirtualKey = 0x30
$winrtTimeoutMilliseconds = 2000
$focusWaitMilliseconds = 350
$clickWaitMilliseconds = 250
$mouseLeftDown = 0x0002
$mouseLeftUp = 0x0004
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
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);

    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);

    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
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

    $rect = [NativeMethods+RECT]::new()
    if ([NativeMethods]::GetWindowRect($target.MainWindowHandle, [ref] $rect)) {
        $centerX = [int](($rect.Left + $rect.Right) / 2)
        $centerY = [int](($rect.Top + $rect.Bottom) / 2)
        [void][NativeMethods]::SetCursorPos($centerX, $centerY)
        [NativeMethods]::mouse_event($mouseLeftDown, 0, 0, 0, [UIntPtr]::Zero)
        [NativeMethods]::mouse_event($mouseLeftUp, 0, 0, 0, [UIntPtr]::Zero)
        Write-Log "Clic de foco en ($centerX, $centerY)."
    }
    else {
        Write-Log 'Aviso: GetWindowRect fallo; se omite el clic de foco.'
    }
    Start-Sleep -Milliseconds $clickWaitMilliseconds

    [NativeMethods]::keybd_event([byte] $keyZeroVirtualKey, 0, 0, [UIntPtr]::Zero)
    [NativeMethods]::keybd_event([byte] $keyZeroVirtualKey, 0, $keyEventKeyUp, [UIntPtr]::Zero)
    Write-Log 'Tecla 0 enviada; el video deberia volver al inicio.'
    exit 0
}
catch {
    Write-Log "Error: $($_.Exception.Message)"
    exit 1
}
