#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
作业文件批量归档脚本 (homework_archive.py)

一个面向作业文件批量整理的小工具，纯命令行、无图形界面，仅依赖 Python 标准库。
支持三种核心操作 + 报告 + 撤销：

  1. scan    —— 扫描指定文件夹，列出文件及其大小、修改时间，支持按扩展名过滤。
  2. rename  —— 按规则批量改名（如「学号_姓名_作业名.pdf」→「作业名_学号.pdf」）。
                 默认只打印预览（将要改成的名字），必须加 --yes 才真正执行；
                 出现重名冲突时跳过并记录原因，绝不覆盖已有文件。
  3. archive —— 按学期或类别把文件移动到子文件夹。
  4. report  —— 查看最近一次操作的处理报告。
  5. undo    —— 撤销最近一次 rename / archive 操作（依据操作日志回滚）。

设计要点
--------
- 安全优先：改名 / 归档默认只预览，需显式确认才写盘；遇到目标重名一律跳过，不覆盖。
- 可撤销：每次写盘操作都会把「旧路径 -> 新路径」记录到日志，undo 按逆序回滚。
- 零依赖：只使用 Python 标准库，Windows / macOS / Linux 通用。
- 报告可审计：每次操作会生成一份 Markdown 报告（处理数、跳过数、跳过原因明细）。
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 操作日志与报告存放在目标目录下的隐藏子目录
META_DIR = ".homework_archive"
JOURNAL_FILE = "journal.json"
REPORT_PREFIX = "report_"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _meta_dir(base: Path) -> Path:
    """操作日志 / 报告的存放目录。"""
    return base / META_DIR


def _load_journal(base: Path) -> list:
    """读取操作日志；不存在或损坏时返回空列表。"""
    jf = _meta_dir(base) / JOURNAL_FILE
    if not jf.exists():
        return []
    try:
        data = json.loads(jf.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_journal(base: Path, journal: list) -> None:
    """写入操作日志。"""
    md = _meta_dir(base)
    md.mkdir(parents=True, exist_ok=True)
    jf = md / JOURNAL_FILE
    jf.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_report(base: Path, op_id: str, title: str, lines: list) -> Path:
    """生成一份 Markdown 报告文件，并返回其路径。"""
    md = _meta_dir(base)
    md.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = md / f"{REPORT_PREFIX}{op_id}.md"
    body = [f"# {title}", "", f"- 操作时间：{stamp}", f"- 操作目录：{base}", ""]
    body += lines
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def _human_size(n: int) -> str:
    """把字节数转成易读的 KB / MB。"""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} GB"


def _collect_files(base: Path, exts, recursive: bool) -> list:
    """
    收集目标目录下的文件（不含隐藏的元数据目录）。
    返回 (path, size, mtime) 三元组列表，按文件名排序。
    """
    it = base.rglob("*") if recursive else base.iterdir()
    results = []
    for p in it:
        try:
            if not p.is_file():
                continue
        except OSError:
            continue
        # 跳过元数据目录内部文件
        if META_DIR in p.parts:
            continue
        if exts and p.suffix.lower() not in exts:
            continue
        try:
            st = p.stat()
            results.append((p, st.st_size, st.st_mtime))
        except OSError:
            continue
    results.sort(key=lambda x: x[0].name.lower())
    return results


def _split_parts(stem: str, delim: str):
    """按分隔符切分文件名主干，返回各部分列表。"""
    return stem.split(delim)


# ---------------------------------------------------------------------------
# 子命令：scan
# ---------------------------------------------------------------------------
def cmd_scan(args) -> int:
    base = Path(args.dir).resolve()
    if not base.is_dir():
        print(f"错误：目录不存在：{base}")
        return 1
    exts = _parse_exts(args.ext)
    files = _collect_files(base, exts, args.recursive)

    print(f"扫描目录：{base}")
    print(f"文件数量：{len(files)}" + (f"（过滤扩展名：{', '.join(exts)}）" if exts else "（全部文件）"))
    print("-" * 60)
    print(f"{'文件名':<40}{'大小':>12}{'修改时间':>22}")
    print("-" * 60)
    for p, size, mtime in files:
        ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        print(f"{p.name:<40}{_human_size(size):>12}{ts:>22}")
    return 0


