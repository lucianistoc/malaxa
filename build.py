#!/usr/bin/env python3
"""White-label hospital website generator.

Reads site.config.json (brand) and content/*.json (data) and writes a complete
static website to ./public. No dependencies beyond the Python 3 standard library.

    python3 build.py              # build into ./public
    python3 -m http.server -d public 8000   # preview at http://localhost:8000
    BASE_PATH=/malaxa/ python3 build.py     # when served from a sub-path (GitHub Pages project site)
"""
import json
import os
import re
import shutil
import unicodedata
from urllib.parse import quote
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "public"
CFG = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
DOCS = json.loads((ROOT / "content/doctors.json").read_text(encoding="utf-8"))
NEWS = sorted(json.loads((ROOT / "content/news.json").read_text(encoding="utf-8")), key=lambda n: n["date"], reverse=True)
L = json.loads((ROOT / "content/lists.json").read_text(encoding="utf-8"))
C = CFG["contact"]
NAME = CFG["name"]
E = escape
MONTHS = ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august",
          "septembrie", "octombrie", "noiembrie", "decembrie"]
SEARCH_INDEX = []
# URL path the site is served from; only the root 404.html needs it (all other links are relative).
# e.g. BASE_PATH=/malaxa/ for https://<user>.github.io/malaxa/
BASE_PATH = "/" + os.environ.get("BASE_PATH", "/").strip("/") + "/" if os.environ.get("BASE_PATH", "/").strip("/") else "/"


def num(v):
    return f"{v:,}".replace(",", ".")


def stat(s):
    return f'<div><strong data-count="{s["value"]}" data-prefix="+">+{num(s["value"])}</strong><span>{E(s["label"])}</span></div>'


def fdate(iso):
    y, m, d = map(int, iso.split("-"))
    return f"{d} {MONTHS[m - 1]} {y}"


# ---------------------------------------------------------------- icons (inline SVG, stroke style)
_P = {
    "stethoscope": '<path d="M5 3v6a5 5 0 0 0 10 0V3"/><path d="M10 14v2a5 5 0 0 0 10 0v-3"/><circle cx="20" cy="11" r="2"/>',
    "run": '<circle cx="14" cy="4" r="2"/><path d="M8 21l3-6 3 2v5M6 12l3-4 4 1 3 4h3"/>',
    "microscope": '<path d="M6 18h8M3 22h18M14 22a7 7 0 1 0 0-14h-1"/><path d="M9 14h2M9 12a2 2 0 0 1-2-2V6h6v4a2 2 0 0 1-2 2zM12 6V3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3"/>',
    "heartbeat": '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8z"/><path d="M3 12h5l2-3 3 6 2-3h6"/>',
    "virus": '<circle cx="12" cy="12" r="5"/><path d="M12 2v5M12 17v5M2 12h5M17 12h5M4.9 4.9l3.5 3.5M15.6 15.6l3.5 3.5M4.9 19.1l3.5-3.5M15.6 8.4l3.5-3.5"/>',
    "heart": '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8z"/>',
    "scalpel": '<path d="M3 21l9-9M12 12l7-7a2.8 2.8 0 0 1 0 4l-4 4-3-1z"/>',
    "ambulance": '<path d="M10 17h4V5H2v12h3M14 9h4l4 4v4h-3"/><circle cx="7.5" cy="17.5" r="2.5"/><circle cx="16.5" cy="17.5" r="2.5"/><path d="M8 8v4M6 10h4"/>',
    "skin": '<circle cx="12" cy="12" r="9"/><circle cx="9" cy="10" r="1"/><circle cx="15" cy="9" r="1"/><circle cx="13" cy="15" r="1"/>',
    "document": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8M8 9h2"/>',
    "gland": '<path d="M12 3c-4 3-7 6-7 10a7 7 0 0 0 14 0c0-4-3-7-7-10z"/><path d="M12 10v6M9 13h6"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/>',
    "drop": '<path d="M12 2.7l5.7 5.6a8 8 0 1 1-11.4 0z"/>',
    "flask": '<path d="M9 3h6M10 3v6L4 19a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-6-10V3"/><path d="M7 15h10"/>',
    "clipboard": '<rect x="5" y="4" width="14" height="18" rx="2"/><path d="M9 2h6v4H9zM9 12h6M9 16h4"/>',
    "helmet": '<path d="M2 18h20M4 18v-3a8 8 0 0 1 16 0v3M10 7V4h4v3"/>',
    "brain": '<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-1.54"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-1.54"/>',
    "female": '<circle cx="12" cy="9" r="6"/><path d="M12 15v7M9 19h6"/>',
    "eye": '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    "ribbon": '<path d="M12 2a4 4 0 0 0-4 4c0 3 4 7 4 7s4-4 4-7a4 4 0 0 0-4-4zM10 11l-5 11 3-1 2 2 2-6M14 11l5 11-3-1-2 2-2-6"/>',
    "ear": '<path d="M6 8.5a6.5 6.5 0 1 1 13 0c0 6-6 6-6 10a3.5 3.5 0 1 1-7 0"/><path d="M15 8.5a2.5 2.5 0 0 0-5 0v1a2 2 0 1 1 0 4"/>',
    "mind": '<circle cx="12" cy="9" r="7"/><path d="M9 21h6M10 17v4M14 17v4M12 5v4l2 2"/>',
    "xray": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 6v12M8 8h8M7 11h10M8 14h8"/>',
    "atom": '<circle cx="12" cy="12" r="1.5"/><ellipse cx="12" cy="12" rx="10" ry="4"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)"/>',
    "phone": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 6l-10 7L2 6"/>',
    "pin": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.3-4.3"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h10"/>',
    "close": '<path d="M18 6L6 18M6 6l12 12"/>',
    "caret": '<path d="M6 9l6 6 6-6"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "up": '<path d="M12 19V5M5 12l7-7 7 7"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "chat": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M9.5 8a2.5 2.5 0 1 1 3 2.5V12M12 14.5h.01"/>',
    "cart": '<circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.7 13.4a2 2 0 0 0 2 1.6h9.7a2 2 0 0 0 2-1.6L23 6H6"/>',
    "contract": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17l2-1 2 1 2-1"/>',
    "handshake": '<path d="M11 17l2 2a1 1 0 0 0 1.4 0l4.6-4.6a2 2 0 0 0 0-2.8L15 7.6 13 9.5a2 2 0 0 1-2.8 0 2 2 0 0 1 0-2.8L13 4l-1-1-9 9 1 1M21 3l-3 3"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M7 16v-4M12 16V8M17 16v-7"/>',
    "pen": '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "people": '<circle cx="9" cy="7" r="4"/><path d="M1 21v-2a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v2M16 3.1a4 4 0 0 1 0 7.8M23 21v-2a4 4 0 0 0-3-3.9"/>',
    "money": '<circle cx="12" cy="12" r="10"/><path d="M15 9a3 3 0 0 0-3-1.5c-1.7 0-3 .8-3 2s1.3 1.8 3 2 3 .8 3 2-1.3 2-3 2a3 3 0 0 1-3-1.5M12 6v1.5M12 16.5V18"/>',
    "pill": '<path d="M10.5 20.5a7 7 0 0 1-9.9-9.9l9.9-9.9a7 7 0 0 1 9.9 9.9z"/><path d="M5.6 5.6l12.8 12.8" transform="rotate(90 12 12)"/>',
    "gavel": '<path d="M14 13l-7.5 7.5a2.1 2.1 0 0 1-3-3L11 10M16 16l6-6M8 8l6-6M9 7l8 8M21 11l-8-8"/>',
    "star": '<path d="M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="M8 12l3 3 5-6"/>',
    "org": '<rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><rect x="9" y="17" width="6" height="5" rx="1"/><path d="M12 7v10M5 17v-3h14v3"/>',
    "hands": '<path d="M12 21s-7-4.3-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.7-7 10-7 10z"/><path d="M12 10v5M9.5 12.5h5"/>',
    "hospital": '<path d="M3 21h18M5 21V7l7-4 7 4v14"/><path d="M12 8v5M9.5 10.5h5M9 21v-4h6v4"/>',
    "award": '<circle cx="12" cy="8" r="6"/><path d="M8.2 13.9L7 23l5-3 5 3-1.2-9.1"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
    "facebook": '<path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" fill="currentColor" stroke="none"/>',
    "instagram": '<rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.5 6.5h.01"/>',
    "youtube": '<path d="M22.5 6.4a2.8 2.8 0 0 0-2-2C18.8 4 12 4 12 4s-6.8 0-8.5.4a2.8 2.8 0 0 0-2 2A29 29 0 0 0 1 12a29 29 0 0 0 .5 5.6 2.8 2.8 0 0 0 2 2c1.7.4 8.5.4 8.5.4s6.8 0 8.5-.4a2.8 2.8 0 0 0 2-2A29 29 0 0 0 23 12a29 29 0 0 0-.5-5.6z"/><path d="M9.8 15.5l5.7-3.5-5.7-3.5z" fill="currentColor"/>',
    "linkedin": '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6zM2 9h4v12H2z"/><circle cx="4" cy="4" r="2"/>',
    "a11y": '<circle cx="12" cy="4" r="2"/><path d="M4 8l8 1 8-1M12 9v5l-4 7M12 14l4 7"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "metro": '<rect x="4" y="3" width="16" height="14" rx="3"/><path d="M4 11h16M8 21l2-4M16 21l-2-4"/><circle cx="8.5" cy="14" r=".5"/><circle cx="15.5" cy="14" r=".5"/>',
    "bus": '<rect x="4" y="3" width="16" height="15" rx="2"/><path d="M4 11h16M8 18v3M16 18v3M8 7h8"/>',
    "tram": '<rect x="5" y="6" width="14" height="12" rx="2"/><path d="M8 2l4 4 4-4M5 13h14M8 18l-2 4M16 18l2 4"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    "tooth": '<path d="M7 3c-2.2 0-4 1.8-4 4.5 0 3 1.5 4.5 2 7.5.4 2.6 1 6 2.5 6 1.7 0 1.5-5 4.5-5s2.8 5 4.5 5c1.5 0 2.1-3.4 2.5-6 .5-3 2-4.5 2-7.5C21 4.8 19.2 3 17 3c-2 0-3 1.2-5 1.2S9 3 7 3z"/>',
    "external": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>',
    "building": '<rect x="4" y="2" width="16" height="20" rx="1"/><path d="M9 22v-4h6v4M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/>',
}


def icon(name, cls="icon"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_P.get(name, _P["hospital"])}</svg>')



R = "{{ROOT}}"  # replaced with the relative path to the site root on every page


def cap(s):
    return s[:1].upper() + s[1:] if s else s


def ext(url):
    return url.startswith(("http://", "https://"))


def a_doc(t, u, cls="doc-link"):
    tgt = ' target="_blank" rel="noopener"' if ext(u) else ""
    ic = "download" if u.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")) else ("external" if ext(u) else "arrow")
    href = u if ext(u) else R + quote(u, safe="/#")
    return f'<a class="{cls}" href="{E(href)}"{tgt}>{icon(ic)}<span>{E(file_label(t, u))}</span></a>'


def file_label(t, u):
    """Append format and size to links to local documents: "Regulament (PDF, 240 KB)"."""
    if ext(u) or "." not in u.rsplit("/", 1)[-1]:
        return t
    f = ROOT / u.split("#")[0]
    fmt = u.rsplit(".", 1)[-1].upper()
    if fmt not in ("PDF", "DOC", "DOCX", "XLS", "XLSX") or not f.is_file():
        return t
    kb = f.stat().st_size / 1024
    size = f"{kb / 1024:.1f} MB".replace(".", ",") if kb >= 1024 else f"{max(1, round(kb))} KB"
    t = re.sub(r"\s*\((PDF|DOC|DOCX|XLS|XLSX)\)\s*$", "", t, flags=re.I)
    return f"{t} ({fmt}, {size})"


def updated():
    d = CFG.get("content_updated")
    return f'<p class="updated">Ultima actualizare: {E(d)}</p>' if d else ""



def paras(lst):
    return "".join(f"<p>{E(p)}</p>" for p in lst)


# ---------------------------------------------------------------- navigation

