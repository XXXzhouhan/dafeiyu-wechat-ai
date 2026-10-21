$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
Set-Location $root
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$env:PYTHONIOENCODING = "utf-8"

$lines = New-Object System.Collections.Generic.List[string]
function Add-Line($text) {
    Write-Host $text
    $lines.Add($text) | Out-Null
}

Add-Line "=================================================="
Add-Line " 诊断报告 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Add-Line "=================================================="
Add-Line ("系统：" + (Get-CimInstance Win32_OperatingSystem).Caption + " " + [Environment]::OSVersion.Version)
Add-Line ("目录：" + $root)
Add-Line ""

Add-Line "--- Python / 依赖 ---"
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    Add-Line (".venv: " + (& $venvPy --version 2>&1))
    $pkgs = & $venvPy -m pip list --format=freeze 2>$null
    foreach ($name in @("wechatauto-replica", "uiautomation", "psutil", "requests")) {
        $hit = $pkgs | Where-Object { $_ -like "$name==*" }
        if ($hit) { Add-Line ("  " + $hit) } else { Add-Line ("  $name : 未安装") }
    }
} else {
    Add-Line "  .venv 不存在（setup.bat 第 2 步没跑完）"
}
Add-Line ""

Add-Line "--- 微信进程 ---"
$procs = Get-Process Weixin, WeChat -ErrorAction SilentlyContinue
if ($procs) {
    foreach ($p in $procs) {
        $ver = ""
        try { $ver = (Get-Item $p.Path).VersionInfo.FileVersion } catch {}
        Add-Line ("  " + $p.ProcessName + " | " + $p.Path + " | 版本 " + $ver)
    }
} else {
    Add-Line "  没有微信进程（没登录或没启动）"
}
Add-Line ""

Add-Line "--- 微信安装位置（按文件/注册表/卸载项查找）---"
$found = @()
$paths = @(
    "$env:ProgramFiles\Tencent\Weixin\Weixin.exe",
    "${env:ProgramFiles(x86)}\Tencent\Weixin\Weixin.exe",
    "$env:ProgramFiles\Tencent\WeChat\WeChat.exe",
    "${env:ProgramFiles(x86)}\Tencent\WeChat\WeChat.exe",
    "$env:LOCALAPPDATA\Tencent\Weixin\Weixin.exe"
)
foreach ($p in $paths) { if (Test-Path $p) { $found += $p } }

if (-not $found) {
    foreach ($u in @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )) {
        Get-ItemProperty $u -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -match "微信|WeChat|Weixin" } |
            ForEach-Object {
                $found += ("卸载项：" + $_.DisplayName + " -> " + $_.InstallLocation + " | " + $_.DisplayVersion)
                if ($_.DisplayIcon) { $found += ("图标：" + $_.DisplayIcon) }
            }
    }
}
if (-not $found) {
    Add-Line "  默认路径和注册表都没找到，可能装到了自定义目录。"
} else {
    foreach ($f in ($found | Select-Object -Unique)) { Add-Line ("  " + $f) }
}
Add-Line ""

Add-Line "--- 配置 ---"
$local = Join-Path $root "config_local.py"
if (Test-Path $local) {
    Get-Content $local -Encoding UTF8 | Where-Object { $_ -match "GROUPS|BOT_NAMES|TRIGGER_MODE" } | ForEach-Object { Add-Line ("  " + $_) }
} else {
    Add-Line "  config_local.py 不存在（配置向导没跑完）"
}
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile -Encoding UTF8 | Where-Object { $_ -match "^LLM_(BASE_URL|MODEL)" } | ForEach-Object { Add-Line ("  " + $_) }
    Add-Line "  LLM_API_KEY：已设置（不显示）"
} else {
    Add-Line "  .env 不存在（模型 Key 没配）"
}
Add-Line ""

Add-Line "--- bot.py --doctor ---"
if (Test-Path $venvPy) {
    & $venvPy "$root\bot.py" --doctor 2>&1 | ForEach-Object { Add-Line ("  " + $_) }
} else {
    Add-Line "  跳过（.venv 不存在）"
}

Add-Line ""
Add-Line "--- 最后 20 行 bot.log ---"
$log = Join-Path $root "bot.log"
if (Test-Path $log) {
    Get-Content $log -Tail 20 -Encoding UTF8 | ForEach-Object { Add-Line ("  " + $_) }
} else {
    Add-Line "  没有 bot.log"
}

$out = Join-Path $root "check.log"
[IO.File]::WriteAllLines($out, $lines, (New-Object System.Text.UTF8Encoding($true)))
Write-Host ""
Write-Host ("报告已保存：" + $out) -ForegroundColor Green
Read-Host "把 check.log 发给我。按回车退出"