# ---------------------------------------------------------------------------
# 子命令：rename
# ---------------------------------------------------------------------------
def cmd_rename(args) -> int:
    base = Path(args.dir).resolve()
    if not base.is_dir():
        print(f"错误：目录不存在：{base}")
        return 1

    # 解析改名规则：--parts "2,0" 表示新名字按原第 2、第 0 个片段拼接
    try:
        parts = [int(x) for x in args.parts.split(",") if x.strip() != ""]
    except ValueError:
        print("错误：--parts 必须是用逗号分隔的数字索引，例如 --parts 2,0")
        return 1
    if not parts:
        print("错误：--parts 不能为空")
        return 1

    exts = _parse_exts(args.ext)
    files = _collect_files(base, exts, args.recursive)

    # 构造计划：原路径 -> 新路径；同时检测重名冲突
    plan = []          # [(old, new)]
    conflicts = []     # 因目标重名而跳过的文件
    unmatched = []     # 因片段数不符规则而跳过的文件
    used_names = {}    # 记录本批次内已占用的新名字，防止批次内互相覆盖

    for p, _, _ in files:
        stem = p.stem
        ext = p.suffix
        chunks = _split_parts(stem, args.delim)
        # 规则要求用到的最大索引必须在片段范围内
        if any(i >= len(chunks) for i in parts):
            unmatched.append((p, f"分隔符「{args.delim}」拆出的片段数为 {len(chunks)}，无法应用规则 {args.parts}"))
            continue
        new_stem = args.delim.join(chunks[i] for i in parts)
        new_name = new_stem + ext
        new_path = p.with_name(new_name)

        if new_path == p:
            unmatched.append((p, "新名字与原名字相同，无需改名"))
            continue
        # 目标已存在（且不是本次计划改名的同一个文件）——不覆盖
        if new_path.exists() and new_path not in [o for o, _ in plan]:
            conflicts.append((p, new_path, f"目标文件已存在：{new_name}"))
            continue
        # 批次内已被其他文件占用——不覆盖
        if new_name.lower() in used_names:
            conflicts.append((p, new_path, f"与同批次文件重名：{new_name}"))
            continue
        used_names[new_name.lower()] = p
        plan.append((p, new_path))

    # 打印预览
    print(f"目录：{base}")
    print(f"规则：按片段索引 {parts} 重新排序（分隔符「{args.delim}」）")
    print(f"计划改名：{len(plan)} 个，跳过：{len(unmatched) + len(conflicts)} 个")
    print("-" * 60)
    for old, new in plan:
        print(f"  {old.name}  ->  {new.name}")
    if unmatched:
        print("-" * 60)
        print("跳过（无法应用规则）：")
        for p, reason in unmatched:
            print(f"  ✗ {p.name} —— {reason}")
    if conflicts:
        print("-" * 60)
        print("跳过（重名冲突，绝不覆盖）：")
        for p, newp, reason in conflicts:
            print(f"  ✗ {p.name} -> {newp.name} —— {reason}")

    if not args.yes:
        print("-" * 60)
        print("预览模式：未做任何修改。确认无误后，请加上 --yes 真正执行。")
        return 0

    # 确认模式：真正执行
    if not plan:
        print("没有需要改名的文件，已退出。")
        return 0

    op_id = _new_op_id()
    moved = []
    for old, new in plan:
        try:
            # 再次保险检查：目标在写盘前仍不存在才执行
            if new.exists():
                print(f"✗ 已跳过（写盘前目标已存在）：{new.name}")
                continue
            old.rename(new)
            moved.append({"old": str(old), "new": str(new)})
        except OSError as e:
            print(f"✗ 改名失败：{old.name} —— {e}")

    journal = _load_journal(base)
    journal.append({
        "op_id": op_id,
        "type": "rename",
        "time": datetime.now().isoformat(timespec="seconds"),
        "files": moved,
    })
    _save_journal(base, journal)

    report_lines = [
        "## 结果",
        "",
        f"- 处理（已改名）：{len(moved)} 个",
        f"- 跳过：{len(unmatched) + len(conflicts)} 个",
        "",
        "### 改名明细",
        "",
    ]
    for item in moved:
        report_lines.append(f"- `{item['old']}` → `{item['new']}`")
    report_lines += ["", "### 跳过明细", ""]
    for p, reason in unmatched:
        report_lines.append(f"- {p.name} —— {reason}")
    for p, newp, reason in conflicts:
        report_lines.append(f"- {p.name}（目标 {newp.name}）—— {reason}")
    report_path = _write_report(base, op_id, "批量改名报告", report_lines)

    print("-" * 60)
    print(f"✓ 已改名 {len(moved)} 个，跳过 {len(unmatched) + len(conflicts)} 个。")
    print(f"报告已生成：{report_path}")
    print(f"如需撤销本次操作，请运行：python homework_archive.py undo --dir \"{base}\"")
    return 0