def doc_url(d): return f"team/{d['slug']}/"
def post_url(n): return (f"{n['date'][:4]}/{n['date'][5:7]}/{n['date'][8:10]}/{n['slug']}/" if n.get("date") else f"noutati/{n['slug']}/")





def logo(r):
    if CFG.get("logo_image"):
        return f'<a class="logo" href="{r}" aria-label="{E(NAME)} – acasă"><img src="{r}{CFG["logo_image"]}" alt="{E(NAME)}"></a>'
    ic = f'<img class="logo-icon" src="{r}{CFG["logo_icon"]}" alt="" width="52" height="52">' if CFG.get("logo_icon") else ""
    return (f'<a class="logo" href="{r}" aria-label="{E(NAME)} – acasă">{ic}<span class="logo-txt"><span class="logo-word">{E(CFG["logo_text"])}</span>'
            f'<span class="logo-sub">{E(CFG["logo_subtext"])}</span></span></a>')





def socials():
    return "".join(f'<a href="{E(u)}" aria-label="{k.title()}" rel="noopener" target="_blank">{icon(k)}</a>'
                   for k, u in CFG["social"].items() if u)


def booking_href(r):
    return C.get("online_booking") or f"{r}contact/#programari"


# ---------------------------------------------------------------- layout
PATTERN = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='104' viewBox='0 0 120 104'%3E"
           "%3Cg fill='none' stroke='%23ffffff' stroke-opacity='.05' stroke-width='2'%3E%3Cpath d='M30 2l28 16v32L30 66 2 50V18z'/%3E"
           "%3Cpath d='M90 38l28 16v32L90 102 62 86V54z'/%3E%3Cpath d='M30 26v16M22 34h16M90 62v16M82 70h16'/%3E%3C/g%3E%3C/svg%3E\")")


def layout(path, title, body, desc=None, current=None, section="Pagini"):
    depth = path.count("/") if path else 0
    r = "../" * depth
    col = CFG["colors"]
    desc = desc or f"{NAME} – {CFG['tagline']}."
    hero_img = f'--hero-image: url("../../{CFG["hero_image"]}");' if CFG.get("hero_image") else ""  # resolved relative to static/css/
    full_title = f"{title} – {NAME}" if title != NAME else NAME
    text = re.sub(r"<[^>]+>", " ", body)
    SEARCH_INDEX.append({"url": path, "title": title, "section": section,
                         "text": unicodedata.normalize("NFD", (title + " " + text).lower()).encode("ascii", "ignore").decode()[:6000]})
    book = booking_href(r)
    book_attr = ' target="_blank" rel="noopener"' if ext(book) else ""
    badge = (f'<img class="badge-img" src="{r}{CFG["accreditation_image"]}" alt="{E(CFG["accreditation_badge"])}">' if CFG.get("accreditation_image")
             else f'<span class="badge">{icon("award")} {E(CFG["accreditation_badge"])}</span>')
    ext_links = "".join(f'<li><a href="{E(u)}" target="_blank" rel="noopener">{E(t)}</a></li>' for t, u in CFG.get("external_links", []))
    html = f"""<!doctype html>
<html lang="{CFG['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(full_title)}</title>
<meta name="description" content="{E(desc)}">
<meta property="og:title" content="{E(full_title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:type" content="website">
{f'<meta property="og:image" content="{CFG["base_url"].rstrip("/")}/{CFG["hero_image"]}">' if CFG.get("hero_image") else ""}
<link rel="canonical" href="{CFG['base_url'].rstrip('/')}/{path}">
<link rel="icon" href="{r}favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{r}static/css/style.css">
<!-- Hide native scrollbars before first paint (site-rendered bars in main.js); without JS the native ones stay. -->
<script>document.documentElement.classList.add("site-scrollbars")</script>
<style>:root{{--primary:{col['primary']};--primary-dark:{col['primary_dark']};--accent:{col['accent']};--accent-dark:{col['accent_dark']};--highlight:{col['highlight']};--soft:{col['soft']};--pattern:{PATTERN};{hero_img}}}</style>
</head>
<body>
<a class="skip-link" href="#main">Sari la conținut</a>
<header class="header">
  <div class="container header-inner">
    {logo(r)}
    <nav class="nav" aria-label="Meniu principal">{nav_html(r, current)}</nav>
    <div class="header-actions">
      <button class="icon-btn" id="searchToggle" aria-label="Caută" aria-expanded="false" aria-controls="searchPanel">{icon('search')}</button>
      <a class="btn btn-primary" href="{book}"{book_attr}>Programări</a>
      <button class="icon-btn burger" id="burger" aria-label="Meniu" aria-controls="offcanvas">{icon('menu')}</button>
    </div>
  </div>
  <div class="search-panel" id="searchPanel">
    <form class="container search-form" action="{r}cautare/" role="search">
      <input type="search" name="q" placeholder="Caută o secție, un medic sau o informație…" aria-label="Caută">
      <button class="btn btn-primary" type="submit">Caută</button>
    </form>
  </div>
</header>

<div class="offcanvas-backdrop" id="ocBackdrop"></div>
<button class="oc-close" id="ocClose" aria-label="Închide meniul">{icon('close')}</button>
<aside class="offcanvas" id="offcanvas" aria-hidden="true" aria-label="Meniu lateral">
  {logo(r)}
  {mobile_nav(r)}
  <div class="oc-mobile-extra">
    <button class="oc-search" id="ocSearch" aria-label="Caută">{icon('search')}</button>
    <div class="oc-social">{socials()}</div>
  </div>
  <div class="oc-info">
  <h4>{E(CFG['legal_name'])}</h4>
  <p class="muted">{E(CFG['tagline'])}. {E(CFG['hero_subtitle'])}</p>
  <h4>Contactează-ne</h4>
  <ul>
    <li>{icon('pin')}<span>{E(C['address'])}</span></li>
    <li>{icon('phone')}<span>Centrală: <a href="tel:{C['phone_href']}">{C['phone']}</a></span></li>
    {f'<li>{icon("calendar")}<span>Programări: <a href="tel:{C["phone_appointments_href"]}">{C["phone_appointments"]}</a></span></li>' if C.get("phone_appointments_href") else ""}
    <li>{icon('mail')}<a href="mailto:{C['email']}">{C['email']}</a></li>
  </ul>
  <a class="btn btn-accent" style="margin-top:16px" href="{book}"{book_attr}>Programări online {icon('arrow')}</a>
  <h4>Urmărește-ne</h4>
  <div class="socials">{socials()}</div>
  </div>
</aside>

<main id="main">
{body}
</main>

<footer class="footer">
  <div class="container footer-top">
    {logo(r)}
    {badge}
    <div class="socials">{socials()}</div>
  </div>
  <div class="container footer-grid">
    <div>
      <h4>{E(CFG['legal_name'])}</h4>
      <ul>
        <li><a href="{r}despre-noi/">Scurt istoric</a></li>
        <li><a href="{r}conducere/">Conducere</a></li>
        <li><a href="{r}spital/">Spital</a></li>
        <li><a href="{r}ambulatoriu/">Ambulatoriu</a></li>
        <li><a href="{r}team/">Medici</a></li>
        <li><a href="{r}cariere/">Cariere</a></li>
        <li><a href="{r}contact/">Contact</a></li>
      </ul>
    </div>
    <div>
      <h4>Informații utile</h4>
      <ul>
        <li><a href="{r}tipuri-de-prezentare/">Tipuri de prezentare</a></li>
        <li><a href="{r}servicii-medicale-cu-plata/">Plata serviciilor medicale</a></li>
        <li><a href="{r}contracte-casmb-cnas/">Contracte CASMB / CNAS</a></li>
        <li><a href="{r}reguli-si-program-de-vizita/">Program de vizită</a></li>
        <li><a href="{r}interes-public/">Interes public</a></li>
        <li><a href="{r}intrebari-frecvente/">Întrebări frecvente</a></li>
        <li><a href="{r}declaratie-privind-accesibilitatea/">Declarație privind accesibilitatea</a></li>
      </ul>
    </div>
    <div>
      <h4>Contactează-ne</h4>
      <ul>
        <li class="contact-line">{icon('pin')}<span>{E(C['address'])}</span></li>
        <li class="contact-line">{icon('phone')}<span>Centrală: <a href="tel:{C['phone_href']}">{C['phone']}</a>{f"<br>Fax: {C['fax']}" if C.get('fax') else ""}</span></li>
        <li class="contact-line">{icon('mail')}<span><a href="mailto:{C['email']}">{C['email']}</a>{f"<br><a href='mailto:{C['email_office']}'>{C['email_office']}</a>" if C.get('email_office') else ""}</span></li>
      </ul>
    </div>
    <div>
      <h4>Linkuri utile</h4>
      <ul>{ext_links}</ul>
    </div>
  </div>
  <div class="container footer-cta">
    <div><small>Programări telefonice</small><br><a class="big" href="tel:{C.get('phone_appointments_href', C['phone_href'])}">{C.get('phone_appointments') or C['phone']}</a></div>
    <a class="btn btn-white" href="{book}"{book_attr}>Programează-te online {icon('arrow')}</a>
  </div>
  <div class="copyright">Copyright © {date.today().year} {E(CFG['legal_name'])}
    <nav><a href="{r}confidentialitate/">Confidențialitate</a><a href="{r}declaratie-privind-accesibilitatea/">Accesibilitate</a><a href="https://anpc.ro" rel="noopener" target="_blank">ANPC</a></nav>
  </div>
</footer>

<button class="a11y-btn" id="a11yBtn" aria-label="Opțiuni de accesibilitate" aria-expanded="false" aria-controls="a11yPanel">{icon('a11y')}</button>
<div class="a11y-panel" id="a11yPanel" role="group" aria-label="Accesibilitate">
  <button data-a11y="plus">A+ Mărește textul</button><button data-a11y="minus">A− Micșorează textul</button>
  <button data-a11y="contrast">Contrast ridicat</button><button data-a11y="grayscale">Tonuri de gri</button>
  <button data-a11y="links">Subliniază linkurile</button><button data-a11y="reset">Resetează</button>
</div>
<button class="back-top" id="backTop" aria-label="Înapoi sus">{icon('up')}</button>
<div class="lightbox" id="lightbox" hidden><button class="icon-btn" aria-label="Închide">{icon('close')}</button><img alt=""></div>
<script src="{r}static/js/main.js"></script>
</body>
</html>
"""
    dest = OUT / path / "index.html" if path else OUT / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html.replace(R, r), encoding="utf-8")


def page_hero(title, crumbs=()):
    bc = f'<a href="{R}">Acasă</a>' + "".join(f' / <a href="{R}{u}">{E(t)}</a>' if u else f" / {E(t)}" for t, u in crumbs)
    return f"""<section class="page-hero">
  <span class="hero-side" aria-hidden="true">{E(CFG['legal_name'])}</span>
  <div class="hero-social socials">{socials()}</div>
  <div class="container"><h1>{E(title)}</h1><div class="breadcrumbs">{bc}</div></div>
  <a class="hero-phone" href="tel:{C['phone_href']}"><span class="ring">{icon('phone')}</span>{C['phone']}</a>
</section>"""


def contact_box(phone_lines=None, hours=None):
    extra = ""
    if hours:
        extra += '<ul class="cb-list">' + "".join(f"<li>{icon('clock')}<span>{E(h)}</span></li>" for h in hours) + "</ul>"
    if phone_lines:
        extra += '<ul class="cb-list">' + "".join(f"<li>{icon('phone')}<span>{E(p)}</span></li>" for p in phone_lines) + "</ul>"
    book = booking_href(R)
    tgt = ' target="_blank" rel="noopener"' if ext(book) else ""
    return f"""<div class="contact-box">
  <div class="card-icon">{icon('chat')}</div>
  <h3>Contactează-ne</h3>
  <a class="phone" href="tel:{C['phone_href']}">{C['phone']}</a>
  <a class="mail" href="mailto:{C['email']}">{C['email']}</a>
  {extra}
  <a class="btn btn-white" href="{book}"{tgt}>Programări {icon('arrow')}</a>
</div>"""


def accordion(items, open_first=True):
    return '<div class="accordion">' + "".join(
        f'<details{" open" if open_first and i == 0 else ""}><summary>{E(q)}</summary><div class="acc-body">{a}</div></details>'
        for i, (q, a) in enumerate(items)) + "</div>"


