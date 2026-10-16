# PPT Skills

一个 Codex 技能：先访谈确认内容和风格，用 AI 生成整套豪华的图片版 PPT，再把每一页还原成**可编辑的 PPTX**。

基于 [Gorden Sun 的 GordenSuperPPTSkills](https://github.com/GordenSun/GordenSuperPPTSkills) 改造：原来的三个技能合并为一个 [`ppt-skills`](ppt-skills/SKILL.md)，加入需求访谈、风格样张确认和逐页子代理转换，同时精简了流程说明。

## 效果

AI 生成的图片版 PPT：

![AI 生成的图片版 PPT 示例](examples/example-Image-ppt.png)

还原后的可编辑 PPTX（文字是真文本框，背景、框架、图标是可移动图片）：

![还原后的可编辑 PPTX 示例](examples/example-editable-pptx.png)

## 流程

1. **需求访谈**：分轮提问，问清用途、受众、页数、画幅、语言、品牌要求和信息密度。只用你提供的材料，不编数据。
2. **风格选择**：按主题现编 4 个风格选项，可多选；和主题匹配时会把内置参考图风格编进选项。
3. **大纲确认**：逐页列出标题、核心信息、版式和全部文字，确认后作为唯一文字依据。
4. **样张确认**：每个选中风格各出 1 张同一页的样张，你看图定稿。
5. **全套出图**：Codex 内置 `image_gen`，不锁定模型（平台自动用最新），始终要求最高质量。
6. **逐页转换**：每页一个独立上下文的子代理（默认 `gpt-6.1-sol` / `high`，最多 4 个并行），依次提取背景图、框架图、图标/装饰图，量好位置写成文本框，再用 PowerPoint 真实渲染并和原图对照，最多自动修正 2 轮。
7. **合并交付**：合成整套可编辑 PPTX，并列出需要人工复查的页面。

每次启动会对比 Codex 的模型列表；出现新模型时会问你要不要换转换模型，每个新模型只问一次。

## 安装

把 `ppt-skills/` 整个文件夹复制到 Codex 的 skills 目录：

```powershell
Copy-Item -Recurse ppt-skills "$env:USERPROFILE\.codex\skills\ppt-skills"
```

依赖：

```text
pip install -r ppt-skills/requirements.txt
```

逐页核对要用 Microsoft PowerPoint 渲染，所以需要在装了 PowerPoint 的 Windows 上运行。

## 使用

```text
使用 $ppt-skills，把这份材料做成 PPT：<材料或文件路径>
```

想把框架图切成可单独移动的部件，在需求里说明「框架要切分」即可。

## 目录

```text
ppt-skills/
├── SKILL.md                  主代理流程
├── references/
│   ├── interview.md          需求访谈（内置 grilling）、风格选择、大纲与样张确认
│   ├── image-prompts.md      出图规则、内容密度、版式目录、提示词模板
│   ├── styles.md             参考风格图库说明
│   ├── worker.md             子代理的单页转换说明
│   └── models.json           转换模型与已知模型清单
├── scripts/                  模型检查、探色、抠图、切图、标尺、布局检查、合成、PowerPoint 渲染、单页检查
└── assets/styles/            5 组参考图（红藏青商务、红藏青汇报、蓝白架构、蓝色科研、绿色学术）
tests/                        脚本测试（不调用生图）
```

## 原理

核心是 GPT 的生图能力和视觉能力：先生成整页图片，再让模型从这张图里分别提取干净的背景图、框架图（卡片、线条、图表图形）和图标/装饰图，绿幕抠图后按坐标放回 PPT，文字则写成真正的文本框。

| 背景图 | 框架图 | 图标和装饰 |
|---|---|---|
| ![背景图](examples/背景图.png) | ![框架图](examples/框架图.png) | ![图标和装饰](examples/图标和装饰.png) |

## 测试

```text
python -m unittest discover -s tests -v
```

在装了 PowerPoint 的 Windows 上设置 `PPT_SKILLS_OFFICE_TESTS=1` 会额外跑真实渲染测试。

## 致谢与版权

- 原作者 Gorden Sun：可以商用，**必须标明 GitHub 出处，或标记出作者 @Gorden Sun**。
- 原项目：[GordenSun/GordenSuperPPTSkills](https://github.com/GordenSun/GordenSuperPPTSkills)；感谢 [LinuxDO](https://linux.do) 社区。
