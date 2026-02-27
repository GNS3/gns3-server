# GNS3 Server Copilot AI Agent 集成文档

## 概述

本文档说明 GNS3 Server 集成的 AI Copilot Agent 功能，该功能使用 LangChain 和 LangGraph 构建，为用户提供智能化的网络拓扑管理和自动化能力。

## 架构设计

### 技术栈

```
┌─────────────────────────────────────────────────────────┐
│  表示层: FastAPI                                        │
│  /v3/copilot/* - 配置管理 API                           │
│  /v3/projects/{id}/copilot/* - 项目聊天 API              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  服务层: CopilotService                                 │
│  - Agent 生命周期管理                                     │
│  - 工具绑定                                              │
│  - 对话状态管理                                          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  AI 框架: LangChain + LangGraph                          │
│  - LangChain: 模型、工具、消息                           │
│  - LangGraph: 状态机、工作流编排                        │
│  - Checkpoint: 对话持久化                                │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  工具层: Copilot Tools                                   │
│  - 拓扑管理、节点操作、链路创建                            │
│  - 命令执行 (显示/配置/VPCS)                              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  数据层                                                 │
│  - 用户配置: copilot_configs 表                          │
│  - 项目对话: {项目目录}/copilot_checkpoints.db           │
└─────────────────────────────────────────────────────────┘
```

## 目录结构

```
gns3server/
├── db/
│   ├── models/
│   │   └── copilot.py                 # CopilotConfig 数据模型
│   └── repositories/
│       └── copilot.py               # CopilotRepository 数据仓库
│
├── schemas/
│   └── controller/
│       └── copilot.py               # API Schemas (请求/响应模型)
│
├── api/routes/controller/
│   ├── copilot.py                   # 配置管理 API
│   └── copilot_chat.py              # 聊天 API
│
├── services/
│   ├── copilot_service.py           # CopilotAgent 服务
│   ├── copilot_prompts/             # 系统提示词
│   │   ├── __init__.py
│   │   └── base_prompt.py            # 来自 gns3-copilot
│   └── copilot_tools/               # 工具集
│       ├── __init__.py
│       ├── base.py                   # 工具基类
│       ├── topology.py               # 拓扑工具
│       ├── nodes.py                  # 节点工具
│       ├── links.py                  # 链路工具
│       ├── templates.py              # 模板工具
│       ├── network_commands.py       # 网络命令工具
│       └── vpcs.py                   # VPCS 工具
```

## 功能模块

### 1. 配置管理 API

#### 创建配置
```bash
POST /v3/copilot/config
Content-Type: application/json
Authorization: Bearer <token>

{
  "provider": "openai",
  "model_name": "gpt-4o",
  "api_key": "sk-xxx",
  "temperature": 0.7,
  "enabled": true
}
```

#### 获取配置
```bash
GET /v3/copilot/config
Authorization: Bearer <token>
```

**响应 (配置存在时)**:
```json
{
  "config_id": "abc123",
  "user_id": "user456",
  "provider": "openai",
  "model_name": "gpt-4o",
  "base_url": "https://api.openai.com/v1",
  "temperature": 0.7,
  "max_tokens": 2000,
  "enabled": true
}
```

**响应 (配置不存在时)**:
```json
{
  "message": "Copilot configuration not found. Please create one first.",
  "details": {
    "action": "Create a copilot configuration",
    "endpoint": "POST /v3/copilot/config",
    "required_fields": {
      "provider": "AI provider (e.g., 'openai', 'anthropic', 'ollama', 'azure_openai')",
      "model_name": "Model name (e.g., 'gpt-4', 'claude-3-5-sonnet-20241022')",
      "api_key": "Your API key for the provider",
      "base_url": "API base URL (optional, required for some providers)",
      "temperature": "Sampling temperature (0.0-2.0, optional, default: 0.7)",
      "max_tokens": "Maximum tokens to generate (optional, default: 2000)",
      "enabled": "Whether the configuration is enabled (optional, default: true)"
    },
    "example": {
      "provider": "openai",
      "model_name": "gpt-4",
      "api_key": "sk-...",
      "base_url": "https://api.openai.com/v1",
      "temperature": 0.7,
      "max_tokens": 2000,
      "enabled": true
    }
  }
}
```

**根据错误响应创建配置 (POST 方法)**:
```bash
POST /v3/copilot/config
Content-Type: application/json
Authorization: Bearer <token>

{
  "provider": "openai",
  "model_name": "gpt-4o",
  "api_key": "sk-xxxx",
  "base_url": "https://api.openai.com/v1",
  "temperature": 0.7,
  "max_tokens": 2000,
  "enabled": true
}
```

