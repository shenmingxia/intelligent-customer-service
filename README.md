# 智能客服助手框架

这是一个可扩展的智能客服助手框架，基于 FastAPI 构建，已包含可视化网页聊天窗口、多轮对话记忆和 OpenAI 大模型回退回答。

## 已包含能力

- FAQ 问答匹配
- 简单意图识别
- OpenAI 大模型回答，未配置 Key 时自动回退到规则逻辑
- 人工客服转接规则
- REST API 接口
- 网页聊天窗口
- 多轮对话记忆，支持订单号、退款原因等上下文槽位
- 配置文件和示例知识库
- 后续可接入数据库、向量检索、企业微信/网页聊天窗口

## 项目结构

```text
smart_customer_service/
├─ app/
│  ├─ main.py
│  ├─ schemas.py
│  ├─ static/
│  │  ├─ index.html
│  │  ├─ styles.css
│  │  └─ app.js
│  ├─ routers/
│  │  └─ chat.py
│  └─ services/
│     ├─ assistant.py
│     ├─ faq.py
│     ├─ intent.py
│     ├─ llm.py
│     └─ policy.py
├─ data/
│  ├─ config.json
│  └─ faq.json
├─ tests/
├─ .env.example
├─ requirements.txt
└─ README.md
```

## 启动方式

```powershell
cd D:\AI_file\smart_customer_service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开网页客服窗口：

```text
http://127.0.0.1:8000/
```

打开接口文档：

```text
http://127.0.0.1:8000/docs
```

## 配置大模型

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`：

```text
OPENAI_API_KEY=你的 OpenAI API Key
OPENAI_MODEL=gpt-5.5
OPENAI_REASONING_EFFORT=low
OPENAI_TIMEOUT_SECONDS=10
OPENAI_MAX_RETRIES=1
```

重新启动服务后，规则和 FAQ 无法处理的问题会交给大模型回答。没有配置 `OPENAI_API_KEY` 时，系统会继续使用当前规则逻辑，不会报错。


## 会话存储配置

默认情况下，系统使用进程内存保存会话，并通过 `SESSION_TTL_SECONDS` 控制过期时间。生产环境建议配置 Redis，这样服务重启或多进程部署时仍可共享会话状态。

```text
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=86400
```

会话会绑定首次创建时的 `user_id`。后续请求如果使用相同 `session_id` 但传入不同 `user_id`，接口会返回 `403`，避免跨用户复用会话上下文。

## 测试聊天接口

```powershell
curl -X POST "http://127.0.0.1:8000/api/chat" `
  -H "Content-Type: application/json" `
  -d '{"user_id":"u001","message":"退款多久到账","session_id":null}'
```

返回示例：

```json
{
  "reply": "退款审核通过后，通常 1-3 个工作日原路退回。银行或支付平台处理时间可能略有差异。",
  "intent": "refund_time",
  "confidence": 0.5,
  "need_human": false,
  "session_id": "u001-xxxxxxxx",
  "context": {
    "turn_count": "0"
  }
}
```

## 多轮对话示例

先问：

```text
我要查订单
```

客服会要求提供订单号。继续输入：

```text
A123456
```

客服会记住这是同一个会话中的订单查询，并返回订单状态。网页端会把 `session_id` 保存到浏览器本地存储；点击“清空”会开启新会话。

退款也支持多轮槽位：

```text
我要退款
订单号 B987654
买错了
```

系统会依次记录退款意图、订单号和退款原因。

## 前端说明

- `app/static/index.html`：聊天页面结构。
- `app/static/styles.css`：页面视觉样式，支持桌面和手机。
- `app/static/app.js`：调用 `/api/chat`、保存 `session_id` 并渲染聊天消息。

## 后续扩展建议

1. 把大模型用于意图识别，而不只是未知问题回退回答。
2. 接入向量数据库，把 FAQ 从关键词匹配升级为语义检索。
3. 把内存会话迁移到 Redis / 数据库，支持服务重启后保留会话。
4. 接入 MySQL / PostgreSQL，查询真实订单、物流、售后数据。
5. 增加管理员后台，用来维护 FAQ 和人工转接规则。
