# 单页转换（子代理说明）

你负责把**一页**幻灯片图片还原成可编辑页：四层从下到上依次是 背景图 → 框架图 → 图标/装饰图 → 真文本框。文字可编辑；背景、框架、图标是 AI 生成的图片，可整体移动和替换。

- 页目录 `PAGE`：里面有 `source.png`（要还原的幻灯片图）和 `prompt.md`（其中【页面文字】是用户确认过的全部文字）。所有产物只写在 `PAGE` 里。
- 技能目录 `SKILL`：脚本用 `python SKILL/scripts/<脚本>.py` 运行，各脚本 `--help` 有详细用法。
- 不要读主技能的其它文件、不要找历史项目里的相似页面；只处理这一页。

## 三条底线

1. **三个图片层都用 `image_gen` 从 source.png 提取生成。** 不能拿原图当背景（会出现双重文字），不能从原图裁局部当素材，不能用代码、SVG 或 PPT 形状画背景/框架/图标（会失真、变廉价）。
2. **真正把图传给 image_gen。** 每次调用前先 `view_image` 打开 `PAGE/source.png`（或者用工具的本地图片参数传入），提示词开头写「以这张图片作为编辑目标」。只在提示词里写文件路径不算传图，模型会凭空猜，框架和图标就会跑偏。
3. **文字内容以 prompt.md 的【页面文字】为准。** 图上有错字、漏字也用原文；看图只是为了确定位置、换行、字号、颜色和粗细。

每次 image_gen 都要求最高质量（工具有质量参数就设最高档）。生成图在 `$CODEX_HOME/generated_images/...`，复制到 `PAGE` 下对应文件名（保留原图）。

## 第 1 步：定抠图底色

```
python SKILL/scripts/probe_palette.py PAGE/source.png
```

输出的 `recommended_key` 就是本页底色 K（默认 #00ff00；页面里有绿色时会推荐 #ff00ff 等）。后面框架图、图标图的纯色背景和去底都用 K。

## 第 2 步：背景图 → background.png

提示词：

```text
以这张图片作为编辑目标，复刻这张幻灯片的背景：保持完全一致的底色、渐变、光影、纹理和大面积背景装饰，
但生成一张完全空白的背景——不要任何文字、图标、卡片、方框、占位块、分隔条。比例与原图完全相同。
```

背景是照片或复杂纹理时，改成「擦除原图上的所有文字、图标、卡片和装饰，补全背景」。卡片、容器、分隔线等一律不留在背景里，它们属于框架图。

## 第 3 步：框架图 → frame.png

**框架图 = 页面里除了背景、图标/装饰/艺术字、普通文字以外的全部图形**：容器和卡片（含底色填充、彩色标题条、阴影辉光、渐变）、分区线、标题下的短强调线、下划线、连接线和箭头、节点圆点、标签胶囊的边框、**所有图表图形**（坐标轴、网格线、柱体、折线、数据点、扇区、饼图、阶梯、雷达等）、缎带横幅、装饰线条与色块。

**艺术字**（渐变色、书法笔刷、变形、描边阴影纹理、徽章式排版等普通字体写不出的字）不算普通文字，归第 4 步的图标层。

提示词（固定，只把 XXXXXX 换成 K）：

```text
以这张图片作为编辑目标，生成一张图片，提取这张图片中的框架图，纯色背景，背景色值为XXXXXX，「框架图」= 原图里除背景/图标/装饰/艺术字/普通文本外的一切（容器轮廓与底色填充/标题条/辉光、分隔/连接线、全部图表图形：折线/柱状/阶梯/饼图/坐标网格/趋势线、缎带/装饰）→ 形状·大小·位置与原图 1:1 一致，保留原色与填充，别漏数据折线/装饰、别自己额外加空心线框、占位框；不要出现文字、不要出现图标；
```

存为 `PAGE/frame_raw.png`，去底：

```
python SKILL/scripts/chroma_key.py --input PAGE/frame_raw.png --out PAGE/frame.png --preset frame-safe --scale 2 --force
```

K 不是绿色时加 `--auto-key none --key-color "#ff00ff"`（换成 K）。`frame-safe` 预设会完整保留颜色和 1px 细线；不要自己加 `--soft-matte`、`--despill`、`--contract` 这类激进参数（会褪色、吃线）。

检查：