# ---------------------------------------------------------------------------
# 子命令：archive
# ---------------------------------------------------------------------------
_SEMESTER_PATTERNS = [
    # 学年-学期：2024-2025-1 / 2024-2025/1 / 2024-2025学年第1学期
    re.compile(r"(20\d{2})[-/](20\d{2})[-/]?([12])"),
    # 季节学期：2024秋 / 2024年秋 / 2024年秋季学期 / 2024春季
    re.compile(r"(20\d{2})[-\s年]*(春|秋|夏|冬)"),
    # 仅年份：2024 → 2024年
    re.compile(r"(20\d{2})"),
]

_CATEGORY_NAMES = {
    ".docx": "文档",
    ".doc": "文档",
    ".pdf": "PDF",
    ".pptx": "演示文稿",
    ".ppt": "演示文稿",
    ".xlsx": "表格",
    ".xls": "表格",
    ".png": "图片",
    ".jpg": "图片",
    ".jpeg": "图片",
    ".gif": "图片",
    ".zip": "压缩包",
    ".rar": "压缩包",
    ".txt": "文本",
}


def _detect_semester(name: str):
    """从文件名中识别学期，返回规范化字符串；识别不到返回 None。"""
    for pat in _SEMESTER_PATTERNS:
        m = pat.search(name)
        if m:
            g = m.groups()
            year = g[0]
            if len(g) >= 3 and g[1] and g[2]:
                return f"{year}-{g[1]}学年第{g[2]}学期"
            if len(g) >= 2 and g[1]:
                return f"{year}年{g[1]}季学期"
            return f"{year}年"
    return None


