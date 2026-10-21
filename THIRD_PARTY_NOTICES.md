# 第三方组件与声明

本仓库**不包含**任何第三方源代码、二进制、字体或图片素材。运行时由 pip 从 PyPI 安装以下组件，版权与许可证归各自作者所有：

| 组件 | 许可证 | 用途 |
|---|---|---|
| [wechatauto-replica](https://github.com/fanyuantaier/wechatauto-replica) | Apache-2.0 | 读取微信本地数据库、UIA 发送消息 |
| [requests](https://pypi.org/project/requests/) | Apache-2.0 | HTTP 请求 |
| [Pillow](https://pypi.org/project/Pillow/) | MIT-CMU | 图片处理 |
| uiautomation | Apache-2.0 | Windows UI 自动化 |
| pywin32 | PSF-2.0 | Windows API 绑定 |
| psutil | BSD-3-Clause | 进程与系统状态 |
| cryptography | Apache-2.0 / BSD-3-Clause | 加密相关依赖 |
| winsdk | MIT | Windows SDK 绑定 |
| opencv-python | Apache-2.0 | 图像处理（wechatauto 依赖） |
| zstandard | BSD-3-Clause | 压缩数据读取 |
| imageio-ffmpeg | BSD-2-Clause | 媒体处理 |
| pyautogui / pyperclip / colorama | BSD | 辅助工具 |

完整依赖树以 `requirements.txt` 和 pip 实际安装结果为准。各项目的许可证原文见其发行包内的 `LICENSE` / `METADATA`。

## 说明

- 这些依赖不随本仓库分发，本仓库的 MIT 许可证不覆盖它们
- 如果你把本项目与依赖一起打包分发（例如做成 exe 或离线包），需要自行满足各依赖的许可证要求，包括 Apache-2.0 的 NOTICE 保留义务
- `wechatauto-replica` 为第三方独立项目，其代码来源与合规性由该项目维护者负责

## 非关联声明

本项目与腾讯、DeepSeek 及其关联公司没有任何隶属、合作或背书关系。“微信”“DeepSeek”等名称仅用于说明本程序读取/调用的对象，相关商标归其权利人所有。
