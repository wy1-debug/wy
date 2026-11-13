import logging
from pathlib import Path

try:
    import markdown as markdown_lib
except ImportError:
    markdown_lib = None

try:
    import pythoncom
    import win32com.client as win32_client
except ImportError:
    pythoncom = None
    win32_client = None


def convert_md_to_pdf_via_word(md_abs_path: Path, pdf_abs_path: Path) -> str:
    """
    Convert Markdown to PDF through Microsoft Word COM.
    This requires Windows, Microsoft Word, pywin32, and markdown.
    """
    if markdown_lib is None:
        return "缺少 markdown 依赖，请安装 markdown 后再转换 PDF。"
    if pythoncom is None or win32_client is None:
        return "缺少 pywin32 或当前环境不支持 Word COM，无法转换 PDF。"

    temp_html_path = md_abs_path.with_suffix(".temp.html")
    word_app = None
    doc = None

    try:
        md_content = md_abs_path.read_text(encoding="utf-8")
        html_body = markdown_lib.markdown(md_content, extensions=["tables", "fenced_code"])
        html_content = f"""
<!doctype html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: "Microsoft YaHei", "SimHei", sans-serif; line-height: 1.6; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #999; padding: 8px; }}
    pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 4px; }}
    code {{ font-family: Consolas, Monaco, monospace; }}
  </style>
</head>
<body>
{html_body}
</body>
</html>
"""
        temp_html_path.write_text(html_content, encoding="utf-8")

        pythoncom.CoInitialize()
        word_app = win32_client.Dispatch("Word.Application")
        word_app.Visible = False
        word_app.DisplayAlerts = False

        doc = word_app.Documents.Open(str(temp_html_path.resolve()))
        doc.SaveAs(str(pdf_abs_path.resolve()), FileFormat=17)

        if pdf_abs_path.exists():
            return f"PDF 文件已生成: {pdf_abs_path.name}"
        return f"转换完成，但未找到生成的 PDF 文件: {pdf_abs_path}"
    except Exception as exc:
        logging.error("Word 转换 PDF 失败: %s", exc, exc_info=True)
        return f"转换 PDF 失败: {exc}"
    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=0)
            except Exception:
                pass
        if word_app is not None:
            try:
                word_app.Quit()
            except Exception:
                pass
        if temp_html_path.exists():
            try:
                temp_html_path.unlink()
            except Exception:
                pass
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
