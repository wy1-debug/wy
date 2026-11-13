import tempfile
import unittest
from pathlib import Path

import pandas as pd
from api.context import set_session_context, reset_session_context
from tools.upload_file_read_tool import read_file_content


class FileReaderTests(unittest.TestCase):
    def test_excel_includes_every_sheet(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "multi.xlsx"
            with pd.ExcelWriter(path) as writer:
                pd.DataFrame({"数量": [2]}).to_excel(writer, sheet_name="库存", index=False)
                pd.DataFrame({"客户": ["测试客户"]}).to_excel(writer, sheet_name="销售", index=False)
            token = set_session_context(directory)
            try:
                result = read_file_content.invoke({"filename": "multi.xlsx"})
            finally:
                reset_session_context(token)
        self.assertIn("工作表: 库存", result)
        self.assertIn("工作表: 销售", result)
        self.assertIn("测试客户", result)

    def test_utf8_bom_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "bom.txt").write_text("文本", encoding="utf-8-sig")
            token = set_session_context(directory)
            try:
                result = read_file_content.invoke({"filename": "bom.txt"})
            finally:
                reset_session_context(token)
        self.assertEqual(result, "文本")