def cmd_archive(args) -> int:
    base = Path(args.dir).resolve()
    if not base.is_dir():
        print(f"错误：目录不存在：{base}")
        return 1
    if args.mode not in ("category", "semester"):
        print("错误：--mode 必须是 category 或 semester")
        return 1

    exts = _parse_exts(args.ext)
    files = _collect_files(base, exts, args.recursive)

    # 计算每个文件的归类目标
    plan = []      # [(old, dest_dir, target_path)]
    skipped = []   # [(old, reason)]
    for p, _, _ in files:
        if args.mode == "category":
            folder = _CATEGORY_NAMES.get(p.suffix.lower(), p.suffix.lstrip(".").upper() or "其他")
        else:
            folder = _detect_semester(p.name)
            if folder is None:
                folder = "未分类"
        dest_dir = base / folder
        plan.append((p, dest_dir, dest_dir / p.name))

    # 预览
    print(f"目录：{base}")
    print(f"归档模式：{args.mode}（{'按类别' if args.mode == 'category' else '按学期'}）")
    print(f"计划归档：{len(plan)} 个文件")
    print("-" * 60)
    by_folder = {}
    for p, d, _ in plan:
        by_folder.setdefault(d.name, []).append(p)
    for folder, flist in sorted(by_folder.items()):
        print(f"  [{folder}]  {len(flist)} 个")
        for p in flist:
            print(f"      {p.name}")
    if not args.yes:
        print("-" * 60)
        print("预览模式：未做任何移动。确认无误后，请加上 --yes 真正执行。")
        return 0

    if not plan:
        print("没有需要归档的文件，已退出。")
        return 0

    op_id = _new_op_id()
    moved = []
    for p, dest_dir, target in plan:
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            if target.exists():
                skipped.append((p, f"目标已存在：{target.name}（未覆盖）"))
                print(f"✗ 跳过（目标已存在，不覆盖）：{p.name}")
                continue
            shutil.move(str(p), str(target))
            moved.append({"old": str(p), "new": str(target)})
        except OSError as e:
            skipped.append((p, f"移动失败：{e}"))
            print(f"✗ 归档失败：{p.name} —— {e}")

    journal = _load_journal(base)
    journal.append({
        "op_id": op_id,
        "type": "archive",
        "mode": args.mode,
        "time": datetime.now().isoformat(timespec="seconds"),
        "files": moved,
    })
    _save_journal(base, journal)

    report_lines = [
        "## 结果",
        "",
        f"- 处理（已归档）：{len(moved)} 个",
        f"- 跳过：{len(skipped)} 个",
        "",
        "### 归档明细",
        "",
    ]
    for item in moved:
        report_lines.append(f"- `{item['old']}` → `{item['new']}`")
    if skipped:
        report_lines += ["", "### 跳过明细", ""]
        for p, reason in skipped:
            report_lines.append(f"- {p.name} —— {reason}")
    report_path = _write_report(base, op_id, "归档整理报告", report_lines)

    print("-" * 60)
    print(f"✓ 已归档 {len(moved)} 个，跳过 {len(skipped)} 个。")
    print(f"报告已生成：{report_path}")
    print(f"如需撤销本次操作，请运行：python homework_archive.py undo --dir \"{base}\"")
    return 0


# ---------------------------------------------------------------------------
# 子命令：report
# ---------------------------------------------------------------------------
def cmd_report(args) -> int:
    base = Path(args.dir).resolve()
    if not base.is_dir():
        print(f"错误：目录不存在：{base}")
        return 0
    journal = _load_journal(base)
    if not journal:
        print("没有找到任何操作记录。")
        return 0
    print(f"操作日志（共 {len(journal)} 条，最近的在最下方）：")
    print("-" * 60)
    for entry in journal:
        kind = "改名" if entry.get("type") == "rename" else "归档"
        print(f"  [{entry.get('time')}] {kind} —— 处理 {len(entry.get('files', []))} 个")
    print("-" * 60)
    reports = sorted(_meta_dir(base).glob(f"{REPORT_PREFIX}*.md"), reverse=True)
    if reports:
        print(f"最近报告：{reports[0]}")
    return 0


