# 端到端双基线（加空壳基线）全链路自检脚本（tests/smoke.ps1）
# 验证范围：
#   1. 仓库全量 Python 语法字节码校验（py_compile）
#   2. 计分插值、WCAG 对比度、A 得分率封顶、评审日志防重与隔离脱敏单元测试
#   3. 基线零（EmptyStub）：未实现模板防崩溃、连环画平稳兜底抓拍与客观 0 分验证
#   4. 基线一（NaiveModel 简陋基线）：仅实现最低主干、通过公开冒烟，在三波浏览器物理测量中准确暴露短板
#   5. 基线二（GoldenModel-s1 黄金参考基线）：痛点体贴交互 + 靶向补测 judge_probe + 多评委防重 + 三波浏览器高分出榜

param(
    [switch]$KeepTmp
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== [1/7] 全量 Python 字节码语法校验 ==" -ForegroundColor Cyan
python -c "
import pathlib, py_compile
root = pathlib.Path('.')
files = [p for d in ('src', 'tools', 'leaderboard', 'tests') for p in (root / d).rglob('*.py')]
for f in sorted(files):
    py_compile.compile(str(f), doraise=True)
print(f'编译通过：{len(files)} 个 Python 文件')
"
if ($LASTEXITCODE -ne 0) { throw "Python 语法检查失败" }

Write-Host "== [2/7] 执行计分、WCAG 对比度与时间/隔离审计单元测试 ==" -ForegroundColor Cyan
python tests/scoring_units.py
if ($LASTEXITCODE -ne 0) { throw "scoring_units.py 失败" }
python tests/timing_audit_units.py
if ($LASTEXITCODE -ne 0) { throw "timing_audit_units.py 失败" }

$TmpDir = Join-Path $PSScriptRoot "_tmp"
if (Test-Path $TmpDir) { Remove-Item -Recurse -Force $TmpDir }
New-Item -ItemType Directory -Path $TmpDir | Out-Null

$RunsDir      = Join-Path $TmpDir "runs"
$BlindDir     = Join-Path $TmpDir "blind"
$BlindMapsDir = Join-Path $TmpDir "blind-maps"
$VerdictsDir  = Join-Path $TmpDir "verdicts"
$DraftDir     = Join-Path $TmpDir "draft"
$ReviewLog    = Join-Path $TmpDir "reviews.jsonl"
$RunsLog      = Join-Path $TmpDir "runs_log.jsonl"
$ScoresMd     = Join-Path $TmpDir "scores.md"

try {
    Write-Host "== [3/7] 基线零：未实现空壳沙盒（EmptyStub）防崩溃与零分验证 ==" -ForegroundColor Cyan
    $t0Stub = (Get-Date).AddMinutes(-6).ToString("yyyy-MM-ddTHH:mm:sszzz")
    python tools/start_run.py --model EmptyStub --t0 $t0Stub --runs-dir $RunsDir --runs-log $RunsLog
    if ($LASTEXITCODE -ne 0) { throw "EmptyStub start_run 失败" }

    $ErrorActionPreference = "Continue"
    python "$RunsDir/EmptyStub/workspace/smoke_public.py" > $null 2>&1
    $stubSmokeCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($stubSmokeCode -eq 0) { throw "空壳沙盒 smoke_public.py 不应返回退出码 0" }

    python src/scoring/judge_pack.py --model EmptyStub --runs-dir $RunsDir --blind-dir $BlindDir --blind-maps-dir $BlindMapsDir --runs-log $RunsLog
    if ($LASTEXITCODE -ne 0) { throw "EmptyStub judge_pack 失败" }

    $stubMapFile = Get-ChildItem "$BlindMapsDir/emptystub.*.blind-map.json" | Select-Object -First 1
    $stubMap = Get-Content $stubMapFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $stubPackDir = Join-Path $BlindDir $stubMap.pack_id

    python src/scoring/judge_submit.py `
        --pack-dir $stubPackDir --case-id case-01 `
        --judge-id judge-alpha --judge-model claude-opus `
        --D1 0.0 --D2 0.0 --D3 0.5 `
        --evidence "[S01-S12] 仍保留初始未实现占位页，DECISIONS.md 未填写" `
        --note "未进行任何前端开发，按红线封顶" `
        --review-log $ReviewLog
    if ($LASTEXITCODE -ne 0) { throw "EmptyStub judge_submit 失败" }

    Write-Host "== [4/7] 基线一：仅实现最低主干功能的简陋基线（NaiveModel） ==" -ForegroundColor Cyan
    $t0Naive = (Get-Date).AddMinutes(-9).ToString("yyyy-MM-ddTHH:mm:sszzz")
    python tools/start_run.py --model NaiveModel --t0 $t0Naive --runs-dir $RunsDir --runs-log $RunsLog
    if ($LASTEXITCODE -ne 0) { throw "NaiveModel start_run 失败" }

    Copy-Item -Path "src/baselines/naive_baseline/*" -Destination "$RunsDir/NaiveModel/workspace/" -Recurse -Force
    python "$RunsDir/NaiveModel/workspace/smoke_public.py"
    if ($LASTEXITCODE -ne 0) { throw "NaiveModel 应能通过公开基础契约冒烟检查 smoke_public.py" }

    python src/scoring/judge_pack.py --model NaiveModel --runs-dir $RunsDir --blind-dir $BlindDir --blind-maps-dir $BlindMapsDir --runs-log $RunsLog
    if ($LASTEXITCODE -ne 0) { throw "NaiveModel judge_pack 失败" }

    $naiveMapFile = Get-ChildItem "$BlindMapsDir/naivemodel.*.blind-map.json" | Select-Object -First 1
    $naiveMap = Get-Content $naiveMapFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $naivePackDir = Join-Path $BlindDir $naiveMap.pack_id

    python src/scoring/judge_submit.py `
        --pack-dir $naivePackDir --case-id case-01 `
        --judge-id judge-alpha --judge-model claude-opus `
        --D1 4.5 --D2 4.0 --D3 5.0 `
        --evidence "[S01][S02] 返回后Y2归零丢失浏览位置 + [S03] 静态装饰SVG无动态重绘 + [S07][S10] 无冲突顺延且503首次提交失败无保底 + [code/app.js:L1-L240] C1-C5属实但缺乏并发防竞态" `
        --note "仅把基础异步展示跑通，存在慢请求倒灌竞态、无冲突消解与503无重试硬伤，按低档定分" `
        --review-log $ReviewLog
    if ($LASTEXITCODE -ne 0) { throw "NaiveModel judge_submit 失败" }

    Write-Host "== [5/7] 基线二：痛点体贴交互黄金参考基线（GoldenModel-s1）与靶向补测验证 ==" -ForegroundColor Cyan
    $t0Gold = (Get-Date).AddMinutes(-10).ToString("yyyy-MM-ddTHH:mm:sszzz")
    python tools/start_run.py --model GoldenModel-s1 --t0 $t0Gold --runs-dir $RunsDir --runs-log $RunsLog
    if ($LASTEXITCODE -ne 0) { throw "GoldenModel-s1 start_run 失败" }

    Copy-Item -Path "src/baselines/golden_baseline/*" -Destination "$RunsDir/GoldenModel-s1/workspace/" -Recurse -Force
    python "$RunsDir/GoldenModel-s1/workspace/smoke_public.py"
    if ($LASTEXITCODE -ne 0) { throw "GoldenModel-s1 smoke_public.py 未通过" }

    @"
{
  "input_tokens": 38500,
  "output_tokens": 12400,
  "total_tokens": 50900,
  "source": "self_report",
  "note": "golden reference smoke test"
}
"@ | Set-Content -Path "$RunsDir/GoldenModel-s1/token_usage.json" -Encoding UTF8

    python src/scoring/judge_pack.py --model GoldenModel-s1 --runs-dir $RunsDir --blind-dir $BlindDir --blind-maps-dir $BlindMapsDir --runs-log $RunsLog
    if ($LASTEXITCODE -ne 0) { throw "GoldenModel-s1 judge_pack 失败" }

    $goldMapFile = Get-ChildItem "$BlindMapsDir/goldenmodel.*.blind-map.json" | Select-Object -First 1
    $goldMap = Get-Content $goldMapFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $goldPackDir = Join-Path $BlindDir $goldMap.pack_id

    # 验证评委靶向补测工具 judge_probe.py 可正常运行，并在提交前清理临时截图
    $probePng = Join-Path $DraftDir "probe_test.png"
    python tools/judge_probe.py --case-dir "$goldPackDir/case-01" --viewport 1440x900 --click "[data-testid='article-open']" --press "Escape" --out $probePng
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $probePng)) { throw "judge_probe.py 靶向补测失败" }
    Remove-Item -Recurse -Force $DraftDir

    # 执行严格隔离审计与时间重叠审计
    python tools/isolation_audit.py --runs-dir $RunsDir --blind-dir $BlindDir --blind-maps-dir $BlindMapsDir --draft-dir $DraftDir --strict
    if ($LASTEXITCODE -ne 0) { throw "isolation_audit 严格审计未通过" }
    python tools/timing_audit.py $RunsDir --strict
    if ($LASTEXITCODE -ne 0) { throw "timing_audit 严格审计未通过" }

    # 两位独立评委盲评提交 + 验证同一评委重复提交被退出码 2 拒绝
    python src/scoring/judge_submit.py `
        --pack-dir $goldPackDir --case-id case-01 `
        --judge-id judge-alpha --judge-model claude-opus `
        --D1 10.5 --D2 9.5 --D3 8.5 `
        --evidence "[S01][S02] Y1=Y2精准恢复 + [S03] 零重叠动态SVG雷达图 + [S07][S08] 14周连续空闲顺延 + [S09][S10] 非破坏带入与503自动退避回执生成 + [code/app.js] C1-C5全核实" `
        --note "手机窄屏下目录位于正文上方，超多小节长文时可增加折叠收起开关" `
        --review-log $ReviewLog
    if ($LASTEXITCODE -ne 0) { throw "GoldenModel 评委1 提交失败" }

    $ErrorActionPreference = "Continue"
    python src/scoring/judge_submit.py `
        --pack-dir $goldPackDir --case-id case-01 `
        --judge-id judge-alpha --judge-model claude-opus `
        --D1 10.0 --D2 9.0 --D3 8.0 `
        --evidence "[S01] 重复提交防重拦截验证" `
        --note "重复提交应被拒绝" `
        --review-log $ReviewLog > $null 2>&1
    $dupCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($dupCode -ne 2) { throw "同一评委重复提交未被拦截（期望退出码 2，实际 $dupCode）" }

    python src/scoring/judge_submit.py `
        --pack-dir $goldPackDir --case-id case-01 `
        --judge-id judge-beta --judge-model gemini-pro `
        --D1 10.0 --D2 9.5 --D3 8.5 `
        --evidence "[S02][S08][S10] 滚动记忆、AbortController并发锁、IME拼字保护与503退避完备 + [code/app.js] 工程结构解耦清晰" `
        --note "搜索命中高亮仅作用于列表摘要与标签，未展示正文上下文摘录片段" `
        --review-log $ReviewLog
    if ($LASTEXITCODE -ne 0) { throw "GoldenModel 评委2 提交失败" }

    python src/scoring/review_merge.py --log $ReviewLog --out "$TmpDir/merged_reviews.json"
    if ($LASTEXITCODE -ne 0) { throw "review_merge.py 失败" }

    Write-Host "== [6/7] 统一拉起三波无头浏览器剧本定稿客观分并合成总榜（finalize.py） ==" -ForegroundColor Cyan
    python src/scoring/finalize.py `
        --runs-dir $RunsDir `
        --blind-maps-dir $BlindMapsDir `
        --review-log $ReviewLog `
        --leaderboard-path $ScoresMd `
        --verdicts-dir $VerdictsDir `
        --runs-log $RunsLog
    if ($LASTEXITCODE -ne 0) { throw "finalize.py 全量出榜失败" }

    Write-Host "== [7/7] 断言三档基线留档完备度、连环画与分数梯度 ==" -ForegroundColor Cyan
    python tests/assert_smoke.py $TmpDir
    if ($LASTEXITCODE -ne 0) { throw "assert_smoke.py 断言未通过" }

    # 出榜后再次复核隔离审计确认无沙盒污染
    python tools/isolation_audit.py --runs-dir $RunsDir --blind-dir $BlindDir --blind-maps-dir $BlindMapsDir --draft-dir $DraftDir --strict
    if ($LASTEXITCODE -ne 0) { throw "出榜后 isolation_audit 复核未通过" }

    if (-not $KeepTmp) {
        Remove-Item -Recurse -Force $TmpDir
    }
    Write-Host "`nALL SMOKE & DUAL-BASELINE TESTS PASSED!" -ForegroundColor Green
}
catch {
    Write-Host "`n[SMOKE FAILED] $_" -ForegroundColor Red
    Write-Host "现场临时目录已保留以便排查：$TmpDir" -ForegroundColor Yellow
    exit 1
}
