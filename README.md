<div align="center">

# RESUME_SKILL

### AI-powered job application copilot for resume analysis, browser automation, and GUI recovery

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/LangGraph-Orchestration-1C3C3C?style=for-the-badge" alt="LangGraph" />
  <img src="https://img.shields.io/badge/Chrome_DevTools-MCP-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Chrome DevTools MCP" />
  <img src="https://img.shields.io/badge/Vision-GUI_Agent-8A2BE2?style=for-the-badge" alt="Vision GUI Agent" />
  <img src="https://img.shields.io/badge/License-MIT-00D9FF?style=for-the-badge" alt="MIT License" />
</p>

RESUME_SKILL is evolving from an autofill script into a LangGraph-driven application agent: it analyzes your resume, understands job descriptions, plans the application flow, operates Chrome through Google Chrome DevTools MCP, and uses vision feedback to recover from complex UI failures.

</div>

---

## What It Does

RESUME_SKILL helps with the repetitive parts of online job applications while keeping the user in control.

```text
Resume PDF
  -> AI resume analysis
  -> profile review
  -> JD analysis
  -> tailored application materials
  -> browser application planning
  -> Chrome MCP execution
  -> vision-based GUI verification and recovery
```

The project is designed for real application forms, not only simple HTML inputs. The next-generation workflow treats each page as an interactive GUI task: observe the page, plan one safe action, execute it, verify visually, and recover when the UI behaves unexpectedly.

## Why This Matters

Most job application sites are not clean forms. They contain custom dropdowns, async validation, file upload widgets, modal dialogs, multi-step flows, city pickers, date pickers, and login interruptions. A one-shot `fill()` call is not enough.

RESUME_SKILL combines three layers:

| Layer | Role |
| --- | --- |
| Text LLM | Understands resume data, JD requirements, field meaning, and safe answers |
| Chrome DevTools MCP | Provides browser observation and controlled actions such as `click`, `fill_form`, `upload_file`, `take_snapshot`, and `take_screenshot` |
| Vision GUI Agent | Verifies what actually happened on screen and proposes recovery actions for difficult UI controls |

The goal is not blind automation. The goal is controlled assistance with visible state, logs, recovery, and explicit manual handoff for sensitive or unsafe steps.

---

## Current Direction

The core workflow is being migrated to LangGraph.

```text
START
  -> Resume Analyzer
  -> Job Description Analyzer
  -> Resume Customization
  -> Cover Letter Generator
  -> Application Planner
  -> Browser Executor
  -> Verify Result
      -> success -> END
      -> recoverable failure -> GUI Recovery -> Browser Executor
      -> manual required -> END
```

### Unified Agent State

The workflow is centered around a shared state object:

```python
{
    "user_profile": {...},
    "resume_data": {...},
    "resume_pdf_path": "...",
    "job_description": {...},
    "application_form": {...},
    "generated_documents": {...},
    "browser_context": {...},
    "current_task": "...",
    "next_action": {...},
    "execution_history": [...],
    "errors": [...],
    "gui_recovery_needed": False,
    "manual_required": False,
    "success": False,
}
```

This gives the agent memory, traceability, and a clear success criterion: a field is not considered done until the browser action has completed and the page state has been verified.

---

## Agent Nodes

The planned LangGraph nodes are intentionally small and auditable.

| Node | Responsibility |
| --- | --- |
| Resume Analyzer | Parse the user's resume and extract profile, education, projects, skills, and work history |
| Job Description Analyzer | Extract requirements, responsibilities, keywords, and match criteria from a JD |
| Resume Customization | Tailor resume content toward the target role |
| Cover Letter Generator | Generate cover letters, self-introductions, and open-question drafts |
| Application Planner | Decide the next safe browser action from profile, page state, and execution history |
| Browser Executor | Execute whitelisted browser actions through Chrome DevTools MCP |
| Verify Result | Use snapshot and screenshot evidence to decide whether the action really worked |
| GUI Recovery | Use a lightweight vision-guided loop to recover from custom dropdowns, upload widgets, modals, and failed inputs |

---

## Browser Automation Strategy

RESUME_SKILL uses Google Chrome DevTools MCP as the browser execution layer.

Key MCP tools used by the project:

| Tool | Purpose |
| --- | --- |
| `take_snapshot` | Read the accessibility tree and obtain stable `uid` references |
| `take_screenshot` | Capture the actual visual page for vision verification |
| `fill_form` | Fill multiple stable inputs quickly |
| `fill` | Fill one text input, textarea, select, checkbox, or radio |
| `click` | Open dropdowns, buttons, tabs, and custom controls |
| `upload_file` | Upload the local resume PDF to the official application website |
| `type_text` / `press_key` | Recover when direct filling does not work |
| `wait_for` | Wait for async page changes |

Chrome DevTools MCP is the agent's hands and eyes. The models decide what to do; MCP executes only approved actions.

---

## Lightweight GUI Agent

