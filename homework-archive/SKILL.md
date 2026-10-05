---
name: homework-archive
description: "作业文件批量归档脚本（homework-archive / 作业文件批量整理）。在用户要求批量整理、扫描、重命名、归档作业/学生文件时使用，例如「帮我把作业按学期归档」「按规则批量改文件名」「列出文件夹里所有 PDF 作业」。提供扫描列出（大小/修改时间、扩展名过滤）、按规则批量改名（先预览确认、重名不覆盖）、按学期或类别归档、生成整理报告、撤销上次操作五大能力。纯命令行、无图形界面，不处理网页抓取/PDF 解析/Anki。触发词：作业、归档、批量改名、整理文件、扫描文件、撤销改名。"
license: MIT
---

# 作业文件批量归档脚本 (homework-archive)

一个零依赖、纯 Python 标准库的命令行小工具，用于批量整理作业/学生文件。
脚本位置：`scripts/homework_archive.py`，直接 `python homework_archive.py <命令>` 运行。

## 何时使用

- 用户想查看一个文件夹里都有哪些作业文件（列出文件名、大小、修改时间）。
- 用户想按统一规则批量改名，例如「学号_姓名_作业名.pdf」→「作业名_学号.pdf」。
- 用户想按学期或类别把文件移动（归档）到子文件夹。
- 用户想知道上次整理处理了多少、跳过了多少、为什么跳过，或想撤销上次操作。

## 核心原则（务必遵守）

1. **改名 / 归档 / 撤销一律先预览**。脚本默认只打印「将要发生的变化」，绝不直接改文件。
   只有用户明确确认后，才追加 `--yes` 真正执行。
2. **绝不覆盖已有文件**。目标重名或批次内重名都会跳过并记录原因。
3. **所有写盘操作都写入操作日志**，可通过 `undo` 回滚。
4. 脚本只处理文件，不处理目录本身；自动跳过 `.homework_archive/` 元数据目录。

## 使用工作流

### 命令总览

```
python scripts/homework_archive.py <命令> --dir <文件夹> [选项]

scan     扫描并列出文件（大小、修改时间），支持扩展名过滤
rename   按规则批量改名（默认预览，需 --yes 执行）
archive  按学期或类别归档到子文件夹（默认预览，需 --yes 执行）
report   查看最近一次操作的处理报告
undo     撤销最近一次 rename / archive 操作（默认预览，需 --yes 执行）
```

### 1. 扫描与列出

```bash
# 列出某文件夹下全部文件
python homework_archive.py scan --dir "C:/作业"

# 只看 .docx 和 .pdf
python homework_archive.py scan --dir "C:/作业" --ext .docx,.pdf

# 递归包含子文件夹
python homework_archive.py scan --dir "C:/作业" --ext .pdf --recursive
```

### 2. 批量改名（预览 → 确认）

改名规则用 `--parts` 指定**新名字的片段顺序索引**（0 起），用 `--delim` 指定分隔符（默认 `_`）。

示例：「学号_姓名_作业名.pdf」→「作业名_学号.pdf」

```bash
# 第一步：预览将要改成的名字（不会真正修改）
python homework_archive.py rename --dir "C:/作业" --parts 2,0

# 第二步：用户确认后，加 --yes 真正执行
python homework_archive.py rename --dir "C:/作业" --parts 2,0 --yes
```

说明：
- `--parts 2,0`：新文件名 = 原第 2 个片段（作业名）`_` 原第 0 个片段（学号），原第 1 个片段（姓名）自然被去掉。
- 片段数不符、新名与原相同、目标已存在、批次内重名 → 一律跳过并记录原因。
- 用 `--ext` 可只对指定类型改名。

### 3. 归档（预览 → 确认）

```bash
# 按类别：.docx → 文档/，.pdf → PDF/，.png → 图片/ 等
python homework_archive.py archive --dir "C:/作业" --mode category --yes

# 按学期：从文件名识别「2024秋 / 2024-2025-1」等并归入对应子文件夹
python homework_archive.py archive --dir "C:/作业" --mode semester --yes
```

- 按类别：`文档/ PDF/ 演示文稿/ 表格/ 图片/ 压缩包/ 文本/`，未知类型用扩展名大写命名。
- 按学期：识别 `20xx春/秋/夏/冬`、`20xx-20xx-1/2`；识别不出归入 `未分类/`。

### 4. 报告与撤销

```bash
# 查看最近一次操作的处理数与跳过原因
python homework_archive.py report --dir "C:/作业"

# 撤销上次操作（先预览）
python homework_archive.py undo --dir "C:/作业"
# 确认后执行
python homework_archive.py undo --dir "C:/作业" --yes
```

报告是 Markdown 文件，存放在目标目录 `.homework_archive/` 下；操作日志 `journal.json` 也存放在那里。

## 已明确不支持

- 网页抓取 / 爬虫
- PDF 内容解析、OCR
- Anki 卡片生成
- 图形界面（纯命令行）

## 安全与可审计性

- 默认只预览、不写盘；写盘需 `--yes`。
- 冲突一律跳过、绝不覆盖。
- 每次写盘记录日志，`undo` 可回滚最近一次操作。
- 报告可审计：记录处理数、跳过数及每个跳过原因。
