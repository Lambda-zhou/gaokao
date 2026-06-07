# brainstorm: analyze codebase and improvement directions

## Goal

Read the repository end-to-end, explain what the system currently does, what business it already covers, and identify the most valuable improvement directions for the next iteration.

## What I already know

* This repo is an AI-assisted gaokao volunteering system named “志愿智选”.
* The user is explicitly interested in whether LLM can be configured to read existing project data and help users find preferred schools / volunteer choices.
* The user chose direction 1: design a minimum viable approach for “LLM + existing local data” to help users find schools / volunteer options.
* The user chose the first MVP entrypoint: recommend schools based on the student's profile.
* The product combines:
  * AI consultation
  * student-profile capture
  * school directory browsing
  * synced recommendation audit desk
  * career / profession insight display
* Backend stack is FastAPI + Pydantic + local JSON data + DeepSeek / Anthropic integration.
* Frontend is a single-file HTML app (`zhiyuan-agent.html`) using React UMD + Babel + Tailwind CDN.
* Core backend behavior is concentrated in a few large modules:
  * `core/consult_orchestrator.py` ≈ 4064 lines
  * `core/agent_engine.py` ≈ 1813 lines
  * `core/llm_client.py` ≈ 844 lines
* Frontend is highly monolithic:
  * `zhiyuan-agent.html` ≈ 5604 lines
* Main local datasets:
  * `data/schools.json` — 498 schools
  * `data/majors.json` — 58 majors
  * `data/school_admissions_urls.json`
  * `data/quotes.json`
* Current tests focus mainly on consultation intent contracts, response guardrails, and stream/final reconciliation.
* Session storage and rate limiting are currently in-memory only.
* The repo already encodes an important product stance: distinguish official data, public-source data, local estimates, and rule simulation.

## Assumptions (temporary)

* Current codebase is aimed at demo / MVP / course-project / showcase stage rather than production-grade deployment.
* The strongest current value is “AI explanation + rule-based recommendation framing”, not “authoritative admissions decisioning”.
* Several UI modules are presentation-heavy or front-end-local, while the chat/recommendation workflow is the most complete product path.

## Open Questions

* (none at the moment; ready for confirmation)

## Requirements (evolving)

* Produce a repository-level explanation of implemented functionality.
* Explain what real business workflow the code already supports.
* Identify structural strengths and weaknesses from code inspection, not only from README claims.
* Propose concrete improvement directions and prioritize them.
* Evaluate whether existing local datasets + LLM can support school / volunteer search in a practical way.
* Produce a concrete MVP design for “LLM + current local data” without requiring a full admissions data rebuild first.
* MVP entrypoint is profile-based school recommendation.
* MVP output mode is hybrid:
  * main result = coarse recommendation based on current local data
  * secondary result = “冲/稳/保 tendency” with explicit low-confidence / reference-only wording
* First implementation lives inside the existing chat flow only; avoid building a new dedicated page or primary entrypoint in this MVP.
* When the profile is incomplete, use dual-layer output:
  * still provide directional advice based on known preferences
  * clearly state that an actual school list requires province / score (and ideally rank)
* Recommendation result should be a short curated list of 6 schools, ideally expressed as 2 冲 / 2 稳 / 2 保 tendencies.
* When precise admissions data is missing, rank candidates primarily by preference-match score:
  * city preference
  * major preference
  * school level / type fit
  * family-risk fit
  * employment / direction fit
  and only then map the shortlist into “冲 / 稳 / 保 tendency” buckets with explicit low-confidence wording.

## Acceptance Criteria (evolving)

* [ ] Summarize the product in business language.
* [ ] Map major features to actual code structure.
* [ ] Distinguish implemented capabilities from demo/static capabilities where relevant.
* [ ] Provide a prioritized improvement roadmap with rationale.
* [ ] Define an MVP that works inside the existing chat flow.
* [ ] MVP can produce a short list of 6 schools from current local data when profile data is sufficient.
* [ ] MVP uses coarse recommendation as the main output and “冲/稳/保 tendency” as secondary low-confidence output.
* [ ] MVP gives directional advice instead of fake precision when profile data or admissions data is incomplete.

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Technical Approach

Use the current chat flow as the only MVP entrypoint.

1. Detect a profile-based school recommendation intent from the existing consult flow.
2. Build / refine a candidate selector over current local data (`schools.json`, `majors.json`).
3. Compute a coarse preference-match score from:
   * city preference
   * major preference
   * school level / school type
   * family background risk fit
   * employment / direction fit
4. Select a short curated list of 6 schools.
5. Convert the 6-school shortlist into:
   * main output: coarse recommendation
   * secondary output: “冲 / 稳 / 保 tendency” with explicit reference-only wording
6. Hand only the shortlisted structured result to the LLM for explanation, trade-offs, and risk reminders.
7. If key profile fields are missing, output:
   * directional advice from known preferences
   * a clear statement that school-list recommendation requires province / score / ideally rank

## Decision (ADR-lite)

**Context**: Current repo already has chat orchestration, rule engine structure, and local school/major data, but lacks precise admissions-grade data needed for reliable录取-level recommendation.

**Decision**: Build the first usable school-finding MVP as a chat-only, hybrid coarse recommendation system. Candidate ranking is preference-match-first, not admissions-precision-first. The visible result is a short 6-school list, with “冲/稳/保” shown only as low-confidence tendency labeling.

**Consequences**:

* Pros:
  * minimal code-surface change
  * reuses current architecture
  * avoids fake precision
  * lets LLM add explanation without forcing it to search the whole dataset
* Cons:
  * recommendation credibility remains limited by current data
  * “冲/稳/保” cannot be treated as real录取判断
  * later migration to admissions-grade recommendation will still require new data sources

## Out of Scope (explicit)

* Implementing the improvements in this brainstorm step
* Declaring any admissions / salary / employment data authoritative
* Full production-readiness audit of infrastructure/security/compliance
* Precise province-year-major admissions probability modeling

## Technical Notes

* Files inspected:
  * `README.md`
  * `main.py`
  * `api/consult.py`
  * `api/agent.py`
  * `api/data.py`
  * `api/evaluate.py`
  * `api/sessions.py`
  * `core/consult_orchestrator.py`
  * `core/agent_engine.py`
  * `core/llm_client.py`
  * `core/research_client.py`
  * `core/models.py`
  * `core/session_manager.py`
  * `core/zxf_engine.py`
  * `core/answer_guard.py`
  * `core/family_risk.py`
  * `middleware/rate_limit.py`
  * `tests/test_consult_intent_contracts.py`
  * `zhiyuan-agent.html`
* Initial architectural read:
  * backend has a real execution path from API → orchestrator → rule engine / research / LLM → guard
  * chat flow is the most operationally complete path
  * school directory and career insight pages contain a large amount of embedded front-end data / display logic
  * maintainability risk is dominated by file-size concentration and mixed responsibilities
