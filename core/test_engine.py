import os
import time
import json
from datetime import datetime
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from models.actions import AgentAction, ActionType, StepRecord, TestResult
from core.browser_controller import BrowserController
from core.dom_observer import DomObserver
from core.llm_planner import LLMPlanner

console = Console()


class TestEngine:
    """
    Autonomous Execution Engine that orchestrates browser observation,
    LLM action planning, execution, and verification.
    """

    def __init__(self, headless: bool = False, max_steps: int = 10, api_key: Optional[str] = None, model: Optional[str] = None):
        self.headless = headless
        self.max_steps = max_steps
        self.controller = BrowserController(headless=headless)
        self.planner = LLMPlanner(api_key=api_key, model=model)
        self.report_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
        os.makedirs(os.path.join(self.report_dir, "screenshots"), exist_ok=True)

    def run_test(self, goal: str) -> TestResult:
        start_time = time.time()
        steps_history: List[StepRecord] = []
        status = "FAIL"
        summary = ""
        error_msg = None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        console.print(Panel(
            f"[bold cyan]TASK 2: NATURAL-LANGUAGE AUTOMATED TEST RUNNER[/bold cyan]\n"
            f"[bold white]Goal:[/bold white] {goal}\n"
            f"[bold white]Engine:[/bold white] Playwright + LLM Agent ({self.planner.provider})\n"
            f"[bold white]Headless:[/bold white] {self.headless}",
            border_style="cyan"
        ))

        try:
            self.controller.start()

            for step_num in range(1, self.max_steps + 1):
                # 1. Perceive current page state
                elements_map = {}
                snapshot = DomObserver.capture_snapshot(self.controller.page)
                for el in snapshot.interactive_elements:
                    elements_map[el.id] = el

                # 2. Decide next action via LLM Planner
                action = self.planner.plan_next_action(goal, snapshot, steps_history)

                console.print(f"\n[bold yellow]Step {step_num}:[/bold yellow] [bold white]{action.action.value.upper()}[/bold white] - {action.reasoning}")
                if action.element_id:
                    target_info = elements_map.get(action.element_id)
                    desc = f"<{target_info.tag} text='{target_info.text}'>" if target_info else action.element_id
                    console.print(f"  Target: [cyan]{desc}[/cyan]")
                if action.value:
                    console.print(f"  Value: [magenta]{action.value if 'pass' not in (action.element_id or '').lower() else '***'}[/magenta]")

                # 3. Check for Terminal Finish Action
                if action.action == ActionType.FINISH:
                    status = "PASS" if action.test_passed else "FAIL"
                    summary = action.reasoning
                    break

                # 4. Execute Action in Browser
                success, details = self.controller.execute_action(action, elements_map)

                # 5. Capture Screenshot for Evidence
                screenshot_filename = f"step_{step_num}_{timestamp}.png"
                screenshot_path = os.path.join(self.report_dir, "screenshots", screenshot_filename)
                self.controller.take_screenshot(screenshot_path)

                step_status = "SUCCESS" if success else "FAILED"
                color = "green" if success else "red"
                console.print(f"  Status: [{color}]{step_status}[/{color}] -> {details}")

                steps_history.append(StepRecord(
                    step_number=step_num,
                    action=action,
                    status=step_status,
                    details=details,
                    screenshot_path=screenshot_path,
                    page_url=self.controller.page.url
                ))

                if not success:
                    # Give short pause before letting the LLM react to failure
                    time.sleep(1.0)

            else:
                summary = f"Reached maximum allowed steps ({self.max_steps}) without definitive completion."

            # Final screenshot
            final_ss_path = os.path.join(self.report_dir, "screenshots", f"final_{timestamp}.png")
            self.controller.take_screenshot(final_ss_path)

        except Exception as e:
            status = "FAIL"
            summary = f"Unexpected execution error: {str(e)}"
            error_msg = str(e)
            console.print(f"[bold red]Error:[/bold red] {summary}")

        finally:
            self.controller.stop()

        duration = time.time() - start_time

        # Generate Test Result
        result = TestResult(
            goal=goal,
            status=status,
            summary=summary,
            total_steps=len(steps_history),
            duration_seconds=round(duration, 2),
            steps=steps_history,
            error_message=error_msg,
            final_url=steps_history[-1].page_url if steps_history else None,
            final_screenshot=os.path.join(self.report_dir, "screenshots", f"final_{timestamp}.png"),
        )

        # Generate Reports
        result.report_path = self._generate_html_report(result, timestamp)
        self._generate_json_report(result, timestamp)
        self._print_terminal_summary(result)

        return result

    def _print_terminal_summary(self, result: TestResult):
        color = "bold green" if result.status == "PASS" else "bold red"
        table = Table(title="Test Execution Summary", border_style="cyan")
        table.add_column("Property", style="bold")
        table.add_column("Value")

        table.add_row("Status", f"[{color}]{result.status}[/{color}]")
        table.add_row("Goal", result.goal)
        table.add_row("Steps Executed", str(result.total_steps))
        table.add_row("Duration", f"{result.duration_seconds}s")
        table.add_row("Summary", result.summary)
        table.add_row("HTML Report", result.report_path or "N/A")

        console.print("\n")
        console.print(table)

    def _generate_json_report(self, result: TestResult, timestamp: str) -> str:
        filepath = os.path.join(self.report_dir, f"test_report_{timestamp}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        return filepath

    def _generate_html_report(self, result: TestResult, timestamp: str) -> str:
        filepath = os.path.join(self.report_dir, f"test_report_{timestamp}.html")
        status_color = "#10b981" if result.status == "PASS" else "#ef4444"

        rows = ""
        for s in result.steps:
            img_rel = os.path.relpath(s.screenshot_path, self.report_dir) if s.screenshot_path else ""
            img_tag = f'<a href="{img_rel}" target="_blank"><img src="{img_rel}" class="step-thumb" /></a>' if img_rel else 'No image'
            rows += f"""
            <tr>
              <td><strong>{s.step_number}</strong></td>
              <td><span class="badge badge-action">{s.action.action.value.upper()}</span></td>
              <td>{s.action.reasoning}</td>
              <td>{s.details}</td>
              <td><span class="badge badge-{s.status.lower()}">{s.status}</span></td>
              <td>{img_tag}</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Test Execution Report - {result.status}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f8fafc; color: #1e293b; padding: 30px; margin: 0; }}
    .container {{ max-width: 1100px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
    .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; }}
    .status-badge {{ background: {status_color}; color: white; padding: 8px 18px; border-radius: 9999px; font-weight: bold; font-size: 1.1rem; }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 25px 0; background: #f1f5f9; padding: 18px; border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 25px; }}
    th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 0.95rem; }}
    th {{ background: #f8fafc; color: #475569; font-weight: 600; }}
    .step-thumb {{ width: 120px; border-radius: 6px; border: 1px solid #cbd5e1; transition: transform 0.2s; }}
    .step-thumb:hover {{ transform: scale(1.1); }}
    .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }}
    .badge-action {{ background: #e0f2fe; color: #0369a1; }}
    .badge-success {{ background: #dcfce7; color: #15803d; }}
    .badge-failed {{ background: #fee2e2; color: #b91c1c; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1 style="margin: 0 0 8px 0;">Automated Test Execution Report</h1>
        <p style="margin: 0; color: #64748b;">Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
      </div>
      <div class="status-badge">{result.status}</div>
    </div>

    <div class="meta-grid">
      <div><span style="color:#64748b; font-size:0.85rem;">TEST GOAL</span><br><strong>{result.goal}</strong></div>
      <div><span style="color:#64748b; font-size:0.85rem;">DURATION</span><br><strong>{result.duration_seconds} seconds</strong></div>
      <div><span style="color:#64748b; font-size:0.85rem;">STEPS EXECUTED</span><br><strong>{result.total_steps}</strong></div>
      <div><span style="color:#64748b; font-size:0.85rem;">SUMMARY</span><br><strong>{result.summary}</strong></div>
    </div>

    <h3>Step-by-Step Execution Log</h3>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Action</th>
          <th>Reasoning</th>
          <th>Execution Details</th>
          <th>Status</th>
          <th>Screenshot</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>
</body>
</html>"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        return filepath

