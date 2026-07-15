<div align="center">

# RESUME_SKILL

### A browser GUI agent for resume parsing and job application form filling

<p>
  <img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-Web_UI-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Chrome_DevTools-MCP-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Chrome DevTools MCP" />
  <img src="https://img.shields.io/badge/LangGraph-Workflow-1C3C3C?style=for-the-badge" alt="LangGraph" />
  <img src="https://img.shields.io/badge/Vision-Multimodal_Agent-7B3FE4?style=for-the-badge" alt="Vision" />
</p>

RESUME_SKILL is a vertical GUI agent prototype for online job applications. It parses a local resume, builds a structured profile, observes real application pages through Chrome DevTools MCP, fills form fields, uploads attachments, handles custom controls, and verifies results with accessibility snapshots plus vision review.

</div>

---

## Overview

Most application portals are not simple HTML forms. They use custom dropdowns, date pickers, repeated education or work-history sections, asynchronous file upload widgets, modals, validation states, and multi-step flows. A single `fill()` call is often not enough.

RESUME_SKILL approaches the page as an interactive browser task:

```text
Resume PDF
  -> local extraction and profile consolidation
  -> page snapshot and screenshot observation
  -> section-level form planning
  -> answer generation from the profile
  -> Chrome DevTools MCP actions
  -> confirmation by snapshot and vision review
  -> retry, repair, or manual handoff
```

The project is not intended to blindly submit applications. By default, it does not click final submit or apply buttons. Its purpose is to reduce repetitive form entry while keeping the user in control.

---

## Current Capabilities

| Area | Capability |
| --- | --- |
| Resume parsing | Extracts structured profile data from PDF text, with local fallback when LLM extraction fails |
| Web UI | Flask + Vue 2 CDN workflow for profile review, browser launch, and smart filling |
| Browser control | Uses Google Chrome DevTools MCP to observe and operate the real browser |
| Form planning | Groups fields into sections such as basic info, education, work history, projects, attachments, and agreements |
| Answer generation | Uses the consolidated profile and markdown evidence to answer fields section by section |
| Dropdown handling | Opens, selects, blurs, waits, and verifies selected values before marking fields confirmed |
| Resume upload | Attempts attachment upload with diagnostics and confirmation instead of treating tool success as page success |
| Vision review | Uses a vision model to assist field discovery and post-fill verification, with retry and image compression |
| Recovery | Performs bounded repair actions such as `fill`, `click`, `type_text`, `press_key`, and `upload_file` |
| Testing | Includes pytest coverage for workflow nodes, task APIs, web regressions, executor behavior, and form-plan safeguards |

---

## Architecture

```text
Web UI
  Flask app + Vue frontend
      |
      v
Profile Layer
  PDF extraction -> unified profile YAML -> profile_template.md evidence
      |
      v
Planning Layer
  Snapshot parser + visual hints + section-level FormPlan
      |
      v
Execution Layer
  Chrome DevTools MCP tools: take_snapshot, take_screenshot, click, fill, type_text, press_key, upload_file
      |
      v
Verification Layer
  Snapshot confirmation + vision review + bounded recovery actions
```

The repository also contains LangGraph-style workflow modules under `src/resume_skill/workflow/`. The current Web UI Step 5 uses a direct browser filling loop for practical reliability, while the workflow modules provide a structured path for planner/executor/verifier evolution.

---

## GUI Agent Scope

RESUME_SKILL can reasonably be described as a vertical browser GUI agent:

- It observes a live browser page through snapshots and screenshots.
- It plans actions from page state and user profile data.
- It executes bounded GUI actions through Chrome DevTools MCP.
- It verifies whether actions actually changed the page.
- It uses vision as an auxiliary recognizer and reviewer for complex UI states.

It is not a general-purpose Computer Use agent. It is specialized for online application forms and deliberately avoids arbitrary desktop control.

---

## Safety And Privacy

This project handles sensitive data. Treat local profile files, resumes, logs, and API keys carefully.

- Do not commit `.env`.
- Do not commit real resumes or personal profile files.
- Do not commit generated logs that contain profile data or API responses.
- Use `.env.example` only as a public template with placeholder values.
- Keep `FORM_FILLING_AUTO_SUBMIT` disabled unless you explicitly implement and audit final submission behavior.

