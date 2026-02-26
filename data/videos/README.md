# 仿真模式视频文件目录

将本地视频文件（MP4/TS格式）放置于此目录，供仿真模式使用。

## 使用说明

1. 将测试视频文件复制到此目录（如 `test.mp4`）
2. 在数据库中设置频道的 `sim_video` 字段为文件路径（如 `/data/videos/test.mp4`）
3. 探针服务仿真模式将读取该文件并通过UDP组播发送

## 快速下载测试视频

```bash
# 使用 ffmpeg 生成一个测试视频（彩色条纹，含音频）
ffmpeg -f lavfi -i testsrc=duration=30:size=1280x720:rate=25 \
       -f lavfi -i sine=frequency=1000:duration=30 \
       -c:v libx264 -c:a aac \
       /data/videos/testsrc.mp4
```

## 文件格式支持

- MP4（H.264/AAC，推荐）
- TS（MPEG-TS，直接封装）
- MKV（通过 PyAV 解码）
