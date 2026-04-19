[CmdletBinding(DefaultParameterSetName = 'Detect')]
param(
    [Parameter(ParameterSetName = 'SessionOnly')]
    [switch]$SessionOnly,

    [Parameter(ParameterSetName = 'PersistUserPath')]
    [switch]$PersistUserPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$msysBin = 'C:\msys64\usr\bin'
$msysMake = Join-Path $msysBin 'make.exe'

function Get-MakeCommand {
    return Get-Command make -ErrorAction SilentlyContinue
}

function Get-PathEntries([string]$PathValue) {
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return @()
    }

    return $PathValue -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
}

function Test-PathEntry([string[]]$Entries, [string]$Target) {
    $normalizedTarget = $Target.TrimEnd('\')

    foreach ($entry in $Entries) {
        if ($entry.TrimEnd('\') -ieq $normalizedTarget) {
            return $true
        }
    }

    return $false
}

function Add-SessionPathEntry([string]$Target) {
    $entries = Get-PathEntries $env:Path

    if (Test-PathEntry -Entries $entries -Target $Target) {
        return $false
    }

    $env:Path = "$Target;$env:Path"
    return $true
}

function Add-UserPathEntry([string]$Target) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = Get-PathEntries $userPath

    if (Test-PathEntry -Entries $entries -Target $Target) {
        return $false
    }

    $newUserPath = if ([string]::IsNullOrWhiteSpace($userPath)) {
        $Target
    }
    else {
        "$userPath;$Target"
    }

    [Environment]::SetEnvironmentVariable('Path', $newUserPath, 'User')
    return $true
}

function Show-MakeStatus([string]$Prefix) {
    $makeCommand = Get-MakeCommand

    if (-not $makeCommand) {
        Write-Host "$Prefix make no esta disponible en PATH."
        return
    }

    Write-Host "$Prefix make disponible en PATH."

    if ($makeCommand.Source) {
        Write-Host "Ruta: $($makeCommand.Source)"
    }
    else {
        Write-Host "Comando: $($makeCommand.Name)"
    }

    & make --version | Select-Object -First 1 | ForEach-Object { Write-Host $_ }
}

function Show-ValidationHint {
    Write-Host ''
    Write-Host 'Valida con:'
    Write-Host '  make --version'
}

function Fail-Script([string[]]$Messages) {
    foreach ($message in $Messages) {
        Write-Host $message
    }

    Show-ValidationHint
    throw 'ensure-make failed'
}

$makeCommand = Get-MakeCommand
if ($makeCommand) {
    Show-MakeStatus -Prefix 'OK:'
    Show-ValidationHint
    return
}

if (-not (Test-Path -LiteralPath $msysMake -PathType Leaf)) {
    Fail-Script @(
        'No se encontro make en PATH.'
        "Tampoco existe MSYS2 make en: $msysMake"
        'Instala MSYS2 o usa una terminal MSYS2 que ya exponga make.'
    )
}

switch ($PSCmdlet.ParameterSetName) {
    'SessionOnly' {
        $changed = Add-SessionPathEntry -Target $msysBin

        if ($changed) {
            Write-Host "OK: se agrego $msysBin al PATH de la sesion actual."
        }
        else {
            Write-Host "OK: $msysBin ya estaba en el PATH de la sesion actual."
        }

        Show-MakeStatus -Prefix 'Estado final:'
        Show-ValidationHint
        return
    }

    'PersistUserPath' {
        $changed = Add-UserPathEntry -Target $msysBin
        Add-SessionPathEntry -Target $msysBin | Out-Null

        if ($changed) {
            Write-Host "OK: se agrego $msysBin al PATH de usuario."
        }
        else {
            Write-Host "OK: $msysBin ya estaba en el PATH de usuario."
        }

        Write-Host 'Nota: otras ventanas de PowerShell o Codex pueden necesitar reinicio para ver el cambio persistente.'
        Show-MakeStatus -Prefix 'Estado final:'
        Show-ValidationHint
        return
    }

    default {
        Fail-Script @(
            "MSYS2 make fue encontrado en: $msysMake"
            'Elegi uno de estos modos:'
            '  .\scripts\windows\ensure-make.ps1 -SessionOnly'
            '  .\scripts\windows\ensure-make.ps1 -PersistUserPath'
        )
    }
}
