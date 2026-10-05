#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""homework_archive.py 的单元测试（仅用标准库 unittest，无第三方依赖）。"""

import sys
import unittest
from pathlib import Path

# 让测试能 import 到脚本
SCRIPTS = Path(__file__).resolve().parent.parent / "homework-archive" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import homework_archive as ha  # noqa: E402


class TestDetectSemester(unittest.TestCase):
    """学期识别规则测试。"""

    def test_year_year_term(self):
        self.assertEqual(
            ha._detect_semester("2024-2025-1_操作系统作业.pdf"),
            "2024-2025学年第1学期",
        )

    def test_season(self):
        self.assertEqual(
            ha._detect_semester("2024秋_程序设计作业.docx"),
            "2024年秋季学期",
        )

    def test_year_only(self):
        # 学号串里的 2023 应归为年份
        self.assertEqual(
            ha._detect_semester("2023001_张三_高等数学.pdf"),
            "2023年",
        )

    def test_no_semester(self):
        self.assertIsNone(ha._detect_semester("课堂随拍.png"))


class TestParseExts(unittest.TestCase):
    """扩展名过滤参数解析。"""

    def test_basic(self):
        self.assertEqual(ha._parse_exts(".docx,.PDF"), [".docx", ".pdf"])

    def test_need_dot(self):
        # 不带点时自动补点并小写
        self.assertEqual(ha._parse_exts("pdf"), [".pdf"])

    def test_empty(self):
        self.assertIsNone(ha._parse_exts(""))


class TestHumanSize(unittest.TestCase):
    """文件大小格式化。"""

    def test_bytes(self):
        self.assertEqual(ha._human_size(7), "7 B")

    def test_kb(self):
        out = ha._human_size(2048)
        self.assertIn("KB", out)


class TestParser(unittest.TestCase):
    """命令行参数解析。"""

    def test_scan(self):
        args = ha.build_parser().parse_args(["scan", "--dir", "/tmp", "--ext", ".pdf"])
        self.assertEqual(args.command, "scan")
        self.assertEqual(args.ext, ".pdf")
        self.assertFalse(args.recursive)

    def test_rename_parts(self):
        args = ha.build_parser().parse_args(
            ["rename", "--dir", "/tmp", "--parts", "2,0"]
        )
        self.assertEqual(args.parts, "2,0")
        self.assertFalse(args.yes)

    def test_archive_mode(self):
        args = ha.build_parser().parse_args(
            ["archive", "--dir", "/tmp", "--mode", "semester"]
        )
        self.assertEqual(args.mode, "semester")

    def test_default_delim(self):
        args = ha.build_parser().parse_args(
            ["rename", "--dir", "/tmp", "--parts", "2,0"]
        )
        self.assertEqual(args.delim, "_")


if __name__ == "__main__":
    unittest.main()