def faq_block(title="Întrebări frecvente"):
    return f'<h2 class="h2">{title}</h2>' + accordion([(f["q"], f"<p>{E(f['a'])}</p>") for f in L["faq"]])


def initials(name):
    parts = [p for p in re.sub(r"\(.*?\)|^(Dr\.|Biol\.|Psiholog)\s*", "", name).split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper()




def post_card(n):
    thumb = f'<img src="{R}{n["image"]}" alt="" loading="lazy">' if n.get("image") else icon("hospital")
    when = f'<time datetime="{n["date"]}">{fdate(n["date"])}</time>' if n.get("date") else ""
    return f"""<article class="post-card"><a class="post-thumb" href="{R}{post_url(n)}" tabindex="-1">{thumb}</a>
  <div class="post-body"><div class="post-meta"><b>{E(n['category'])}</b>{when}</div>
  <h3><a href="{R}{post_url(n)}">{E(n['title'])}</a></h3><p>{E(n['excerpt'])}</p>
  <a class="read-more" href="{R}{post_url(n)}">Citește mai mult →</a></div></article>"""


def gallery(imgs):
    if not imgs:
        return ""
    return '<div class="gallery">' + "".join(f'<a href="{R}{g}" data-lightbox><img src="{R}{g}" alt="" loading="lazy"></a>' for g in imgs) + "</div>"


def docs_list(docs):
    return '<div class="doc-list">' + "".join(a_doc(t, u) for t, u in docs) + "</div>"


def simple(path, title, content, crumbs=None, sidebar=True, desc=None, section="Pagini", current=None):
    side = f'<aside class="sidebar">{contact_box()}</aside>' if sidebar else ""
    inner = f'<div class="with-sidebar right"><div class="prose">{content}</div>{side}</div>' if sidebar else content
    layout(path, title, page_hero(title, crumbs or [(title, None)]) + f'<section class="section"><div class="container">{inner}</div></section>',
           desc=desc, current=current or path, section=section)


TODO = '<p class="placeholder">[Conținut de completat de către spital.]</p>'
ABOUT_CRUMB = [("Despre noi", "despre-noi/")]
INFO_CRUMB = [("Informații utile", "informatii-utile/")]


# ---------------------------------------------------------------- pages





def accreditations():
    cards = "".join(f'<a class="card tile" href="{E(a["url"] if ext(a["url"]) else R + quote(a["url"]))}" target="_blank" rel="noopener"><div class="card-icon">{icon("award")}</div><h3>{E(a["title"])}</h3><span class="read-more">{icon("download")} Vezi documentul</span></a>' for a in L["accreditations"])
    img = f'<img src="{R}{CFG["accreditation_image"]}" alt="{E(CFG["accreditation_badge"])}" style="max-width:220px;margin:0 auto 30px">' if CFG.get("accreditation_image") else ""
    body = page_hero("Acreditări / Certificări", ABOUT_CRUMB + [("Acreditări / Certificări", None)]) + f"""
<section class="section tiles-bg"><div class="container">{img}<div class="grid g3">{cards}</div>
<p class="center mt-40 muted">Laboratorul de analize medicale este acreditat RENAR conform ISO 15189:2013 pentru hematologie, chimie clinică, imunologie și parazitologie.</p></div></section>"""
    layout("acreditari/", "Acreditări / Certificări", body, current="despre-noi/")


def indicators():
    rows = "".join(f"<tr><td>{E(a)}</td><td class='price'>{b}</td><td class='price'>{c}</td></tr>" for a, b, c in L["statistics"])
    content = f"""<h2>Indicatori de activitate</h2>
<div class="table-wrap"><table><thead><tr><th>Indicator</th><th style="text-align:right">2015</th><th style="text-align:right">2016</th></tr></thead><tbody>{rows}</tbody></table></div>
<h3>Date și informații referitoare la activitatea spitalului (Ordinul 1117/2025)</h3>
{docs_list([["Date și informații referitoare la activitatea spitalului (PDF)", "uploads/docs/files/2026/date si informatii referitoare la activitatea spitalului.pdf"]])}
<h3>Acreditări</h3><p>Spitalul este acreditat ANMCS și certificat ISO 9001; laboratorul de analize medicale este acreditat RENAR.</p>
<a class="btn btn-primary" href="{R}acreditari/">Acreditări / Certificări</a>"""
    simple("indicatori-de-calitate/", "Indicatori și statistici", content, ABOUT_CRUMB + [("Indicatori și statistici", None)], current="despre-noi/")


def research():
    items = "".join(f'<div class="card"><div class="card-icon">{icon("microscope")}</div><h3>{E(a)}</h3><p>{E(b)}</p></div>' for a, b in L["research"])
    body = page_hero("Cercetare și proiecte", ABOUT_CRUMB + [("Cercetare și proiecte", None)]) + f"""
<section class="section"><div class="container"><div class="section-head"><h2>Activități de cercetare</h2></div><div class="grid g3">{items}</div></div></section>
<section class="section bg-soft"><div class="container prose"><h2>Programe și proiecte</h2>
{docs_list([["Programul Național de Diabet Zaharat", "http://www.cnas.ro/page/programul-national-de-diabet-zaharat.html"], ["Îngrijiri la domiciliu – furnizori în contract cu CASMB", "http://www.cnas.ro/casmb/page/lista-furnizori-in-contract.html"], ["Listă cabinete de medicină de familie", "http://www.cnas.ro/casmb/page/lista-cabinete-medicina-de-familie.html"]])}</div></section>"""
    layout("cercetare-si-inovare/", "Cercetare și proiecte", body, current="despre-noi/")


def partners():
    items = "".join(f'<div class="card"><div class="card-icon">{icon("handshake")}</div><h3>{E(a)}</h3><p>{E(b)}</p>{a_doc("Site oficial", c, "read-more") if c else ""}</div>' for a, b, c in L["partners"])
    body = page_hero("Parteneriate", ABOUT_CRUMB + [("Parteneriate", None)]) + f'<section class="section"><div class="container"><div class="grid g2">{items}</div></div></section>'
    layout("parteneriate/", "Parteneriate", body, current="despre-noi/")








def sidebar_news():
    recent = "".join(f'<li><a href="{R}{post_url(n)}">{E(n["title"])}</a>{("<time>" + fdate(n["date"]) + "</time>") if n.get("date") else ""}</li>' for n in NEWS[:6])
    return f"""<aside class="sidebar">
    <div class="widget"><h3>Caută</h3><form class="search-form" style="padding:0" action="{R}cautare/"><input type="search" name="q" aria-label="Caută"><button class="btn btn-primary btn-sm" type="submit">{icon('search')}</button></form></div>
    <div class="widget"><h3>Articole recente</h3><ul>{recent}</ul></div>
    <div class="widget"><h3>Anunțuri și concursuri</h3><ul><li><a href="{R}cariere/">Concursuri și examene</a></li><li><a href="{R}anunturi/">Anunțuri publicitare</a></li></ul></div>
  </aside>"""


def news_list():
    body = page_hero("Noutăți și campanii", ABOUT_CRUMB + [("Noutăți", None)]) + f"""
<section class="section"><div class="container with-sidebar right">
  <div class="grid g2">{"".join(post_card(n) for n in NEWS)}</div>
  {sidebar_news()}
</div></section>"""
    layout("noutati/", "Noutăți și campanii", body, current="despre-noi/")


def post_page(n):
    related = [x for x in NEWS if x is not n][:2]
    when = f'<time datetime="{n["date"]}">{fdate(n["date"])}</time>' if n.get("date") else ""
    img = f'<a href="{R}{n["image"]}" data-lightbox><img class="post-img" src="{R}{n["image"]}" alt="{E(n["title"])}"></a>' if n.get("image") else ""
    links = "".join(a_doc(t, u) for t, u in [("Descarcă afișul (PDF)", n.get("attachment")), ("Site-ul programului", n.get("link"))] if u)
    body = page_hero(n["title"], [("Noutăți", "noutati/"), (n["category"], None)]) + f"""
<section class="section"><div class="container with-sidebar right">
  <article class="prose">
    <div class="post-meta"><b>{E(n['category'])}</b>{when}</div>
    {paras(n["body"])}{f'<div class="doc-list">{links}</div>' if links else ""}{img}
    <h3 style="margin-top:50px">Articole asemănătoare</h3><div class="grid g2">{"".join(post_card(x) for x in related)}</div>
  </article>
  {sidebar_news()}
</div></section>"""
    layout(post_url(n), n["title"], body, desc=n["excerpt"], current="despre-noi/", section="Noutăți")


def careers():
    items = "".join(a_doc(c["title"], c["url"]) for c in L["contests"])
    content = f"""<h2>Alătură-te echipei noastre!</h2>
<p>Posturile vacante sunt scoase la concurs conform legislației în vigoare. Anunțurile de concurs, centralizatoarele cu rezultatele fiecărei probe și rezultatele finale sunt publicate pe această pagină.</p>
<div class="info-box"><span class="ring">{icon('phone')}</span><div><small>Concursuri / examene – Serviciul R.U.N.O.S. (Luni – Vineri, 08:00 – 16:00)</small><strong>{C.get('phone_hr', C['phone'])}</strong></div></div>
<h2>Concursuri și examene</h2>
<div class="doc-list scroll">{items}</div>"""
    simple("cariere/", "Cariere", content, ABOUT_CRUMB + [("Cariere", None)], current="despre-noi/")


def announcements():
    content = f"""<h2>Anunțuri publicitare și achiziții</h2>{docs_list([[a["title"], a["url"]] for a in L["announcements"]])}
<h3>Planul anual al achizițiilor publice</h3>{docs_list(next(p["docs"] for p in L["public_interest"] if p["title"] == "Achiziții publice")[:1])}"""
    simple("anunturi/", "Anunțuri și achiziții", content, INFO_CRUMB + [("Anunțuri", None)], current="informatii-utile/")


def garzi_page():
    content = f"""<h2>Programul gărzilor din spital</h2>
<p>Spitalul asigură asistență medicală 24/24 h, 7/7 zile, cu linii de gardă pentru obstetrică-ginecologie, neonatologie, diabet, nutriție și boli metabolice, medicină internă, chirurgie generală, ATI și laborator de analize medicale.</p>
{docs_list([[g["title"], g["url"]] for g in L["garzi"]])}
<div class="info-box"><span class="ring">{icon('ambulance')}</span><div><small>Camera de gardă</small><strong>{C['phone']} – tasta 1</strong></div></div>"""
    simple("program-garzi/", "Program gărzi spital", content, INFO_CRUMB + [("Program gărzi", None)], current="informatii-utile/")



def visitors_hub():
    body = page_hero("Pentru vizitatori și aparținători", INFO_CRUMB + [("Pentru vizitatori și aparținători", None)]) + f"""
<section class="section"><div class="container"><div class="grid g2">
  <a class="card" href="{R}reguli-si-program-de-vizita/"><div class="card-icon">{icon('clock')}</div><h3>Program și reguli de vizită</h3><p>Programul de vizită pe secții și regulile pentru vizitatori.</p><span class="read-more">Află mai multe →</span></a>
  <a class="card" href="{R}chestionar-de-feedback/"><div class="card-icon">{icon('chat')}</div><h3>Chestionar de feedback</h3><p>Spune-ne cum ți s-a părut experiența în spitalul nostru.</p><span class="read-more">Completează →</span></a>
</div></div></section>"""
    layout("pentru-vizitatori-si-apartinatori/", "Pentru vizitatori și aparținători", body, current="informatii-utile/")



def cas_page():
    feats = [("Medici cu experiență", "people"), ("Tehnologie medicală modernă", "cpu"), ("Laborator acreditat RENAR", "flask"), ("Cabinete de specialitate în ambulatoriu", "stethoscope")]
    cats = [("Ambulatoriu de specialitate", "ambulatoriu/", "stethoscope"), ("Laborator analize medicale", "service/laborator/", "flask"), ("Radiologie și imagistică", "service/radiologie/", "xray"), ("Medicină fizică și reabilitare", "service/recuperare/", "run")]
    body = page_hero("Servicii decontate prin CASMB", INFO_CRUMB + [("Servicii decontate prin CASMB", None)]) + f"""
<section class="section"><div class="container split">
  <div><span class="eyebrow">Fără costuri pentru asigurați</span><h2 class="h2">Servicii medicale gratuite, decontate prin CASMB</h2>
  <p class="muted">Ca pacient asigurat, ai acces gratuit la consultații, analize și investigații decontate de Casa de Asigurări de Sănătate a Municipiului București, pe baza biletului de trimitere și în limita fondurilor contractate.</p>
  {docs_list([["Servicii pentru asigurați – CASMB", "https://www.casmb.ro/asigurati_servicii.php"], ["Investigații paraclinice decontate de CASMB", "http://www.cnas.ro/casmb/page/investigatii-paraclinice-decontate-de-casmb.html"]])}</div>
  <div class="media"><img src="{R}uploads/images/galerie-foto/laborator/1.jpg" alt="Laborator"></div>
</div></section>
<section class="section bg-soft"><div class="container"><div class="section-head"><h2>Ce beneficii ai la {E(NAME)}?</h2></div>
  <div class="grid g4">{"".join(f'<div class="card"><div class="card-icon">{icon(i)}</div><h3>{t}</h3></div>' for t, i in feats)}</div></div></section>
<section class="section"><div class="container prose"><h2>De ce documente ai nevoie?</h2>
  {ul(["Bilet de trimitere de la medicul de familie sau de la un medic specialist aflat în contract cu CASMB", "Cardul de sănătate", "Dovada calității de asigurat (sau adeverință eliberată de CASMB, în lipsa cardului)", "CI / BI / Pașaport / Certificat de naștere, original și xerocopie"])}
  <p>În lipsa biletului de trimitere, serviciile pot fi oferite contra cost, conform <a href="{R}servicii-medicale-cu-plata/"><u>listei de tarife</u></a>.</p>
  <div class="grid g4" style="margin-top:30px">{"".join(f'<a class="card" href="{R}{u}"><div class="card-icon">{icon(i)}</div><h4>{t}</h4><span class="read-more">Detalii →</span></a>' for t, u, i in cats)}</div>
</div></section>"""
    layout("servicii-decontate-prin-cas/", "Servicii decontate prin CASMB", body, current="informatii-utile/")



def rights_page():
    r_ = L["rights"]
    groups = "".join(f"<h3>{E(g['title'])}</h3>{ul(g['items'])}" for g in r_["groups"])
    content = f"""<h2>Drepturile pacienților</h2>{paras(r_['intro'][:1])}{groups}
<h2>Obligațiile pacienților</h2>{ul(r_['obligations'])}"""
    simple("drepturile-pacientilor/", "Drepturile și obligațiile pacienților", content, INFO_CRUMB + [("Drepturile pacienților", None)], current="informatii-utile/")


def visit_rules():
    rows = "".join(f"<tr><td><strong>{E(a)}</strong></td><td>{E(b)}{('<br>' + E(c)) if c else ''}</td></tr>" for a, b, c in CFG.get("visiting", []))
    pdf = docs_list([["Program de vizită aparținători (PDF)", CFG["visiting_pdf"]]]) if CFG.get("visiting_pdf") else ""
    content = f"""<h2>Program de vizită</h2>
<div class="table-wrap"><table><thead><tr><th>Secție</th><th>Program</th></tr></thead><tbody>{rows}</tbody></table></div>{pdf}{updated()}
<h2>Reguli pentru vizitatori</h2>
{ul(["Vizitatorii respectă orele de vizită impuse de specificul fiecărei secții", "La intrarea în secție, vizitatorii se echipează cu halate și papuci de protecție", "Pacienții sunt rugați să limiteze pe cât posibil numărul vizitatorilor", "Fumatul și consumul de băuturi alcoolice sunt interzise în incinta spitalului", "Vizitatorii respectă regulile de acces, de conduită și disciplină ale spitalului"])}"""
    simple("reguli-si-program-de-vizita/", "Program de vizită", content, INFO_CRUMB + [("Program de vizită", None)], current="informatii-utile/")


def feedback_page():
    url = CFG.get("feedback_url")
    content = f"""<h2>Spune-ne părerea ta și ajută-ne să fim mai buni!</h2>
<p>Opinia pacienților și a aparținătorilor ne ajută să îmbunătățim calitatea serviciilor. Puteți completa chestionarul oficial de feedback al Ministerului Sănătății sau chestionarul de satisfacție pe care îl primiți la externare (se lasă în urna special amenajată în secție).</p>
{f'<p><a class="btn btn-primary" href="{E(url)}" target="_blank" rel="noopener">Completează chestionarul online {icon("external")}</a></p>' if url else ""}
<p>Sesizări privind integritatea: <a href="mailto:{C.get('email_integrity', C['email'])}">{C.get('email_integrity', C['email'])}</a></p>"""
    simple("chestionar-de-feedback/", "Chestionar de feedback", content, INFO_CRUMB + [("Chestionar de feedback", None)], current="informatii-utile/")


def health_education():
    body = page_hero("Campanii de sănătate", INFO_CRUMB + [("Campanii de sănătate", None)]) + f'<section class="section"><div class="container"><div class="grid g3">{"".join(post_card(n) for n in NEWS)}</div></div></section>'
    layout("educatie-pentru-sanatate/", "Campanii de sănătate", body, current="informatii-utile/")


def faq_page():
    simple("intrebari-frecvente/", "Întrebări frecvente", faq_block("Răspunsuri la cele mai frecvente întrebări"), INFO_CRUMB + [("Întrebări frecvente", None)], current="informatii-utile/")


def public_interest():
    tiles, sections = [], []
    for i, p in enumerate(L["public_interest"]):
        if p.get("page"):
            href, label = R + p["page"], "Vezi pagina"
        elif p.get("docs"):
            sid = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFD", p["title"].lower()).encode("ascii", "ignore").decode()).strip("-")
            href, label = f"#doc-{sid}", f"{len(p['docs'])} {'document' if len(p['docs']) == 1 else 'documente'}"
            note = f'<p class="muted">{E(p["note"])}</p>' if p.get("note") else ""
            sections.append(f'<details id="doc-{sid}"><summary>{E(p["title"])} <small>({len(p["docs"])})</small></summary><div class="acc-body">{note}{docs_list(p["docs"])}</div></details>')
        elif p.get("link"):
            href, label = p["link"], "Vezi documentele"
        else:
            continue
        tgt = ' target="_blank" rel="noopener"' if ext(href) else ""
        tiles.append(f'<a class="card tile" href="{E(href)}"{tgt} data-open="{href[1:] if href.startswith("#") else ""}"><div class="card-icon">{icon(p["icon"])}</div><h3>{E(p["title"])}</h3><span class="btn btn-primary btn-sm">{label}</span></a>')
    officer = (f"Persoana responsabilă de primirea solicitărilor în baza Legii nr. 544/2001 este <strong>{E(C['public_info_officer'])}</strong>." if C.get("public_info_officer")
               else "Solicitările de informații de interes public în baza Legii nr. 544/2001 se adresează secretariatului spitalului.")
    body = page_hero("Interes public", INFO_CRUMB + [("Interes public", None)]) + f"""
<section class="section tiles-bg"><div class="container"><div class="grid g4">{"".join(tiles)}</div></div></section>
<section class="section"><div class="container"><h2 class="h2">Documente</h2><div class="accordion" id="docsAccordion">{"".join(sections)}</div></div></section>
<section class="section bg-soft"><div class="container">
  <h2 class="h2">Solicitare informații de interes public</h2>
  <p>{officer}</p>
  <div class="req-grid" style="grid-template-columns:repeat(3,1fr);margin-top:24px">
    <div class="req">{icon('mail')}<div><strong>Email</strong>{C['email']}<br>{C.get('email_office', '')}</div></div>
    <div class="req">{icon('phone')}<div><strong>Telefon</strong>{C['phone']}{('<br>Fax: ' + C['fax']) if C.get('fax') else ''}</div></div>
    <div class="req">{icon('building')}<div><strong>Depus la Registratura Spitalului</strong>{E(C['address_short'])}</div></div>
  </div>
</div></section>"""
    layout("interes-public/", "Interes public", body, current="informatii-utile/")


def contact():
    t = CFG["transport"]
    tic = {"metrou": "metro", "autobuz": "bus", "troleibuz": "bus", "tramvai": "tram"}
    trans = "".join(f'<div class="card"><div class="card-icon">{icon(tic.get(k, "bus"))}</div><h3>{k.title()}</h3><p>{E(v)}</p></div>' for k, v in t.items() if v)
    book = booking_href(R)
    body = page_hero("Contact", [("Contact", None)]) + f"""
<section class="section"><div class="container">
  <div class="section-head"><h2>{E(CFG['legal_name'])}</h2><p>{E(C['address'])}</p>{updated()}</div>
  <div class="grid g4 contact-cards">
    <div class="card"><div class="card-icon">{icon('phone')}</div><h3>Telefon</h3><p><a href="tel:{C['phone_href']}">{C['phone']}</a>{('<br>Fax: ' + C['fax']) if C.get('fax') else ''}</p></div>
    <div class="card"><div class="card-icon">{icon('calendar')}</div><h3>Programări</h3><p>{f'<a href="tel:{C["phone_appointments_href"]}">{C["phone_appointments"]}</a><br>' if C.get("phone_appointments_href") else ""}<a href="{book}" target="_blank" rel="noopener">Programări online</a></p></div>
    <div class="card"><div class="card-icon">{icon('mail')}</div><h3>Email</h3><p><a href="mailto:{C['email']}">{C['email']}</a>{f"<br><a href='mailto:{C['email_office']}'>{C['email_office']}</a>" if C.get('email_office') else ""}</p></div>
    <div class="card"><div class="card-icon">{icon('people')}</div><h3>Audiențe management</h3><p>{"<br>".join(E(x.strip()) for x in C['audiente'].split("·"))}</p></div>
  </div>
</div></section>
<section class="section bg-soft" id="programari"><div class="container split" style="align-items:start">
  <div>
    <span class="eyebrow">Programări</span><h2 class="h2">Cum te programezi</h2>
    <div class="info-box"><span class="ring">{icon('phone')}</span><div><small>Centrală – apoi tasta secției dorite</small><strong>{C['phone']}</strong></div></div>
    {f'<div class="info-box"><span class="ring">{icon("calendar")}</span><div><small>Programări</small><strong>{C["phone_appointments"]}</strong></div></div>' if C.get("phone_appointments") else ""}
    <a class="btn btn-primary" href="{book}" target="_blank" rel="noopener">Programări online {icon('external')}</a>
    <h3 style="margin-top:30px">Centrala telefonică</h3>
    <ul class="list-check"><li>Tasta 1 – Camera de gardă</li><li>Tasta 4 – Imagistică medicală (1 Radiologie, 2 CT, 3 Mamograf)</li><li>Tasta 5 – Secții spital (1 Obstetrică-Ginecologie, 2 Neonatologie, 3 Medicină internă, 4 Diabet, 5 Chirurgie, 6 Recuperare, 7 Alergologie, 8 Anatomie patologică, 9 ATI)</li><li>Tasta 6 – Laborator analize (1 Punct de recoltare)</li></ul>
  </div>
  <div class="form-card"><h3>Mass-media</h3><p>Purtător de cuvânt: {E(C.get('spokesperson', ''))}</p><h3>Integritate</h3><p>Sesizări: <a href="mailto:{C.get('email_integrity', '')}">{C.get('email_integrity', '')}</a></p>
  <h3>Concursuri / Resurse umane</h3><p>{C.get('phone_hr', '')} (R.U.N.O.S.)</p></div>
</div></section>
<section class="section"><div class="container">
  <iframe class="map" title="Hartă – {E(NAME)}" loading="lazy" src="https://maps.google.com/maps?q={E(C['map_query'])}&output=embed"></iframe>
  <div class="grid g3 transport" style="margin-top:30px">{trans}</div>
</div></section>"""
    layout("contact/", "Contact", body, current="contact/")


def accessibility():
    content = f"""<h2>Angajamentul nostru privind accesibilitatea</h2>
<p>{E(CFG['legal_name'])} se angajează să asigure accesibilitatea website-ului său pentru toate persoanele, inclusiv pentru persoanele cu dizabilități, în conformitate cu legislația în vigoare și cu recomandările WCAG 2.1, nivel AA.</p>
<h2>Accesibilitatea pe site</h2>{ul(["structură semantică a paginilor și navigare din tastatură", "texte alternative pentru imagini", "contrast adecvat între text și fundal", "design responsive, adaptat pentru dispozitive mobile"])}
<h2>Activarea meniului pentru Accesibilitate</h2><p>Apăsați butonul rotund din colțul stânga-jos al ecranului pentru a mări sau micșora textul, a activa contrastul ridicat, tonurile de gri sau sublinierea linkurilor.</p>
<h2>Conținut neaccesibil</h2><p>Unele documente PDF scanate pot să nu fie complet accesibile. Le puteți solicita într-un format alternativ folosind datele de contact de mai jos.</p>
<h2>Date de contact pentru utilizatori</h2><p>Email: <a href="mailto:{C['email']}">{C['email']}</a><br>Telefon: {C['phone']}</p>
<h2>Întocmirea declarației</h2><p>Prezenta declarație a fost întocmită la data de {fdate(date.today().isoformat())}.</p>"""
    simple("declaratie-privind-accesibilitatea/", "Declarație privind accesibilitatea", content, [("Declarație privind accesibilitatea", None)])


def privacy():
    content = f"""<h2>Protecția datelor cu caracter personal</h2>
<p>{E(CFG['legal_name'])} prelucrează datele cu caracter personal în conformitate cu Regulamentul (UE) 2016/679 (GDPR) și cu legislația națională aplicabilă.</p>
{TODO}
<p>Pentru exercitarea drepturilor privind datele personale vă puteți adresa la <a href="mailto:{C['email']}">{C['email']}</a>.</p>"""
    simple("confidentialitate/", "Confidențialitate", content, [("Confidențialitate", None)])


def search_page():
    body = page_hero("Căutare", [("Căutare", None)]) + f"""
<section class="section"><div class="container" style="max-width:860px">
  <form class="search-form" action="" role="search"><input id="searchPageInput" type="search" name="q" aria-label="Caută"><button class="btn btn-primary" type="submit">Caută</button></form>
  <div class="results" id="searchResults" data-index="{R}search-index.json" data-root="{R}" aria-live="polite"></div>
</div></section>"""
    layout("cautare/", "Căutare", body)


def not_found():
    body = page_hero("Pagina nu a fost găsită") + f'<section class="section"><div class="container center"><p>Ne pare rău, pagina căutată nu există.</p><a class="btn btn-primary" href="{R}">Înapoi la pagina principală</a></div></section>'
    layout("404/", "Pagina nu a fost găsită", body)
    (OUT / "404.html").write_text((OUT / "404/index.html").read_text(encoding="utf-8").replace('"../', f'"{BASE_PATH}'), encoding="utf-8")



# ==== DATA ====================================================================
HOSP = json.loads((ROOT / "content/hospital.json").read_text(encoding="utf-8"))
AMB = json.loads((ROOT / "content/ambulatory.json").read_text(encoding="utf-8"))
HOSP_BY = {h["slug"]: h for h in HOSP}
AMB_BY = {c["slug"]: c for c in AMB}
CATEGORIES = [("clinic", "Secții și compartimente clinice"), ("paraclinic", "Laboratoare și servicii paraclinice"), ("other", "Alte structuri")]


def sort_key(name):
    """Alphabetical by surname, then first name (titles such as Dr./Biol./Psiholog are ignored)."""
    bare = re.sub(r"^(Conf\. univ\. dr\.|Dr\.|Biol\.|Psiholog|Ec\.|Dna|Dl|As\. med\.( princ\.)?)\s*", "", name)
    plain = unicodedata.normalize("NFD", bare.lower()).encode("ascii", "ignore").decode()
    return (plain, bare)


DOCS.sort(key=lambda d: sort_key(d["name"]))


# ==== helpers =================================================================
def rich(text):
    """Escape text; [[...]] marks a draft/placeholder that the hospital must confirm."""
    # HIDE_PLACEHOLDERS=1 (public launch) renders drafts as plain text instead of highlighted
    cls = "" if os.environ.get("HIDE_PLACEHOLDERS") else ' class="placeholder"'
    return re.sub(r"\[\[(.*?)\]\]", rf'<span{cls}>\1</span>', E(text))


def lines_html(lines):
    """Paragraphs, with consecutive '– …' lines rendered as a dashed list."""
    out, items = [], []
    def flush():
        if items:
            out.append('<ul class="list-check">' + "".join(f"<li>{rich(i)}</li>" for i in items) + "</ul>")
            items.clear()
    for ln in lines:
        if not ln:
            continue
        if ln.startswith("– "):
            items.append(ln[2:])
        else:
            flush()
            out.append(f"<p>{rich(ln)}</p>")
    flush()
    return "".join(out)


def ul(items, cls="list-check"):
    out = []
    for x in items:
        x = re.sub(r"^[–-]\s+", "", x)
        if x.endswith(":") and len(x) < 60:
            out.append(f'</ul><h4 class="list-sub">{E(x.rstrip(":"))}</h4><ul class="{cls}">')
        else:
            out.append(f"<li>{rich(cap(x))}</li>")
    return f'<ul class="{cls}">' + "".join(out) + "</ul>"


def hosp_url(h): return f"service/{h['slug']}/"
def cab_url(c): return f"ambulatoriu/{c['slug']}/"
def spec_url(s): return hosp_url(s)


def section_doctors(slug): return [d for d in DOCS if d.get("section") == slug]
def cabinet_doctors(slug): return [d for d in DOCS if d.get("cabinet") == slug]


def redirect(path, target):
    """Old URL kept working: a tiny page that forwards to the new one."""
    depth = path.count("/")
    r = "../" * depth
    dest = OUT / path / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={r}{target}">'
                    f'<link rel="canonical" href="{r}{target}"><title>Pagina s-a mutat</title><a href="{r}{target}">Pagina s-a mutat aici.</a>', encoding="utf-8")


