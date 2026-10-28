param(
    [Parameter(Mandatory = $true)][string]$InitialInstaller,
    [Parameter(Mandatory = $true)][string]$UpgradeInstaller,
    [Parameter(Mandatory = $true)][string]$ExpectedVersion
)
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or -not $env:RUNNER_TEMP) { throw 'Run installation acceptance only on a disposable GitHub Actions runner.' }
$testRoot = [IO.Path]::GetFullPath((Join-Path $env:RUNNER_TEMP 'vericivil-installer-acceptance'))
$runnerRoot = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'
if (-not $testRoot.StartsWith($runnerRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Test directory is outside the runner workspace.' }
$installPath = Join-Path $testRoot 'application'
$profilePath = Join-Path $env:APPDATA 'VeriCivil Superelevation'
if (Test-Path -LiteralPath $profilePath) { throw 'Refusing to change an existing VeriCivil profile.' }
New-Item -ItemType Directory -Path $testRoot, $profilePath -Force | Out-Null
$savedProject = Join-Path $testRoot 'customer.vericivil'
$recoveryPath = Join-Path $profilePath 'recovery.json'
$project = '{"version":5,"vars":{"project_name":"Installer acceptance"},"last_results":{"retained":42}}'
[IO.File]::WriteAllText($savedProject, $project)
[IO.File]::WriteAllText($recoveryPath, $project)
$application = Join-Path $installPath 'VeriCivilSuperelevation.exe'
foreach ($installer in @($InitialInstaller, $UpgradeInstaller)) {
    $resolvedInstaller = (Resolve-Path -LiteralPath $installer).Path
    $process = Start-Process -FilePath $resolvedInstaller -ArgumentList @('/S', "/D=$installPath") -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -notin @(0, 3010)) { throw "Installer failed: $($process.ExitCode)" }
    if (-not (Test-Path -LiteralPath $application)) { throw 'Installed executable is missing.' }
    if ([IO.File]::ReadAllText($savedProject) -ne $project -or [IO.File]::ReadAllText($recoveryPath) -ne $project) { throw 'An installation changed user project or recovery data.' }
}
if ((Get-Item -LiteralPath $application).VersionInfo.ProductVersion -notlike "$ExpectedVersion*") { throw 'Upgrade did not install the expected application version.' }
if (-not (Test-Path -LiteralPath (Join-Path $installPath 'resources/app.asar'))) { throw 'Installed runtime is missing.' }
node desktop/tests/installed-smoke.cjs $application
if ($LASTEXITCODE -ne 0) { throw 'Installed application runtime acceptance failed.' }
$uninstallers = @(Get-ChildItem -LiteralPath $installPath -Filter '*Uninstall*.exe')
if ($uninstallers.Count -ne 1) { throw 'Expected one native uninstaller.' }
$uninstall = Start-Process -FilePath $uninstallers[0].FullName -ArgumentList '/S' -WindowStyle Hidden -PassThru -Wait
if ($uninstall.ExitCode -notin @(0, 3010)) { throw 'Uninstaller failed.' }
for ($attempt = 0; $attempt -lt 40 -and (Test-Path -LiteralPath $application); $attempt++) { Start-Sleep -Milliseconds 250 }
if (Test-Path -LiteralPath $application) { throw 'Uninstall did not remove the application.' }
if ([IO.File]::ReadAllText($savedProject) -ne $project -or [IO.File]::ReadAllText($recoveryPath) -ne $project) { throw 'Uninstall removed user project or recovery data.' }
Write-Output 'PASS: Windows install, N-to-N+1 upgrade, and uninstall preserve saved projects and recovery data.'
