---
name: resume-auto-fill
description: >
  AI-powered resume auto-fill skill for job applications on Chinese recruitment
  websites (BOSS Zhipin, Lagou, 51job, Zhaopin, NetEase, Niuke, etc.). Use when
  the user wants to extract info from a resume PDF, fill job application forms
  automatically, or apply to positions. Handles form scanning, semantic field
  matching, auto-filling with human-in-the-loop safety, and resume PDF upload.
  Keywords: 投递, 网申, 填表, apply, resume fill, job application, 简历, 秋招.
license: MIT
---

# Resume Auto-Fill Skill

AI-driven smart form filling for job applications. Extracts personal info from
your resume, semantically matches form fields, and auto-fills with safety checks.

## Prerequisites

1. Install the package:
   ```bash
   pip install resume-skill
   resume-skill setup
   ```

2. Configure API key in `.env`:
   ```env
   LLM_PROVIDER=deepseek
   DEEPSEEK_API_KEY=your_key_here
   ```
   Or use OpenAI:
   ```env
   LLM_PROVIDER=openai
   OPENAI_API_KEY=your_key_here
   ```

3. Place your PDF resume in `personal_info/formal_resume/`

## Workflow

### Step 1: Extract Personal Info

```bash
resume-skill extract --pdf personal_info/resume/my_resume.pdf
```

This extracts info from your PDF and updates `profile_template.md`. Review and
edit the template to add any missing information.

### Step 2: Generate Unified Profile

```bash
resume-skill consolidate
```

This reads `profile_template.md` and generates `personal_info/unified_profile.yaml`
using AI. This YAML file is the data source for form filling.

### Step 3: Auto-Fill Job Applications

```bash
# Login to recruitment site first (saves session)
resume-skill apply --url "https://..." --mode login

# Then auto-fill the form
resume-skill apply --url "https://..." --mode fill --auto-fill

# Or do everything in one go
resume-skill apply --url "https://..." --auto-fill
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `resume-skill extract --pdf <path>` | Extract info from resume PDF |
| `resume-skill consolidate` | Generate unified_profile.yaml |
| `resume-skill apply --url <url>` | Open job page and fill form |
| `resume-skill apply --mode login` | Login only (save session) |
| `resume-skill apply --mode fill` | Fill form using saved session |
| `resume-skill setup` | Install Playwright browsers |
| `resume-skill doctor` | Check LLM connectivity |

## Apply Mode Options

- `--mode full` - Full workflow: analyze JD + fill form (default)
- `--mode login` - Only login to save browser session
- `--mode fill` - Skip JD analysis, go straight to form filling
- `--mode form` - Same as fill mode
- `--auto-fill` - Enable automatic form filling
- `--keep-browser-open` - Keep browser open after completion
- `--headless` - Run browser in headless mode
- `--json` - Output results in JSON format (for programmatic use)

## How It Works

### Dual-Channel Field Extraction

1. **Channel A (Rule-based)**: Fast extraction of all visible form elements using
   DOM selectors. Captures inputs, selects, textareas, radio groups, checkboxes,
   file uploads, and custom components.

2. **Channel B (AI HTML Analysis)**: Sends page HTML to LLM for semantic
   understanding. Identifies field purposes, relationships, and generates precise
   selectors.

3. **Merge**: AI results are preferred; rule-based results fill gaps.

### Semantic Field Matching

Uses LLM to match form fields with your profile data through semantic understanding:
- "联系方式" → matches phone number
- "就读高校" → matches school name
- "毕业院校" → matches university
- "到岗时间" → matches availability

Each match includes:
- `fill_strategy`: text / select / radio_click / checkbox_click / datepicker /
  cascader / upload / contenteditable
- `confidence`: 0.0-1.0
- `action`: auto_fill / review / manual / skip

### Multi-Strategy Form Filling

For each field, tries multiple strategies with fallback:

| Strategy | Fallback Chain |
|----------|---------------|
| Text input | fill → keyboard type → JS evaluate |
| Native select | select_option(label) → select_option(value) → fuzzy match |
| Custom dropdown | click+find option → type+search → keyboard navigate |
| Radio button | click label → click input → text-based search |
| Checkbox | click → click label |
| Date picker | fill → keyboard type → calendar click |
| Cascader | level-by-level click → type filter |
| File upload | set_input_files → hidden input → click button |
| Contenteditable | click+type → JS innerText → JS innerHTML |

Post-fill verification checks actual values against expected values.

## Safety Rules

- **NEVER auto-submit forms** - Always require explicit user confirmation
- Sensitive fields (ID card, political status, etc.) are marked as manual-only
- Fill plan summary is displayed before any auto-fill execution
- All personal data stays local - nothing is uploaded to cloud
- Browser session data is stored locally in `.session/`

## JSON Output Mode

Add `--json` to extract/consolidate commands for programmatic use:

```json
{
  "status": "success",
  "action": "extract",
  "profile_path": "personal_info/unified_profile.yaml"
}
```

## Troubleshooting

- Run `resume-skill doctor` to check LLM connectivity
- Ensure Playwright browsers are installed: `resume-skill setup`
- Check `.env` has valid API key
- Review `outputs/logs/` for detailed error logs