The GUI recovery layer is deliberately narrow. It is not a heavyweight Computer Use agent.

It only performs:

1. Page screenshot
2. Visual understanding
3. Control or coordinate localization
4. Mouse and keyboard actions through the browser adapter

Example action schema:

```json
{
  "type": "click",
  "uid": "1_24",
  "value": "",
  "reason": "Open the education dropdown before selecting an option"
}
```

Allowed recovery actions are restricted to:

```text
click | type_text | press_key | upload_file | manual
```

The agent does not execute arbitrary JavaScript and does not click final submit buttons unless explicitly allowed.

---

## Installation

### Requirements

| Dependency | Version |
| --- | --- |
| Python | 3.10+ recommended |
| Node.js | 18+ |
| Google Chrome | Recent stable version |
| LLM API Key | Volcengine Ark / OpenAI-compatible provider |

The local development environment used by this project is:

```powershell
conda activate resume-skill-v24
```

Environment path used during development:

```text
D:\ProgramData\Anaconda3\envs\resume-skill-v24
```

### Setup

```powershell
git clone git@github.com:GalaxyKB/RESUME_SKILL.git
cd RESUME_SKILL

conda activate resume-skill-v24
pip install -e .

copy .env.example .env
# Edit .env and add your own API keys. Never commit .env.

npx chrome-devtools-mcp@latest --help
```

### Start Web UI

```powershell
$env:PYTHONPATH = "src"
python -B -m resume_skill.webui.app --clean
```

Then open:

```text
http://127.0.0.1:5000/
```

---

## Configuration

`.env.example` is a public template. It must not contain real keys.

`.env` is your private local configuration and is ignored by Git.

Recommended dual-model setup:

```env
LLM_PROVIDER=ark
ARK_API_KEY=your_ark_api_key_here
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=doubao-seed-2-0-lite-260428

VISION_ENABLED=true
VISION_PROVIDER=ark_chat
VISION_API_KEY=your_ark_api_key_here
VISION_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VISION_MODEL=doubao-seed-2-1-turbo-260628
```

Recommended model split:

| Capability | Model Role |
| --- | --- |
| Text planning | Resume/JD understanding, field semantics, safe answers |
| Vision verification | Screen-state validation, dropdown recovery, upload confirmation, UI anomaly detection |

---

## User Workflow

### 1. Upload Resume Locally

Upload a PDF resume in the Web UI. This step extracts local profile data and creates `profile_template.md`.

This is separate from website attachment upload.

### 2. Review Profile

Edit and complete the generated Markdown profile.

### 3. Set Job Preferences

Add target companies, roles, cities, and preference information.

### 4. Scout Openings

Open target company career pages and collect candidate jobs.

### 5. Fill Application Page

Navigate Chrome to the target application form. The agent observes the page, plans browser actions, fills stable controls, uploads the resume PDF when required, and uses vision verification to decide whether the page is actually complete.

### 6. Review and Submit Manually

The project is designed to help prepare the application, not blindly submit it. Final submission should remain user-controlled unless explicitly enabled.

---

## Privacy and Safety

- `.env` is ignored by Git and must contain real API keys only locally.
- `.env.example` is safe to publish and must contain placeholders only.
- Resume files and generated personal profiles are ignored by Git.
- Sensitive fields such as ID number, political status, passport number, bank details, and verification codes should be marked manual.
- The agent should not auto-submit final applications without explicit user approval.
- Execution history is recorded so every browser action can be inspected.

---

## Project Layout

```text
src/resume_skill/
├── cli.py                       # CLI entrypoints
├── config.py                    # Application configuration
├── extractor/
│   └── extractor.py             # Resume PDF extraction and profile generation
├── llm/
│   ├── base.py                  # Base LLM interface
│   ├── ark_provider.py          # Volcengine Ark text/vision providers
│   ├── vision.py                # Vision client factory
│   └── factory.py               # Text LLM factory
├── agent/
│   └── mcp/
│       ├── chrome_client.py     # Chrome DevTools MCP JSON-RPC client
│       └── agent.py             # Legacy MCP filling logic
├── workflow/
│   ├── state.py                 # LangGraph state model
│   ├── graph.py                 # StateGraph construction
│   ├── nodes.py                 # Agent node implementations
│   ├── runner.py                # Workflow runner
│   └── store.py                 # In-memory task store
└── webui/
    ├── app.py                   # Flask API
    └── templates/index.html     # Vue2 single-page Web UI
```

---

## Roadmap

- LangGraph orchestration for the full application lifecycle
- Background task execution with status polling
- Per-action visual verification
- GUI recovery for dropdowns, modal dialogs, upload widgets, and custom controls
- JD-aware resume tailoring
- Cover letter and open-question generation
- Safer manual handoff for login, CAPTCHA, SMS verification, and sensitive fields

---

## License

[MIT License](LICENSE)

<div align="center">

Built for people who are tired of typing the same application form twenty times.

</div>
