# 作业文件批量归档脚本 (homework-archive)

一个**零依赖、纯命令行**（仅用 Python 标准库）的作业/学生文件批量整理工具，无图形界面。

## 1. 项目解决什么问题

每个学期结束时，作业文件夹里往往堆满命名混乱、类型混杂的文件，例如：

```
2023001_张三_高等数学.pdf    2023002_李四_大学英语.docx    课堂随拍.png
```

逐个手动整理既慢又容易出错：看不清都有哪些文件、文件名不统一、不同课程/学期的文件混在一起、误覆盖同名文件后悔莫及。本项目用一个命令行脚本解决这些痛点：

- **看不清** → 一键扫描列出文件名、大小、修改时间，并按扩展名过滤。
- **命名乱** → 按统一规则批量改名（如「学号_姓名_作业名」→「作业名_学号」），先预览、确认后才真正改。
- **混在一起** → 按学期或类别自动归档到子文件夹。
- **怕出错** → 重名一律跳过不覆盖、每次操作都有报告、可一键撤销上次操作。

## 2. 主要功能

| 命令 | 功能 |
|------|------|
| `scan` | 扫描文件夹，列出文件名、大小、修改时间；支持按扩展名过滤、递归子文件夹 |
| `rename` | 按规则批量改名；**默认只打印预览，需 `--yes` 确认后才真正执行**；重名冲突一律跳过、绝不覆盖 |
| `archive` | 按**学期**或**类别**把文件移动到子文件夹 |
| `report` | 生成整理报告：处理多少个、跳过多少个、为什么跳过 |
| `undo` | 撤销最近一次 `rename` / `archive` 操作（也可预览、需 `--yes` 执行） |

> 明确不支持：网页抓取、PDF 内容解析、Anki、图形界面。

## 3. 安装方法

**前提**：需要 Python 3.7 或更高版本（Windows / macOS / Linux 均可）。项目不依赖任何第三方库。

```bash
# 检查 Python 是否可用
python --version
```

**方式 A：作为命令行脚本直接用**（下载/拷贝本项目后即可运行）

```bash
git clone https://github.com/Winnie-an/homework-archive.git
cd homework-archive
```

**方式 B：作为 Agent 技能安装**（供豆包/Agent 识别与调用）

把 `homework-archive` 整个文件夹放到技能的 `workspace/.user_skills` 目录下即可；Agent 会依据 `SKILL.md` 与 `agents/openai.yaml` 在用户提出"作业/归档/批量改名/整理文件"等需求时自动调用。

安装后无需 `pip install`，可直接运行验证：

```bash
python homework-archive/scripts/homework_archive.py --help
```

## 4. 使用方法

统一命令格式：

```bash
python homework-archive/scripts/homework_archive.py <命令> --dir <文件夹> [选项]
```

### 4.1 扫描与列出（scan）

```bash
# 列出某文件夹下全部文件
python homework_archive.py scan --dir "C:/作业"

# 只看 .docx 和 .pdf
python homework_archive.py scan --dir "C:/作业" --ext .docx,.pdf

# 递归包含子文件夹
python homework_archive.py scan --dir "C:/作业" --ext .pdf --recursive
```

### 4.2 批量改名（rename，先预览、确认后才改）

改名规则用 `--parts` 指定**新名字的片段顺序索引**（0 起），`--delim` 指定分隔符（默认 `_`）。
「学号_姓名_作业名.pdf」→「作业名_学号.pdf」即 `--parts 2,0`（取第 2 个片段"作业名"+ 第 0 个片段"学号"，中间的姓名自然去掉）：

```bash
# 第一步：预览将要改成的名字（此时不会修改任何文件）
python homework_archive.py rename --dir "C:/作业" --parts 2,0

# 第二步：确认无误后，加 --yes 真正执行
python homework_archive.py rename --dir "C:/作业" --parts 2,0 --yes
```

- 片段数不符、新名与原相同、目标已存在、批次内重名 → 一律跳过并记录原因，绝不覆盖。
- 用 `--ext .pdf,.docx` 可只对指定类型改名。

### 4.3 归档（archive，按类别 / 按学期）

