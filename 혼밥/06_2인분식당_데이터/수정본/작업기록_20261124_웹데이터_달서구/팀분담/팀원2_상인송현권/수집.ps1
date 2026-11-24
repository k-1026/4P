# 혼밥 달서구 지도 수집 (팀원용). 이 폴더의 prompt_NNN.txt 를 Aside로 하나씩 돌려 out_NNN.csv 로 저장한다.
# 쓰는 법: 이 폴더에서 PowerShell을 열고  powershell -ExecutionPolicy Bypass -File .\수집.ps1
#          동시 개수 바꾸기:  ... -File .\수집.ps1 -Par 2
# 끊겨도 다시 실행하면 이미 끝난 묶음(out 파일에 "수집ID" 머리줄이 있음)은 건너뛴다.
param([int]$Par = 3, [string]$Aside = "")

Set-Location -LiteralPath $PSScriptRoot
if (-not $Aside) {
    $cmd = Get-Command aside -ErrorAction SilentlyContinue
    if ($cmd) { $Aside = $cmd.Source }
    elseif (Test-Path "$env:LOCALAPPDATA\Aside\CLI\current\aside.exe") { $Aside = "$env:LOCALAPPDATA\Aside\CLI\current\aside.exe" }
}
if (-not $Aside -or -not (Test-Path $Aside)) {
    Write-Host "aside 명령을 찾지 못했습니다. Aside 앱을 설치하고 로그인한 뒤 다시 실행하세요." -ForegroundColor Red
    exit 1
}

function Test-Done([string]$out) {
    (Test-Path -LiteralPath $out) -and (Select-String -LiteralPath $out -Pattern '"수집ID"' -SimpleMatch -Quiet)
}

$todo = @()
foreach ($p in (Get-ChildItem -LiteralPath $PSScriptRoot -Filter 'prompt_*.txt' | Sort-Object Name)) {
    $i = $p.BaseName.Substring(7)
    if (Test-Done (Join-Path $PSScriptRoot "out_$i.csv")) { Write-Host "건너뜀 $i" } else { $todo += $p }
}
Write-Host "남은 묶음 $($todo.Count)개, 동시 $Par개 ($(Get-Date -Format 'HH:mm') 시작)"

$runOne = {
    param($aside, $promptFile, $outFile, $errFile)
    $text = [IO.File]::ReadAllText($promptFile, [Text.Encoding]::UTF8)
    # Windows 명령줄 규칙대로 따옴표·역슬래시를 이스케이프해서 지시문 하나를 인자 하나로 넘긴다
    $esc = [regex]::Replace($text, '(\\*)"', { param($m) ($m.Groups[1].Value * 2) + '\"' })
    $esc = [regex]::Replace($esc, '(\\+)$', '$1$1')
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $aside
    $psi.Arguments = 'exec --effort medium "' + $esc + '"'
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [Text.Encoding]::UTF8
    $proc = [System.Diagnostics.Process]::Start($psi)
    $errTask = $proc.StandardError.ReadToEndAsync()
    $out = $proc.StandardOutput.ReadToEnd()
    $proc.WaitForExit()
    [IO.File]::WriteAllText($outFile, $out, (New-Object Text.UTF8Encoding($false)))
    [IO.File]::WriteAllText($errFile, $errTask.Result, (New-Object Text.UTF8Encoding($false)))
    $proc.ExitCode
}

$jobs = @()
foreach ($p in $todo) {
    while (@($jobs | Where-Object { $_.State -eq 'Running' }).Count -ge $Par) { Start-Sleep -Seconds 15 }
    $i = $p.BaseName.Substring(7)
    $jobs += Start-Job -Name "묶음$i" -ScriptBlock $runOne -ArgumentList $Aside, $p.FullName, (Join-Path $PSScriptRoot "out_$i.csv"), (Join-Path $PSScriptRoot "err_$i.txt")
    Write-Host "시작 $i  $(Get-Date -Format 'HH:mm')"
}
$jobs | Wait-Job | Out-Null
$bad = @()
foreach ($p in $todo) { $i = $p.BaseName.Substring(7); if (-not (Test-Done (Join-Path $PSScriptRoot "out_$i.csv"))) { $bad += $i } }
if ($bad.Count) { Write-Host "결과가 없는 묶음: $($bad -join ', ')  → 수집.ps1 을 한 번 더 실행하세요." -ForegroundColor Yellow }
else { Write-Host "모두 끝 ($(Get-Date -Format 'HH:mm')). 이제 마무리.ps1 을 실행하세요." -ForegroundColor Green }
