# Task 2: Autonomous Natural-Language Automated Testing Tool (Playwright & AI)

## Overview
An autonomous, AI-driven web test automation tool built with **Python**, **Playwright**, and a **ReAct (Reason + Act) Agent Architecture**.

It takes test cases written in **plain, unstructured English** (e.g., *"Log in as a customer on phptravels.net and verify the dashboard is shown"*), launches a real browser, autonomously explores and interacts with web elements, validates assertions, and outputs a clear **PASS/FAIL** report with visual evidence.

### Zero Hardcoding
Evaluators explicitly required: *"We will run your tool on new test cases you haven't seen, including on a different website, so please don't hard-code anything to one site."*

This tool does **not** rely on static locators or site-specific scripts. Instead, it inspects live DOM state, generates a semantic interactive accessibility tree, decides on optimal actions using LLM reasoning (with automatic fallback), and verifies assertions dynamically across any web platform (e.g. PHP Travels, Herokuapp, CloudQA, etc.).

---

## Architecture & How It Works

```
                                  [ Plain-English Test Goal ]
                                              │
                                              ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               AUTONOMOUS AGENT LOOP (ReAct)                            │
│                                                                                        │
│   ┌────────────────────┐     ┌─────────────────────┐     ┌────────────────────────┐    │
│   │  DOM OBSERVER      │ ──> │  LLM PLANNER        │ ──> │  BROWSER CONTROLLER    │    │
│   │  Extracts visible  │     │  (Gemini / OpenAI / │     │  Executes actions      │    │
│   │  interactive nodes │     │  Heuristic Fallback)│     │  (click, fill, wait)   │    │
│   │  [e1], [e2], ...   │     │  Decides next step  │     │  via Playwright        │    │
│   └────────────────────┘     └─────────────────────┘     └────────────────────────┘    │
│             ▲                                                        │                 │
│             └────────────────── [ New Page State ] ──────────────────┘                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                            [ HTML & JSON Test Report with Screenshots ]
                            [ Terminal PASS / FAIL Verdict ]
```

1. **Perceive (DomObserver)**: Injects a lightweight DOM extractor that finds visible interactive nodes (`<button>`, `<a>`, `<input>`, `<select>`, ARIA controls), filters out hidden elements, and assigns token-efficient identifiers `[e1]`, `[e2]`, etc.
2. **Decide (LLMPlanner)**: The agent receives the test goal, current URL, page text highlights, and available controls. It returns a structured JSON action (`navigate`, `click`, `fill`, `assert`, `finish`) with explicit reasoning.
3. **Multi-Model & Offline Resilience**:
   - Supports **Google Gemini** (`gemini-2.5-flash`, `gemini-1.5-flash`) via the official `google-genai` SDK.
   - Supports **OpenAI** (`gpt-4o`, `gpt-4o-mini`).
   - Includes a deterministic **Semantic Heuristic Planner** that runs immediately out of the box if no API key is configured.
4. **Act (BrowserController)**: Dispatches actions via Playwright with smart scrolling, force clicks, masked password inputs, and modal banner auto-handling.
5. **Report (TestEngine)**: Records step-by-step history, captures timestamped PNG screenshots, and compiles interactive HTML and JSON reports.

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10+
- Pip package manager

### 2. Install Dependencies
```bash
cd Task2_NL_AutomatedTesting_Playwright
pip install -r requirements.txt
playwright install chromium
```

### 3. (Optional) Configure AI Model API Key
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add your API key:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
# or OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gemini-2.5-flash
```
> **Note**: Even if you do not provide an API key, the tool automatically activates its built-in semantic planner so you can immediately run tests offline without errors!

---

## Running Test Cases

### 1. Run the Primary PHP Travels Test Case (Visible Browser)
```bash
python run_test.py --test "Log in as a customer on phptravels.net and verify the dashboard is shown"
```

### 2. Run in Headless Mode
```bash
python run_test.py --test "Log in as a customer on phptravels.net and verify the dashboard is shown" --headless
```

### 3. Run on a Completely Different Website (Herokuapp Authentication)
```bash
python run_test.py --test "Visit https://the-internet.herokuapp.com/login, log in with username tomsmith and password SuperSecretPassword!, and verify Secure Area is displayed" --headless
```

### 4. Run the Full Multi-Site Test Suite
```bash
python run_test.py --suite examples/test_cases.json --headless
```

---

## Generated Execution Reports

After every run, detailed reports and step screenshots are saved to `reports/`:
- **HTML Report**: `reports/test_report_<timestamp>.html` (Interactive table with goal, duration, step reasoning, execution status, and click-to-zoom screenshots).
- **JSON Report**: `reports/test_report_<timestamp>.json` (Full structured telemetry for CI/CD pipelines).
- **Step Screenshots**: `reports/screenshots/step_<N>_<timestamp>.png`

---

## Project Structure

```
Task2_NL_AutomatedTesting_Playwright/
├── core/
│   ├── browser_controller.py      # Playwright driver, action execution & screenshots
│   ├── dom_observer.py            # Extracts interactive DOM tree & token-efficient snapshots
│   ├── llm_planner.py             # Multi-provider reasoning agent (Gemini, OpenAI, Heuristic)
│   └── test_engine.py             # Orchestrator & report generator
├── models/
│   └── actions.py                 # Pydantic schemas for actions, elements & reports
├── examples/
│   └── test_cases.json            # Multi-site test cases suite
├── reports/                       # Generated HTML/JSON reports & step screenshots
├── .env.example                   # Configuration template
├── run_test.py                    # Main CLI entry point
├── requirements.txt               # Dependencies
├── README.md                      # Setup & documentation
└── APPROACH_AND_LIMITATIONS.md    # Design rationale & limitations analysis
```
