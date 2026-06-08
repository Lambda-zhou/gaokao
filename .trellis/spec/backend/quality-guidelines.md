# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

<!-- Patterns that must always be used -->

(To be filled by the team)

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Scenario: Coarse chat recommendation without admissions-grade data

### 1. Scope / Trigger
- Trigger: backend chat recommendation changes the visible recommendation contract across orchestrator, rule engine, and tests.
- Applies when the system recommends schools from local `schools.json` / `majors.json` data without province-year-major admissions-grade data.

### 2. Signatures
- Intent entry: `ConsultOrchestrator.consult(request, history=None)`
- Candidate generation: `AgentEngine.recommend(RecommendRequest(user=..., limit=...))`
- Visible recommendation payload: `ConsultResponse.recommendation_plans`

### 3. Contracts
- Complete-enough profile for school-list recommendation:
  - required: `province`, `score`
  - recommended: `rank`
  - optional but influential: `subjects`, `city_preference`, `major_preference`, `family_background`, `risk_appetite`
- Chat recommendation contract:
  - shortlist size target: 6 schools
  - visible positioning: coarse shortlist first, “冲/稳/保” only as tendency labeling
  - tendency wording must not be presented as real录取概率
- Structured recommendation fields:
  - `match_score`: coarse preference-match score for sorting/explanation
  - `recommendation_basis`: short human-readable bullets explaining why the school entered the shortlist
  - `recommendation_breakdown`: structured dimension list for later UI rendering (e.g. 城市匹配 / 专业匹配 / 学校平台 / 就业出口 / 家庭适配)
- Incomplete-profile contract:
  - do not output a school list
  - output directional advice only
  - explicitly ask for province / score / ideally rank

### 4. Validation & Error Matrix
- Missing `province` or `score` on recommendation intent -> return directional guidance, no school list, low confidence
- LLM answer introduces schools outside backend shortlist -> guard / remove
- Local data can only support rough matching -> answer must explicitly mention coarse / reference-only nature

### 5. Good / Base / Bad Cases
- Good: profile complete enough -> 6-school shortlist + low-confidence tendency wording + official verification reminder
- Base: profile has major/city/family preference but lacks score/province -> give direction, do not name schools
- Bad: missing profile but still outputs concrete schools, exact probabilities, or authoritative录取 claims

### 6. Tests Required
- Recommendation intent with complete profile:
  - assert shortlist exists
  - assert shortlist is capped to MVP size
  - assert risk buckets are balanced for the MVP target where candidate supply allows
  - assert structured explanation fields are populated on recommendation plans
- Recommendation intent with incomplete profile:
  - assert no `recommendation_plans`
  - assert answer asks for province / score / rank
  - assert answer gives direction instead of school names
- Guardrail:
  - assert answer does not keep LLM-invented schools when profile is insufficient

### 7. Wrong vs Correct
#### Wrong
- “你这个情况我直接给你 10 所学校，冲 3 稳 4 保 3，录取概率分别是 ...”
- “没有分数也先推荐复旦、上大、华师大试试”

#### Correct
- “现在先给你方向，不给学校名单。补齐省份、分数、位次后，再把学校按冲稳保倾向粗筛成短名单。”
- “当前推荐是基于本地院校/专业库做的第一轮粗筛 shortlist，冲稳保只表示倾向。”

---

## Scenario: Notebook / DSW proxy deployment for the single-file frontend

### 1. Scope / Trigger
- Trigger: deployment changes that make `zhiyuan-agent.html` run outside a local desktop browser, especially ModelScope / Alibaba DSW notebook proxy URLs.
- Applies when the browser-visible frontend and the FastAPI backend are reached through different origins or through a `*-proxy-8000.*` public gateway.

### 2. Signatures
- Frontend entry page: `GET /zhiyuan-agent.html`
- Optional frontend alias: `GET /app`
- Static assets: `GET /assets/*`, `GET /images/*`
- Backend API base selection:
  - URL query: `?api=<api-base>` / `?apiBase=<api-base>` / `?api_base=<api-base>`
  - browser storage key: `localStorage["zhiyuan_api_base_url"]`
  - DSW same-origin fallback: host matching `*-proxy-8000.*`

### 3. Contracts
- FastAPI should be able to serve the single-file frontend from the same backend port when deployed behind an 8000 proxy.
- When the page is opened from a `proxy-8000` public gateway, default API calls must use `window.location.origin`, not browser-local `127.0.0.1`.
- When the page is opened from a local file or ordinary local static server, the development fallback may remain `http://127.0.0.1:8000`.
- Users can override auto-detection by adding `?api=<public-api-base>` or setting the localStorage key above.

### 4. Validation & Error Matrix
- `GET /zhiyuan-agent.html` returns 404 -> FastAPI is not serving the frontend entry; add or verify the static page route.
- Frontend requests `http://127.0.0.1:8000` from a hosted notebook page -> wrong browser/network boundary; use same-origin proxy or explicit `?api=`.
- Frontend is opened in a sandboxed Jupyter HTML preview and scripts are blocked -> serve it through FastAPI or a real static HTTP server tab instead.
- Static page loads but logo/assets 404 -> verify `/assets` and `/images` mounts.

