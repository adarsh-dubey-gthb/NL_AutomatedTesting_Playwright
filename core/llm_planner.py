import os
import json
import re
from typing import List, Optional, Dict
from models.actions import AgentAction, ActionType, PageSnapshot, StepRecord
from core.dom_observer import DomObserver


class LLMPlanner:
    """
    Intelligent Planner that turns natural-language test cases and live DOM snapshots
    into executable browser actions.
    Supports Google Gemini, OpenAI, and a built-in semantic heuristic fallback planner.
    """

    SYSTEM_PROMPT = """You are an expert autonomous web QA automation engineer.
Your task is to accomplish a plain-English test goal by interacting with a real web browser step-by-step.

At each step, you will be given:
1. The overall test goal (in plain English).
2. The current page URL and title.
3. The page text summary and alerts.
4. A list of interactive elements currently visible on the page, with temporary IDs like [e1], [e2], etc.
5. The history of actions already executed.

Based on this, you must output a SINGLE JSON object representing the next action to take.

JSON SCHEMA:
{
  "action": "navigate" | "click" | "fill" | "select_option" | "press_key" | "wait" | "assert" | "finish",
  "element_id": "e1", // The element ID from the list, or null if navigating/waiting/finishing
  "value": "text to fill, URL to navigate, or key to press",
  "assertion_condition": "expected text or URL fragment if action is assert",
  "test_passed": true | false, // Only required when action is "finish"
  "reasoning": "Clear 1-sentence explanation of why this action progresses towards the goal"
}

GUIDELINES:
- To start, if you are not yet on the relevant site, use "navigate" with the appropriate URL.
- Prefer selecting elements by their exact [eX] identifier.
- When logging in, if credentials are not explicitly given in the prompt, inspect the page for demo credentials or use standard defaults (e.g. user@phptravels.com / demouser).
- Note: Do NOT issue "finish" while still on a login/signin page. First complete the login.
- When asserting completion, check for dashboard widgets, welcome banners, account dropdowns, or logout buttons after leaving the login page.
- When the goal is verified, issue action "finish" with test_passed: true.
- If an insurmountable error or page blocker occurs, issue action "finish" with test_passed: false.
- OUTPUT ONLY VALID JSON. Do not include markdown code block ticks or explanatory prose outside the JSON.
"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
        self.provider = self._detect_provider()

    def _detect_provider(self) -> str:
        if os.getenv("OPENAI_API_KEY") and not os.getenv("GEMINI_API_KEY"):
            return "openai"
        elif self.api_key and ("sk-" in self.api_key or "openai" in self.model_name.lower()):
            return "openai"
        elif self.api_key:
            return "gemini"
        else:
            return "heuristic_fallback"

    def plan_next_action(self, goal: str, snapshot: PageSnapshot, history: List[StepRecord]) -> AgentAction:
        """Determines the next action using LLM reasoning or fallback heuristics."""
        if self.provider == "gemini":
            try:
                return self._call_gemini(goal, snapshot, history)
            except Exception as e:
                print(f"[LLMPlanner] Gemini call failed ({e}). Falling back to semantic heuristic planner.")
                return self._call_heuristic_planner(goal, snapshot, history)
        elif self.provider == "openai":
            try:
                return self._call_openai(goal, snapshot, history)
            except Exception as e:
                print(f"[LLMPlanner] OpenAI call failed ({e}). Falling back to semantic heuristic planner.")
                return self._call_heuristic_planner(goal, snapshot, history)
        else:
            return self._call_heuristic_planner(goal, snapshot, history)

    def _build_user_prompt(self, goal: str, snapshot: PageSnapshot, history: List[StepRecord]) -> str:
        history_text = "\n".join([
            f"Step {s.step_number}: {s.action.action.value} -> {s.details} [{s.status}]"
            for s in history[-5:]
        ]) if history else "None (Test just started)"

        elements_text = DomObserver.format_elements_for_prompt(snapshot.interactive_elements, limit=70)

        return f"""TEST GOAL: "{goal}"

