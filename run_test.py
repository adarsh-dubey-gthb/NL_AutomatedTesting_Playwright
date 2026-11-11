import os
import sys
import argparse
import json
from dotenv import load_dotenv

# Ensure core and models can be imported
sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()

from core.test_engine import TestEngine


def main():
    parser = argparse.ArgumentParser(
        description="Turn plain-English test cases into automated tests using Playwright & AI."
    )
    parser.add_argument(
        "--test", "-t",
        type=str,
        default="Log in as a customer on phptravels.net and verify the dashboard is shown",
        help="Plain-English test case description (e.g. 'Log in as a customer and verify dashboard is shown')"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: false, launches visible browser)"
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=10,
        help="Maximum allowed ReAct steps before terminating (default: 10)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Optional API key for Gemini or OpenAI (can also be set in .env)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (e.g. gemini-2.5-flash, gemini-1.5-flash, gpt-4o-mini)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the pre-configured PHP Travels customer login test case"
    )
    parser.add_argument(
        "--suite",
        type=str,
        default=None,
        help="Path to a JSON file containing a list of test cases to run sequentially"
    )

    args = parser.parse_args()

    engine = TestEngine(
        headless=args.headless,
        max_steps=args.max_steps,
        api_key=args.api_key,
        model=args.model
    )

    if args.suite:
        if not os.path.exists(args.suite):
            print(f"Error: Suite file not found at '{args.suite}'")
            sys.exit(1)
        with open(args.suite, "r", encoding="utf-8") as f:
            suite_data = json.load(f)

        results = []
        for item in suite_data:
            goal = item if isinstance(item, str) else item.get("goal")
            print(f"\n=======================================================")
            print(f"Executing Suite Test Case: {goal}")
            print(f"=======================================================\n")
            res = engine.run_test(goal)
            results.append(res)

        passed = sum(1 for r in results if r.status == "PASS")
        print(f"\nSuite Execution Finished: {passed}/{len(results)} Passed.")
        sys.exit(0 if passed == len(results) else 1)

    else:
        goal = args.test
        if args.demo:
            goal = "Log in as a customer on phptravels.net and verify the dashboard is shown"

        result = engine.run_test(goal)
        sys.exit(0 if result.status == "PASS" else 1)


if __name__ == "__main__":
    main()

