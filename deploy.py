"""
SmartCents — Cloudflare Worker Deploy Script
=============================================
Wraps index.html + admin.html into a Cloudflare Worker and deploys it.

Run: python deploy.py
"""

import urllib.request
import urllib.error
import json
import os
import ssl
import time
import re

# ── CONFIG ────────────────────────────────────────────────────
CLOUDFLARE_API_TOKEN  = "cfut_C2Pk0dwNRWY9Zxeh4PPh8P5XzhZGc8e1jcCmTDJdbff44e7b"
CLOUDFLARE_ACCOUNT_ID = "21c4edb7632333b227166f70dee6654a"
WORKER_NAME           = "smartcents"
VERSION_FILE          = "version.txt"

FILES = {
    "index.html": "index.html",
    "admin.html": "admin.html",
}

# ── READ & VERSION FILES ──────────────────────────────────────
def read_files():
    contents = {}
    for key, filename in FILES.items():
        if not os.path.exists(filename):
            print(f"❌ {filename} not found!")
            exit(1)
        with open(filename, "r", encoding="utf-8") as f:
            contents[key] = f.read()
        size_kb = len(contents[key].encode("utf-8")) / 1024
        print(f"✅ Read {filename} ({size_kb:.1f} KB)")

    # Version bumping
    stored_ver = None
    if os.path.exists(VERSION_FILE):
        try:
            stored_ver = open(VERSION_FILE).read().strip()
        except:
            pass

    old_ver = stored_ver or "1.00"
    try:
        new_ver = round(float(old_ver) + 0.01, 2)
        new_ver_str = f"{new_ver:.2f}"

        # Update version in admin.html
        contents["admin.html"] = re.sub(
            r"const APP_VERSION = '[^']+';",
            f"const APP_VERSION = '{new_ver_str}';",
            contents["admin.html"]
        )
        contents["admin.html"] = re.sub(
            r"'v[\d.]+'",
            f"'v{new_ver_str}'",
            contents["admin.html"],
            count=1
        )

        # Save updated admin.html
        with open("admin.html", "w", encoding="utf-8") as f:
            f.write(contents["admin.html"])

        # Save version
        with open(VERSION_FILE, "w") as fv:
            fv.write(new_ver_str)

        print(f"✅ Version bumped: v{old_ver} → v{new_ver_str}")
    except Exception as ex:
        print(f"⚠️  Could not bump version: {ex}")

    return contents

# ── ESCAPE FOR JS ─────────────────────────────────────────────
def escape(html):
    return html.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

# ── BUILD WORKER ──────────────────────────────────────────────
def build_worker(contents):
    index_escaped = escape(contents["index.html"])
    admin_escaped = escape(contents["admin.html"])

    # Read sw.js and manifest.json if they exist
    sw_content = ""
    manifest_content = ""
    if os.path.exists("sw.js"):
        with open("sw.js", "r", encoding="utf-8") as f:
            sw_content = escape(f.read())
    if os.path.exists("manifest.json"):
        with open("manifest.json", "r", encoding="utf-8") as f:
            manifest_content = f.read()

    worker = f"""
addEventListener('fetch', event => {{
  event.respondWith(handleRequest(event.request));
}});

async function handleRequest(request) {{
  const url = new URL(request.url);
  const path = url.pathname;

  // ── Admin Dashboard ───────────────────────────────────────
  if (path === '/admin.html' || path === '/admin') {{
    const html = `{admin_escaped}`;
    return new Response(html, {{
      headers: {{
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
      }}
    }});
  }}

  // ── Service Worker ────────────────────────────────────────
  if (path === '/sw.js') {{
    const sw = `{sw_content}`;
    return new Response(sw, {{
      headers: {{
        'Content-Type': 'application/javascript',
        'Service-Worker-Allowed': '/',
        'Cache-Control': 'no-cache',
      }}
    }});
  }}

  // ── PWA Manifest ─────────────────────────────────────────
  if (path === '/manifest.json') {{
    return new Response(`{manifest_content}`, {{
      headers: {{
        'Content-Type': 'application/manifest+json',
        'Cache-Control': 'public, max-age=86400',
      }}
    }});
  }}

  // ── PWA Icons ─────────────────────────────────────────────
  if (path === '/icon-192.png' || path === '/icon-512.png') {{
    const size = path.includes('512') ? 512 : 192;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${{size}}" height="${{size}}" viewBox="0 0 100 100">
      <rect width="100" height="100" rx="22" fill="#080808"/>
      <rect width="100" height="100" rx="22" fill="#C9A84C" opacity="0.2"/>
      <text x="50" y="58" font-size="40" text-anchor="middle">💰</text>
      <text x="50" y="82" font-size="12" text-anchor="middle" fill="#C9A84C" font-family="sans-serif" font-weight="bold">SmartCents</text>
    </svg>`;
    return new Response(svg, {{
      headers: {{ 'Content-Type': 'image/svg+xml', 'Cache-Control': 'public, max-age=86400' }}
    }});
  }}

  // ── Main Site ─────────────────────────────────────────────
  const html = `{index_escaped}`;
  return new Response(html, {{
    headers: {{
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-cache, no-store, must-revalidate',
    }}
  }});
}}
"""
    print(f"✅ Worker script built ({len(worker.encode('utf-8'))/1024:.1f} KB)")
    return worker

# ── DEPLOY ────────────────────────────────────────────────────
def deploy(worker_script, retries=3):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{WORKER_NAME}"
    script_bytes = worker_script.encode("utf-8")
    print(f"📤 Uploading to Cloudflare ({len(script_bytes)/1024:.1f} KB)...")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=script_bytes,
                method="PUT",
                headers={
                    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                    "Content-Type": "application/javascript",
                    "Content-Length": str(len(script_bytes)),
                }
            )
            handler = urllib.request.HTTPSHandler(context=ctx)
            opener = urllib.request.build_opener(handler)

            with opener.open(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if data.get("success"):
                print(f"\n✅ DEPLOYED SUCCESSFULLY!")
                print(f"🌐 Site:  https://smartcents.shaheryardesigns.workers.dev")
                print(f"⚙️  Admin: https://smartcents.shaheryardesigns.workers.dev/admin.html")
                return True
            else:
                print(f"❌ Cloudflare errors: {data.get('errors', [])}")
                return False

        except urllib.error.URLError as e:
            print(f"  ⚠️  Attempt {attempt}/{retries} failed: {e.reason}")
            if attempt < retries:
                wait = attempt * 3
                print(f"  ⏳ Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"\n❌ All {retries} attempts failed.")
                return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False

# ── MAIN ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  SmartCents — Cloudflare Worker Deploy")
    print("=" * 50)

    contents = read_files()
    script   = build_worker(contents)
    deploy(script)

    print("\n" + "=" * 50)
