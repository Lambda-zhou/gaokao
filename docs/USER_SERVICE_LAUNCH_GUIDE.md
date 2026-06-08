# 志愿智选网页服务上线指南

> 适用对象：希望把当前 `zhiyuan-agent.html + FastAPI` 服务开放给真实用户访问的项目 owner / 运维者。  
> 当前日期：2026-06-08。法规、备案和平台规则可能变化，正式上线前请以主管部门和云厂商最新要求为准。

## 1. 先判断你要上线到什么程度

| 阶段 | 适合场景 | 推荐做法 | 风险 |
| --- | --- | --- | --- |
| 内测 / 小范围体验 | 给朋友、同学、少量家长试用 | 云服务器或 Notebook 公网代理 + 密码/白名单 | 链接不稳定；不适合大量用户；合规材料不完整 |
| 正式公开访问 | 让陌生用户通过域名访问 | 云服务器 + 域名 + HTTPS + 备案/公安联网备案 + 日志监控 | 成本、合规、隐私和 AI 调用稳定性要求更高 |
| 商业化服务 | 收费、留资、批量用户咨询 | 正式公司主体、用户协议、隐私政策、客服、支付、数据留存、安全审计 | 需要更严格的数据保护、内容审核和免责声明 |

**建议路线：**先做“受控内测”验证模型、推荐质量、成本和稳定性；再做正式域名、备案、HTTPS、日志和用户协议；最后再考虑收费。

---

## 2. 当前项目对外提供服务的基本结构

当前项目不是纯静态网页。用户打开网页后，还需要后端 API 支撑：

```text
用户浏览器
  ↓ 访问 /zhiyuan-agent.html 或 /app
FastAPI 服务
  ├─ 提供前端页面和静态资源：/assets、/images
  ├─ 提供咨询 API：/api/consult/stream
  ├─ 提供会话 API：/api/sessions
  ├─ 提供模型配置测试 API：/api/llm/test
  ├─ 提供高校/专业数据 API：/api/data/*
  └─ 调用外部大模型 API：DeepSeek / MiMo / ModelScope / OpenAI-compatible
```

因此给用户使用时，至少要准备：

1. 一台能长期运行 Python FastAPI 的服务器。
2. 一个可访问的公网地址，最好是正式域名。
3. HTTPS 证书。
4. 一个稳定可用的大模型 API Key 和模型配置。
5. 日志、限流、错误排查和成本控制。
6. 面向用户的使用说明、免责声明、隐私政策。

---

## 3. 最低可用上线方案：先跑给少量用户看

### 3.1 适合情况

- 只给少量熟人试用。
- 暂时不收集敏感个人信息或不做商业化。
- 主要验证产品体验和回答质量。

### 3.2 操作步骤

在服务器或 Notebook 中：

```bash
cd /path/to/gaokao
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`，至少配置一个可用模型：

```env
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://你的供应商/v1
LLM_MODEL=供应商控制台里的真实模型ID
LLM_API_KEY=你的API_KEY
LLM_TIMEOUT=40
RATE_LIMIT_WINDOW=60
RATE_LIMIT_MAX=30
```

如果用小米 MiMo token-plan：

```env
LLM_PROVIDER=mimo
MIMO_BASE_URL=https://token-plan-...xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5-pro
MIMO_API_KEY=你的小米MiMo token-plan key
```

启动：

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

让用户访问：

```text
http://你的服务器IP:8000/zhiyuan-agent.html
```

或者：

```text
http://你的服务器IP:8000/app
```

### 3.3 内测前必须确认

```bash
curl http://127.0.0.1:8000/health
```

重点看：

```json
{
  "status": "ok",
  "llm_available": true,
  "llm_last_error_type": ""
}
```

如果 `llm_available=false` 或 `llm_last_error_type=authentication`，不要发给用户；这说明 AI 没接好，会影响体验。

---

## 4. 正式公开上线方案

### 4.1 推荐架构

```text
用户
 ↓ HTTPS
域名 example.com
 ↓
Nginx / Caddy 反向代理
 ↓
Uvicorn / Gunicorn + UvicornWorker
 ↓
FastAPI app: main.py
 ↓
外部 LLM API + 本地 data/*.json
```

### 4.2 服务器建议

最低配置：

- 2 vCPU
- 2GB～4GB 内存
- 20GB 以上磁盘
- Python 3.10+，建议 Python 3.11
- 出网能力正常，能访问你的 LLM 供应商 API

如果用户较多，建议：

