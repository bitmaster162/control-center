param(
    [string]$Source = (Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR28\app'),
    [string]$Destination = (Join-Path (Split-Path -Parent $PSScriptRoot) 'hanri_runtime\r28'),
    [string]$ManifestPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'hanri_runtime\R28_SOURCE_MANIFEST.sha256.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-RelativePath([string]$Base, [string]$Path) {
    $baseFull = [IO.Path]::GetFullPath($Base).TrimEnd('\') + '\'
    $pathFull = [IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($baseFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside source root: $Path"
    }
    return $pathFull.Substring($baseFull.Length)
}

$sourceFull = [IO.Path]::GetFullPath($Source)
$destFull = [IO.Path]::GetFullPath($Destination)
$manifestFull = [IO.Path]::GetFullPath($ManifestPath)

if (-not (Test-Path -LiteralPath $sourceFull -PathType Container)) {
    throw "HANRI R28 app source not found: $sourceFull"
}

if (Test-Path -LiteralPath $destFull) {
    $existing = @(Get-ChildItem -LiteralPath $destFull -Force -ErrorAction Stop)
    if ($existing.Count -gt 0) {
        throw "Destination is not empty. Refusing to overwrite forensic staging: $destFull"
    }
} else {
    New-Item -ItemType Directory -Path $destFull -Force | Out-Null
}

$excludedDirNames = @(
    '.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    'state', 'decision_inbox', 'logs', 'log', 'cache', '.cache', 'tmp', 'temp'
)

$excludedFileNames = @('.env', '.env.local', '.env.production')
$excludedExtensions = @('.key', '.pem', '.pfx', '.p12', '.sqlite', '.sqlite3', '.db', '.log', '.tmp')

$files = Get-ChildItem -LiteralPath $sourceFull -Recurse -File -Force | Sort-Object FullName
$copied = New-Object System.Collections.Generic.List[object]
$excluded = New-Object System.Collections.Generic.List[object]

foreach ($file in $files) {
    $rel = Get-RelativePath $sourceFull $file.FullName
    $parts = $rel -split '[\\/]'
    $dirBlocked = $false
    foreach ($part in $parts[0..([Math]::Max(0, $parts.Count - 2))]) {
        if ($excludedDirNames -contains $part) { $dirBlocked = $true; break }
    }

    $nameBlocked = $excludedFileNames -contains $file.Name
    $extBlocked = $excludedExtensions -contains $file.Extension.ToLowerInvariant()
    $sensitiveName = $file.Name -match '(?i)(credential|secret|private[_-]?key|id_rsa|wallet|keystore)'

    if ($dirBlocked -or $nameBlocked -or $extBlocked -or $sensitiveName) {
        $excluded.Add([ordered]@{ path = $rel; reason = 'policy_exclusion' })
        continue
    }

    $target = Join-Path $destFull $rel
    $targetDir = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    $copied.Add([ordered]@{
        path = $rel.Replace('\','/')
        size = (Get-Item -LiteralPath $target).Length
        sha256 = $hash
    })
}

# Verify copied bytes a second time after the copy phase.
foreach ($entry in $copied) {
    $target = Join-Path $destFull ($entry.path -replace '/', '\')
    $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $entry.sha256) {
        throw "Post-copy SHA mismatch: $($entry.path)"
    }
}

$runtimeConfig = Join-Path $sourceFull 'config\r28.windows.json'
$configSha = $null
if (Test-Path -LiteralPath $runtimeConfig -PathType Leaf) {
    $configSha = (Get-FileHash -LiteralPath $runtimeConfig -Algorithm SHA256).Hash.ToLowerInvariant()
}

$manifest = [ordered]@{
    schema = 'hanri.r28.forensic_source_manifest.v1'
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    source = $sourceFull
    destination = $destFull
    expected_program_version = '28.0.0'
    observed_runtime_config_sha256_reference = '0e0652621528597770d57a848e46f9ad7ae32123db70fbd496bf38a6b70cdabb'
    copied_runtime_config_sha256 = $configSha
    file_count = $copied.Count
    files = $copied
    excluded_count = $excluded.Count
    excluded = $excluded
    can_trade = $false
    self_application = $false
    note = 'Read-only forensic export. Review for secrets before git add/commit. No runtime mutation performed.'
}

$manifestDir = Split-Path -Parent $manifestFull
if (-not (Test-Path -LiteralPath $manifestDir)) {
    New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestFull -Encoding UTF8

if ($configSha -and $configSha -ne $manifest.observed_runtime_config_sha256_reference) {
    throw "R28 config SHA differs from observed runtime reference. Export created, but baseline binding is NOT verified. Expected $($manifest.observed_runtime_config_sha256_reference), got $configSha"
}

Write-Host "HANRI R28 forensic export complete."
Write-Host "Source:      $sourceFull"
Write-Host "Destination: $destFull"
Write-Host "Manifest:    $manifestFull"
Write-Host "Files:       $($copied.Count)"
Write-Host "Excluded:    $($excluded.Count)"
Write-Host 'NEXT GATE: review staged files for secrets; do not edit source before the first baseline commit.'
