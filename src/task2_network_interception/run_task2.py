import json
from pathlib import Path
from collections import Counter
from playwright.sync_api import sync_playwright

URL = "https://cd.captchaaiplus.com/turnstile.html"


def is_relevant(url: str) -> bool:
    u = url.lower()
    return ("turnstile" in u) or ("cloudflare" in u) or ("challenge-platform" in u) or ("challenges.cloudflare.com" in u)


def classify_url(url: str) -> str:
    u = url.lower()
    if "turnstile/v0/api.js" in u:
        return "turnstile_api_loader"
    if "/turnstile/v0/g/" in u and "api.js" in u:
        return "turnstile_api_versioned"
    if "challenge-platform" in u and "turnstile" in u:
        return "challenge_iframe_or_doc"
    if "/flow/" in u:
        return "challenge_flow"
    if "/pat/" in u:
        return "private_token_pat"
    if "cloudflareinsights" in u:
        return "cloudflare_insights"
    return "other_cloudflare"


def main():
    out_dir = Path("src/task2_network_interception/outputs")
    videos_dir = out_dir / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    events = []
    redirects = []  # list of {from,to,status}
    status_counter = Counter()
    important_urls = {}  # category -> set(url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context(
            record_video_dir=str(videos_dir),
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        def on_request(req):
            if not is_relevant(req.url):
                return
            cat = classify_url(req.url)
            important_urls.setdefault(cat, set()).add(req.url)

            events.append({
                "kind": "request",
                "category": cat,
                "url": req.url,
                "method": req.method,
                "resource_type": req.resource_type,
                "headers": dict(req.headers),
            })

        def on_response(res):
            if not is_relevant(res.url):
                return
            cat = classify_url(res.url)
            important_urls.setdefault(cat, set()).add(res.url)

            status_counter[res.status] += 1

            # capture redirects
            if res.status in (301, 302, 303, 307, 308):
                loc = res.headers.get("location")
                if loc:
                    redirects.append({"from": res.url, "to": loc, "status": res.status})

            events.append({
                "kind": "response",
                "category": cat,
                "url": res.url,
                "status": res.status,
                "headers": dict(res.headers),
            })

        page.on("request", on_request)
        page.on("response", on_response)

        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(4500)

        # sitekey extraction from DOM
        widget_info = page.evaluate("""() => {
            const el = document.querySelector('[data-sitekey]') || document.querySelector('.cf-turnstile');
            return {
                sitekey: el ? (el.getAttribute('data-sitekey') || null) : null,
                url: location.href,
                title: document.title
            };
        }""")

        sitekey = widget_info.get("sitekey")
        print("SITEKEY:", sitekey)
        print("Captured events:", len(events))
        print("Status counts:", dict(status_counter))
        if redirects:
            print("Redirects captured:", len(redirects))

        # save full log (capped sample)
        full_log = {
            "page_widget_info": widget_info,
            "captured_events_count": len(events),
            "captured_events_sample": events[:250],
        }
        (out_dir / "task2_network_log.json").write_text(json.dumps(full_log, indent=2), encoding="utf-8")

        # build summary
        summary = {
            "sitekey": sitekey,
            "key_urls": {k: sorted(list(v))[:10] for k, v in important_urls.items()},
            "redirects": redirects[:20],
            "response_status_counts": dict(status_counter),
            "notes": []
        }

        # Add note if 401 with PrivateToken appears
        if 401 in status_counter:
            summary["notes"].append("Observed HTTP 401 on some Cloudflare challenge endpoints (e.g., PAT/private token).")

        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        print("Saved JSON to:", out_dir / "task2_network_log.json")
        print("Saved summary to:", out_dir / "summary.json")
        print("Video saved to:", videos_dir)

        context.close()
        browser.close()


if __name__ == "__main__":
    main()