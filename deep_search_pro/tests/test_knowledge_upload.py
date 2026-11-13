import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from rawflow.knowledge_demo import upload_file_to_knowledge


class KnowledgeUploadTests(unittest.TestCase):
    def test_upload_uses_dataset_api_and_starts_parsing(self):
        client = Mock()
        dataset = Mock()
        client.list_datasets.return_value = [dataset]
        dataset.upload_documents.return_value = [SimpleNamespace(id="doc-1")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "知识.txt"
            path.write_text("内容", encoding="utf-8")
            with patch("rawflow.knowledge_demo._get_ragflow_client", return_value=client):
                documents = upload_file_to_knowledge("kb-1", [path])
        client.list_datasets.assert_called_once_with(id="kb-1")
        self.assertEqual(dataset.upload_documents.call_args.args[0][0]["blob"], "内容".encode())
        dataset.async_parse_documents.assert_called_once_with(["doc-1"])
        self.assertEqual(documents[0].id, "doc-1")

    def test_missing_dataset_has_clear_error(self):
        client = Mock()
        client.list_datasets.return_value = []
        with patch("rawflow.knowledge_demo._get_ragflow_client", return_value=client):
            with self.assertRaisesRegex(ValueError, "知识库不存在"):
                upload_file_to_knowledge("missing", [])

    def test_upload_can_store_documents_before_models_are_configured(self):
        client = Mock()
        dataset = Mock()
        client.list_datasets.return_value = [dataset]
        dataset.upload_documents.return_value = [SimpleNamespace(id="doc-1")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manual.txt"
            path.write_text("documentation", encoding="utf-8")
            with patch("rawflow.knowledge_demo._get_ragflow_client", return_value=client):
                upload_file_to_knowledge("kb-1", [path], parse=False)
        dataset.async_parse_documents.assert_not_called()
