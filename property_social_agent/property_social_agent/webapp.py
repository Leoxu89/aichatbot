"""Local web dashboard for reviewing and approving a draft before posting.

Serves a small page on localhost showing the selected photos and editable
Instagram/Facebook captions with Approve / Reject buttons. Editing is inline:
change the caption text, then click Approve. Used both by the real `run`
flow (when approval.method = web) and by the `demo` command.
"""

from __future__ import annotations

import html
import threading
import time
import webbrowser
from dataclasses import dataclass

from .approval import ApprovalRequest
from .content_generator import GeneratedContent


@dataclass
class WebDecision:
    approved: bool
    content: GeneratedContent  # reflects any inline edits the user made


def run_web_approval(
    req: ApprovalRequest,
    host: str = "127.0.0.1",
    port: int = 8000,
    open_browser: bool = True,
) -> WebDecision:
    """Serve the review page and block until the user approves or rejects."""
    from flask import Flask, abort, request, send_file
    from werkzeug.serving import make_server

    app = Flask(__name__)
    outcome: dict = {}
    done = threading.Event()

    @app.route("/")
    def index():  # noqa: ANN202
        return _page(req)

    @app.route("/photo/<int:idx>")
    def photo(idx: int):  # noqa: ANN202
        if not (0 <= idx < len(req.photos)):
            abort(404)
        return send_file(str(req.photos[idx]))

    @app.route("/submit", methods=["POST"])
    def submit():  # noqa: ANN202
        action = request.form.get("action", "reject")
        tags = request.form.get("hashtags", " ".join(req.content.hashtags)).split()
        outcome["content"] = GeneratedContent(
            summary=req.content.summary,
            instagram_caption=request.form.get("instagram_caption", req.content.instagram_caption),
            facebook_caption=request.form.get("facebook_caption", req.content.facebook_caption),
            hashtags=tags,
        )
        outcome["approved"] = action == "approve"
        done.set()
        return _result_page(action == "approve")

    server = make_server(host, port, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://{host}:{port}/"
    print(f"[approval] Review the draft at: {url}  (waiting for your decision...)")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - headless machines have no browser
            pass

    done.wait()
    time.sleep(0.3)  # let the result page finish rendering before shutdown
    server.shutdown()
    return WebDecision(approved=outcome.get("approved", False), content=outcome.get("content", req.content))


# --- HTML rendering -----------------------------------------------------------
_STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
       background: #f4f1ea; color: #1c1c1c; }
.wrap { max-width: 920px; margin: 0 auto; padding: 24px; }
h1 { font-size: 1.4rem; margin: 0 0 4px; }
.sub { color: #6b6b6b; margin: 0 0 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px,1fr));
        gap: 10px; margin-bottom: 20px; }
.grid img { width: 100%; height: 150px; object-fit: cover; border-radius: 10px;
            box-shadow: 0 1px 4px rgba(0,0,0,.15); }
.card { background: #fff; border-radius: 12px; padding: 16px 18px; margin-bottom: 16px;
        box-shadow: 0 1px 6px rgba(0,0,0,.08); }
.card h2 { font-size: 1rem; margin: 0 0 8px; }
textarea { width: 100%; font: inherit; padding: 10px; border: 1px solid #ddd;
           border-radius: 8px; resize: vertical; background: #fafafa; }
.actions { display: flex; gap: 12px; margin-top: 8px; }
button { font: inherit; font-weight: 600; border: 0; border-radius: 999px;
         padding: 12px 26px; cursor: pointer; }
.approve { background: #2e7d32; color: #fff; }
.reject { background: #eee; color: #333; }
small { color: #888; }
"""


def _page(req: ApprovalRequest) -> str:
    photos = "".join(
        f'<img src="/photo/{i}" alt="{html.escape(p.name)}" title="{html.escape(p.name)}">'
        for i, p in enumerate(req.photos)
    )
    ig = html.escape(req.content.instagram_caption)
    fb = html.escape(req.content.facebook_caption)
    tags = html.escape(" ".join(req.content.hashtags))
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Approve post — {html.escape(req.property_name)}</title><style>{_STYLE}</style></head>
<body><div class="wrap">
  <h1>Review this week's post</h1>
  <p class="sub">{html.escape(req.property_name)} &middot; {html.escape(', '.join(req.platforms))}
     &middot; <small>edit any text below, then Approve</small></p>
  <div class="grid">{photos}</div>
  <form method="post" action="/submit">
    <div class="card"><h2>Instagram caption</h2>
      <textarea name="instagram_caption" rows="4">{ig}</textarea></div>
    <div class="card"><h2>Facebook caption</h2>
      <textarea name="facebook_caption" rows="5">{fb}</textarea></div>
    <div class="card"><h2>Hashtags</h2>
      <textarea name="hashtags" rows="2">{tags}</textarea></div>
    <div class="actions">
      <button class="approve" name="action" value="approve" type="submit">✓ Approve &amp; post</button>
      <button class="reject" name="action" value="reject" type="submit">✕ Reject</button>
    </div>
  </form>
</div></body></html>"""


def _result_page(approved: bool) -> str:
    msg = "Approved — posting now. You can close this tab." if approved else "Rejected — nothing will be posted."
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Done</title><style>{_STYLE}</style></head>
<body><div class="wrap"><div class="card"><h1>{msg}</h1></div></div></body></html>"""
