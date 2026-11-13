# LLM Customer Service

基于自研对话框架 `atguigu_ai` 构建的电商智能客服系统 Demo。整条链路打通了
「大模型意图理解 → 业务流程编排 → MySQL 业务数据查询 → Neo4j 知识图谱检索（GraphRAG）→ 回复生成」，
覆盖订单、物流、售后三条主线业务。

## 功能概览

- **意图理解**：`LLMCommandGenerator` 基于通义千问（qwen-plus）把用户自然语言解析成结构化命令
- **业务流程**：`FlowPolicy` 按 YAML 定义的 flow 驱动多轮对话，支持槽位填充与流程跳转
- **企业检索**：`EnterpriseSearchPolicy` 走 GraphRAG，先在 Neo4j 中定位入口节点，再由 LLM 生成 Cypher 查询
- **业务查询**：`actions` 层直连 MySQL 电商库，读取订单、物流、售后数据
- **模型接入**：LLM 客户端支持 OpenAI 兼容接口与 DashScope，可切换 provider

## 目录结构

```
llm_customer_service/
├── atguigu_ai/                 # 对话框架本体（可 pip 安装，CLI 命令名 atguigu）
│   ├── agent/                  # Agent 与 LangGraph 图编排
│   ├── api/                    # FastAPI 服务与模板
│   ├── channels/               # 接入渠道
│   ├── cli/                    # 命令行入口（init/train/run/shell/export/inspect）
│   ├── core/                   # Tracker、Store 等核心组件
│   ├── dialogue_understanding/ # LLM 命令生成、flow 栈、处理器
│   ├── nlg/                    # 回复生成
│   ├── policies/               # FlowPolicy、EnterpriseSearchPolicy 等策略
│   ├── retrieval/              # 检索层
│   ├── shared/                 # 配置、LLM 客户端等公共模块
│   └── training/               # 训练与微调
├── ecs_demo/                   # 电商客服 Demo 工程
│   ├── actions/                # 订单/物流/售后动作 + MySQL 会话与表映射
│   ├── addons/                 # GraphRAG 检索、向量索引构建
│   ├── data/flows/             # flow_order / flow_logistics / flow_postsale
│   ├── domain/                 # domain_*.yml 领域定义
│   ├── models/                 # 本地向量模型（已在 .gitignore 中排除）
│   ├── config.yml              # pipeline 与 policies 配置
│   ├── endpoints.yml           # LLM、Neo4j、MySQL 端点配置
│   └── gen_data.py             # 生成测试业务数据
├── requirements-atguigu.txt
└── setup.py
```

## 环境要求

- Python >= 3.10
- MySQL 5.7+（电商业务库，库名默认 `ecs`）
- Neo4j 5.x（知识图谱，默认 `bolt://localhost:7687`）
- 阿里云百炼（DashScope）API Key

## 安装

```bash
pip install -e .
# 或按清单安装
pip install -r requirements-atguigu.txt
```

安装后获得 `atguigu` CLI：

```bash
atguigu --help
```

## 配置

`ecs_demo/.env` 已被版本控制排除，请从模板复制后填写：

```bash
cp ecs_demo/.env.example ecs_demo/.env
```

需要填写的变量：

| 变量 | 说明 |
| --- | --- |
| `DASHSCOPE_API_KEY` | 百炼平台 API Key，`endpoints.yml` 中以 `${DASHSCOPE_API_KEY}` 引用 |
| `NEO4J_PASSWORD` | Neo4j 密码 |
| `MYSQL_PASSWORD` | MySQL 密码（用户名默认 `root`） |
| `EMBEDDING_MODEL` | 本地向量模型路径，默认 `./models/bge-base-zh-v1.5` |

## 向量模型

仓库不包含模型权重。GraphRAG 依赖 `bge-base-zh-v1.5`（约 390MB，超过 GitHub 单文件限制），
请单独下载后放到 `ecs_demo/models/bge-base-zh-v1.5/`：

```bash
# 方式一：ModelScope
modelscope download --model BAAI/bge-base-zh-v1.5 --local_dir ecs_demo/models/bge-base-zh-v1.5

# 方式二：HuggingFace
huggingface-cli download BAAI/bge-base-zh-v1.5 --local-dir ecs_demo/models/bge-base-zh-v1.5
```

若模型放在其他位置，改 `.env` 里的 `EMBEDDING_MODEL` 即可。

## 准备数据

```bash
cd ecs_demo
python gen_data.py            # 用 Faker 生成订单、物流、售后测试数据
python addons/create_indexing.py   # 构建 Neo4j 向量索引
```

## 运行

在 `ecs_demo` 目录下执行：

```bash
atguigu train    # 解析 domain / config / flows
atguigu run      # 启动服务（FastAPI）
atguigu shell    # 命令行交互调试
atguigu inspect  # 查看解析后的 assistant 结构
```

## 安全说明

- `.env`、`__pycache__`、`.idea`、`*.egg-info`、模型权重与压缩包均在 `.gitignore` 中排除
- 数据库密码统一通过环境变量读取，代码内仅为本地开发默认值
- 提交前请确认没有把真实 API Key 或数据库密码写入任何被跟踪的文件

## 致谢

对话框架 `atguigu_ai` 的骨架来自尚硅谷相关课程，在此基础上做了扩展与业务接入。