```bash
# 按类别：.docx → 文档/，.pdf → PDF/，.png → 图片/，.txt → 文本/ …
python homework_archive.py archive --dir "C:/作业" --mode category --yes

# 按学期：识别「2024秋 / 2024-2025-1」等归入对应子文件夹；识别不出归入 未分类/
python homework_archive.py archive --dir "C:/作业" --mode semester --yes
```

### 4.4 报告与撤销（report / undo）

```bash
# 查看最近一次操作的处理数与跳过原因
python homework_archive.py report --dir "C:/作业"

# 撤销最近一次改名/归档（先预览）
python homework_archive.py undo --dir "C:/作业"
# 确认后执行
python homework_archive.py undo --dir "C:/作业" --yes
```

报告（Markdown）与操作日志 `journal.json` 都存放在目标目录下的 `.homework_archive/` 隐藏文件夹中。

## 5. 输入输出示例

**输入**：文件夹 `C:/作业` 里有以下文件

```
2023001_张三_高等数学.pdf
2023002_李四_大学英语.docx
2023003_王五_数据结构.pdf
2024秋_程序设计作业.docx
2024-2025-1_操作系统作业.pdf
课堂随拍.png
```

**① 扫描（过滤 .pdf）**

```bash
python homework_archive.py scan --dir "C:/作业" --ext .pdf
```

输出：

```
扫描目录：C:/作业
文件数量：3（过滤扩展名：.pdf）
文件名                大小      修改时间
2023001_张三_高等数学.pdf   7 B    2026-10-05 23:06
2023003_王五_数据结构.pdf   7 B    2026-10-05 23:06
2024-2025-1_操作系统作业.pdf  7 B   2026-10-05 23:06
```

**② 批量改名（预览）**

```bash
python homework_archive.py rename --dir "C:/作业" --parts 2,0
```

输出：

```
计划改名：3 个，跳过：3 个
  2023001_张三_高等数学.pdf  ->  高等数学_2023001.pdf
  2023002_李四_大学英语.docx  ->  大学英语_2023002.docx
  2023003_王五_数据结构.pdf  ->  数据结构_2023003.pdf
跳过（无法应用规则）：
  ✗ 2024-2025-1_操作系统作业.pdf —— 分隔符「_」拆出的片段数为 2，无法应用规则 2,0
  ✗ 2024秋_程序设计作业.docx —— 分隔符「_」拆出的片段数为 2，无法应用规则 2,0
  ✗ 课堂随拍.png —— 分隔符「_」拆出的片段数为 1，无法应用规则 2,0
预览模式：未做任何修改。确认无误后，请加上 --yes 真正执行。
```

**③ 按类别归档（确认执行）**

```bash
python homework_archive.py archive --dir "C:/作业" --mode category --yes
```

输出（归档后目录结构）：

```
目录：C:/作业
归档模式：category（按类别）
计划归档：6 个文件
  [文档]  2 个
      2023002_李四_大学英语.docx
      2024秋_程序设计作业.docx
  [PDF]  3 个
      2023001_张三_高等数学.pdf
      2023003_王五_数据结构.pdf
      2024-2025-1_操作系统作业.pdf
  [图片]  1 个
      课堂随拍.png
✓ 已归档 6 个，跳过 0 个。
报告已生成：C:/作业/.homework_archive/report_20261005_230712.md
```

## 项目结构

```
作业文件批量归档/
├── README.md
└── homework-archive/                    # 技能本体
    ├── SKILL.md                         # 技能说明（供 Agent 调用）
    ├── agents/
    │   └── openai.yaml                  # 工具描述（OpenAI 风格 schema）
    └── scripts/
        └── homework_archive.py          # 核心脚本（仅标准库）
```

## 安全设计

- 改名 / 归档 / 撤销默认只预览、不写盘，需显式加 `--yes`。
- 重名冲突一律跳过、绝不覆盖已有文件。
- 每次写盘操作写入操作日志，可用 `undo` 回滚最近一次操作。
- 报告可审计：记录处理数、跳过数及每个跳过原因。

## 许可

MIT License
