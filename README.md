# Wallpaper 原图导出工具

这是一个本机 Wallpaper Engine 壁纸浏览和原图导出工具。当前是 Python + PySide6 开发版窗口程序。

它会扫描本机 Steam Workshop 里的 Wallpaper Engine 壁纸，尽量用最直接的方式导出图片：

1. 普通图片/视频壁纸：直接复制原始媒体文件。
2. `scene.pkg` 壁纸：用 RePKG 解包。
3. 可静态还原的场景：合成 `scene.json` 里的图片图层。
4. 静态合不了的动态/模型场景：先询问你，再用 Wallpaper Engine 打开临时窗口抓图。

## 目录结构

```text
.
├─ wallpaper_exporter/                  # 桌面应用代码
│  ├─ ui.py                              # PySide6 窗口
│  ├─ indexer.py                         # Workshop 扫描
│  ├─ exporter.py                        # 导出流程
│  └─ wallpaper_engine/                  # Wallpaper Engine 合成/抓图工具
│     ├─ compose_we_auto.py
│     ├─ compose_we_static.py
│     └─ render_we_scene.py
├─ tools/RePKG/RePKG.exe                 # RePKG 可执行文件
├─ tests/                                # 自动测试
└─ requirements.txt
```

## 首次准备

在项目根目录运行：

```powershell
cd D:\code_Date\codex_projects\explore
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果你已经让我创建过 `.venv`，可以跳过这一步。

## 启动桌面程序

```powershell
cd D:\code_Date\codex_projects\explore
.\.venv\Scripts\python.exe -m wallpaper_exporter
```

打开后会扫描默认目录：

```text
D:\GAME\steam\steamapps\workshop\content\431960
```

## 首次配置

点窗口右上方的 `设置`，确认这几个路径：

```text
Workshop:
D:\GAME\steam\steamapps\workshop\content\431960

导出根目录:
你自己选择

RePKG.exe:
D:\code_Date\codex_projects\explore\tools\RePKG\RePKG.exe

wallpaper64.exe:
D:\GAME\steam\steamapps\common\wallpaper_engine\wallpaper64.exe
```

设置会保存到本地 `wallpaper_exporter_settings.json`，这个文件不会提交到 git。

## 导出图片

1. 在左侧列表选择一个壁纸。
2. 右侧查看预览和状态。
3. 点击 `导出选中`。
4. 如果需要 Wallpaper Engine 抓图，程序会先弹窗问你是否允许。

导出结果会放到：

```text
<你选择的导出根目录>\导出原图\<壁纸标题>\
```

可能生成的文件：

```text
original.png / original.jpg      # 直接图片壁纸
original.mp4 / original.webm     # 直接视频壁纸
composite.png                    # 静态合成结果
render.png                       # Wallpaper Engine 抓图结果
preview.jpg / preview.png        # 预览图
info.json                        # 导出信息
```

## 单独使用合成/抓图命令

这些底层工具已经从根目录移到 `wallpaper_exporter.wallpaper_engine` 包里。

自动判断静态合成还是抓图：

```powershell
.\.venv\Scripts\python.exe -m wallpaper_exporter.wallpaper_engine.compose_we_auto "D:\base_tools\RePKG\待合成\output（示例）"
```

只做静态合成：

```powershell
.\.venv\Scripts\python.exe -m wallpaper_exporter.wallpaper_engine.compose_we_static "D:\base_tools\RePKG\待合成\output（示例）" -o "D:\base_tools\RePKG\待合成\output（示例）\composite_static.png"
```

使用 Wallpaper Engine 抓图：

```powershell
.\.venv\Scripts\python.exe -m wallpaper_exporter.wallpaper_engine.render_we_scene "D:\GAME\steam\steamapps\workshop\content\431960\2777556065\project.json" -o "D:\base_tools\RePKG\待合成\output（星之砂浜）\render.png" --width 3840 --height 2160
```

抓图默认会等待 20 秒再捕获，避免保存到 Wallpaper Engine 的 `Hold on / Compiling assets` 加载页。需要手动调整时可以加 `--wait 秒数`。

如果抓图输出接近全黑，脚本会报错，不会默默保存坏图。遇到这种情况，优先传原始 Workshop 目录里的 `project.json` 或 `scene.pkg`。

## 运行测试

```powershell
cd D:\code_Date\codex_projects\explore
.\.venv\Scripts\python.exe -m pytest
```

## 当前限制

- 这是开发版，还没有打包成双击运行的 `.exe`。
- 扫描和导出当前在窗口进程里执行，处理特别大的壁纸时界面可能短暂等待。
- 动态壁纸不存在真正意义上的“原始静态图”时，只能通过 Wallpaper Engine 抓取当前画面。
