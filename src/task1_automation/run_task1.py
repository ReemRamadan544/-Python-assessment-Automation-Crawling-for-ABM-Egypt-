import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

URL = "https://cd.captchaaiplus.com/turnstile.html"


def safe_token(page):
    return page.evaluate("""() => {
        const el = document.querySelector('[name="cf-turnstile-response"]');
        return el && el.value ? el.value : null;
    }""")


def wait_for_token(page, timeout_ms=25000):
    page.wait_for_function("""
        () => {
            const el = document.querySelector('[name="cf-turnstile-response"]');
            return el && el.value && el.value.length > 0;
        }
    """, timeout=timeout_ms)


def fill_names_strong(page, first="Reem", last="Ramadan"):
    # Wait for inputs to exist
    page.wait_for_selector('input[name="first_name"]', timeout=15000)
    page.wait_for_selector('input[name="last_name"]', timeout=15000)

    # Remove readonly (some pages set it)
    page.eval_on_selector('input[name="first_name"]', "el => el.removeAttribute('readonly')")
    page.eval_on_selector('input[name="last_name"]', "el => el.removeAttribute('readonly')")

    f = page.locator('input[name="first_name"]')
    l = page.locator('input[name="last_name"]')

    # Clear + type to trigger proper events (frameworks often ignore direct .value assignment)
    f.click()
    f.press("Control+A")
    f.press("Backspace")
    f.type(first, delay=25)

    l.click()
    l.press("Control+A")
    l.press("Backspace")
    l.type(last, delay=25)

    # Extra: blur/change events to ensure model updates
    page.evaluate("""
        () => {
            const f = document.querySelector('input[name="first_name"]');
            const l = document.querySelector('input[name="last_name"]');
            if (f) { f.dispatchEvent(new Event('change', { bubbles: true })); f.blur(); }
            if (l) { l.dispatchEvent(new Event('change', { bubbles: true })); l.blur(); }
        }
    """)


def main():
    out_dir = Path("src/task1_automation/outputs/cdp")
    shots_dir = out_dir / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    shots_dir.mkdir(parents=True, exist_ok=True)

    results = []
    attempts = 10
    manual_wait_ms = 25000  # time window for you to complete verification

    with sync_playwright() as p:
        # Make sure Chrome was started with:
        # chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\cdp-profile"
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")

        context = browser.contexts[0] if browser.contexts else browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        for i in range(1, attempts + 1):
            print(f"\nAttempt {i} (CDP Chrome headed)")

            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_timeout(800)

            # ✅ Fill names in a robust way (prevents reverting to default like "Jan")
            fill_names_strong(page, first="Reem", last="Ramadan")

            token = None
            ok = False
            try:
                # Wait for token (you may need to click the checkbox manually)
                wait_for_token(page, timeout_ms=manual_wait_ms)
                token = safe_token(page)
                ok = bool(token)
            except PWTimeoutError:
                ok = False

            # Submit
            try:
                page.get_by_role("button", name="Submit").click(timeout=3000)
            except:
                try:
                    page.click("button:has-text('Submit'), input[type=submit]", timeout=3000)
                except:
                    pass

            page.wait_for_timeout(800)

            # Screenshot proof for each attempt
            page.screenshot(path=str(shots_dir / f"attempt_{i}.png"), full_page=True)

            results.append({
                "attempt": i,
                "success": ok,
                "token_len": 0 if not token else len(token),
            })

            print("  -> success:", ok)
            time.sleep(1)

        # Save report
        report_path = out_dir / "task1_cdp_report.json"
        report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

        # Print final success rate (helpful in video)
        success_count = sum(1 for r in results if r["success"])
        success_rate = (success_count / attempts) * 100
        print("\nSaved:", report_path)
        print(f"Final success rate: {success_rate:.1f}% ({success_count}/{attempts})")

        browser.close()


if __name__ == "__main__":
    main()