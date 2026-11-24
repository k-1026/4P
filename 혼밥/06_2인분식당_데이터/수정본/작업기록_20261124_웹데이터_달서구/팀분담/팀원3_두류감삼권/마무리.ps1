# 혼밥 달서구 지도 수집 마무리 (팀원용). out_NNN.csv 를 합쳐 결과 CSV 1개와 결과 MD 1개를 만든다.
# 쓰는 법: 이 폴더에서  powershell -ExecutionPolicy Bypass -File .\마무리.ps1
# 만들어지는 파일: 결과_<폴더이름>.csv (엑셀로 열림), 결과_<폴더이름>.md  → 이 두 파일을 보내 주세요.
Set-Location -LiteralPath $PSScriptRoot
$name = Split-Path -Leaf $PSScriptRoot
$target = Import-Csv -LiteralPath (Join-Path $PSScriptRoot '대상목록.csv') -Encoding UTF8
$targetIds = @{}; foreach ($t in $target) { $targetIds[$t.'수집ID'] = $t }

$rows = @(); $batchOk = @(); $batchBad = @()
foreach ($f in (Get-ChildItem -LiteralPath $PSScriptRoot -Filter 'prompt_*.txt' | Sort-Object Name)) {
    $i = $f.BaseName.Substring(7)
    $out = Join-Path $PSScriptRoot "out_$i.csv"
    if (-not (Test-Path -LiteralPath $out)) { $batchBad += $i; continue }
    $txt = [IO.File]::ReadAllText($out, [Text.Encoding]::UTF8)
    $s = $txt.IndexOf('"수집ID"')
    if ($s -lt 0) { $batchBad += $i; continue }
    $body = $txt.Substring($s)
    $e = $body.IndexOf('```'); if ($e -ge 0) { $body = $body.Substring(0, $e) }
    $parsed = @($body | ConvertFrom-Csv)
    foreach ($r in $parsed) {
        if (-not $r.'수집ID') { continue }
        $r | Add-Member -NotePropertyName '묶음' -NotePropertyValue $i -Force
        $r | Add-Member -NotePropertyName '몫' -NotePropertyValue $name -Force
        $rows += $r
    }
    $batchOk += $i
}

$csvPath = Join-Path $PSScriptRoot "결과_$name.csv"
$rows | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8

$got = @{}; foreach ($r in $rows) { if ($targetIds.ContainsKey($r.'수집ID')) { $got[$r.'수집ID'] = $true } }
$extra = @($rows | Where-Object { -not $targetIds.ContainsKey($_.'수집ID') } | ForEach-Object { $_.'수집ID' } | Sort-Object -Unique)
$missing = @($target | Where-Object { -not $got.ContainsKey($_.'수집ID') })
$foundCol = ($rows | Select-Object -First 1).PSObject.Properties.Name | Where-Object { $_ -like '찾음*' } | Select-Object -First 1
$notFound = @()
if ($foundCol) {
    $byId = $rows | Group-Object '수집ID'
    foreach ($g in $byId) { if (-not ($g.Group | Where-Object { $_.$foundCol -eq '예' })) { $notFound += $g.Name } }
}

$md = @()
$md += "# 달서구 지도 수집 결과 — $name"
$md += ""
$md += "- 만든 때: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$md += "- 결과 파일: 결과_$name.csv (근거마다 한 줄, 같은 가게는 수집ID가 같음)"
$md += ""
$md += "## 포함한 것"
$md += ""
$md += "| 항목 | 값 |"
$md += "|---|---|"
$md += "| 맡은 가게 (대상목록.csv) | $($target.Count)곳 |"
$md += "| 행정동 | $((($target | ForEach-Object { $_.'행정동' }) | Sort-Object -Unique) -join ', ') |"
$md += "| 묶음 | 전체 $(@(Get-ChildItem -LiteralPath $PSScriptRoot -Filter 'prompt_*.txt').Count)개 / 결과 있음 $($batchOk.Count)개 |"
$md += "| 수집 방법 | Aside로 네이버 지도·카카오맵 메뉴·메뉴판 사진·사장님 답글·방문자 리뷰 (지시문 prompt_NNN.txt 그대로) |"
$md += ""
$md += "## 결과"
$md += ""
$md += "| 항목 | 값 |"
$md += "|---|---|"
$md += "| 결과가 있는 가게 | $($got.Count)곳 |"
$md += "| 결과 줄 수 | $($rows.Count)줄 |"
$md += "| 지도에서 못 찾은 가게 | $($notFound.Count)곳 |"
$md += "| 결과가 빠진 가게 | $($missing.Count)곳 |"
$md += "| 결과가 없는 묶음 | $(if ($batchBad.Count) { $batchBad -join ', ' } else { '없음' }) |"
$md += "| 대상목록에 없는 수집ID | $(if ($extra.Count) { $extra -join ', ' } else { '없음' }) |"
if ($missing.Count) {
    $md += ""
    $md += "### 결과가 빠진 가게"
    $md += ""
    $md += "| 수집ID | 상호 | 행정동 |"
    $md += "|---|---|---|"
    foreach ($m in $missing) { $md += "| $($m.'수집ID') | $($m.'상호') | $($m.'행정동') |" }
}
$md += ""
$md += "## 메모 (수집하면서 있었던 일을 자유롭게 적어 주세요)"
$md += ""
$md += "- "
[IO.File]::WriteAllLines((Join-Path $PSScriptRoot "결과_$name.md"), $md, (New-Object Text.UTF8Encoding($true)))

Write-Host "결과_$name.csv ($($rows.Count)줄, 가게 $($got.Count)/$($target.Count)곳)"
Write-Host "결과_$name.md"
if ($batchBad.Count) { Write-Host "결과가 없는 묶음이 있습니다: $($batchBad -join ', '). 수집.ps1 을 다시 실행한 뒤 마무리.ps1 을 다시 돌리세요." -ForegroundColor Yellow }