```
python SKILL/scripts/build_page.py PAGE --stage layers
```

查看 `PAGE/qa/layers.png`（左边原图，右边是背景叠上框架）：右边应该≈原图去掉文字和图标。逐项核对：卡片填充和标题条在不在（只剩空心细线框 = 失败）、图表图形和短分割线有没有漏、位置大小是否 1:1、有没有多出原图没有的框、有没有残留文字或图标。有问题就在提示词末尾补一句具体缺什么，重新生成。

## 第 4 步：图标与装饰 → icons/

1. **先去重**：对照 source.png 和 `qa/layers.png`，列出原图里全部图标、装饰、插画、艺术字，划掉已经正确出现在框架图里的。只生成剩下的，同一个元素不能既在框架里又在图标层（会出现重影）。框架里多出了不该有的图标，优先重出框架。
2. **生成图标表**，提示词：

```text
以这张图片作为编辑目标，生成一张图片，提取这张PPT图片当中所有的图标元素和装饰元素，纯色背景，背景色值为XXXXXX，不要文字，不要背景条。
要求：
- 方形画布；把元素排成 N×N 等分网格，每格一个元素，居中，四周留出均匀的空白；不要画任何网格线、分割线或虚线。
- 只要以下元素：<待生成清单，逐个写出名称和外观>。艺术字保留字形、渐变和笔画造型。
- 元素之间不重叠、不相连；任何笔画、阴影、外轮廓都不能碰到格子边缘。
- 忠实还原每个元素的造型、颜色和风格（元素上不要用到背景色 XXXXXX）。
```

   小图标每张 4×4，多了就分几张；大装饰、插画、艺术字用 2×2 或单独一张。依次存为 `icons_raw_1.png`、`icons_raw_2.png`…
3. **去底、切片**：

```
python SKILL/scripts/chroma_key.py --input PAGE/icons_raw_1.png --out PAGE/icons_t_1.png --preset icon-safe --scale 2 --force
python SKILL/scripts/slice_grid.py PAGE/icons_t_1.png PAGE/icons --auto --pad 24 --contact-sheet --prefix ic1
```

   K 不是绿色时，抠图命令同第 3 步一样加 `--auto-key none --key-color`。每张图标表依次处理（`icons_raw_2.png` 用 `--prefix ic2`，依此类推）。查看 `PAGE/icons/icons_contact_sheet.png`：每个元素完整，没有被切掉半截、缺角、几个粘成一块，`icons_manifest.json` 里没有 `edge_touch: true`。不合格就加大留白、减少每张的元素数重新生成，或加大 `--pad` 重切。即使生成图里不小心出现了网格线也没关系：抠图后格子内有留白，切片会把它去掉。

## 第 5 步：量位置，写 layout.json

在源图像素坐标里量。先画标尺：

```
python SKILL/scripts/ruler.py PAGE/source.png PAGE/qa/ruler.png
python SKILL/scripts/ruler.py PAGE/source.png PAGE/qa/ruler_zoom.png --region X Y W H
```

`view_image` 显示的往往是缩小图，**一律读网格标注上的数字**（就是源图像素），不要用显示图上的坐标。文字密集的区域用 `--region` 放大后再量。

`PAGE/layout.json`（路径相对 PAGE；所有框都是源图像素 `x, y, w, h`）：

```json
{
  "ref_width": 2400, "ref_height": 1350,
  "background": "background.png",
  "frame": "frame.png",
  "icons": [
    {"file": "icons/ic1_r1c1.png", "x": 150, "y": 480, "w": 120, "h": 112}
  ],
  "texts": [
    {"text": "2023：平台生态成型", "x": 170, "y": 64, "w": 1100, "h": 96,
     "size_px": 80, "color": "#0B2A5B", "bold": true, "align": "left", "valign": "middle"},
    {"runs": [{"text": "更强模型、"}, {"text": "工具调用", "color": "#C00000", "bold": true}, {"text": "与开发者生态"}],
     "x": 170, "y": 190, "w": 1500, "h": 50, "size_px": 36, "color": "#333333"}
  ]
}
```

`ref_width/ref_height` 写 source.png 的真实像素尺寸。

**图标**：量原图里每个图标可见部分的框。宽高比按切片图（`icons_manifest.json` 里有尺寸）保持，不要随手写成正方形。改大小时以原图图标中心为锚点：`x = cx - w/2`、`y = cy - h/2`。

