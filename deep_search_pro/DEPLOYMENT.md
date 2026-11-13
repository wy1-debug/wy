# DeepSearch Pro 本地部署

## 访问入口

- 项目前端：<http://127.0.0.1:8000>
- RAGFlow 管理界面：<http://127.0.0.1:8080>
- RAGFlow API：<http://127.0.0.1:9380>
- 本地登录账号及随机密码：`deploy/ragflow/local-account.json`。此文件包含凭据，已加入忽略规则，请仅在本机查看。
- 默认知识库：`DeepSearch 本地知识库`。模型密钥按用户要求留待后续配置。

## 数据位置（D 盘）

所有项目文件位于 `D:\pythonProject\deep_search_pro`。

| 内容 | 项目内相对目录 |
| --- | --- |
| Docker 编排与服务配置 | `deploy/ragflow/` |
| Elasticsearch 索引 | `deploy/ragflow/data/elasticsearch/` |
| MySQL 元数据 | `deploy/ragflow/data/mysql/` |
| MinIO 原始知识库文件 | `deploy/ragflow/data/minio/` |
| Redis 数据 | `deploy/ragflow/data/redis/` |
| RAGFlow 日志 | `deploy/ragflow/data/logs/` |
| 聊天附件 | `updated/session_<会话ID>/` |
| 当前会话工作文件与报告 | `output/session_<会话ID>/` |

以上服务均使用绑定目录挂载，数据不放在匿名 Docker 卷中。
Docker Desktop 本身的 Linux 镜像磁盘仍在 `C:\Users\86153\AppData\Local\Docker\wsl\disk\docker_data.vhdx`。
本次没有移动 Docker 全局虚拟磁盘，以免影响已有镜像；如需连镜像一起迁移，应在 Docker Desktop 的磁盘位置设置中完成迁移，不能直接移动运行中的 VHDX 文件。

## 启动与停止

先启动 Docker Desktop。在项目目录打开 PowerShell：

```powershell
docker compose -f deploy/ragflow/compose.yaml up -d
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```

也可以执行 `./start-project.ps1`。如果 8000 端口已有本项目后端，请使用现有进程；修改 `.env` 后需重启后端。

检查容器：

```powershell
docker compose -f deploy/ragflow/compose.yaml ps
docker compose -f deploy/ragflow/compose.yaml logs --tail 100 ragflow
```

停止容器（保留 D 盘数据）：

```powershell
docker compose -f deploy/ragflow/compose.yaml stop
```

部署固定使用 RAGFlow `v0.26.0`，包含 Elasticsearch、MySQL、MinIO、Redis 兼容缓存和 RAGFlow 主服务。
管理界面和 API 仅绑定本机 `127.0.0.1`；存储与数据库端口不暴露到宿主机。

## 稍后配置模型

1. 在项目 `.env` 中更新有效的 `OPENAI_API_KEY`，核对 `OPENAI_BASE_URL` 和 `LLM_MODEL`。
2. 登录 RAGFlow，在模型供应商设置中添加百炼/Tongyi-Qianwen 的有效密钥，并选择聊天模型及 `text-embedding-v3` 嵌入模型。
3. 在 RAGFlow 默认模型设置中选中对应模型，并在 `DeepSearch 本地知识库` 中选择嵌入模型。
4. 对已上传文档启动解析；等待解析完成后，再创建关联该知识库的聊天助手。项目里的“RAGFlow 助手”会从服务查询可用助手列表。
5. 重启项目后端，在项目中测试“查询内部知识库”。

Python 当前采用“进程环境变量优先于 `.env`”的加载方式。此次验证发现进程中的 `OPENAI_API_KEY` 与 `.env` 不同：聊天附件测试可以完成，但 `.env` 中的旧百炼密钥单独测试返回 401。后续请核对实际使用的配置来源。
RAGFlow 供应商密钥保存在它自己的服务中，不会自动读取项目聊天模型密钥。

项目 `.env` 中 `RAGFLOW_API_URL`、`RAGFLOW_API_KEY` 和 `RAGFLOW_DATASET_ID` 已由初始化脚本指向本地服务；原文件备份为 `.env.before-local-ragflow`。

如果恢复了干净的新实例，可运行：

```powershell
python deploy/ragflow/bootstrap.py
```

该脚本创建/复用本地账号、API Key 和空知识库，不调用聊天或嵌入模型，不会在终端打印密码。

## 附件与知识库上传的区别

- 项目聊天窗口的“上传”只添加当前会话附件。选择文件后点击“发送”；不输入问题时，系统自动使用“请读取并总结我上传的文件”。
- 长期知识库文档应从“知识库管理”入口上传，在配置模型后启动解析。
- 聊天附件每个最多 50 MB，每次最多 20 个。支持 txt、md、csv、json、yaml、docx、pdf、xlsx、xls。
- 同名附件自动加编号，不覆盖原文件。空文件、不支持的类型和非法会话 ID 会得到明确错误。
- 扫描 PDF 的直接附件读取需要先 OCR；解析器无法抽取文本时会明确提示。

## 本次修复

- 修复仅选择附件时发送无反应。
- 修复 RAGFlow 上传示例调用不存在的 `upload_file()` 方法；改用 dataset 上传接口，并支持控制是否启动解析。
- 修复上传过程中切换会话、修改待上传列表造成的状态竞争。
- WebSocket 必须成功连接后才能启动任务；连接失败时保留问题和附件以便重试。
- 上传使用临时文件和异步分块写入，失败不留下半截附件，同名文件保留。
- 增加会话 ID 和文件名验证；API 上传服务不再依赖启动时立即导入完整模型。
- 补充 `.xls` 所需的 `xlrd`；Excel 读取覆盖全部工作表。

## 验证命令

```powershell
python -m unittest discover -s tests -v
python -m compileall -q api agent rawflow tools utils deploy/ragflow/bootstrap.py
node --check frontend/app.js
```

浏览器上传验证使用了明确标记为测试内容的 `upload-check.txt`，结果保留在测试会话中。
模型配置完成前，本地知识库文档保持未解析状态，不把文件保存成功当作检索已经可用。