# ==== navigation ==============================================================
NAV = [
    ("Despre noi", "despre-noi/", [
        ("Scurt istoric", "despre-noi/"), ("Misiune, viziune, valori", "despre-noi/#misiune"), ("Conducere", "conducere/"),
        ("Structura organizatorică", "structura-organizatorica/"), ("Acreditări / Certificări", "acreditari/"),
        ("Indicatori și statistici", "indicatori-de-calitate/"), ("Noutăți și campanii", "noutati/"),
        ("Cercetare și proiecte", "cercetare-si-inovare/"), ("Parteneriate", "parteneriate/"), ("Cariere", "cariere/")]),
    ("Spital", "spital/", "HOSP"),
    ("Ambulatoriu", "ambulatoriu/", "AMB"),
    ("Medici", "team/", None),
    ("Informații utile", "informatii-utile/", [
        ("§Pentru pacienți", None), ("Tipuri de prezentare", "tipuri-de-prezentare/"),
        ("Servicii decontate prin CASMB", "servicii-decontate-prin-cas/"), ("Contracte cu CASMB și CNAS", "contracte-casmb-cnas/"),
        ("Plata serviciilor medicale", "servicii-medicale-cu-plata/"), ("Drepturile și obligațiile pacienților", "drepturile-pacientilor/"),
        ("Program gărzi spital", "program-garzi/"), ("Chestionar de feedback", "chestionar-de-feedback/"), ("Întrebări frecvente", "intrebari-frecvente/"),
        ("§Pentru vizitatori și aparținători", None), ("Program de vizită", "reguli-si-program-de-vizita/"),
        ("§Interes public", None), ("Informații de interes public", "interes-public/"), ("Anunțuri și achiziții", "anunturi/")]),
    ("Contact", "contact/", None),
]


