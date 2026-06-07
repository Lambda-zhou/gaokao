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

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