CURRENT PAGE STATE:
- URL: {snapshot.url}
- Title: {snapshot.title}
- Page Highlights: {snapshot.clean_text_summary[:400]}

ACTION HISTORY:
{history_text}

VISIBLE INTERACTIVE ELEMENTS:
{elements_text}

Decide the single next best action to advance or verify the test goal. Output ONLY valid JSON:"""

    def _call_gemini(self, goal: str, snapshot: PageSnapshot, history: List[StepRecord]) -> AgentAction:
        from google import genai
        client = genai.Client(api_key=self.api_key)
        user_prompt = self._build_user_prompt(goal, snapshot, history)

        response = client.models.generate_content(
            model=self.model_name if "gemini" in self.model_name else "gemini-2.5-flash",
            contents=user_prompt,
            config={
                "system_instruction": self.SYSTEM_PROMPT,
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        )
        return self._parse_json_action(response.text)

    def _call_openai(self, goal: str, snapshot: PageSnapshot, history: List[StepRecord]) -> AgentAction:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        user_prompt = self._build_user_prompt(goal, snapshot, history)

        response = client.chat.completions.create(
            model=self.model_name if "gpt" in self.model_name else "gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return self._parse_json_action(response.choices[0].message.content)

    def _parse_json_action(self, raw_json: str) -> AgentAction:
        cleaned = raw_json.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        return AgentAction(**data)

    def _call_heuristic_planner(self, goal: str, snapshot: PageSnapshot, history: List[StepRecord]) -> AgentAction:
        """
        Deterministic, intelligent semantic heuristic planner.
        Ensures the tool works seamlessly on test cases out-of-the-box even without an LLM API key!
        """
        goal_lower = goal.lower()
        url_lower = snapshot.url.lower()
        page_text = snapshot.clean_text_summary.lower()

        # 1. Goal Completion Verification Check
        # NEVER claim victory if we are still on the login/signin page!
        is_on_auth_page = ("login" in url_lower or "signin" in url_lower)
        has_logged_in = any(s.action.action == ActionType.FILL for s in history)

        if not is_on_auth_page and "about:blank" not in url_lower:
            if any(term in url_lower for term in ["dashboard", "secure", "account", "profile"]):
                return AgentAction(
                    action=ActionType.FINISH,
                    test_passed=True,
                    reasoning=f"Verified: Session authenticated and navigated to '{snapshot.url}'."
                )

            if any(term in page_text for term in ["welcome back", "dashboard overview", "secure area", "you logged into a secure area", "logout"]):
                return AgentAction(
                    action=ActionType.FINISH,
                    test_passed=True,
                    reasoning="Verified: Target dashboard / secure confirmation content detected on page."
                )

        # 2. Initial Navigation: If about:blank or not on target site
        if "about:blank" in url_lower:
            found_urls = re.findall(r'https?://[^\s,]+', goal)
            if found_urls:
                target_url = found_urls[0]
            elif "phptravels" in goal_lower:
                target_url = "https://phptravels.net/login"
            elif "herokuapp" in goal_lower:
                target_url = "https://the-internet.herokuapp.com/login"
            elif "cloudqa" in goal_lower:
                target_url = "https://app.cloudqa.io/home/AutomationPracticeForm"
            else:
                target_url = "https://phptravels.net/login"

            return AgentAction(
                action=ActionType.NAVIGATE,
                value=target_url,
                reasoning=f"Navigating to test site URL: {target_url}"
            )

        # 3. Handle Cookie / Demo Warning Popups if present
        for el in snapshot.interactive_elements:
            text = (el.text or "").lower()
            if any(k in text for k in ["i understand", "accept all", "agree", "got it"]):
                already_clicked = any(s.action.element_id == el.id for s in history)
                if not already_clicked:
                    return AgentAction(
                        action=ActionType.CLICK,
                        element_id=el.id,
                        reasoning=f"Dismissing modal notice button: '{el.text}'"
                    )

        # 4. If on a landing page (like phptravels.com/demo), find and click Sign In / Login
        if "phptravels.com/demo" in url_lower:
            for el in snapshot.interactive_elements:
                text = (el.text or "").lower()
                href = (el.href or "").lower()
                if "sign in" in text or "phptravels.net/login" in href:
                    return AgentAction(
                        action=ActionType.CLICK,
                        element_id=el.id,
                        reasoning=f"Clicking link '{el.text}' to navigate to login portal"
                    )

        # 5. Form Fill Actions (Email / Username, then Password, then Submit)
        history_fills = [s for s in history if s.action.action == ActionType.FILL]
        filled_reasons = " ".join([h.action.reasoning.lower() for h in history_fills])

        # Find inputs
        email_el = None
        pass_el = None
        submit_btn = None

        for el in snapshot.interactive_elements:
            t = (el.input_type or "").lower()
            n = (el.name or "").lower()
            p = (el.placeholder or "").lower()
            txt = (el.text or "").lower()

            if t in ["email", "text"] and any(k in n or k in p for k in ["email", "username", "user"]):
                if not email_el: email_el = el

            if t == "password" or "pass" in n or "pass" in p:
                if not pass_el: pass_el = el

            if (el.tag == "button" and any(k in txt for k in ["login", "sign in", "submit"])) or (t == "submit" and "subscribe" not in txt):
                if not submit_btn: submit_btn = el

        # Step 5A: Fill Email / Username (if not already filled in history)
        if email_el and "username" not in filled_reasons and "email" not in filled_reasons:
            user_val = "user@phptravels.com"
            if "tomsmith" in goal_lower: user_val = "tomsmith"
            elif "admin" in goal_lower: user_val = "admin@phptravels.com"
            
            # Check if username or email is given in goal
            emails = re.findall(r'[\w\.-]+@[\w\.-]+', goal)
            if emails: user_val = emails[0]

            return AgentAction(
                action=ActionType.FILL,
                element_id=email_el.id,
                value=user_val,
                reasoning=f"Entering username/email: {user_val}"
            )

        # Step 5B: Fill Password (if not already filled in history)
        if pass_el and "password" not in filled_reasons:
            pass_val = "demouser"
            if "supersecretpassword!" in goal_lower: pass_val = "SuperSecretPassword!"
            elif "admin" in goal_lower: pass_val = "demoadmin"

            return AgentAction(
                action=ActionType.FILL,
                element_id=pass_el.id,
                value=pass_val,
                reasoning="Entering credentials password"
            )

        # Step 5C: Click Submit / Login button (if fields filled)
        if submit_btn and any(s.action.action == ActionType.FILL for s in history):
            last_was_submit = history and history[-1].action.action == ActionType.CLICK and history[-1].action.element_id == submit_btn.id
            if not last_was_submit:
                return AgentAction(
                    action=ActionType.CLICK,
                    element_id=submit_btn.id,
                    reasoning=f"Clicking login submit button '{submit_btn.text or 'Submit'}'"
                )

        # Step 5D: If submit was just clicked, wait briefly for navigation
        if history and history[-1].action.action == ActionType.CLICK:
            return AgentAction(
                action=ActionType.WAIT,
                value="3.0",
                reasoning="Waiting for authentication response and page redirect"
            )

        # 6. Fallback verification: Check if non-auth verification condition is met
        if not is_on_auth_page:
            for check in ["practice form", "secure area", "dashboard", "logged in", "welcome"]:
                if check in goal_lower and check in page_text:
                    return AgentAction(
                        action=ActionType.FINISH,
                        test_passed=True,
                        reasoning=f"Page verification succeeded: Found expected content '{check}'"
                    )

        # If nothing else applies, finish
        return AgentAction(
            action=ActionType.FINISH,
            test_passed=False,
            reasoning=f"Unable to progress further from URL {snapshot.url} for goal '{goal}'"
        )
