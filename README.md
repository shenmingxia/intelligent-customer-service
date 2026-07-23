# 智能客服助手框架

这是一个可扩展的智能客服助手框架，基于 FastAPI 构建，已包含可视化网页聊天窗口、多轮对话记忆和 OpenAI 大模型回退回答。

## 已包含能力

- 用户端网页客服窗口：访问 `http://127.0.0.1:8000/`，支持输入消息、快捷问题、清空会话，并在浏览器本地保存 `session_id`。
- 管理后台：访问 `http://127.0.0.1:8000/admin`，支持维护 FAQ、敏感词、人工转接关键词、兜底回复、反馈优化状态。
- 智能聊天接口：`POST /api/chat`，返回客服回复、意图、置信度、是否转人工、会话 ID 和上下文。
- FAQ 自动问答：支持运费、退款到账时间、发票、客服工作时间等常见问题，当前知识库维护在 `data/faq.json`。
- 简单意图识别：支持问候、订单/物流查询、退款/退货/取消、投诉等意图。
- 多轮对话记忆：支持订单查询补充订单号，以及退款流程中补充订单号、退款原因等上下文槽位。
- 订单与物流查询：可返回订单状态、物流公司、物流单号、预计送达时间和订单金额。
- 退款售后流程：支持可退款订单预处理、未付款订单取消提示、超出售后期限转人工、未查到订单提示。
- 人工客服转接：命中“人工”“客服”“转人工”“投诉”“经理”等关键词时触发，并返回 `need_human=true`。
- OpenAI 大模型兜底：配置 `OPENAI_API_KEY` 后，规则和 FAQ 未命中时调用大模型；未配置时自动回退到兜底话术。
- 回复反馈：每条机器人回复下方支持 `👍有用 / 👎没用`，点踩可选择“答非所问”“没解决我的问题”“太啰嗦”。
- 反馈 SQLite 存储：反馈数据写入 `data/feedback.db`，旧版 `data/feedback.json` 可在库为空时自动迁移。
- 反馈分析闭环：后台按点踩率展示 Top10 高优先级优化问题，并支持新建 FAQ、标记已处理、忽略、重新打开。
- 敏感词过滤：命中 `data/sensitive_words.json` 中的词时，阻断正常对话并返回安全提示，历史记录中会脱敏保存。
- 敏感词后台管理：在 `/admin` 支持敏感词查看、新增、编辑、删除，保存后即时刷新过滤器，无需重启服务。
- Rate Limiting：默认对 `/api/chat` 和 `/api/feedback` 生效，优先按 `user_id + path` 限流，缺少 `user_id` 时回退到 `IP + path`。
- 熔断机制：聊天回答超过 `ANSWER_TIMEOUT_SECONDS`（默认 3 秒）时，返回按用户意图设计的兜底话术，并提示用户转人工或重试。
- 熔断结果防污染：超时后后台慢线程即使继续完成，也不会覆盖已写入会话的熔断兜底结果。
- 会话存储：默认使用内存，可通过 `REDIS_URL` 切换到 Redis，并支持 `SESSION_TTL_SECONDS` 控制过期时间。
- 会话归属保护：同一 `session_id` 被不同 `user_id` 复用时返回 `403`，避免跨用户串用上下文。
- 订单数据源扩展：默认读取 JSON，可通过环境变量接入 SQLite 或 HTTP 订单服务。
- 管理鉴权：配置 `ADMIN_TOKEN` 后，后台接口需要请求头 `x-admin-token`。
- 系统接口：提供健康检查 `/health`、Swagger 文档 `/docs`、OpenAPI JSON `/openapi.json` 和统一错误响应。
- 已移除 Boss 直聘自动打招呼相关页面和接口，不再提供 `/boss` 或 `/api/boss/greeting`。

## 项目结构

```text
smart_customer_service/
|-- app/
|   |-- __init__.py
|   |-- errors.py
|   |-- main.py
|   |-- schemas.py
|   |-- routers/
|   |   |-- __init__.py
|   |   |-- admin.py
|   |   |-- chat.py
|   |   `-- feedback.py
|   |-- services/
|   |   |-- __init__.py
|   |   |-- admin_store.py
|   |   |-- assistant.py
|   |   |-- faq.py
|   |   |-- intent.py
|   |   |-- llm.py
|   |   |-- order.py
|   |   |-- policy.py
|   |   |-- rate_limit.py
|   |   |-- safety.py
|   |   `-- session_store.py
|   `-- static/
|       |-- admin.css
|       |-- admin.html
|       |-- admin.js
|       |-- app.js
|       |-- index.html
|       `-- styles.css
|-- data/
|   |-- config.json
|   |-- faq.json
|   |-- feedback.db
|   |-- feedback.json  # legacy JSON feedback, auto-migrated to SQLite when present
|   |-- orders.json
|   `-- sensitive_words.json
|-- tests/
|   |-- test_admin.py
|   |-- test_api.py
|   |-- test_assistant.py
|   |-- test_faq.py
|   |-- test_llm.py
|   `-- test_order.py
|-- .env.example
|-- .gitignore
|-- init_db.py
|-- requirements.txt
|-- 后端接口.txt
`-- README.md
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
ANSWER_TIMEOUT_SECONDS=3
CHAT_WORKER_THREADS=8
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

1. 将 FAQ 从 `data/faq.json` 迁移到 SQLite，与 `feedback.db` 统一存储，避免 FAQ 并发写入风险。
2. 接入向量数据库或 embedding 检索，把 FAQ 从关键词匹配升级为语义检索。
3. 用大模型或轻量分类器升级意图识别，减少关键词规则无法覆盖的问法。
4. 将内存版 Rate Limiting 升级为 Redis 限流，支持多进程、多实例部署。
5. 将会话存储和会话锁迁移到 Redis / 数据库，提升重启恢复能力并减少并发上下文覆盖。
6. 增加运营看板：FAQ 命中率、转人工率、点踩率、超时率、敏感词命中数、LLM 失败率。
7. 增加后台操作审计：记录 FAQ、敏感词、规则配置、反馈状态的修改人、修改时间和修改前后内容。
8. 增加隐私脱敏：保存反馈、会话日志前脱敏手机号、邮箱、身份证、地址等敏感信息。
9. 对接真实人工客服或工单系统，让“转人工”生成工单编号、排队状态和预计响应时间。
10. 增加反馈导出能力，将 Top10 点踩问题、未知问题、点踩原因导出为 CSV，便于运营复盘。

