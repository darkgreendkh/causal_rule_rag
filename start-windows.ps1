param(
    [ValidateSet('all', 'neo4j', 'backend', 'frontend')]
    [string]$Service = 'all'
)

$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot '.runtime'
$env:UV_CACHE_DIR = 'D:/uv/cache'
$env:UV_PYTHON_INSTALL_DIR = 'D:/uv/python'
$env:HF_HOME = Join-Path $runtime 'huggingface'
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
$env:TEMP = Join-Path $runtime 'temp'
$env:TMP = $env:TEMP
$env:PYTHONUTF8 = '1'
$env:JAVA_HOME = 'D:/backend/Java/jdk-21'
$env:NEO4J_HOME = 'D:/backend/neo4j-community-5.26.8'
$env:NEO4J_CONF = Join-Path $runtime 'neo4j/conf'

if ($Service -eq 'all') {
    $ports = @{ neo4j = 7687; backend = 8000; frontend = 5173 }
    foreach ($name in @('neo4j', 'backend', 'frontend')) {
        if (Get-NetTCPConnection -State Listen -LocalPort $ports[$name] -ErrorAction SilentlyContinue) {
            Write-Host "$name port $($ports[$name]) is already listening; skipped."
            continue
        }
        $process = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-Service', $name
        ) -RedirectStandardOutput "$runtime/logs/$name.out.log" -RedirectStandardError "$runtime/logs/$name.err.log"
        $process.Id | Set-Content "$runtime/$name.pid"
        $deadline = (Get-Date).AddSeconds(90)
        while (!(Get-NetTCPConnection -State Listen -LocalPort $ports[$name] -ErrorAction SilentlyContinue)) {
            if ($process.HasExited -or (Get-Date) -gt $deadline) {
                throw "$name did not start. Check $runtime/logs/$name.err.log"
            }
            Start-Sleep -Seconds 1
        }
        Write-Host "$name started on port $($ports[$name])."
    }
    Invoke-RestMethod 'http://localhost:8000/api/health'
    Write-Host 'Open http://localhost:5173'
    return
}

switch ($Service) {
    'neo4j' {
        & "$env:NEO4J_HOME/bin/neo4j.bat" console
    }
    'backend' {
        Set-Location "$PSScriptRoot/backend"
        & ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    }
    'frontend' {
        Set-Location "$PSScriptRoot/frontend"
        & 'D:/tools/nodejs/node.exe' node_modules/vite/bin/vite.js --host localhost --strictPort
    }
}
exit $LASTEXITCODE
