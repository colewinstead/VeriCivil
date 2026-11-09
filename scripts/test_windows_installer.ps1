param(
    [Parameter(Mandatory = $true)][string]$InitialInstaller,
    [Parameter(Mandatory = $true)][string]$UpgradeInstaller,
    [Parameter(Mandatory = $true)][string]$ExpectedVersion,
    [ValidateSet('vericivil', 'neutral')][string]$Edition = 'vericivil',
    [string]$CompanionInstaller
)
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or -not $env:RUNNER_TEMP) { throw 'Run installation acceptance only on a disposable GitHub Actions runner.' }
$editions = Get-Content desktop/editions.json -Raw | ConvertFrom-Json
$branding = $editions.$Edition
$testRoot = [IO.Path]::GetFullPath((Join-Path $env:RUNNER_TEMP "$Edition-installer-acceptance"))
$runnerRoot = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'
if (-not $testRoot.StartsWith($runnerRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Test directory is outside the runner workspace.' }
$installPath = Join-Path $testRoot 'application'
$profilePath = Join-Path $env:APPDATA $branding.profileDirectory
if (Test-Path -LiteralPath $profilePath) { throw 'Refusing to change an existing profile for the selected edition.' }
New-Item -ItemType Directory -Path $testRoot, $profilePath -Force | Out-Null
$savedProject = Join-Path $testRoot 'customer.vericivil'
$recoveryPath = Join-Path $profilePath 'recovery.json'
$project = '{"version":5,"vars":{"project_name":"Installer acceptance"},"last_results":{"retained":42}}'
[IO.File]::WriteAllText($savedProject, $project)
[IO.File]::WriteAllText($recoveryPath, $project)
$application = Join-Path $installPath "$($branding.executableName).exe"
$companionApplication = $null
$companionRecovery = $null
if ($CompanionInstaller) {
    $companionPath = Join-Path $testRoot 'companion'
    $companion = Start-Process -FilePath (Resolve-Path $CompanionInstaller).Path -ArgumentList @('/S', "/D=$companionPath") -WindowStyle Hidden -PassThru -Wait
    if ($companion.ExitCode -notin @(0, 3010)) { throw 'Companion installation failed.' }
    $companionApplication = Join-Path $companionPath "$($editions.vericivil.executableName).exe"
    $companionRecovery = Join-Path (Join-Path $env:APPDATA $editions.vericivil.profileDirectory) 'recovery.json'
    $companionContents = [IO.File]::ReadAllText($companionRecovery)
}
function Get-ProjectAssociation {
    @('HKCU:\Software\Classes\.vericivil', 'HKLM:\Software\Classes\.vericivil') | ForEach-Object {
        $key = Get-Item -LiteralPath $_ -ErrorAction SilentlyContinue
        if ($key) { $key.GetValue('') } else { '<absent>' }
    } | ConvertTo-Json -Compress
}
$originalAssociation = Get-ProjectAssociation
foreach ($installer in @($InitialInstaller, $UpgradeInstaller)) {
    $resolvedInstaller = (Resolve-Path -LiteralPath $installer).Path
    $installerArgs = if ($installer -eq $InitialInstaller) { @('/S', "/D=$installPath") } else { @('/S', '--updated', '--force-run') }
    $process = Start-Process -FilePath $resolvedInstaller -ArgumentList $installerArgs -WindowStyle Hidden -PassThru
    # Wait only for the installer; -Wait also waits for the relaunched app to exit.
    if (-not $process.WaitForExit(120000)) { throw 'Installer timed out.' }
    if ($process.ExitCode -notin @(0, 3010)) { throw "Installer failed: $($process.ExitCode)" }
    if (-not (Test-Path -LiteralPath $application)) { throw 'Installed executable is missing.' }
    if ([IO.File]::ReadAllText($savedProject) -ne $project -or [IO.File]::ReadAllText($recoveryPath) -ne $project) { throw 'An installation changed user project or recovery data.' }
    if ($Edition -eq 'neutral' -and (Get-ProjectAssociation) -ne $originalAssociation) { throw 'Neutral installer changed the existing project association.' }
}
if ((Get-Item -LiteralPath $application).VersionInfo.ProductVersion -notlike "$ExpectedVersion*") { throw 'Upgrade did not install the expected application version.' }
if (-not (Test-Path -LiteralPath (Join-Path $installPath 'resources/app.asar'))) { throw 'Installed runtime is missing.' }
$restarted = @()
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    $restarted = @(Get-Process -Name $branding.executableName -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $application })
    if ($restarted.Count) { break }
    Start-Sleep -Milliseconds 250
}
if (-not $restarted.Count) { throw 'Upgrade did not restart the app from its existing installation.' }
$restarted | Stop-Process -Force -ErrorAction SilentlyContinue
$env:DESKTOP_EDITION = $Edition
node desktop/tests/installed-smoke.cjs $application $companionApplication
if ($LASTEXITCODE -ne 0) { throw 'Installed application runtime acceptance failed.' }
$uninstallers = @(Get-ChildItem -LiteralPath $installPath -Filter '*Uninstall*.exe')
if ($uninstallers.Count -ne 1) { throw 'Expected one native uninstaller.' }
$uninstall = Start-Process -FilePath $uninstallers[0].FullName -ArgumentList '/S' -WindowStyle Hidden -PassThru -Wait
if ($uninstall.ExitCode -notin @(0, 3010)) { throw 'Uninstaller failed.' }
for ($attempt = 0; $attempt -lt 40 -and (Test-Path -LiteralPath $application); $attempt++) { Start-Sleep -Milliseconds 250 }
if (Test-Path -LiteralPath $application) { throw 'Uninstall did not remove the application.' }
if ([IO.File]::ReadAllText($savedProject) -ne $project -or [IO.File]::ReadAllText($recoveryPath) -ne $project) { throw 'Uninstall removed user project or recovery data.' }
if ($Edition -eq 'neutral' -and (Get-ProjectAssociation) -ne $originalAssociation) { throw 'Neutral uninstall changed the existing project association.' }
if ($companionApplication) {
    if (-not (Test-Path $companionApplication) -or [IO.File]::ReadAllText($companionRecovery) -ne $companionContents) { throw 'Neutral lifecycle changed the companion installation or project data.' }
    $companionUninstaller = @(Get-ChildItem -LiteralPath (Split-Path $companionApplication) -Filter '*Uninstall*.exe')
    if ($companionUninstaller.Count -ne 1) { throw 'Expected one companion uninstaller.' }
    $removed = Start-Process $companionUninstaller[0].FullName -ArgumentList '/S' -WindowStyle Hidden -PassThru -Wait
    if ($removed.ExitCode -notin @(0, 3010)) { throw 'Companion uninstall failed.' }
}
Write-Output 'PASS: Windows upgrade reuses its installation and restarts the app; install, upgrade, and uninstall preserve saved projects and recovery data.'