def nav_pairs(sub):
    if sub == "HOSP":
        out = []
        for cat, label in CATEGORIES:
            out.append(("§" + label, None))
            out += [(h["name"], hosp_url(h)) for h in HOSP if h["category"] == cat]
        return out
    if sub == "AMB":
        return [(c["name"], cab_url(c)) for c in AMB]
    return sub


def nav_html(r, current):
    out = []
    top = (current or "").split("/")[0]
    owner = {"service": "spital/", "ambulatoriu": "ambulatoriu/", "team": "team/"}.get(top)
    for label, url, sub in NAV:
        active = " active" if current is not None and (owner == url or top == url.split("/")[0]) else ""
        if sub is None:
            out.append(f'<li class="{active.strip()}"><a href="{r}{url}">{label}</a></li>')
            continue
        pairs = nav_pairs(sub)
        items = "".join(f'<li class="label">{t[1:]}</li>' if t.startswith("§") else f'<li><a href="{r}{u}">{E(t)}</a></li>' for t, u in pairs)
        cls = "submenu cols" if sub in ("HOSP", "AMB") else "submenu"
        out.append(f'<li class="has-sub{active}"><a href="{r}{url}">{label} {icon("caret", "caret")}</a><ul class="{cls}">{items}</ul></li>')
    return "<ul>" + "".join(out) + "</ul>"


def mobile_nav(r):
    out = []
    for label, url, sub in NAV:
        if sub is None:
            out.append(f'<li><a href="{r}{url}">{label}</a></li>')
            continue
        pairs = [(t, u) for t, u in nav_pairs(sub) if u]
        items = f'<li><a href="{r}{url}">Vezi tot</a></li>' + "".join(f'<li><a href="{r}{u}">{E(t)}</a></li>' for t, u in pairs)
        out.append(f'<li><details><summary>{label} {icon("caret", "caret")}</summary><ul>{items}</ul></details></li>')
    return '<nav class="mobile-nav" aria-label="Meniu mobil"><ul>' + "".join(out) + "</ul></nav>"


# ==== cards ===================================================================
def doctor_card(d, show_spec=False):
    role = f'<em class="role">{E(d["role"])}</em>' if d.get("role") else ""
    where = []
    if d.get("section"):
        where.append(HOSP_BY[d["section"]]["name"])
    if d.get("cabinet"):
        where.append("Ambulatoriu – " + AMB_BY[d["cabinet"]]["name"].replace("Cabinet ", ""))
    sub = " · ".join(where) if show_spec else (d["grade"] or "")
    tags = " ".join(filter(None, ["spital" if d.get("section") else "", "ambulatoriu" if d.get("cabinet") else ""]))
    if d.get("photo"):
        return f'<a class="doctor" data-tags="{tags}" href="{R}{doc_url(d)}"><div class="doctor-photo"><img src="{R}{d["photo"]}" alt="{E(d["name"])}" loading="lazy"></div>{role}<h3>{E(d["name"])}</h3><span>{E(sub)}</span></a>'
    return f'<a class="doctor doctor-card" data-tags="{tags}" href="{R}{doc_url(d)}"><span class="avatar">{initials(d["name"])}</span>{role}<h3>{E(d["name"])}</h3><span>{E(sub)}</span></a>'


def unit_card(item, url, n):
    foot = f"{n} {'specialist' if n == 1 else 'specialiști'}" if n else (item.get("beds") or ("Informații în curs de actualizare" if item.get("pending") else ""))
    return f"""<a class="card" href="{R}{url}">
  <div class="card-icon">{icon(item['icon'])}</div><h3>{E(item['name'])}</h3><p>{E(item['summary'])}</p>
  <div class="card-foot"><span>{E(foot)}</span><span class="more">Detalii →</span></div></a>"""


def spec_card(h, anchor=""):
    return unit_card(h, hosp_url(h) + anchor, len(section_doctors(h["slug"])))


def cab_card(c):
    return unit_card(c, cab_url(c), len(cabinet_doctors(c["slug"])))


# ==== pages ===================================================================
def quick_links():
    items = [("Tipuri de prezentare", "tipuri-de-prezentare/", "clipboard"), ("Spital", "spital/", "hospital"),
             ("Ambulatoriu", "ambulatoriu/", "stethoscope"), ("Program de vizită", "reguli-si-program-de-vizita/", "clock"),
             ("Plata serviciilor", "servicii-medicale-cu-plata/", "money")]
    return '<div class="quick-links">' + "".join(f'<a href="{R}{u}">{icon(i)}<span>{t}</span></a>' for t, u, i in items) + "</div>"


