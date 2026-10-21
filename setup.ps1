$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$env:PYTHONIOENCODING = "utf-8"

function Say($msg, $color = "White") { Write-Host $msg -ForegroundColor $color }
function Fail($msg) {
    Say ""
    Say "[失败] $msg" Red
    Read-Host "按回车退出"
    exit 1
}

Say "==================================================" Cyan
Say " 微信群 AI 助手 · 一键安装" Cyan
Say "==================================================" Cyan
Say ""

# ---------- 1. Python ----------
Say "[1/6] 检查 Python ..." Yellow

$pyExe = $null
$candidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:ProgramFiles\Python312\python.exe"
)
foreach ($p in $candidates) {
    if (Test-Path $p) { $pyExe = $p; break }
}
if (-not $pyExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $pyExe = $cmd.Source }
}

function Get-PyVersion($exe) {
    try {
        $v = & $exe -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0) { return $v }
    } catch {}
    return $null
}

if ($pyExe) { $ver = Get-PyVersion $pyExe }
if (-not $pyExe -or -not $ver -or [version]$ver -lt [version]"3.9") {
    Say "未找到可用的 Python，尝试用 winget 安装 Python 3.12 ..." Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        & winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        $candidates = @(
            "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
            "$env:ProgramFiles\Python312\python.exe"
        )
        foreach ($p in $candidates) { if (Test-Path $p) { $pyExe = $p; break } }
    }
}

if (-not $pyExe) {
    Fail "没有找到 Python。请手动安装 Python 3.12（安装时勾选 Add to PATH）后重新运行本脚本：https://www.python.org/downloads/"
}
$ver = Get-PyVersion $pyExe
if (-not $ver -or [version]$ver -lt [version]"3.9") { Fail "Python 版本过低（$ver），需要 3.9 以上。" }
if ([version]$ver -ge [version]"3.13") { Say "提示：wechatauto-replica 推荐 Python 3.9-3.12，3.13 可能装不上 winsdk。" Yellow }
Say "Python $ver  OK" Green

# ---------- 2. 依赖 ----------
Say ""
Say "[2/6] 安装依赖（首次约 1-3 分钟）..." Yellow
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    & $pyExe -m venv "$root\.venv"
    if ($LASTEXITCODE -ne 0) { Fail "创建虚拟环境失败。" }
}
& $venvPy -m pip install --disable-pip-version-check -q --upgrade pip
& $venvPy -m pip install --disable-pip-version-check -r "$root\requirements.txt"
if ($LASTEXITCODE -ne 0) {
    Say "默认源失败，改用清华镜像重试 ..." Yellow
    & $venvPy -m pip install --disable-pip-version-check -r "$root\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
    if ($LASTEXITCODE -ne 0) { Fail "依赖安装失败，请检查网络。" }
}
Say "依赖安装完成" Green

# ---------- 3. 微信 ----------
Say ""
Say "[3/6] 检查微信 4.x ..." Yellow

function Find-Weixin {
    $paths = @(
        "$env:ProgramFiles\Tencent\Weixin\Weixin.exe",
        "${env:ProgramFiles(x86)}\Tencent\Weixin\Weixin.exe",
        "$env:ProgramFiles\Tencent\WeChat\WeChat.exe",
        "${env:ProgramFiles(x86)}\Tencent\WeChat\WeChat.exe",
        "$env:LOCALAPPDATA\Tencent\Weixin\Weixin.exe"
    )
    foreach ($p in $paths) { if (Test-Path $p) { return $p } }

    foreach ($procName in @("Weixin", "WeChat")) {
        $proc = Get-Process $procName -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($proc -and $proc.Path -and (Test-Path $proc.Path)) { return $proc.Path }
    }

    $keys = @(
        "HKCU:\Software\Tencent\Weixin",
        "HKCU:\Software\Tencent\WeChat",
        "HKLM:\SOFTWARE\Tencent\Weixin",
        "HKLM:\SOFTWARE\WOW6432Node\Tencent\Weixin",
        "HKLM:\SOFTWARE\Tencent\WeChat",
        "HKLM:\SOFTWARE\WOW6432Node\Tencent\WeChat"
    )
    foreach ($k in $keys) {
        try {
            $item = Get-ItemProperty $k -ErrorAction Stop
            foreach ($name in @("InstallPath", "InstallDir", "Path")) {
                if ($item.$name) {
                    foreach ($exe in @("Weixin.exe", "WeChat.exe")) {
                        $cand = Join-Path $item.$name $exe
                        if (Test-Path $cand) { return $cand }
                    }
                }
            }
        } catch {}
    }

    $uninstallRoots = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    foreach ($u in $uninstallRoots) {
        $apps = Get-ItemProperty $u -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match "微信|WeChat|Weixin" }
        foreach ($app in $apps) {
            if ($app.InstallLocation) {
                foreach ($exe in @("Weixin.exe", "WeChat.exe")) {
                    $cand = Join-Path $app.InstallLocation $exe
                    if (Test-Path $cand) { return $cand }
                }
            }
            if ($app.DisplayIcon) {
                $icon = $app.DisplayIcon.Trim('"').Split(',')[0]
                if (Test-Path $icon) { return $icon }
            }
        }
    }

    foreach ($dir in @("$env:ProgramFiles\Tencent", "${env:ProgramFiles(x86)}\Tencent", "$env:LOCALAPPDATA\Tencent")) {
        if (Test-Path $dir) {
            foreach ($exe in @("Weixin.exe", "WeChat.exe")) {
                $hit = Get-ChildItem $dir -Filter $exe -Recurse -Depth 2 -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($hit) { return $hit.FullName }
            }
        }
    }
    return $null
}