- 4 vCPU / 8GB 内存起
- 使用进程管理器，例如 systemd、supervisor、pm2 或容器编排
- 日志单独保存
- 监控 CPU、内存、请求数、错误率、LLM 调用耗时

### 4.3 生产启动命令示例

安装依赖：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

启动：

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
```

> 注意：当前项目的会话管理是内存型。如果使用多 worker，不同 worker 之间的会话可能不同步。正式用户使用前，建议把会话持久化到数据库或先用单 worker 验证。

### 4.4 Nginx 反向代理示例

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    client_max_body_size 2m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 流式回答需要避免缓冲
        proxy_buffering off;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
```

### 4.5 CORS 配置

生产环境不要允许任意来源。当前项目通过 `CORS_ORIGINS` 控制：

```env
CORS_ORIGINS=https://your-domain.com
```

如果前端和后端同域部署，例如用户访问 `https://your-domain.com/app`，CORS 压力最小。

---

## 5. 域名、ICP备案、公安联网备案

如果你的服务器在中国大陆，且网页面向公网用户，通常需要准备：

1. 已实名认证的域名。
2. 云厂商处的 ICP 备案。
3. 网站上线后按要求做公安联网备案。

常见流程：

```text
购买域名 → 购买大陆服务器 → 云厂商提交ICP备案 → 备案通过 → 解析域名 → 配置HTTPS → 网站上线 → 公安联网备案
```

注意事项：

- 备案主体要和服务器/域名/实际运营主体匹配。
- 页面底部通常需要展示 ICP 备案号。
- 公安联网备案一般需要在网站开通后按要求办理，并在页面展示备案图标/编号。
- 如果使用境外服务器，ICP备案要求会不同，但访问速度、合规和模型接口出网稳定性仍要评估。

---

## 6. AI Key 与模型配置

### 6.1 推荐策略

正式给用户使用时，不建议完全依赖用户自己填 Key。更好的方式：

- 服务器 `.env` 配置一个默认可用模型。
- 前端保留“用户自带 Key”作为高级选项。
- 后端必须透明提示鉴权失败，不能用模板回复冒充 AI。

### 6.2 服务端默认模型配置

通用 OpenAI-compatible：

```env
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://provider.example.com/v1
LLM_MODEL=provider-model-id
LLM_MODEL_CANDIDATES=backup-model-1,backup-model-2
LLM_API_KEY=your_server_key
LLM_TIMEOUT=40
```

小米 MiMo：

```env
LLM_PROVIDER=mimo
MIMO_BASE_URL=https://token-plan-...xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5-pro
MIMO_API_KEY=your_mimo_key
```

ModelScope：

```env
LLM_PROVIDER=modelscope
MIMO_BASE_URL=https://api-inference.modelscope.cn/v1
MIMO_MODEL=Qwen/Qwen3-235B-A22B
MIMO_MODEL_CANDIDATES=Qwen/Qwen3-235B-A22B,Qwen/Qwen3-30B-A3B
MIMO_API_KEY=your_modelscope_key
```

### 6.3 上线前模型验收

必须实际测试这些问题：

- “我该冲哪些学校？”
- “这个专业的中位数收入多少？”
- “500强去哪些学校招聘？”
- “华南理工大学能上吗？”
- “要不要接受调剂？”
- “只说就业，不要推荐学校”

检查回答是否：

- 没有把事实问题跑偏成院校推荐。
- 没有把模拟概率、估算薪资说成官方数据。
- 没有出现假的录取承诺。
- 鉴权失败时明确提示配置问题，而不是模板回复。

---

## 7. 数据、隐私和用户告知

### 7.1 你会处理哪些用户信息

这个系统可能处理：

- 省份、分数、位次、选科
- 城市偏好、专业偏好、家庭条件、风险偏好
- 用户在聊天里输入的个人情况
- 浏览器 localStorage 中的模型配置
- 后端会话记录
- 访问日志和错误日志

这些信息虽然不一定都是强身份信息，但对高考家庭仍然敏感。正式上线前应当明确告知用户。

### 7.2 隐私政策至少写清楚

建议准备 `隐私政策` 页面，写清楚：

1. 收集哪些信息。
2. 用这些信息做什么。
3. 是否会发送给第三方大模型供应商。
4. 信息保存多久。
5. 用户如何删除会话。
6. 是否用于模型训练或产品改进。
7. 联系方式。

### 7.3 用户协议和免责声明至少写清楚

建议在页面明显位置展示：