The project is designed to avoid final application submission by default. Review all filled information manually before submitting on a real website.

---

## Requirements

| Dependency | Recommended Version |
| --- | --- |
| Python | 3.8+ |
| Node.js | 18+ |
| Google Chrome | Recent stable version |
| Python packages | Installed from `pyproject.toml` |
| LLM provider | Ark / Doubao / DeepSeek / OpenAI-compatible provider |
| Vision provider | Ark responses or chat-compatible vision model |

Chrome DevTools MCP is launched through `npx chrome-devtools-mcp@latest`, so Node.js must be available on `PATH`.

---

## Installation

```powershell
git clone git@github.com:GalaxyKB/RESUME_SKILL.git
cd RESUME_SKILL

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e .
copy .env.example .env
```

Edit `.env` and add your own API keys. Never commit `.env`.

To verify Chrome DevTools MCP is reachable:

```powershell
npx chrome-devtools-mcp@latest --help
```

---

## Configuration

Minimal `.env` example:

```env
LLM_PROVIDER=ark
ARK_API_KEY=your_ark_api_key_here
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=doubao-seed-2-0-lite-260428

VISION_ENABLED=true
VISION_PROVIDER=ark_responses
VISION_API_KEY=your_ark_api_key_here
VISION_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VISION_MODEL=doubao-seed-2-1-pro-260628

BROWSER_CHANNEL=chrome
DEBUG_MODE=false
LOG_LEVEL=INFO
```

Public configuration belongs in `.env.example`. Private values belong only in `.env`.

---

## Start The Web UI

```powershell
python -m resume_skill.webui.app --port 5000
```

Open:

```text
http://127.0.0.1:5000/
```

Typical workflow:

1. Upload a local resume PDF and extract profile data.
2. Review and complete the generated profile template.
3. Open Chrome from the Web UI or use an existing browser session.
4. Navigate to the target application form manually.
5. Click smart filling and watch logs for confirmed, skipped, or unconfirmed fields.
6. Review the page manually before any final submission.

---

## Smart Filling Behavior

The current smart filling loop is intentionally conservative:

- It reads the current page snapshot.
- It captures screenshots for visual hints.
- It builds a section-level `FormPlan`.
- It generates answers from profile evidence.
- It fills fields section by section.
- It confirms custom dropdowns after selection.
- It diagnoses attachment upload candidates.
- It performs vision review and bounded repair actions.

Important log states:

| Log State | Meaning |
| --- | --- |
| `页面结构计划` | Form sections were detected and grouped |
| `select_*_confirm` | A dropdown path was attempted and confirmed |
| `select unconfirmed` | The page did not confirm the selected value |
| `上传诊断` | File path, snapshot candidates, and DOM file input diagnostics were collected |
| `upload_*_confirmed` | Resume attachment upload was confirmed by page state |
| `upload unconfirmed` | Upload tool action did not produce a visible page confirmation |
| `视觉复核` | Vision model reviewed the filled page state |

---

## Development

Run the test suite:

```powershell
pytest -q
```

Run a syntax and bytecode check:

```powershell
python -m compileall src tests
```

Optional frontend script sanity check:

```powershell
node -e "const fs=require('fs'); const html=fs.readFileSync('src/resume_skill/webui/templates/index.html','utf8'); const scripts=[...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)].map(m=>m[1]).join('\n'); new Function(scripts); console.log('script ok')"
```

---

## Repository Layout

```text
src/resume_skill/
  agent/          legacy and MCP agent helpers
  extractor/      resume PDF extraction and profile consolidation
  llm/            text and vision provider adapters
  webui/          Flask Web UI and background task manager
  workflow/       LangGraph-style planner, executor, verifier, and recovery modules

tests/            pytest suite
docs/             workflow notes and quick-start documentation
personal_info/    local profile data, should not contain committed private data
outputs/          generated logs and runtime artifacts, should remain local
```

---

## Known Limitations

- Custom application portals vary heavily; some upload widgets and dropdowns require site-specific handling.
- Vision calls depend on provider latency, image payload size, and model API compatibility.
- Accessibility snapshots may omit hidden file inputs or dynamically rendered options.
- The system assists with form completion but does not replace manual review.
- Final submission remains a user-controlled step by design.

---

## License

This project is released under the MIT License.