$wx = Find-Weixin

if (-not $wx) {
    Say "未检测到微信。本项目需要 4.1.12+，请先从 https://pc.weixin.qq.com 安装最新版微信。" Yellow
    Say "登录 AI 小号后回到这个窗口按回车。" Yellow
    Start-Process "https://pc.weixin.qq.com"
    Read-Host "安装并登录完成后，按回车继续"
    $wx = Find-Weixin
}

if (-not $wx) {
    Say "自动检测失败。请把你电脑上的 Weixin.exe 完整路径粘贴进来（例如 D:\Program Files\Tencent\Weixin\Weixin.exe）。" Yellow
    Say "不知道路径：在任务栏右键微信图标 → 属性，或先启动微信再回来。" Yellow
    $manual = (Read-Host "Weixin.exe 路径（直接回车跳过）").Trim('"').Trim()
    if ($manual -and (Test-Path $manual)) { $wx = $manual }
}

if (-not $wx) {
    Say "仍未找到微信，跳过版本检查（不影响后续；新后端用数据库+UIA，不依赖这个路径）。" Red
} else {
    $wxVer = (Get-Item $wx).VersionInfo.FileVersion
    Say "微信版本：$wxVer  ($wx)" Green
    if ($wxVer -match '^4\.1\.(1[2-9]|[2-9][0-9])') {
        Say "wechatauto-replica：支持 4.1.12+，当前版本 OK。" Green
    } else {
        Say "警告：wechatauto-replica 需要微信 4.1.12+，当前是 $wxVer。" Red
    }
}

# ---------- 4. 配置 ----------
Say ""
Say "[4/6] 配置群名 / 昵称 / 模型 ..." Yellow
if (Test-Path (Join-Path $root "config_local.py")) {
    Say "已存在 config_local.py，跳过。要重配请删除该文件后重跑。" Green
} else {
    & $venvPy "$root\configure.py"
    if ($LASTEXITCODE -ne 0) { Fail "配置未完成。" }
}

# ---------- 5. 自启 ----------
Say ""
Say "[5/6] 设置开机自启 ..." Yellow
try {
    $startup = [Environment]::GetFolderPath("Startup")
    $ws = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut((Join-Path $startup "WeChatAIBot.lnk"))
    $lnk.TargetPath = Join-Path $root "run_forever.bat"
    $lnk.WorkingDirectory = $root
    $lnk.WindowStyle = 7
    $lnk.Description = "微信群 AI 助手"
    $lnk.Save()
    Say "已加入启动项：$startup\WeChatAIBot.lnk" Green
} catch {
    Say "创建启动项失败（不影响使用）：$_" Red
}

try {
    powercfg /change standby-timeout-ac 0 | Out-Null
    powercfg /change monitor-timeout-ac 0 | Out-Null
    Say "电源设置：已关闭睡眠/关屏（仅当前电源计划）" Green
} catch {}

# ---------- 6. 自检 ----------
Say ""
Say "[6/6] 自检 ..." Yellow
& $venvPy "$root\bot.py" --doctor

Say ""
Say "==================================================" Cyan
Say " 安装完成" Cyan
Say "==================================================" Cyan
Say "如果自检里微信账号显示正常、群已找到，就可以："
Say "  1. 双击 run.bat 正式运行"
Say "  2. 用另一个号在群里发：@群昵称 你好"
Say ""
Say "常用命令："
Say "  run.bat                 正式运行"
Say "  run_forever.bat         崩溃自动重启（开机自启用的就是它）"
Say "  python bot.py --doctor  重新自检"
Read-Host "按回车退出"