def split_choice():
    """Two clearly separate entry points: the hospital and the outpatient clinic."""
    n_h = sum(1 for h in HOSP if h["category"] == "clinic")
    return f"""<div class="grid g2 split-choice">
  <a class="choice" href="{R}spital/"><span class="choice-icon">{icon('hospital')}</span><span><small>Internare și servicii spitalicești</small><strong>Spital</strong>
    <em>Secții și compartimente cu paturi, camera de gardă, laboratoare și servicii paraclinice.</em></span><span class="choice-go">{icon('arrow')}</span></a>
  <a class="choice" href="{R}ambulatoriu/"><span class="choice-icon">{icon('stethoscope')}</span><span><small>Consultații fără internare</small><strong>Ambulatoriu</strong>
    <em>Cabinete de specialitate, recoltare analize, radiologie și imagistică.</em></span><span class="choice-go">{icon('arrow')}</span></a>
</div>"""


def home():
    stats = "".join(stat(s) for s in CFG["stats"])
    book = booking_href(R)
    tgt = ' target="_blank" rel="noopener"' if ext(book) else ""
    featured = sorted([d for d in DOCS if d.get("role", "").startswith(("Șef", "Coordonator"))], key=lambda d: sort_key(d["name"]))[:8]
    vis = "".join(f'<li><strong>{E(a)}:</strong> {E(b)}{("<br>" + E(c)) if c else ""}</li>' for a, b, c in CFG.get("visiting", []))
    body = f"""
<section class="home-hero">
  <div class="container">
    <div>
      <span class="eyebrow" style="color:var(--accent)">{E(CFG['legal_name'])}</span>
      <h1>{E(CFG['hero_title'])}</h1>
      <p>{E(CFG['hero_subtitle'])}</p>
      <div class="hero-actions">
        <a class="btn btn-accent" href="{R}spital/">Spital</a>
        <a class="btn btn-accent" href="{R}ambulatoriu/">Ambulatoriu</a>
        <a class="btn btn-outline" style="color:#fff" href="{book}"{tgt}>Programări online</a>
      </div>
    </div>
    <div class="hero-contact">
      <h3>Contactează-ne</h3>
      <ul>
        <li>{icon('pin')}<span>{E(C['address'])}</span></li>
        <li>{icon('phone')}<span>Centrală: <a href="tel:{C['phone_href']}">{C['phone']}</a></span></li>
        {f'<li>{icon("calendar")}<span>Programări: <a href="tel:{C["phone_appointments_href"]}">{C["phone_appointments"]}</a></span></li>' if C.get("phone_appointments_href") else ""}
        <li>{icon('mail')}<a href="mailto:{C['email']}">{C['email']}</a></li>
        <li>{icon('ambulance')}<span>Camera de gardă: non-stop, 24/24 h</span></li>
      </ul>
      <a class="btn btn-white" href="{R}contact/">Contact {icon('arrow')}</a>
    </div>
  </div>
</section>
<div class="container">{quick_links()}</div>

<section class="section">
  <div class="container">
    <div class="section-head"><span class="eyebrow">Unde mergeți</span><h2>Spital sau ambulatoriu?</h2>
      <p>Internarea (continuă sau de zi) și camera de gardă țin de spital. Consultațiile fără internare se fac în cabinetele din ambulatoriu.</p></div>
    {split_choice()}
    <div class="center mt-40"><a class="btn btn-primary" href="{R}tipuri-de-prezentare/">Tipuri de prezentare: gardă, internare de zi, internare continuă, ambulatoriu</a></div>
  </div>
</section>

<section class="section bg-soft">
  <div class="container split">
    <div class="media">{f'<img src="{R}{CFG["hero_image"]}" alt="Sediul {E(NAME)}">' if CFG.get("hero_image") else icon("hospital")}<div class="media-badge"><strong>{CFG['founded']}</strong>anul înființării</div></div>
    <div>
      <span class="eyebrow">Despre noi</span>
      <h2 class="h2">Un spital cu tradiție, construit în jurul pacientului.</h2>
      <p class="muted">Înființat în 1963 ca policlinică a platformei industriale „23 August”, spitalul poartă din 1991 numele industriașului Nicolae Malaxa. Astăzi are 263 de paturi pentru spitalizare continuă și 10 pentru spitalizare de zi, secții clinice universitare, cabinete de specialitate în ambulatoriu și camera de gardă non-stop.</p>
      <div class="stats stats-light" style="grid-template-columns:repeat(2,1fr);text-align:left;margin:30px 0">
        {"".join(stat(s) for s in CFG["stats"][:4])}
      </div>
      <div class="hero-actions"><a class="btn btn-primary" href="{R}despre-noi/">Află mai multe</a>
      <a class="btn btn-outline" style="color:var(--primary)" href="tel:{C['phone_href']}">{icon('phone')} {C['phone']}</a></div>
    </div>
  </div>
</section>

<section class="section-sm bg-primary"><div class="container stats">{stats}</div></section>

<section class="section">
  <div class="container">
    <div class="section-head"><span class="eyebrow">Spital</span><h2>Secții și compartimente clinice</h2>
      <p>Spitalizare continuă și de zi, în secții și compartimente clinice universitare.</p></div>
    <div class="grid g4">{"".join(spec_card(h) for h in HOSP if h["category"] == "clinic")}</div>
    <div class="center mt-40"><a class="btn btn-primary" href="{R}spital/">Toate structurile spitalului</a> <a class="btn btn-outline" style="color:var(--primary)" href="{R}ambulatoriu/">Cabinetele din ambulatoriu</a></div>
  </div>
</section>

<section class="section"><div class="container"><div class="cta-band">
  <div><h2>Servicii decontate prin CASMB</h2><p>Consultații, analize și investigații decontate pentru asigurați, pe baza biletului de trimitere.</p></div>
  <div class="hero-actions" style="margin:0"><a class="btn btn-white" href="{R}servicii-decontate-prin-cas/">Mai multe detalii {icon('arrow')}</a>
  <a class="btn btn-white" href="{R}contracte-casmb-cnas/">Contracte CASMB / CNAS {icon('arrow')}</a></div>
</div></div></section>

<section class="section bg-soft">
  <div class="container split" style="align-items:start">
    <div>
      <span class="eyebrow">Programări</span><h2 class="h2">Ai nevoie de o consultație sau de o internare?</h2>
      <p class="muted">Programările se fac telefonic sau online. Internarea poate fi programată și de medicul curant, după consultul în ambulatoriu.</p>
      <div class="info-box"><span class="ring">{icon('phone')}</span><div><small>Centrală (apoi tasta secției)</small><strong>{C['phone']}</strong></div></div>
      {f'<div class="info-box"><span class="ring">{icon("calendar")}</span><div><small>Programări</small><strong>{C["phone_appointments"]}</strong></div></div>' if C.get("phone_appointments") else ""}
      <a class="btn btn-primary" href="{book}"{tgt}>Programează-te online {icon('arrow')}</a>
    </div>
    <div class="form-card">
      <h3>{icon('clock')} Program de vizită</h3>
      <ul class="visit-list">{vis}</ul>
      <a class="read-more" href="{R}reguli-si-program-de-vizita/">Reguli pentru vizitatori →</a>
    </div>
  </div>
</section>

<section class="section">
  <div class="container">
    <div class="section-head"><span class="eyebrow">De ce să ne alegi?</span><h2>Pentru că în centrul a tot ceea ce facem ești tu, pacientul nostru.</h2></div>
    <div class="grid g2">
      <div class="feature"><div class="card-icon">{icon('award')}</div><div><h3>Spital acreditat</h3><p>Acreditat ANMCS, certificat ISO 9001, laborator acreditat RENAR (ISO 15189).</p></div></div>
      <div class="feature"><div class="card-icon">{icon('people')}</div><div><h3>Clinici universitare</h3><p>Secții clinice în colaborare cu UMF „Carol Davila”, cu activitate de cercetare și studii clinice.</p></div></div>
      <div class="feature"><div class="card-icon">{icon('ambulance')}</div><div><h3>Gardă non-stop</h3><p>Linii de gardă 24/24 h pentru obstetrică-ginecologie, neonatologie, diabet, medicină internă, chirurgie generală, ATI și laborator.</p></div></div>
      <div class="feature"><div class="card-icon">{icon('cpu')}</div><div><h3>Aparatură modernă</h3><p>Computer tomograf multislice, mamograf digital, laparoscopie, facoemulsificare și bază de recuperare completă.</p></div></div>
    </div>
  </div>
</section>

<section class="section bg-soft">
  <div class="container">
    <div class="section-head"><span class="eyebrow">Profesionalism și dăruire</span><h2>Cunoaște-ne echipa</h2>
      <p>Medici cu experiență, care lucrează împreună pentru un singur lucru: binele tău.</p></div>
    <div class="grid g4">{"".join(doctor_card(d, show_spec=True) for d in featured)}</div>
    <div class="center mt-40"><a class="btn btn-primary" href="{R}team/">Toți medicii</a></div>
  </div>
</section>

<section class="section">
  <div class="container">
    <div class="section-head"><span class="eyebrow">Noutăți</span><h2>Noutăți și campanii</h2></div>
    <div class="grid g3">{"".join(post_card(n) for n in NEWS[:3])}</div>
    <div class="center mt-40"><a class="btn btn-primary" href="{R}noutati/">Vezi toate</a></div>
  </div>
</section>"""
    layout("", NAME, body, current="", section="Acasă")


def about():
    values = "".join(f'<div class="card"><div class="card-icon">{icon(i)}</div><h3>{E(v["title"])}</h3><p>{rich(v["text"])}</p></div>'
                     for v, i in zip(L["values"], ["hands", "award", "cpu", "check"]))
    h1, h2 = L["history"]
    body = page_hero("Scurt istoric", [("Despre noi", None)]) + f"""
<section class="section"><div class="container split">
  <div class="media"><img src="{R}uploads/images/nicolae-malaxa.jpg" alt="Nicolae Malaxa" style="object-fit:contain;background:#fff"></div>
  <div class="prose"><span class="eyebrow">Istoric</span><h2>Scurt istoric</h2><p>{E(h1)}</p></div>
</div></section>
<section class="section bg-soft"><div class="container split">
  <div class="prose"><p>{E(h2)}</p><a class="btn btn-primary" href="{R}structura-organizatorica/">Structura organizatorică</a></div>
  <div class="media"><img src="{R}uploads/images/locomotiva.jpg" alt="Locomotivă Malaxa"></div>
</div></section>
<section class="section" id="misiune"><div class="container">
  <div class="grid g2">
    <div class="card"><div class="card-icon">{icon('hands')}</div><h3>Misiune</h3><p>{rich(L['mission'])}</p></div>
    <div class="card"><div class="card-icon">{icon('star')}</div><h3>Viziune</h3><p>{rich(L['vision'])}</p></div>
  </div>
  <div class="section-head" style="margin-top:60px"><h2>Valori</h2></div><div class="grid g4">{values}</div>
</div></section>"""
    layout("despre-noi/", "Scurt istoric", body, current="despre-noi/")


