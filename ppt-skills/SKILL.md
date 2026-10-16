---
name: ppt-skills
description: >-
  做一整套「好看又能编辑」的 PPT：先访谈确认内容、格式和风格，再用 AI 生成整套幻灯片图片，
  然后为每页委派一个子代理，把图片还原成可编辑 PPTX（文字是真文本框，背景、框架、图标是可移动图片）。
  当用户要做 PPT、把材料做成演示文稿、要 AI 生成的高颜值且可编辑的幻灯片时使用。
---

# PPT Skills

流程：准备 → 需求访谈 → 风格选择 → 大纲确认 → 样张确认 → 全套出图 → 逐页委派转换 → 合并交付。

主代理负责访谈、出图和调度。逐页转换全部交给子代理，主代理不需要读 `references/worker.md`。下文 `SKILL` 指本技能目录的绝对路径，`RUN` 指本次任务目录。

## 1. 准备

- 在用户工作目录下新建 `RUN = ppt_runs/<日期时间>_<主题短名>/`，本次所有文件只写在这里，不复用旧任务的文件。
- 确认依赖：`python -c "import pptx, PIL, numpy"`，缺了就 `pip install -r SKILL/requirements.txt`；转换核对要用 Windows 上的 PowerPoint 渲染。
- 检查转换模型：`python SKILL/scripts/check_models.py`。
  - 如果报告了新模型：用一个问题告诉用户新模型的名字、说明和推理档位，问要不要把转换模型从当前设置换成它（推荐项给出你的判断和理由）。
  - 用户回答后运行 `python SKILL/scripts/check_models.py --ack`；要换就加上 `--use <模型> --effort <档位>`。不管换不换都要 ack，以后不再重复问同一个模型。
  - 等待回答期间可以先继续访谈。

## 2. 访谈、风格、大纲、样张

按 [references/interview.md](references/interview.md) 依次完成：

1. 需求访谈，结论写进 `RUN/brief.md`；
2. 按主题现编 4 个风格选项，用户可多选；
3. 写 `RUN/outline.md`，确认逐页的全部文字；
4. 每个选中风格各出 1 张样张，用户定稿风格。

只用用户提供的材料，不补充新事实、不编数据。每一步都等用户确认后再往下走。

## 3. 全套出图

按 [references/image-prompts.md](references/image-prompts.md) 逐页生成：每页写 `RUN/pages/NN/prompt.md`，用 `image_gen` 出图，复制到 `RUN/pages/NN/source.png`（NN 为两位页码）。定稿的样张直接放到对应页。全部页面出齐、逐页检查过再进入转换。

## 4. 逐页委派转换

每页一个子代理，**同时最多 4 个**；有一个结束就启动下一页。主代理只派任务、等结果，不自己做转换。

子代理设置：

- 模型和推理档位读 `SKILL/references/models.json` 的 `conversion`（当前 `gpt-6.1-sol` / `high`）；
- 不带主代理的聊天历史（Codex 的 `fork_turns: "none"`，以实际工具参数为准）；
- 任务名用 `ppt_page_NN`。

任务消息用下面的固定模板，只替换最后几行（开头保持完全一致，便于命中提示词缓存）：

```text
你是 PPT 单页转换子代理。先完整阅读 <SKILL>/references/worker.md，然后严格按它把下面这一页还原成可编辑 PPT。
完成后只回复一行：页码 状态 result.json 路径。
技能目录 SKILL：<SKILL 绝对路径>
页目录 PAGE：<RUN 绝对路径>/pages/NN
框架切分：否
```

用户主动要求框架切分时，把最后一行写成「框架切分：是」。

等待子代理时用较长的等待超时，不要频繁轮询。子代理报告 `blocked`（例如没有 image_gen 或 PowerPoint）时，停下来告诉用户原因并询问怎么处理，不要由主代理代做。

## 5. 合并交付

全部页面结束后，按页码顺序合并：

```
python SKILL/scripts/compose_pptx.py -o RUN/final/<主题>.pptx RUN/pages/01/layout.json RUN/pages/02/layout.json ...
```

只合并，不再做整套核对。然后读取各页 `result.json`，向用户交付：

- 最终 PPTX 的可点击绝对路径；
- 每页原图在 `RUN/pages/NN/source.png`，各页素材和 `layout.json` 也在页目录里；
- `needs_review` 的页码和具体差异（照 issues 原样转述）；
- 编辑边界：文字都是可编辑文本框；背景、框架、图标、艺术字和图表图形是图片，可以移动、缩放、替换，但图表数据不能直接编辑。