**响应 (创建成功)**:
```json
{
  "config_id": "abc123",
  "user_id": "user456",
  "provider": "openai",
  "model_name": "gpt-4o",
  "base_url": "https://api.openai.com/v1",
  "temperature": 0.7,
  "max_tokens": 2000,
  "enabled": true,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

#### 更新配置
```bash
PUT /v3/copilot/config
Content-Type: application/json

{
  "temperature": 0.5,
  "model_name": "gpt-4o-mini"
}
```

#### 删除配置
```bash
DELETE /v3/copilot/config
Authorization: Bearer <token>
```

**响应 (删除成功)**:
```
HTTP/1.1 204 No Content
```
- 状态码: 204
- 无响应体

**响应 (配置不存在)**:
```json
{
  "message": "Copilot configuration not found."
}
```
- 状态码: 404

### 2. 聊天 API

#### 非流式聊天
```bash
POST /v3/projects/{project_id}/copilot/chat
Content-Type: application/json

{
  "message": "帮我创建两个路由器并连接",
  "conversation_id": "session-123"
}

响应:
{
  "response": "好的，我来帮您创建两个路由器...",
  "conversation_id": "session-123",
  "tools_used": ["list_gns3_templates", "create_gns3_node", ...]
}
```

#### 流式聊天 (SSE)
```bash
POST /v3/projects/{project_id}/copilot/chat/stream
Content-Type: application/json

{
  "message": "创建拓扑",
  "stream": true
}

# 返回 Server-Sent Events
event: token
data: {"data": "好的", "conversation_id": "session-123"}

event: tool_call
data: {"data": "list_gns3_templates", "conversation_id": "session-123"}

event: done
data: {"data": "", "conversation_id": "session-123"}
```

## 工具列表

| 工具名称 | 功能 | 描述 |
|---------|------|------|
| `list_gns3_templates` | 列出模板 | 获取可用的节点模板 |
| `get_gns3_topology` | 读取拓扑 | 获取项目拓扑信息 |
| `create_gns3_node` | 创建节点 | 在项目中创建新节点 |
| `start_gns3_node` | 启动节点 | 启动指定的节点 |
| `create_gns3_link` | 创建链路 | 连接两个节点 |
| `read_device_info` | 读取设备信息 | 执行 show 命令 (只读) |
| `apply_device_config` | 应用设备配置 | 执行配置命令 (修改设备) |
| `vpcs_terminal` | VPCS 终端 | 执行 VPCS 设备命令 |

## Checkpoint 对话持久化

### 存储位置

```
项目级存储: {项目目录}/copilot_checkpoints.db

例如:
/var/lib/gns3/projects/abc-123-def/copilot_checkpoints.db
```

### 优势

1. **项目级隔离**: 每个项目独立的对话历史
2. **团队协作**: 多个用户共享项目对话上下文
3. **数据管理**: 删除项目时自动清理对话历史
4. **项目导出**: 导出项目时包含对话历史

### 使用方式

```python
# 同一项目的多轮对话
await chat("创建路由器 R1", project_id="abc", conversation_id="session-1")
await chat("再创建交换机 S1", project_id="abc", conversation_id="session-1")

# Agent 记得之前创建了 R1，可以正确连接
```

## 数据库模型

### CopilotConfig 表

```sql
CREATE TABLE copilot_configs (
    config_id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) UNIQUE NOT NULL,
    provider VARCHAR(50) DEFAULT 'openai',
    model_name VARCHAR(100) DEFAULT 'gpt-4o',
    api_key VARCHAR(500),
    base_url VARCHAR(500),
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
```

## 依赖项

### Python 包

```txt
# LangChain 和 LangGraph
langchain>=1.2.0
langchain-core>=1.2.6
langgraph>=1.0.5
langgraph-checkpoint-sqlite>=3.0.1

# LLM 提供商
langchain-openai>=1.1.6
langchain-anthropic>=1.3.1
langchain-google-genai>=4.1.3
langchain-aws>=1.2.0
langchain-ollama>=1.0.1

# 网络自动化
netmiko>=4.6.0
nornir>=3.5.0
nornir-netmiko>=1.0.1
nornir-utils>=0.2.0
nornir-salt>=0.23.0
telnetlib3>=2.0.8
```

## 工作流程

### Agent 执行流程

```
1. 用户发送消息
   ↓
2. 获取项目特定 Agent (带项目 Checkpoint)
   ↓
3. 构建系统消息 (包含项目拓扑)
   ↓
4. LLM 分析并决定是否调用工具
   ↓
5. 如果需要工具:
   - 执行工具调用
   - 获取结果
   - 返回 LLM 继续处理
   ↓
6. 生成最终响应
   ↓