**文字**：

- 一个视觉上连在一起的文字块写一个文本框，内容从【页面文字】里对应取出；原图在哪里换行，就在那里插入 `\n`。
- 原图上有、【页面文字】里没有的字（模型乱加的）不要；【页面文字】里有、原图上没地方放的，写进 result.json 的 issues。
- 艺术字已经在图标层，不再写文本框。
- **先定样式，再定位置**（粗细、字号、行距会改变换行和占位）：
  - `size_px` = 原图上一个汉字的高度（源图像素）；
  - `color` 吸取原图颜色；
  - `bold` 默认 false，只有标题、按钮、重点数字和关键词按原图加粗，正文不要全加粗；
  - 多行正文用 `"line_spacing": 1.2` 左右；
  - 同一行里颜色或粗细不同（例如关键词高亮）就用 `runs`；
  - 中文字体默认 Microsoft YaHei，原图明显是宋体或楷体就改。
- 框要包住整块文字，宽度给足，否则会多出换行。脚注一类真的很小的字加 `"small_text_ok": true`；原图正文确实全是粗体时，在 layout 里加 `"allow_all_bold_text": true`。

## 第 6 步：检查与修正

```
python SKILL/scripts/build_page.py PAGE --stage boxes
```

会先检查 layout，例如坐标系对不对、框有没有越界、字号是不是从缩小图上量的、是不是全加粗。然后生成 `qa/source_boxes.png`：逐个确认每个框都圈住了原图里正确的对象，例如没有圈到隔壁那一行、那个按钮。检查报错时按提示改；如果坐标是在缩小图上量的，运行 `python SKILL/scripts/layout_guard.py PAGE/source.png PAGE/layout.json --fix-scale` 统一换算回源图像素。

```
python SKILL/scripts/build_page.py PAGE
```

它会合成 `PAGE/page.pptx`，用 PowerPoint 真实渲染，再生成 `qa/side_by_side.png`（原图和渲染图并排）、`qa/preview_boxes.png`、`qa/blend.png`（叠图，看错位）、`qa/diff_heatmap.png`（差异热力图）。主要看并排图，有疑问再看叠图和热力图；并排图缩小后小字看不清时，分别打开 `source.png` 和 `qa/render/slide_01.png` 对照。逐项检查：

- 图标：一个不缺、没有重影、没有缺边；位置和大小贴合，不压字。
- 文字：内容正确；换行位置与原图一致；字号、颜色、粗细、对齐接近原图；不溢出、不被遮挡。
- 框架和背景：对位、干净，没有残留文字。

修正顺序：

1. 图标：以中心点为锚点调整大小和位置。
2. 文字样式：粗细、字号、行距。
3. 文字框位置。
4. 贴在框架上的文字：标题条、按钮、底栏、标签里的文字，按**渲染图里框架的实际位置**对齐，不按原图。框架是生成的，可能和原图偏几个到几十个像素，这时整体平移这些文字框。

每轮改完重新运行 `build_page.py PAGE`。初次检查后**最多修正 2 轮**；2 轮后仍有明显差异就停下，把差异写进 issues。不要为了"对齐"删掉图标或把图标缩到不像原图。

## 可选：框架切分（只有任务消息里写了「框架切分：是」才做）

```
python SKILL/scripts/slice_grid.py PAGE/frame.png PAGE/frame_parts --components --pad 0 --contact-sheet --prefix fp
python SKILL/scripts/frame_parts_to_icons.py PAGE/frame_parts/icons_manifest.json --ref-width <源图宽> --ref-height <源图高>
```

把输出的 `frame_parts_layout_icons.json` 里的条目放到 `layout.icons` 的最前面，并删掉 `"frame"` 字段。

## 收尾

写 `PAGE/result.json`：

```json
{"page": "03", "status": "passed", "issues": [], "pptx": "page.pptx", "render": "qa/render/slide_01.png"}
```

`status`：`passed`（贴合原图）/ `needs_review`（2 轮修正后仍有差异，issues 逐条写清哪里不对）/ `blocked`（缺少 image_gen、PowerPoint 等能力，无法完成，issues 写原因）。

最后只回复一行：`页码 状态 PAGE/result.json`，不要附图片或长篇说明。
