---
name: image-compress
description: >-
  Compress image file size with sharp. Use when an image is too large for
  uploads, attachments, APIs, or vision-model requests. With --max-bytes the
  script lowers quality until the target size is reached (minimum quality 1,
  at most 3 compression rounds); without it, it re-encodes at quality 70.
  Format conversion and resizing only happen when explicitly requested.
---

# Image Compress（图片体积压缩）

## When to use

- 图片上传/发送前被“文件太大”拒绝
- API / VLM / 附件有体积上限（例如 500KB、2MB）
- 想快速得到一张体积更小、画质可接受的图片
- Agent 需要把图片压到指定大小后重试

## Run

先确保依赖已安装（同一个 skill 目录只需一次）：

```bash
cd D:/dev_work/skills/image-compress/scripts
npm install
```

然后从 skill 根目录调用：

```bash
# 默认：quality 70，不换格式、不缩尺寸
node scripts/compress.mjs ./big.png ./small.png

# 指定目标体积：自动降 quality，压到 500KB 以内
node scripts/compress.mjs ./big.png ./small.jpg --max-bytes 500KB

# 显式换格式：PNG → WebP
node scripts/compress.mjs ./big.png ./small.webp --format webp

# 显式限制尺寸：宽高都不超过 2000px，保持比例、绝不放大
node scripts/compress.mjs ./big.png ./small.png --max-dimension 2000

# 手动指定质量
node scripts/compress.mjs ./big.png ./small.jpg --quality 50
```

## Behavior

- **默认只调 quality**：不传 `--format` 就不换格式，不传 `--max-dimension` 就不改尺寸。
- **`--max-bytes`**：从 `--quality`（默认 70）开始按 step 10 降到 1；最低质量仍超限时，把当前最小结果作为输入再压，最多 **3 轮**。达到则成功，达不到则输出当前最小结果并提示 `achieved: false`。
- **`--format jpeg|webp|png`**：只有显式传入才转换格式。
- **`--max-dimension <px>`**：只有显式传入才缩放尺寸，只缩小不放大。
- 输入体积已经 ≤ `--max-bytes` 时，原样返回，不做多余改动。

## Notes

- 依赖 [sharp](https://github.com/lovell/sharp)（Apache-2.0）。
- 输出默认命名：`<原文件名>.compressed.<ext>`；也可直接给 `[output]` 指定路径。
- 如果填写 `--max-bytes` 后结果仍超限，检查 `achieved: false` 与 `rounds` 输出，说明该方案在当前格式/尺寸约束下无法继续压小。