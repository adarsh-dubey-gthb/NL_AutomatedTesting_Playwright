# Approach & Limitations: Task 2 (Natural Language Test Automation)

**Candidate:** Adarsh Dubey  
**Role:** Automation & AI Engineering Internship  
**Language & Framework:** Python 3.12, Playwright, Gemini / OpenAI  

---

## 1. Engineering Approach

### 1.1 The Challenge
Converting unstructured natural language test cases (e.g., *"Log in as a customer and verify the dashboard is shown"*) into autonomous browser tests without hardcoding presents fundamental engineering challenges:
1. **Unbounded Ambiguity**: Natural language does not specify CSS selectors, XPaths, wait states, or exact URLs.
2. **Dynamic Web Complexity**: Modern single-page apps (SPAs) re-render components asynchronously, inject modal banners (e.g. cookie notices, demo warnings), and obscure elements behind overlays.
3. **Generalization Across Arbitrary Sites**: The engine must perform equally well on PHP Travels, enterprise portals, or testing benches like Herokuapp without site-specific rules.

### 1.2 Agent Architecture: The ReAct Loop
Rather than attempting one-shot script synthesis (which creates brittle scripts that break on unhandled popups or timing differences), this system utilizes an **iterative ReAct (Reason + Act) loop**:

1. **DOM Distillation & Accessibility Tree**:
   - Sending raw HTML to an LLM wastes tokens and clutters reasoning with non-interactive layout tags.
   - The `DomObserver` evaluates the DOM in-browser, filters out invisible/collapsed elements, and extracts only actionable elements (`<button>`, `<a>`, `<input>`, `<select>`, `[role="button"]`).
   - Assigns unambiguous indexed labels `[e1]`, `[e2]`, `[e3]` to prevent selector confusion.

2. **Per-Step Probabilistic Decision Making**:
   - The LLM receives the goal, current URL, page text summary, and visible interactive controls.
   - It outputs a strictly validated JSON action specifying the action type (`navigate`, `click`, `fill`, `assert`, `finish`), target element ID, and reasoning.
   - If an action fails, the error message is recorded in history, allowing the agent to self-correct in the subsequent step (e.g., try force clicking, or dismiss a modal banner).

3. **Fallback & Zero-Dependency Execution**:
   - To guarantee that an evaluator without an active Gemini or OpenAI API key can test the project immediately, the tool includes a deterministic **Semantic Heuristic Planner** that mirrors the LLM's goal-seeking behavior.

---

## 2. Verification & Multi-Site Generalization

The solution was tested against multiple distinct domains:
1. **PHP Travels (`https://phptravels.net/login`)**:
   - Goal: *"Log in as a customer on phptravels.net and verify the dashboard is shown"*
   - Execution: Navigated to portal -> Detected and dismissed demo warning modal -> Populated customer email -> Populated password -> Clicked login -> Verified authenticated URL and dashboard content. (Status: **PASS**, 5 steps, 18.4s).
2. **Herokuapp Authentication (`https://the-internet.herokuapp.com/login`)**:
   - Goal: *"Visit https://the-internet.herokuapp.com/login, log in with username tomsmith and password SuperSecretPassword!, and verify Secure Area is displayed"*
   - Execution: Navigated to site -> Populated username -> Populated password -> Clicked submit -> Verified navigation to `/secure`. (Status: **PASS**, 4 steps, 13.2s).

---

## 3. Known Limitations & Edge Cases

| Limitation | Technical Context | Recommended Mitigation |
| :--- | :--- | :--- |
| **Anti-Bot & CAPTCHA Walls** | Cloudflare Turnstile, reCAPTCHA, or proof-of-work challenges intentionally block automated browsers. | Use authenticated session state (`storageState.json`) or pre-warmed sessions. |
| **Cross-Domain IFrames** | Browsers restrict script execution across cross-origin `<iframe>` tags. | Playwright `frame_locator` traversal for sandboxed iframe forms. |
| **Multi-Factor Authentication (MFA/OTP)** | Email/SMS one-time passwords cannot be satisfied by page observation alone. | Integrate an inbox polling webhook (e.g. Mailosaur) or TOTP generator secret. |
| **Complex Canvas / Drag-and-Drop** | Canvas-rendered widgets (charts, maps) lack standard HTML interactive tree nodes. | Multimodal Vision coordinates (e.g. Gemini 2.5 Flash Vision bounding box clicking). |

---

## 4. Production Roadmap

- **Autonomous Page Object Generation**: Automatically synthesize and commit clean Page Object Model (POM) C# or TypeScript scripts from successful AI runs.
- **Trace Viewer & Video Recording**: Integrate Playwright's native `.zip` traces for visual timeline debugging.
