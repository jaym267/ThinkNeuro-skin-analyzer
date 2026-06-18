# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
**Dermatica / DermAI Pro** (repo: `ThinkNeuro-skin-analyzer`) is a skin-image analysis tool. A user uploads a skin photo and a vision model returns a structured, non-diagnostic assessment (severity, possible conditions with likelihood, risk factors, recommended action, self-care tips). Every response carries a disclaimer that it is **not** a medical diagnosis.

## Setup & Commands
- Install deps: `pip install -r requirements.txt`
- Run the web app: `py -m streamlit run app.py --server.port 8501` (or just run `start.bat` on Windows)
- Run the CLI: `python analyze.py <image_path>`
- Requires a `GROQ_API_KEY` in a local `.env` file (never commit it; on Streamlit Cloud it's read from `st.secrets` instead — see `get_client()` in `app.py`).
- There is no test suite, linter, or build step configured in this repo.

## Architecture
- **`app.py`** — the entire app (UI + logic, single file, ~1800 lines). This is the primary entry point. Key pieces, top to bottom:
  - `get_client()` — `st.cache_resource`-cached Groq client; reads the API key from env or `st.secrets`.
  - `RATE_LIMITS` / `acquire_request_slot()` — dual rate limiting: a per-session deque (in `st.session_state`) and a process-wide deque guarded by a lock (`_global_rate_state()`, also `st.cache_resource`, shared across all visitors on a deployment). Both must allow a call before one is recorded.
  - `load_validated_image()` — upload validation pipeline: size cap, empty-file check, `Image.verify()` then a real decode pass, decompression-bomb guard (`Image.MAX_IMAGE_PIXELS`), RGB conversion, downscale to `MAX_IMAGE_DIM`.
  - `analyze_image()` — sends the image (inline base64 JPEG) plus a prompt that demands an exact labeled-section text format (`SEVERITY_SCORE:`, `CONDITIONS:`, etc.) to the vision model.
  - `parse_analysis()` — regex-parses that labeled text back into a dict. **This is tightly coupled to the prompt in `analyze_image()`**: if the prompt's section labels/format change, the regexes must change too, or fields silently fall back to their defaults (e.g. `severity_level: "MODERATE"`) instead of raising an error.
  - `ask_followup_stream()` — streamed chat follow-up; reuses the last analysis text and the original image as context, yields chunks for live typing.
  - `build_report()` — renders the analysis dict as a plain-text downloadable report.
  - Session state (`analysis_history`, `chat_messages`, `current_analysis`, `current_image`, `current_image_b64`, `pending_q`) drives which view renders.
  - UI: sidebar (status, session stats, recent-history list, rotating skin tips, plus a JS-injected `components.html` block that adds a collapsible show/hide toggle for the sidebar). Main area is upload view when `current_analysis is None`, otherwise a 3-tab view: Analysis Results / Follow-up Questions / Download Report.
- **`analyze.py`** — standalone CLI (`python analyze.py image.jpg`). It duplicates the vision call with its own (simpler, unstructured-prose) prompt and is **not** wired into `app.py`'s parsing, rate limiting, or validation — treat it as a separate code path, not a shared library.
- **Model**: Groq API, `meta-llama/llama-4-scout-17b-16e-instruct` (vision). Images are base64-encoded and sent as inline `data:` URLs in both `app.py` and `analyze.py`.
- **`.streamlit/config.toml`** — production server settings: 10 MB upload cap, XSRF on, CORS off.
- **`.devcontainer/devcontainer.json`** — Codespaces/devcontainer setup; note its `postAttachCommand` runs Streamlit with `--server.enableCORS false --server.enableXsrfProtection false`, which is a *dev-only* relaxation distinct from the production `config.toml` above — don't port that combination into production config.

## Conventions & Constraints
- **Secrets**: keep `GROQ_API_KEY` in `.env` only — it is gitignored, never hardcode or commit it.
- **Security**: preserve existing protections (upload size limit, decompression-bomb guard, input validation, output escaping via `html_lib.escape`, rate limiting, XSRF). Don't loosen them without reason.
- **Medical safety**: keep the non-diagnostic disclaimer on every analysis output. Do not present results as a diagnosis.
- **Prompt/parser coupling**: changes to the structured prompt in `analyze_image()` must be mirrored in `parse_analysis()`'s regexes (see Architecture above).
- **Dependencies are pinned** in `requirements.txt` — match the pinned versions.

## Git & GitHub Workflow
- Automatically commit after completing each logical unit of work
- Stage only the files that change as a necessary, direct result of that unit of work — never sweep in unrelated, generated, or stray files (e.g. logs, caches, scratch images) with `git add -A`/`git add .`
- Use conventional commit messages (feat:, fix:, refactor:, docs:)
- Push to remote after commits are made
- Keep commit messages clear and descriptive