7. 保存对话状态到项目 Checkpoint
```

### 工具调用示例

```
用户: "创建两个路由器并连接"
   ↓
LLM: 决定调用 list_gns3_templates
   ↓
Tool: 返回可用模板列表
   ↓
LLM: 决定调用 create_gns3_node (创建 R1)
   ↓
Tool: 返回创建成功
   ↓
LLM: 决定调用 create_gns3_node (创建 R2)
   ↓
Tool: 返回创建成功
   ↓
LLM: 决定调用 create_gns3_link
   ↓
Tool: 返回连接成功
   ↓
LLM: 生成最终响应
```

## 配置说明

### 支持的提供商

| Provider | 说明 | 示例模型 |
|----------|------|----------|
| `openai` | OpenAI | gpt-4o, gpt-4o-mini |
| `anthropic` | Anthropic | claude-3-5-sonnet-20241022 |
| `google` | Google AI | gemini-2.0-flash-exp |
| `aws` | AWS Bedrock | anthropic.claude-3-5-sonnet-20241022-v2:0 |
| `ollama` | Ollama 本地 | llama3.2, qwen2.5 |
| `deepseek` | DeepSeek | deepseek-chat |
| `xai` | xAI | grok-2-1212 |

### 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | string | "openai" | 模型提供商 |
| `model_name` | string | "gpt-4o" | 模型名称 |
| `api_key` | string | 必填 | API 密钥 |
| `base_url` | string | null | 自定义 API 端点 |
| `temperature` | float | 0.7 | 温度 (0.0-2.0) |
| `max_tokens` | integer | null | 最大 token 数 |
| `enabled` | boolean | true | 是否启用 |

## 使用示例

### 完整工作流

```bash
# 1. 登录获取 token
TOKEN=$(curl -X POST http://localhost:3080/v3/access/users/login \
  -d "username=admin&password=admin" | jq -r '.access_token')

# 2. 创建 Copilot 配置
curl -X POST http://localhost:3080/v3/copilot/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model_name": "gpt-4o",
    "api_key": "sk-xxxx",
    "temperature": 0.7
  }'

# 3. 使用 AI Agent 创建拓扑
PROJECT_ID="your-project-id"
curl -X POST http://localhost:3080/v3/projects/$PROJECT_ID/copilot/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我创建一个包含三个路由器的网络拓扑，并用环状拓扑连接它们"
  }'

# Agent 会自动:
# 1. 调用 list_gns3_templates 查看可用模板
# 2. 调用 create_gns3_node 创建三个路由器
# 3. 调用 create_gns3_link 连接成环状
# 4. 返回完整的执行结果
```

## 常见问题

### Q: 对话历史保存在哪里？
A: 保存在项目目录中的 `copilot_checkpoints.db` 文件。

### Q: 多个用户协作同一个项目时，对话历史共享吗？
A: 是的，因为 checkpoint 是基于项目的，所有用户共享该项目的对话历史。

### Q: 如何删除对话历史？
A: 删除项目时会自动清理对话历史，或者手动删除 `copilot_checkpoints.db` 文件。

### Q: 支持哪些 LLM 提供商？
A: 支持 OpenAI、Anthropic、Google、AWS、Ollama、DeepSeek、xAI 等。

### Q: Agent 可以执行哪些操作？
A: 创建节点、创建链路、启动节点、执行网络命令、读取拓扑等。

## API 端点总览

```
# 配置管理
POST   /v3/copilot/config     # 创建配置
GET    /v3/copilot/config     # 获取配置
PUT    /v3/copilot/config     # 更新配置
DELETE /v3/copilot/config     # 删除配置

# 项目聊天
POST   /v3/projects/{id}/copilot/chat         # 非流式聊天
POST   /v3/projects/{id}/copilot/chat/stream  # 流式聊天 (SSE)
```

## 性能考虑

1. **Agent 缓存**: Agent 按项目缓存，避免重复创建
2. **工具并发**: Nornir 自动并发执行多设备命令
3. **Checkpoint 高效**: SQLite 轻量级持久化
4. **流式响应**: 支持实时流式返回，提升用户体验

## 安全说明

1. **API Key 加密**: 当前明文存储，生产环境建议加密
2. **用户隔离**: 每个用户有独立的配置
3. **权限控制**: 需要有效的用户 token
4. **项目访问**: 用户只能访问有权限的项目

## 后续开发计划

- [ ] API Key 加密存储
- [ ] 更多网络设备类型支持
- [ ] 对话历史管理 API
- [ ] 工具执行结果缓存
- [ ] 更详细的错误处理和日志
- [ ] 单元测试和集成测试

## 相关文档

- [LangChain 文档](https://python.langchain.com/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [gns3-copilot 项目](https://github.com/yueguobin/gns3-copilot)