> 本服务为高考志愿辅助决策工具，不替代省教育考试院、阳光高考、学校本科招生网、招生章程和高校官方就业质量报告。系统输出包含本地规则、公开资料摘要和大模型生成内容，可能存在错误、滞后或不完整。最终志愿填报应以官方最新招生计划、投档线、专业组、选科要求和招生章程为准。

如果你商业化，还要增加：

- 服务范围和不保证事项。
- 退款规则。
- 人工咨询与 AI 咨询的边界。
- 未成年人使用须由监护人同意。

---

## 8. 安全要求

### 8.1 API Key 安全

- `.env` 不要提交到 Git。
- 不要在前端代码写死服务端 API Key。
- 日志里不要输出 API Key。
- `/api/llm/test` 返回信息不能泄露用户填写的 Key。
- 定期轮换 Key。

### 8.2 访问控制

内测期建议：

- 给入口加 Basic Auth。
- 或者只允许白名单 IP。
- 或者用临时口令保护页面。

正式期建议：

- 注册/登录。
- 用户级限流。
- 用户级配额。
- 管理后台可封禁异常用户。

### 8.3 当前项目已有但还应加强的点

已有：

- CORS 配置项。
- 简单限流中间件。
- 统一错误处理。
- LLM 鉴权失败透明提示。

建议加强：

- 会话持久化到数据库。
- 登录系统。
- 每用户限流，而不是全局简单限流。
- 内容安全过滤。
- 管理员查看错误日志。
- HTTPS 强制跳转。
- 备份与恢复。

---

## 9. 会话和数据存储

当前项目的 `session_manager` 适合演示和内测，不适合长期生产：

- 服务重启后可能丢会话。
- 多 worker / 多实例时会话不共享。
- 无用户隔离。
- 无数据删除审计。

正式上线建议：

```text
SQLite/PostgreSQL/MySQL
  ├─ users
  ├─ sessions
  ├─ messages
  ├─ consultation_profiles
  ├─ synced_plans
  └─ audit_logs
```

最低生产改造：

1. 每个用户有独立 ID。
2. 会话按用户隔离。
3. 支持用户删除自己的历史记录。
4. 管理员不能随便查看用户敏感内容，除非有明确授权或风控需要。
5. 设定自动过期时间，例如 30～180 天。

---

## 10. 成本控制

大模型服务会按 token / 调用次数计费。上线前要估算：

| 项目 | 需要关注 |
| --- | --- |
| 单次咨询成本 | prompt 长度、联网摘要、回答长度、模型单价 |
| 用户频率 | 每人每天问几次 |
| 并发量 | 同时多少用户咨询 |
| 失败重试 | 失败时不要无限重试 |
| 流式输出 | 改善体验，但连接时间更长 |

建议：

- 每个用户每天限制咨询次数。
- 对超长输入做截断或提醒。
- 对重复问题做缓存。
- 非核心问题使用便宜模型。
- 复杂推荐用主模型，普通解释用备用模型。
- 每天设置预算告警。

---

## 11. 内容质量和高考业务风险

高考志愿属于高风险决策辅助，必须降低“误导用户”的概率。

上线前建议建立人工验收表：

| 检查项 | 要求 |
| --- | --- |
| 省份、分数、位次缺失 | 不给具体学校名单，只要求补充信息 |
| 冲稳保 | 只说倾向，不说真实录取概率 |
| 薪资 | 标注本地估算/非官方统计/仅供参考 |
| 官方核验 | 指向省考试院、阳光高考、学校本科招生网 |
| 调剂 | 明确专业组和服从调剂风险 |
| 家庭条件 | 普通家庭强调确定性和试错成本 |
| AI 失败 | 明确提示失败原因，不模板冒充 |

建议上线前准备 30～50 个真实问题做验收，包括：

- 不同省份。
- 高分、中分、低分。
- 物化生、政史地等选科。
- 普通/中产/富裕家庭。
- 城市优先、专业优先、保底优先。
- 问就业、问薪资、问调剂、问单校机会。

---

## 12. 页面和产品内容准备

正式给用户使用，除了技术部署，还需要补齐这些页面或文案：

### 12.1 必备页面

- 首页 / 产品介绍
- AI 咨询页：`/app` 或 `/zhiyuan-agent.html`
- 使用说明
- 免责声明
- 隐私政策
- 用户协议
- 联系我们 / 客服方式
- 备案信息展示区域

### 12.2 页面底部建议文案

```text
本服务为高考志愿辅助决策工具，结果仅供参考。最终志愿填报请以省教育考试院、阳光高考、学校本科招生网、招生章程和官方就业质量报告为准。
```

如果已备案，底部还应展示：

