#!/usr/bin/env python3
import os, shutil, re, pathlib, sys, html
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown import markdown
from datetime import datetime, timezone
from re import sub as _re_sub

# ========= PATHS =========

BASE = pathlib.Path(__file__).parent.resolve()
CONTENT = BASE / "content"
TEMPLATES = BASE / "templates"
STATIC = BASE / "static"
DIST = BASE / "dist"

# ========= HELPERS =========

fm_re = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)

def parse_md(path: pathlib.Path):
    raw = path.read_text(encoding="utf-8")
    m = fm_re.match(raw)
    fm = {}
    body_md = raw
    if m:
        fm = yaml.safe_load(m.group(1)) or {}
        body_md = m.group(2)
    html_out = markdown(body_md, extensions=["tables", "fenced_code"])
    return fm, html_out

def strip_html(text, max_len=240):
    s = _re_sub(r"<[^>]+>", "", text)
    s = _re_sub(r"\s+", " ", s).strip()
    return (s[:max_len] + "…") if len(s) > max_len else s

def load_config():
    cfg = BASE / "config.yaml"
    return yaml.safe_load(cfg.read_text()) if cfg.exists() else {}

def copy_static():
    if STATIC.exists():
        dest = DIST / "static"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(STATIC, dest)

# ========= JINJA =========

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    autoescape=select_autoescape(["html"])
)

def render_tpl(name, **ctx):
    return env.get_template(name).render(**ctx)

# ========= BUILD =========

def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)

    site_cfg = load_config()
    site_url = site_cfg.get("site_url", "").rstrip("/") or "https://loadstone.gg"
    base_href = site_cfg.get("base_url", "").rstrip("/")
    mode = site_cfg.get("mode", "")
    IS_LOADSTONE = mode == "loadstone"

    copy_static()

    posts = []
    tag_map = {}

    for root, _, files in os.walk(CONTENT):
        root_p = pathlib.Path(root)

        for file in files:
            if not file.endswith(".md"):
                continue

            src = root_p / file
            rel = src.relative_to(CONTENT)
            fm, body_html = parse_md(src)

            title = fm.get("title", rel.stem)
            template = fm.get("template", "page")

            out_rel = rel.with_suffix(".html")
            if rel.stem == "index":
                out_rel = rel.parent / "index.html"

            out_path = DIST / out_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)

            ctx = {
                "title": title,
                "body": body_html,
                "base": base_href,
                "site": site_cfg,
            }

            out_path.write_text(
                render_tpl(f"{template}.html", **ctx),
                encoding="utf-8"
            )

    # ---------- SITEMAP ----------
    urls = []
    for root, _, files in os.walk(DIST):
        for f in files:
            if f.endswith(".html"):
                p = (pathlib.Path(root) / f).relative_to(DIST).as_posix()
                urls.append("/" + p.replace("index.html", ""))

    sitemap = "<?xml version='1.0'?>\n<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>\n"
    sitemap += "".join(f"<url><loc>{site_url}{u}</loc></url>\n" for u in urls)
    sitemap += "</urlset>"
    (DIST / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    print("Build complete → dist/")

# ========= CLI =========

if __name__ == "__main__":
    try:
        build()
    except Exception as e:
        print("Build failed:", e)
        sys.exit(1)
