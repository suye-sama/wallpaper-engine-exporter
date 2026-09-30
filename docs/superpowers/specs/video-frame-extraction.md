# 视频帧截图工具规格

## 目标

为 Wallpaper 原图导出工具增加一个独立的「视频帧截图」页面，用于从视频壁纸中按需截取帧图片。

## 需求

1. 与现有壁纸导出页面分隔，通过页签切换。
2. 扫描结果中识别为视频格式的壁纸出现在本页面。
3. 页面布局：
   - 左侧：视频壁纸列表，带搜索与预览缩略图，交互与导出页一致。
   - 右侧：视频预览播放器。进度条可拖放到指定位置，点击「提取视频帧」从当前播放进度截取图片。
4. 提取参数：
   - 视频帧采样间隔（秒）
   - 视频帧总数
   - 帧图片大小（原始尺寸 / 自定义宽度等比缩放）
5. 从当前播放位置开始，按采样间隔依次截取指定数量的帧，超出视频时长的部分自动丢弃。

## 非目标

- 不做视频转码、剪辑或拼接。
- 不依赖外部 ffmpeg；仅使用 PySide6 QtMultimedia。

## 输出

- 输出目录：`图片\Wallpaper Engine Exports\视频帧\<壁纸标题>\`
- 文件命名：`frame_001.png`、`frame_002.png`……（PNG，覆盖旧文件）
- 提取过程中显示进度；完成后可一键打开输出目录。

## 技术方案

- `wallpaper_exporter/paths.py`：新增 `frames_folder_for(root, title)`。
- `wallpaper_exporter/frame_extractor.py`：
  - 纯逻辑：`compute_timestamps(start_ms, duration_ms, interval_s, count)`、
    `frame_filename(index)`、`scaled_size(frame_size, target_width)`。
  - `VideoFrameExtractor(QObject)`：基于 `QMediaPlayer` + `QVideoSink`，逐时间点
    seek 后从 `videoFrameChanged` 抓帧、缩放、保存 PNG。信号驱动，不阻塞 UI；
    单帧 4 秒超时保护，全部失败时报错。
- `wallpaper_exporter/video_page.py`：`VideoFramePage(QWidget)` 页面实现。
- `wallpaper_exporter/ui.py`：主窗口改为 `QTabWidget` 双页签；扫描完成后把
  entries 与 settings 同步给视频页。

## 已知限制

- 帧解码依赖系统多媒体后端（Windows Media Foundation），个别编码（如部分
  webm）可能无法预览或抓帧。
- seek 落点可能受关键帧间隔影响产生少量偏差。