# ---------------------------------------------------------------------------
# 子命令：undo
# ---------------------------------------------------------------------------
def cmd_undo(args) -> int:
    base = Path(args.dir).resolve()
    if not base.is_dir():
        print(f"错误：目录不存在：{base}")
        return 1
    journal = _load_journal(base)
    if not journal:
        print("没有可撤销的操作。")
        return 0
    last = journal[-1]
    files = last.get("files", [])
    if not files:
        print("最近一条操作没有可回滚的文件记录。")
        return 0

    kind = "改名" if last.get("type") == "rename" else "归档"
    print(f"准备撤销最近一次【{kind}】操作（{last.get('time')}），涉及 {len(files)} 个文件：")
    print("-" * 60)
    for item in files:
        print(f"  {item['new']}  <-  {item['old']}")

    if not args.yes:
        print("-" * 60)
        print("预览模式：未做任何回滚。确认无误后，请加上 --yes 真正执行撤销。")
        return 0

    restored, failed = 0, 0
    # 逆序回滚，避免路径依赖
    for item in reversed(files):
        new = Path(item["new"])
        old = Path(item["old"])
        try:
            if not new.exists():
                print(f"✗ 回滚失败（目标不存在）：{new}")
                failed += 1
                continue
            if old.exists():
                print(f"✗ 回滚跳过（原路径已存在，不覆盖）：{old}")
                failed += 1
                continue
            old.parent.mkdir(parents=True, exist_ok=True)
            new.rename(old)
            restored += 1
        except OSError as e:
            print(f"✗ 回滚失败：{new.name} —— {e}")
            failed += 1

    # 从日志中移除已撤销的记录
    journal.pop()
    _save_journal(base, journal)

    print("-" * 60)
    print(f"✓ 已回滚 {restored} 个，失败 {failed} 个。")
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def _new_op_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _parse_exts(text):
    """把用户输入的扩展名列表转成小写且带点的集合；为空则返回 None（不过滤）。"""
    if not text:
        return None
    exts = []
    for raw in text.split(","):
        raw = raw.strip().lower()
        if not raw:
            continue
        if not raw.startswith("."):
            raw = "." + raw
        exts.append(raw)
    return exts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homework_archive.py",
        description="作业文件批量归档脚本：扫描 / 批量改名 / 归档 / 报告 / 撤销",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = sub.add_parser("scan", help="扫描并列出文件（大小、修改时间）")
    p_scan.add_argument("--dir", required=True, help="要扫描的文件夹")
    p_scan.add_argument("--ext", default="", help="扩展名过滤，逗号分隔，如 .docx,.pdf")
    p_scan.add_argument("--recursive", action="store_true", help="递归包含子文件夹")
    p_scan.set_defaults(func=cmd_scan)

    # rename
    p_rename = sub.add_parser("rename", help="按规则批量改名（默认预览，需 --yes 执行）")
    p_rename.add_argument("--dir", required=True, help="目标文件夹")
    p_rename.add_argument("--parts", required=True, help="新名字的片段顺序索引，逗号分隔，如 2,0")
    p_rename.add_argument("--delim", default="_", help="文件名分隔符（默认 _）")
    p_rename.add_argument("--ext", default="", help="扩展名过滤，逗号分隔")
    p_rename.add_argument("--recursive", action="store_true", help="递归包含子文件夹")
    p_rename.add_argument("--yes", action="store_true", help="确认执行（不加则仅预览）")
    p_rename.set_defaults(func=cmd_rename)

    # archive
    p_arc = sub.add_parser("archive", help="按学期或类别移动到子文件夹（默认预览，需 --yes 执行）")
    p_arc.add_argument("--dir", required=True, help="目标文件夹")
    p_arc.add_argument("--mode", required=True, choices=["category", "semester"],
                       help="category=按类别；semester=按学期")
    p_arc.add_argument("--ext", default="", help="扩展名过滤，逗号分隔")
    p_arc.add_argument("--recursive", action="store_true", help="递归包含子文件夹")
    p_arc.add_argument("--yes", action="store_true", help="确认执行（不加则仅预览）")
    p_arc.set_defaults(func=cmd_archive)

    # report
    p_rep = sub.add_parser("report", help="查看最近一次操作的处理报告")
    p_rep.add_argument("--dir", required=True, help="目标文件夹")
    p_rep.set_defaults(func=cmd_report)

    # undo
    p_undo = sub.add_parser("undo", help="撤销最近一次改名 / 归档操作（默认预览，需 --yes 执行）")
    p_undo.add_argument("--dir", required=True, help="目标文件夹")
    p_undo.add_argument("--yes", action="store_true", help="确认执行撤销（不加则仅预览）")
    p_undo.set_defaults(func=cmd_undo)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