### 5. Good / Base / Bad Cases
- Good: `https://<id>-proxy-8000.<gateway>/zhiyuan-agent.html` loads the UI and `/api/sessions` is requested from the same origin.
- Base: frontend is served from another port and opened as `...?api=https://<id>-proxy-8000.<gateway>`.
- Bad: hosted frontend keeps calling `http://127.0.0.1:8000/api/*`, which points at the user's browser machine instead of the notebook container.

### 6. Tests Required
- Compile/import check for `main.py` in a Python 3.10+ environment with project requirements installed.
- HTTP smoke test:
  - `GET /zhiyuan-agent.html` -> 200 and HTML content type
  - `GET /assets/brand-logo.png` -> 200 when the asset exists
  - `GET /api/sessions` -> 200 from the same public origin
- Browser smoke test on DSW:
  - open `/zhiyuan-agent.html`
  - confirm network requests use `https://<id>-proxy-8000.../api/*`
  - confirm no `Failed to fetch` caused by `127.0.0.1`

### 7. Wrong vs Correct
#### Wrong
```js
return 'http://127.0.0.1:8000';
```
for every hosted environment.

#### Correct
```js
if (location.hostname.includes('proxy-8000')) return location.origin;
return 'http://127.0.0.1:8000';
```
while still allowing `?api=` / localStorage overrides.

---

## Scenario: Flexible OpenAI-compatible LLM configuration

### 1. Scope / Trigger
- Trigger: backend code changes LLM provider/model/base URL resolution in `core/config.py` or `core/llm_client.py`.
- Applies to DeepSeek, Mimo/ModelScope, and arbitrary OpenAI-compatible providers.

### 2. Signatures
- Settings fields:
  - `LLM_PROVIDER`
  - `LLM_API_KEY`
  - `LLM_BASE_URL`
  - `LLM_MODEL`
  - `LLM_MODEL_CANDIDATES`
  - `DEEPSEEK_API_KEY`
  - `DEEPSEEK_BASE_URL`
  - `DEEPSEEK_MODEL`
  - `MIMO_API_KEY` / `MODELSCOPE_API_KEY`
  - `MIMO_BASE_URL` / `MODELSCOPE_BASE_URL`
  - `MIMO_MODEL` / `MODELSCOPE_MODEL`
  - `MIMO_MODEL_CANDIDATES` / `MODELSCOPE_MODEL_CANDIDATES`
- Runtime entry:
  - `ZXFLLMClient._resolve_llm_endpoint()`
  - `ZXFLLMClient._complete_with_retry(messages, max_retries=1)`

### 3. Contracts
- Generic provider contract:
  - For unknown providers, prefer `LLM_PROVIDER=openai-compatible`.
  - `LLM_BASE_URL` may be either an OpenAI-compatible root ending in `/v1` or a full `/chat/completions` URL.
  - `LLM_MODEL` must be the exact model id shown by the user's provider console.
  - `LLM_MODEL_CANDIDATES` is a comma-separated retry order for alternate model ids.
- Mimo/ModelScope contract:
  - `LLM_PROVIDER=mimo` and `LLM_PROVIDER=modelscope` both use the OpenAI-compatible call path.
  - `mimo-v2.5-pro` is a legacy alias and must not be documented as the preferred model id.
  - Legacy `mimo-v2.5-pro` is mapped to `Qwen/Qwen3-235B-A22B` to avoid breaking existing demo env files.
- Availability contract:
  - OpenAI-compatible providers are available only when API key, normalized base URL, and resolved model are all non-empty.

### 4. Validation & Error Matrix
- Missing API key/base/model -> `is_available()` is false and consultation uses local fallback.
- HTTP 400 with “invalid model / model id / model not found” -> try the next configured model candidate before final fallback.
- All model candidates fail -> return local fallback with the error summary in `thinking_process`, not in the main answer.
- Network timeout / provider unreachable -> retry the same model according to `max_retries`, then local fallback.

### 5. Good / Base / Bad Cases
- Good: `LLM_PROVIDER=openai-compatible`, exact provider model id in `LLM_MODEL`, and backup ids in `LLM_MODEL_CANDIDATES`.
- Base: `LLM_PROVIDER=mimo` with `MIMO_MODEL=Qwen/Qwen3-235B-A22B`.
- Bad: documenting or requiring `mimo-v2.5-pro` as the active ModelScope model id.

### 6. Tests Required
- Endpoint resolution:
  - assert generic OpenAI-compatible config uses `LLM_*` fields.
  - assert `/v1` base URLs normalize to `/v1/chat/completions`.
- Model compatibility:
  - assert legacy `mimo-v2.5-pro` maps to a valid ModelScope-style model id.
  - assert invalid-model errors advance to the next candidate.
- Fallback:
  - assert non-model HTTP errors do not skip to another model unless they match invalid-model wording.

### 7. Wrong vs Correct
#### Wrong
```env
LLM_PROVIDER=mimo
MIMO_MODEL=mimo-v2.5-pro
```

#### Correct
```env
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://api-inference.modelscope.cn/v1
LLM_API_KEY=your_key
LLM_MODEL=Qwen/Qwen3-235B-A22B
LLM_MODEL_CANDIDATES=Qwen/Qwen3-235B-A22B,Qwen/Qwen3-30B-A3B
```

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