def structure():
    o = L["organigram"]
    def table(head, rows, nums):
        th = "".join(f'<th{" style=text-align:right" if i in nums else ""}>{h}</th>' for i, h in enumerate(head))
        trs = "".join("<tr>" + "".join(f'<td{" class=price" if i in nums else ""}>{E(c)}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
        return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'
    content = f"""<p>Structura de mai jos este cea din organigrama aprobată de Administrația Spitalelor și Serviciilor Medicale București (ASSMB). „Posturi” reprezintă numărul de posturi aprobate (conducere + execuție).</p>
{docs_list([o['source']])}
<h2>Conducere</h2>{ul(o['leadership'])}
<h2>Secții și compartimente clinice</h2>{table(['Paturi', 'Secție / compartiment', 'Posturi'], o['clinic'], {0, 2})}
<p><strong>Total:</strong> {E(o['beds_total'])}.</p>
<h2>Laboratoare, explorări paraclinice și alte structuri medicale</h2>{table(['Structură', 'Posturi'], o['paraclinic'], {1})}
<h2>Ambulatoriu – cabinete de specialitate</h2>{table(['Cabinet', 'Posturi'], o['ambulatory'], {1})}
<h2>Structuri funcționale și administrative</h2>{table(['Structură', 'Posturi'], o['support'], {1})}
<p><strong>Total posturi:</strong> {E(o['posts_total'])}.</p>"""
    simple("structura-organizatorica/", "Structura organizatorică", content, ABOUT_CRUMB + [("Structura organizatorică", None)], current="despre-noi/")


def management():
    mg = "".join(f'<div class="card center-card"><div class="doctor-photo sm"><span class="initials">{initials(m["name"])}</span></div><h3>{E(m["name"])}</h3><p><strong>{E(m["role"])}</strong>{("<br>Audiențe: " + E(m["audiente"])) if m.get("audiente") else ""}</p></div>' for m in L["management"])
    board = "".join(f'<tr><td><strong>{E(b["rank"])}</strong></td><td>{E(b["name"])}</td><td>{E(b.get("represents", ""))}</td></tr>' for b in L["board"])
    ethics = "".join(f'<tr><td><strong>{E(b["rank"])}</strong></td><td>{E(b["name"])}{(" – " + E(b["represents"])) if b.get("represents") else ""}</td></tr>' for b in L["ethics"])
    cd = "".join(f'<tr><td><strong>{E(m["role"])}</strong></td><td>{E(m["name"])}</td></tr>' for m in L["management"])
    bd = L.get("board_doc")
    toc = "".join(f'<a class="btn btn-sm btn-outline" style="color:var(--primary)" href="#{a}">{t}</a> ' for a, t in [("conducerea", "Conducerea"), ("ca", "Consiliul de administrație"), ("cd", "Comitetul director"), ("ce", "Consiliul etic")])
    body = page_hero("Conducere", ABOUT_CRUMB + [("Conducere", None)]) + f"""
<section class="section-sm"><div class="container center">{toc}</div></section>
<section class="section" id="conducerea"><div class="container"><div class="section-head"><h2>Conducerea</h2><p>Audiențele se programează prin secretariat.</p></div><div class="grid g3">{mg}</div></div></section>
<section class="section bg-soft" id="ca"><div class="container prose"><h2>Consiliul de administrație (CA)</h2>
<div class="table-wrap"><table><thead><tr><th>Calitate</th><th>Nume</th><th>Reprezentant al</th></tr></thead><tbody>{board}</tbody></table></div>{docs_list([bd]) if bd else ""}</div></section>
<section class="section" id="cd"><div class="container prose"><h2>Comitetul director (CD)</h2>
<div class="table-wrap"><table><thead><tr><th>Funcție</th><th>Nume</th></tr></thead><tbody>{cd}</tbody></table></div></div></section>
<section class="section bg-soft" id="ce"><div class="container prose"><h2>Consiliul etic (CE)</h2>
<div class="table-wrap"><table><thead><tr><th>Calitate</th><th>Nume</th></tr></thead><tbody>{ethics}</tbody></table></div>
{docs_list([["Anuarul consiliului etic – 2020", "uploads/docs/files/Anuarul Etic-2020.pdf"], ["Raportul consiliului etic – Sem. 2 2020", "uploads/docs/files/Raport Consiliul Etic-s2.2020.pdf"]])}
{f'<p>Sesizări privind integritatea: <a href="mailto:{C["email_integrity"]}">{C["email_integrity"]}</a></p>' if C.get("email_integrity") else ""}</div></section>"""
    layout("conducere/", "Conducere", body, current="despre-noi/")


def centers():
    cs = [("Centrul de Diabet, Nutriție și Boli Metabolice", "Secție clinică cu 45 de paturi, spitalizare de zi și cabinete de ambulatoriu cu program zilnic; derulează Programul Național de Sănătate – Diabet.", "service/diabet/", "drop"),
          ("Clinica universitară de Alergologie și Imunologie", "Clinică universitară a UMF „Carol Davila”, cu laborator de imunologie clinică și testare alergologică in vivo și in vitro.", "service/alergologie/", "flask"),
          ("Laboratorul de analize medicale acreditat RENAR", "Acreditat conform ISO 15189:2013 pentru hematologie, chimie clinică, imunologie și parazitologie.", "service/laborator/", "microscope"),
          ("Secția Clinică Obstetrică-Ginecologie", "50 de paturi, 2 săli de naștere, laparoscopie STORZ și nucleu de cercetare cu studii clinice în desfășurare.", "service/obstetrica-ginecologie/", "female")]
    items = "".join(f'<a class="card" href="{R}{u}"><div class="card-icon">{icon(i)}</div><h3>{E(t)}</h3><p>{E(d)}</p><span class="read-more">Detalii →</span></a>' for t, d, u, i in cs)
    body = page_hero("Centre de excelență", [("Spital", "spital/"), ("Centre de excelență", None)]) + f'<section class="section"><div class="container"><div class="grid g2">{items}</div></div></section>'
    layout("centre-de-excelenta/", "Centre de excelență", body, current="spital/")


def specialties_page():
    groups = "".join(f'<h2 class="h2" style="margin-top:50px">{label}</h2><div class="grid g4">{"".join(spec_card(h) for h in HOSP if h["category"] == cat)}</div>' for cat, label in CATEGORIES)
    body = page_hero("Spital", [("Spital", None)]) + f"""
<section class="section bg-soft"><div class="container">
  <div class="section-head"><h2>Structurile spitalului</h2><p>Internarea continuă și de zi, camera de gardă, laboratoarele și serviciile paraclinice. Pentru consultații fără internare, vedeți <a href="{R}ambulatoriu/"><u>cabinetele din ambulatoriu</u></a>.</p></div>
  {groups}
  <div class="center mt-40"><a class="btn btn-primary" href="{R}tipuri-de-prezentare/">Tipuri de prezentare</a> <a class="btn btn-outline" style="color:var(--primary)" href="{R}centre-de-excelenta/">Centre de excelență</a> <a class="btn btn-outline" style="color:var(--primary)" href="{R}ambulatoriu/">Ambulatoriu</a></div>
</div></section>"""
    layout("spital/", "Spital", body, current="spital/")


def ambulatoriu():
    body = page_hero("Ambulatoriu", [("Ambulatoriu", None)]) + f"""
<section class="section"><div class="container">
  <div class="section-head"><h2>Servicii medicale în ambulatoriu</h2><p>Consultații de specialitate fără internare. Pentru internare și camera de gardă, vedeți <a href="{R}spital/"><u>structurile spitalului</u></a>.</p></div>
  <div class="grid g2" style="max-width:860px;margin:0 auto 30px">
    <div class="info-box" style="margin:0"><span class="ring">{icon('phone')}</span><div><small>Programări – centrală</small><strong>{C['phone']}</strong></div></div>
    <a class="info-box" style="margin:0" href="{booking_href(R)}" target="_blank" rel="noopener"><span class="ring">{icon('calendar')}</span><div><small>Programări online</small><strong>programari.axamedis.ro</strong></div></a>
  </div>
  <div class="center" style="margin-bottom:40px"><a class="btn btn-primary" href="{R}tipuri-de-prezentare/#ambulatoriu">Cum vă prezentați: documente, condiții, excepții</a></div>
  <div class="grid g4">{"".join(cab_card(c) for c in AMB)}</div>
</div></section>"""
    layout("ambulatoriu/", "Ambulatoriu", body, current="ambulatoriu/")


AMB_DOCS = ["Bilet de trimitere de la medicul de familie sau de la un medic specialist aflat în contract cu casa de asigurări", "Cardul de sănătate",
            "Dovada calității de asigurat", "Act de identitate (CI / BI / pașaport), original și copie"]
HOSP_DOCS = ["Bilet de internare de la medicul de familie sau bilet de trimitere de la medicul din ambulatoriu / scrisoare medicală",
             "Cardul de sănătate", "Dovada calității de asigurat", "Act de identitate (CI / BI / pașaport / certificat de naștere), original și copie"]


def unit_page(item, kind):
    """One template for hospital structures and outpatient cabinets, with the same order of information:
    descriere → echipa medicală → servicii → dotări → program → programări și contact → documente necesare → tarife → galerie → legături."""
    is_h = kind == "hosp"
    items = HOSP if is_h else AMB
    url_of = hosp_url if is_h else cab_url
    team = section_doctors(item["slug"]) if is_h else cabinet_doctors(item["slug"])
    parts = []
    # 1. Descriere
    if item.get("beds"):
        parts.append(f'<p class="pill">{icon("hospital")} {E(item["beds"])}</p>')
    parts.append(f'<h2>Descriere</h2>{lines_html(item.get("intro") or [item["summary"]])}')
    # 2. Echipa medicală
    if team:
        parts.append(f'<h2>Echipa medicală</h2><div class="grid g3 team-grid">{"".join(doctor_card(d) for d in team)}</div>')
    # 3. Servicii medicale (and other content sections)
    for sec in item.get("sections", []):
        h = f"<h3>{E(sec['title'])}</h3>" if sec.get("title") else ""
        if sec.get("accordion"):
            parts.append(h + accordion([(x["q"], ul(x["a"])) for x in sec["accordion"]], open_first=False))
        else:
            parts.append(h + paras(sec.get("text", [])) + (ul(sec["items"], "list-check" + (" cols" if len(sec["items"]) > 8 else "")) if sec.get("items") else ""))
    # 4. Dotări
    if item.get("equipment"):
        parts.append(f'<h2>Dotări</h2>{ul(item["equipment"], "list-check cols" if len(item["equipment"]) > 5 else "list-check")}')
    # 5. Program
    if item.get("hours"):
        parts.append("<h2>Program</h2>" + updated() + "".join(f'<div class="info-box"><span class="ring">{icon("clock")}</span><div><strong>{E(x)}</strong></div></div>' for x in item["hours"]))
    if item.get("schedule"):
        parts.append('<h3>Program medici</h3><div class="table-wrap"><table><thead><tr><th>Medic</th><th>Program</th></tr></thead><tbody>'
                     + "".join(f"<tr><td><strong>{E(m)}</strong></td><td>{E(p)}</td></tr>" for m, p in item["schedule"]) + "</tbody></table></div>")
    # 6. Programări și contact
    if item.get("phone"):
        parts.append(f'<h2>Programări și contact</h2>{ul(item["phone"], "list-plain")}')
    # 7. Documente necesare (patient-facing structures)
    if is_h and item["category"] == "clinic" and item["slug"] != "camera-de-garda":
        parts.append(f'<h2>Documente necesare la internare</h2>{ul(HOSP_DOCS)}<p><a class="read-more" href="{R}tipuri-de-prezentare/">Tipuri de prezentare: condiții și excepții →</a></p>')
    elif not is_h:
        parts.append(f'<h2>Documente necesare</h2>{ul(AMB_DOCS)}<p><a class="read-more" href="{R}tipuri-de-prezentare/#ambulatoriu">Condiții și excepții →</a></p>')
    # 8. Tarife
    pg = next((p for p in L["prices"] if p["group"] == item.get("price_group")), None)
    if pg:
        rows = "".join(f'<tr><td>{E(x)}</td><td class="price">{E(y)}</td></tr>' for x, y in pg["items"])
        parts.append(f'<h2>Tarife</h2><p class="muted">Pentru pacienții neasigurați, fără bilet de trimitere sau fără programare. <a href="{R}servicii-medicale-cu-plata/"><u>Plata serviciilor medicale</u></a></p><details class="price-toggle"><summary>Vezi tarifele ({len(pg["items"])} servicii)</summary><div class="table-wrap"><table><thead><tr><th>Serviciu</th><th style="text-align:right">Tarif</th></tr></thead><tbody>{rows}</tbody></table></div></details>')
    # 9. Galerie foto
    if item.get("gallery"):
        parts.append(f"<h2>Galerie foto</h2>{gallery(item['gallery'])}")
    # 10. Legături: the matching cabinet / section
    links = []
    if is_h and item.get("cabinet") in AMB_BY:
        c = AMB_BY[item["cabinet"]]
        links.append((f"Ambulatoriu: {c['name']}", cab_url(c)))
    if not is_h and item.get("structure") in HOSP_BY:
        h = HOSP_BY[item["structure"]]
        links.append((f"Spital: {h['name']}", hosp_url(h)))
    links += [(t, u) for t, u in item.get("links", [])]
    if links:
        parts.append('<h2>Vezi și</h2><div class="doc-list">' + "".join(a_doc(t, u) for t, u in links) + "</div>")

    if is_h:
        side = "".join(f'<li class="label">{label}</li>' + "".join(f'<li><a class="{"active" if x["slug"] == item["slug"] else ""}" href="{R}{url_of(x)}">{E(x["name"])}</a></li>' for x in items if x["category"] == cat) for cat, label in CATEGORIES)
        crumbs = [("Spital", "spital/"), (item["name"], None)]
        side_title = "Spital"
    else:
        side = "".join(f'<li><a class="{"active" if x["slug"] == item["slug"] else ""}" href="{R}{url_of(x)}">{E(x["name"])}</a></li>' for x in items)
        crumbs = [("Ambulatoriu", "ambulatoriu/"), (item["name"], None)]
        side_title = "Ambulatoriu"
    body = page_hero(item["name"], crumbs) + f"""
<section class="section"><div class="container with-sidebar">
  <aside class="sidebar"><nav class="side-menu" aria-label="{side_title}"><h3>{side_title}</h3><ul>{side}</ul></nav>{contact_box(None, None)}</aside>
  <div class="prose">{"".join(parts)}</div>
</div></section>"""
    layout(url_of(item), item["name"], body, desc=item["summary"], current=("spital/" if is_h else "ambulatoriu/"), section="Spital" if is_h else "Ambulatoriu")


def specialty(s):
    unit_page(s, "hosp")


def cabinet(c):
    unit_page(c, "amb")


def team_page():
    filters = '<button class="active" data-filter="all">Toți ({})</button><button data-filter="spital">Spital ({})</button><button data-filter="ambulatoriu">Ambulatoriu ({})</button>'.format(
        len(DOCS), sum(1 for d in DOCS if d.get("section")), sum(1 for d in DOCS if d.get("cabinet")))
    body = page_hero("Medici", [("Medici", None)]) + f"""
<section class="section"><div class="container">
  <div class="section-head"><p>Medicii sunt prezentați în ordinea alfabetică a numelui, urmat de prenume. Sub fiecare nume sunt trecute secția din spital și/sau cabinetul din ambulatoriu.</p></div>
  <div class="filters" id="teamFilters">{filters}</div>
  <div class="grid g4" id="teamGrid">{"".join(doctor_card(d, show_spec=True) for d in DOCS)}</div>
</div></section>"""
    layout("team/", "Medici", body, current="team/")


def doctor_page(d):
    s = HOSP_BY.get(d.get("section"))
    c = AMB_BY.get(d.get("cabinet"))
    photo = f'<img src="{R}{d["photo"]}" alt="{E(d["name"])}">' if d.get("photo") else f'<span class="initials">{initials(d["name"])}</span>'
    bio = f"<p>{E(d['bio'])}</p>" if d.get("bio") else ""
    amb = None
    if c:
        last = d["name"].split()[1] if len(d["name"].split()) > 1 else ""
        amb = next((p for m, p in c.get("schedule", []) if last and last in m), None)
    where = []
    if s:
        where.append(f'<a class="btn btn-primary" href="{R}{hosp_url(s)}">Spital: {E(s["name"])} {icon("arrow")}</a>')
    if c:
        where.append(f'<a class="btn btn-outline" style="color:var(--primary)" href="{R}{cab_url(c)}">Ambulatoriu: {E(c["name"])} {icon("arrow")}</a>')
    amb_html = f'<div class="info-box"><span class="ring">{icon("clock")}</span><div><small>Program în ambulatoriu</small><strong>{E(amb)}</strong></div></div>' if amb else ""
    role = f'<p class="pill">{E(d["role"])}</p>' if d.get("role") else ""
    grade = f'<p class="grade">{E(d["grade"])}</p>' if d.get("grade") else ""
    primary = s or c
    body = f"""<section class="section"><div class="container profile">
  <div><div class="doctor-photo">{photo}</div><div class="profile-spec">{E(primary['name'])}</div>{contact_box(primary.get("phone"))}</div>
  <div class="prose"><h1>{E(d['name'])}</h1>{role}{grade}{bio}{amb_html}
  <p class="hero-actions">{"".join(where)}</p></div>
</div></section>"""
    layout(doc_url(d), d["name"], body, desc=f"{d['name']} – {d['grade']}", current="team/", section="Medici")


def presentation_page():
    T = L["presentation"]
    nav = "".join(f'<a class="card center-card" href="#{t["id"]}"><div class="card-icon">{icon(t["icon"])}</div><h3>{E(t["title"])}</h3></a>' for t in T)
    secs = ""
    for i, t in enumerate(T):
        fields = "".join(f'<div class="pres-row"><h3>{E(k)}</h3><div>{lines_html(v)}</div></div>' for k, v in t["fields"])
        secs += f'<section class="section{" bg-soft" if i % 2 else ""}" id="{t["id"]}"><div class="container prose"><h2>{icon(t["icon"])} {E(t["title"])}</h2><div class="pres">{fields}</div></div></section>'
    body = page_hero("Tipuri de prezentare", INFO_CRUMB + [("Tipuri de prezentare", None)]) + f"""
<section class="section-sm"><div class="container"><div class="section-head"><p>Alegeți modul în care vă prezentați la spital. Pentru fiecare găsiți specificațiile, timpul alocat, modalitățile, condițiile, documentele necesare și excepțiile.</p></div>
<div class="grid g4">{nav}</div></div></section>{secs}"""
    layout("tipuri-de-prezentare/", "Tipuri de prezentare", body, current="informatii-utile/")


def paid_page():
    P = L["payment"]
    items = [(f'{p["group"]} ({len(p["items"])})', '<div class="table-wrap"><table><thead><tr><th>Serviciu</th><th style="text-align:right">Tarif</th></tr></thead><tbody>' +
              "".join(f'<tr><td>{E(a)}</td><td class="price">{E(b)}</td></tr>' for a, b in p["items"]) + "</tbody></table></div>") for p in L["prices"]]
    content = f"""<h2>Plata serviciilor medicale</h2>
<p>Pacienții asigurați beneficiază de serviciile decontate de CASMB, pe baza biletului de trimitere (<a href="{R}servicii-decontate-prin-cas/"><u>servicii decontate prin CASMB</u></a>). Serviciile se plătesc în următoarele situații:</p>
{lines_html(P['when'])}
<h3>Tarife aprobate</h3><p>{E(P['decision'])}</p>
<h3>Alte situații în care se plătește</h3>{lines_html(P['other'])}
<h3>Cum se plătește</h3>{lines_html(["– " + x for x in P['how']])}
<div class="info-box"><span class="ring">{icon('phone')}</span><div><small>Informații și programări</small><strong>{C['phone']}</strong></div></div>
<h2>Lista serviciilor medicale cu plată și tarifele</h2>
<div class="filter-input"><input type="search" id="priceFilter" placeholder="Caută un serviciu (ex.: hemoleucogramă, CT, ecografie)…" aria-label="Caută în tarife"></div>
<div id="priceAccordion">{accordion(items, open_first=False)}</div>{updated()}"""
    simple("servicii-medicale-cu-plata/", "Plata serviciilor medicale", content, INFO_CRUMB + [("Plata serviciilor medicale", None)], current="informatii-utile/")


def contracts_page():
    K = L["contracts"]
    rows = "".join(f'<tr><td><strong style="font-size:20px">{E(t)}</strong></td><td>{rich(d)}</td></tr>' for t, d in K["types"])
    prog = next((p["docs"] for p in L["public_interest"] if p["title"] == "Programe naționale"), [])
    content = f"""<h2>Contracte cu CASMB și CNAS</h2><p>{E(K['intro'])}</p>
<div class="table-wrap"><table><thead><tr><th>Tip</th><th>Descriere</th></tr></thead><tbody>{rows}</tbody></table></div>
<h3>Documente</h3>{docs_list(prog) if prog else ""}
<p><a class="btn btn-primary" href="https://www.casmb.ro/asigurati_servicii.php" target="_blank" rel="noopener">CASMB – servicii pentru asigurați {icon('external')}</a></p>{updated()}"""
    simple("contracte-casmb-cnas/", "Contracte cu CASMB și CNAS", content, INFO_CRUMB + [("Contracte CASMB / CNAS", None)], current="informatii-utile/")


def info_hub():
    def tiles(items):
        return '<div class="grid g3">' + "".join(f'<a class="card" href="{R}{u}"><div class="card-icon">{icon(i)}</div><h3>{t}</h3><span class="read-more">Află mai multe →</span></a>' for t, u, i in items) + "</div>"
    pac = [("Tipuri de prezentare", "tipuri-de-prezentare/", "clipboard"), ("Servicii decontate prin CASMB", "servicii-decontate-prin-cas/", "check"),
           ("Contracte cu CASMB și CNAS", "contracte-casmb-cnas/", "contract"), ("Plata serviciilor medicale", "servicii-medicale-cu-plata/", "money"),
           ("Drepturile și obligațiile pacienților", "drepturile-pacientilor/", "shield"), ("Program gărzi spital", "program-garzi/", "ambulance"),
           ("Campanii de sănătate", "educatie-pentru-sanatate/", "award"), ("Chestionar de feedback", "chestionar-de-feedback/", "chat"),
           ("Întrebări frecvente", "intrebari-frecvente/", "clipboard")]
    viz = [("Program de vizită", "reguli-si-program-de-vizita/", "clock"), ("Chestionar de feedback", "chestionar-de-feedback/", "chat")]
    pub = [("Informații de interes public", "interes-public/", "document"), ("Anunțuri și achiziții", "anunturi/", "cart"), ("Declarație privind accesibilitatea", "declaratie-privind-accesibilitatea/", "a11y")]
    body = page_hero("Informații utile", [("Informații utile", None)]) + f"""
<section class="section"><div class="container"><h2 class="h2">Pentru pacienți</h2>{tiles(pac)}</div></section>
<section class="section bg-soft"><div class="container"><h2 class="h2">Pentru vizitatori și aparținători</h2>{tiles(viz)}</div></section>
<section class="section"><div class="container"><h2 class="h2">Interes public</h2>{tiles(pub)}</div></section>"""
    layout("informatii-utile/", "Informații utile", body, current="informatii-utile/")


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")
    if (ROOT / "uploads").exists():
        shutil.copytree(ROOT / "uploads", OUT / "uploads")
    col = CFG["colors"]
    (OUT / "favicon.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="{col["primary"]}"/><path d="M16 8v16M8 16h16" stroke="{col["highlight"]}" stroke-width="5" stroke-linecap="round"/></svg>', encoding="utf-8")

    home(); about(); structure(); management(); accreditations(); indicators(); research(); partners(); centers()
    specialties_page(); ambulatoriu(); team_page()
    for h in HOSP: specialty(h)
    for c in AMB: cabinet(c)
    for d in DOCS: doctor_page(d)
    news_list()
    for n in NEWS: post_page(n)
    careers(); announcements(); garzi_page(); info_hub(); visitors_hub(); presentation_page(); contracts_page(); cas_page(); paid_page(); rights_page()
    visit_rules(); feedback_page(); health_education(); faq_page(); public_interest(); contact(); accessibility(); privacy()
    search_page(); not_found()
    # Old addresses keep working
    for old, new in [("specialitati-medicale/", "spital/"), ("internare-si-externare/", "tipuri-de-prezentare/"), ("echipa-de-management/", "conducere/"),
                     ("service/psihologie/", "ambulatoriu/psihologie/"), ("service/stomatologie/", "ambulatoriu/stomatologie/"), ("service/orl/", "ambulatoriu/orl/")]:
        redirect(old, new)

    (OUT / "search-index.json").write_text(json.dumps(SEARCH_INDEX, ensure_ascii=False), encoding="utf-8")
    base = CFG["base_url"].rstrip("/")
    urls = "".join(f"<url><loc>{base}/{p['url']}</loc></url>" for p in SEARCH_INDEX if not p["url"].startswith(("404", "cautare")))
    (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    print(f"Built {len(SEARCH_INDEX)} pages into {OUT}")


if __name__ == "__main__":
    build()
