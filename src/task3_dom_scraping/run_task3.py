import os, json, base64, re, time
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from PIL import Image

TARGET_URL = "https://egypt.blsspainglobal.com/Global/CaptchaPublic/GenerateCaptcha?data=4CDiA9odF2%2b%2bsWCkAU8htqZkgDyUa5SR6waINtJfg1ThGb6rPIIpxNjefP9UkAaSp%2fGsNNuJJi5Zt1nbVACkDRusgqfb418%2bScFkcoa1F0I%3d"

OUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

ALL_IMAGES_PATH = os.path.join(OUT_DIR, "allimages.json")
VISIBLE_IMAGES_PATH = os.path.join(OUT_DIR, "visible_images_only.json")
VISIBLE_TEXT_PATH = os.path.join(OUT_DIR, "visible_text.json")
CAPTCHA_SHOT = os.path.join(OUT_DIR, "captcha_grid.png")


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def is_data_image(url: str) -> bool:
    return url.startswith("data:image/")


def extract_data_b64(data_url: str) -> str | None:
    m = re.search(r"base64,(.*)$", data_url)
    return m.group(1) if m else None


def crop_3x3_to_base64(png_path: str):
    """Return list of 9 tiles (row, col, base64_png)."""
    img = Image.open(png_path).convert("RGBA")
    w, h = img.size
    tile_w = w // 3
    tile_h = h // 3

    tiles = []
    idx = 0
    for r in range(3):
        for c in range(3):
            left = c * tile_w
            top = r * tile_h
            right = (c + 1) * tile_w if c < 2 else w
            bottom = (r + 1) * tile_h if r < 2 else h

            tile = img.crop((left, top, right, bottom))
            out_path = os.path.join(OUT_DIR, f"captcha_tile_{idx+1}.png")
            tile.save(out_path, format="PNG")

            with open(out_path, "rb") as f:
                tiles.append({
                    "index": idx,
                    "row": r,
                    "col": c,
                    "base64": b64e(f.read())
                })
            idx += 1
    return tiles


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            locale="en-US",
        )
        page = context.new_page()

        # retry load
        last_err = None
        for _ in range(5):
            try:
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1500)
                html = page.content().lower()
                if "forbidden" in html or "access denied" in html:
                    raise Exception("Blocked content detected.")
                break
            except Exception as e:
                last_err = e
                time.sleep(1.5)
        else:
            raise RuntimeError(f"Could not load page. Last error: {last_err}")

        # -------------------------
        # A) Visible text only
        # -------------------------
        visible_text = page.evaluate("() => document.body.innerText || ''")
        lines = [ln.strip() for ln in visible_text.splitlines() if ln.strip()]
        with open(VISIBLE_TEXT_PATH, "w", encoding="utf-8") as f:
            json.dump({"target_url": TARGET_URL, "visible_text_lines": lines}, f, ensure_ascii=False, indent=2)

        # -------------------------
        # B) All images (as before)
        # -------------------------
        img_urls = page.evaluate("""
        () => {
          const imgs = Array.from(document.images || []);
          const urls = [];
          for (const im of imgs) {
            const u = (im.currentSrc || im.src || '').trim();
            if (u) urls.push(u);
          }
          return Array.from(new Set(urls));
        }
        """)
        bg_urls = page.evaluate("""
        () => {
          const urls = new Set();
          const all = Array.from(document.querySelectorAll('*'));
          for (const el of all) {
            const st = window.getComputedStyle(el);
            const bg = st.getPropertyValue('background-image');
            if (bg && bg !== 'none') {
              const matches = bg.matchAll(/url\\(["']?(.*?)["']?\\)/g);
              for (const m of matches) if (m[1]) urls.add(m[1]);
            }
          }
          return Array.from(urls);
        }
        """)
        canvas_data_urls = page.evaluate("""
        () => {
          const cvs = Array.from(document.querySelectorAll('canvas'));
          const out = [];
          for (const c of cvs) {
            try {
              const d = c.toDataURL('image/png');
              if (d && d.startsWith('data:image/')) out.push(d);
            } catch (e) {}
          }
          return out;
        }
        """)

        raw_urls = img_urls + bg_urls + canvas_data_urls

        urls = []
        for u in raw_urls:
            if not u:
                continue
            u = u.strip()
            if u.startswith("//"):
                u = "https:" + u
            if (not u.startswith("http")) and (not is_data_image(u)):
                u = urljoin(TARGET_URL, u)
            urls.append(u)

        urls_unique = list(dict.fromkeys(urls))

        def fetch_b64(u: str) -> str | None:
            try:
                if is_data_image(u):
                    return extract_data_b64(u)
                resp = page.request.get(u, timeout=30000)
                if resp.ok:
                    return b64e(resp.body())
            except:
                return None
            return None

        all_records = [{"index": i, "url": u, "base64": fetch_b64(u)} for i, u in enumerate(urls_unique)]

        with open(ALL_IMAGES_PATH, "w", encoding="utf-8") as f:
            json.dump({"target_url": TARGET_URL, "images_count": len(all_records), "images": all_records}, f, ensure_ascii=False, indent=2)

        # -------------------------
        # C) Visible 9 captcha tiles ONLY (guaranteed)
        # Strategy: pick the largest visible canvas/img in viewport -> screenshot -> crop 3x3
        # -------------------------
        # candidates: canvas first, then img
        candidates = page.locator("canvas")
        if candidates.count() == 0:
            candidates = page.locator("img")

        best = None
        best_area = 0

        for i in range(candidates.count()):
            el = candidates.nth(i)
            try:
                if not el.is_visible():
                    continue
                box = el.bounding_box()
                if not box:
                    continue
                area = box["width"] * box["height"]
                if area > best_area:
                    best_area = area
                    best = el
            except:
                continue

        if not best:
            # fallback: screenshot whole page and crop center 3x3 (rare)
            page.screenshot(path=CAPTCHA_SHOT, full_page=False)
        else:
            best.screenshot(path=CAPTCHA_SHOT)

        tiles = crop_3x3_to_base64(CAPTCHA_SHOT)

        with open(VISIBLE_IMAGES_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "target_url": TARGET_URL,
                "note": "These are the 9 captcha tiles extracted by screenshot cropping (3x3).",
                "visible_images_count": len(tiles),
                "images": tiles
            }, f, ensure_ascii=False, indent=2)

        browser.close()

    print("✅ Done")
    print("->", ALL_IMAGES_PATH)
    print("->", VISIBLE_IMAGES_PATH)
    print("->", VISIBLE_TEXT_PATH)
    print("-> captcha screenshot:", CAPTCHA_SHOT)


if __name__ == "__main__":
    run()