```text
ICP备案号：xxxxxx
公安联网备案号：xxxxxx
```

### 12.3 用户首次进入提示

建议弹窗或明显提示：

```text
请先填写省份、分数、位次和选科。缺少这些信息时，系统只能给方向建议，不会给具体学校名单。
```

---

## 13. 上线前检查清单

### 技术检查

- [ ] `python -m py_compile main.py core/*.py api/*.py middleware/*.py` 通过。
- [ ] `pip install -r requirements.txt` 在服务器成功。
- [ ] `/health` 返回 `status=ok`。
- [ ] `/health` 中 `llm_available=true`。
- [ ] `/app` 或 `/zhiyuan-agent.html` 能正常打开。
- [ ] `/assets/brand-logo.png` 正常加载。
- [ ] `/api/sessions` 正常返回。
- [ ] `/api/consult/stream` 能流式输出。
- [ ] Nginx 对 SSE 关闭 proxy buffering。
- [ ] HTTPS 正常。
- [ ] CORS 只允许正式域名。
- [ ] 服务器重启后服务能自动恢复。

### AI 检查

- [ ] 服务端默认 LLM Key 可用。
- [ ] `/api/llm/test` 可测试用户自带 Key。
- [ ] 401/403 时前端显示配置失败，不显示模板建议。
- [ ] 模型回答不会承诺录取。
- [ ] 模型回答会提醒官方核验。
- [ ] 模型不会把估算薪资说成官方统计。

### 安全和隐私检查

- [ ] `.env` 未提交到 Git。
- [ ] 日志不包含 API Key。
- [ ] 用户协议已准备。
- [ ] 隐私政策已准备。
- [ ] 免责声明已展示。
- [ ] 用户可删除历史会话。
- [ ] 已设置限流和预算告警。
- [ ] 如面向中国大陆公网，已处理 ICP/公安联网备案。

### 产品检查

- [ ] 有清晰的“如何填写画像”说明。
- [ ] 有“结果仅供参考”的提醒。
- [ ] 有客服或反馈入口。
- [ ] 有常见问题 FAQ。
- [ ] 准备了真实问题验收集。

---

## 14. 推荐的上线顺序

### 第 1 步：受控内测

- 服务器跑通。
- 给 5～20 个熟人使用。
- 记录失败问题、跑题问题、成本和耗时。
- 不收费，不公开传播。

### 第 2 步：稳定性修复

- 修复 LLM 鉴权、模型适配、前端报错。
- 增加更清晰的免责声明。
- 增加日志和限流。
- 明确用户数据保存策略。

### 第 3 步：正式域名上线

- 域名、HTTPS、备案。
- Nginx 反代。
- 配置 `CORS_ORIGINS`。
- 做 30～50 个问题验收。

### 第 4 步：商业化前改造

- 登录系统。
- 数据库持久化。
- 支付/订单。
- 用户协议和隐私政策正式版。
- 人工客服和纠错机制。
- 成本监控和风控。

---

## 15. 你现在最应该补的代码能力

如果要从“演示项目”变成“给用户用的服务”，建议优先级如下：

1. **会话持久化数据库**：否则重启丢数据，多 worker 不一致。
2. **用户身份系统**：否则不同用户的会话无法隔离。
3. **生产部署脚本**：systemd / Docker / Nginx 示例。
4. **正式免责声明与隐私政策页面**。
5. **更细的限流和配额**：按用户、IP、模型成本限制。
6. **日志和错误后台**：方便发现 401、超时、模型跑偏。
7. **官方数据核验工作流**：让推荐结果更可追溯。
8. **内容审核与纠错入口**：用户能标记“回答不准”。

---

## 16. 最小生产 `.env` 模板

```env
DEBUG=false
CORS_ORIGINS=https://your-domain.com

LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://provider.example.com/v1
LLM_MODEL=provider-model-id
LLM_MODEL_CANDIDATES=provider-backup-model-id
LLM_API_KEY=replace_with_real_key

LLM_TIMEOUT=40
RESEARCH_TIMEOUT=6
RATE_LIMIT_WINDOW=60
RATE_LIMIT_MAX=30
```

---

## 17. 一句话结论

如果只是给熟人试用：一台能访问公网的服务器 + `.env` 里可用的 LLM Key + `/app` 链接就能跑。  
如果要正式给陌生用户使用：你需要域名、HTTPS、备案、隐私政策、免责声明、稳定模型、限流、日志、会话持久化和用户隔离。  
如果要商业化：必须再补登录、支付、客服、数据治理、预算控制和更严格的内容质量验收。
