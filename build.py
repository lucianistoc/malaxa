#!/usr/bin/env python3
"""White-label hospital website generator.

Reads site.config.json (brand) and content/*.json (data) and writes a complete
static website to ./public. No dependencies beyond the Python 3 standard library.

    python3 build.py              # build into ./public
    python3 -m http.server -d public 8000   # preview at http://localhost:8000
"""
import json
import re
import shutil
import unicodedata
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "public"
CFG = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
SPECS = json.loads((ROOT / "content/specialties.json").read_text(encoding="utf-8"))
DOCS = json.loads((ROOT / "content/doctors.json").read_text(encoding="utf-8"))
NEWS = sorted(json.loads((ROOT / "content/news.json").read_text(encoding="utf-8")), key=lambda n: n["date"], reverse=True)
L = json.loads((ROOT / "content/lists.json").read_text(encoding="utf-8"))
SPEC_BY = {s["slug"]: s for s in SPECS}
C = CFG["contact"]
NAME = CFG["name"]
E = escape
MONTHS = ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august",
          "septembrie", "octombrie", "noiembrie", "decembrie"]
SEARCH_INDEX = []


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
    "building": '<rect x="4" y="2" width="16" height="20" rx="1"/><path d="M9 22v-4h6v4M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/>',
}


def icon(name, cls="icon"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_P.get(name, _P["hospital"])}</svg>')


# ---------------------------------------------------------------- navigation
def spec_url(s): return f"service/{s['slug']}/"
def doc_url(d): return f"team/{d['slug']}/"
def post_url(n): return f"{n['date'][:4]}/{n['date'][5:7]}/{n['date'][8:10]}/{n['slug']}/"


NAV = [
    ("Despre noi", "despre-noi/", [
        ("Despre noi", "despre-noi/"), ("Echipa de management", "echipa-de-management/"),
        ("Indicatori de calitate", "indicatori-de-calitate/"), ("Grijă și siguranță", "grija-si-siguranta/"),
        ("Confidențialitate", "confidentialitate/"), ("Noutăți și apariții media", "noutati/"),
        ("Cercetare și inovare", "cercetare-si-inovare/"), ("Cariere", "cariere/")]),
    ("Specialități medicale", "specialitati-medicale/", "SPECS"),
    ("Ambulatoriu", "ambulatoriu/", None),
    ("Medici", "team/", None),
    ("Informații utile", "informatii-utile/", [
        ("§Pentru pacienți", None), ("Servicii decontate prin CAS", "servicii-decontate-prin-cas/"),
        ("Servicii medicale cu plată", "servicii-medicale-cu-plata/"), ("Drepturile pacienților", "drepturile-pacientilor/"),
        ("Educație pentru sănătate", "educatie-pentru-sanatate/"), ("Chestionar de feedback", "chestionar-de-feedback/"),
        ("Întrebări frecvente", "intrebari-frecvente/"),
        ("§Pentru vizitatori și aparținători", None), ("Reguli și program de vizită", "reguli-si-program-de-vizita/"),
        ("Chestionar de feedback", "chestionar-de-feedback-vizitatori/"),
        ("§Interes public", None), ("Informații de interes public", "interes-public/")]),
    ("Centre de excelență", "centre-de-excelenta/", None),
    ("Contact", "contact/", None),
]


def logo(r):
    if CFG.get("logo_image"):
        return f'<a class="logo" href="{r}" aria-label="{E(NAME)} – acasă"><img src="{r}{CFG["logo_image"]}" alt="{E(NAME)}"></a>'
    return (f'<a class="logo" href="{r}" aria-label="{E(NAME)} – acasă"><span class="logo-word">{E(CFG["logo_text"])}<span>+</span></span>'
            f'<span class="logo-sub">{E(CFG["logo_subtext"])}</span></a>')


def nav_html(r, current):
    out = []
    for label, url, sub in NAV:
        active = " active" if current and current.startswith(url.split("/")[0]) else ""
        if sub is None:
            out.append(f'<li class="{active.strip()}"><a href="{r}{url}">{label}</a></li>')
            continue
        if sub == "SPECS":
            items = "".join(f'<li><a href="{r}{spec_url(s)}">{E(s["name"])}</a></li>' for s in SPECS)
            ul = f'<ul class="submenu cols">{items}</ul>'
        else:
            items = "".join(f'<li class="label">{t[1:]}</li>' if t.startswith("§") else f'<li><a href="{r}{u}">{t}</a></li>' for t, u in sub)
            ul = f'<ul class="submenu">{items}</ul>'
        out.append(f'<li class="has-sub{active}"><a href="{r}{url}">{label} {icon("caret", "caret")}</a>{ul}</li>')
    return "<ul>" + "".join(out) + "</ul>"


def mobile_nav(r):
    out = []
    for label, url, sub in NAV:
        if sub is None:
            out.append(f'<li><a href="{r}{url}">{label}</a></li>')
            continue
        pairs = [(s["name"], spec_url(s)) for s in SPECS] if sub == "SPECS" else [(t, u) for t, u in sub if u]
        items = f'<li><a href="{r}{url}">Vezi tot – {label}</a></li>' + "".join(f'<li><a href="{r}{u}">{E(t)}</a></li>' for t, u in pairs)
        out.append(f'<li><details><summary>{label}</summary><ul>{items}</ul></details></li>')
    return '<nav class="mobile-nav" aria-label="Meniu mobil"><ul>' + "".join(out) + "</ul></nav>"


def socials():
    return "".join(f'<a href="{E(u)}" aria-label="{k.title()}" rel="noopener" target="_blank">{icon(k)}</a>'
                   for k, u in CFG["social"].items() if u)


# ---------------------------------------------------------------- layout
PATTERN = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='104' viewBox='0 0 120 104'%3E"
           "%3Cg fill='none' stroke='%23ffffff' stroke-opacity='.05' stroke-width='2'%3E%3Cpath d='M30 2l28 16v32L30 66 2 50V18z'/%3E"
           "%3Cpath d='M90 38l28 16v32L90 102 62 86V54z'/%3E%3Cpath d='M30 26v16M22 34h16M90 62v16M82 70h16'/%3E%3C/g%3E%3C/svg%3E\")")


def layout(path, title, body, desc=None, current=None, section="Pagini"):
    depth = path.count("/") if path else 0
    r = "../" * depth
    col = CFG["colors"]
    desc = desc or f"{NAME} – {CFG['tagline']}."
    hero_img = f'--hero-image: url("{r}{CFG["hero_image"]}");' if CFG.get("hero_image") else ""
    full_title = f"{title} – {NAME}" if title != NAME else NAME
    text = re.sub(r"<[^>]+>", " ", body)
    SEARCH_INDEX.append({"url": path, "title": title, "section": section,
                         "text": unicodedata.normalize("NFD", (title + " " + text).lower()).encode("ascii", "ignore").decode()[:4000]})
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
<link rel="canonical" href="{CFG['base_url'].rstrip('/')}/{path}">
<link rel="icon" href="{r}favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{r}static/css/style.css">
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
      <a class="btn btn-primary" href="{r}contact/#programari">Programări</a>
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
<aside class="offcanvas" id="offcanvas" aria-hidden="true" aria-label="Meniu lateral">
  <button class="icon-btn close" id="ocClose" aria-label="Închide">{icon('close')}</button>
  {logo(r)}
  {mobile_nav(r)}
  <h4>{E(CFG['legal_name'])}</h4>
  <p class="muted">{E(CFG['tagline'])}. {E(CFG['hero_subtitle'])}</p>
  <h4>Contactează-ne</h4>
  <ul>
    <li>{icon('pin')}<span>{E(C['address'])}</span></li>
    <li>{icon('mail')}<a href="mailto:{C['email']}">{C['email']}</a></li>
    <li>{icon('phone')}<a href="tel:{C['phone_href']}">{C['phone']}</a></li>
  </ul>
  <h4>Newsletter</h4>
  <form class="newsletter" data-form data-success="Te-ai abonat!"><input type="email" name="email" required placeholder="Adresa de email" aria-label="Email"><button class="btn btn-accent" type="submit">{icon('arrow')}</button><span class="form-msg"></span></form>
  <h4>Urmărește-ne</h4>
  <div class="socials">{socials()}</div>
</aside>

<main id="main">
{body}
</main>

<footer class="footer">
  <div class="container footer-top">
    {logo(r)}
    <span class="badge">{icon('award')} {E(CFG['accreditation_badge'])}</span>
    <div class="socials">{socials()}</div>
  </div>
  <div class="container footer-grid">
    <div>
      <h4>{E(CFG['legal_name'])}</h4>
      <ul>
        <li><a href="{r}despre-noi/">Despre noi</a></li>
        <li><a href="{r}specialitati-medicale/">Specialități medicale</a></li>
        <li><a href="{r}team/">Medici</a></li>
        <li><a href="{r}cariere/">Cariere</a></li>
        <li><a href="{r}contact/">Contact</a></li>
      </ul>
    </div>
    <div>
      <h4>Informații utile</h4>
      <ul>
        <li><a href="{r}servicii-decontate-prin-cas/">Servicii decontate prin CAS</a></li>
        <li><a href="{r}servicii-medicale-cu-plata/">Servicii medicale cu plată</a></li>
        <li><a href="{r}pentru-vizitatori-si-apartinatori/">Pentru vizitatori și aparținători</a></li>
        <li><a href="{r}interes-public/">Interes public</a></li>
        <li><a href="{r}intrebari-frecvente/">Întrebări frecvente</a></li>
        <li><a href="{r}declaratie-privind-accesibilitatea/">Declarație privind accesibilitatea</a></li>
      </ul>
    </div>
    <div>
      <h4>Contactează-ne</h4>
      <ul>
        <li class="contact-line">{icon('pin')}<span>{E(C['address'])}</span></li>
        <li class="contact-line">{icon('mail')}<a href="mailto:{C['email']}">{C['email']}</a></li>
        <li class="contact-line">{icon('clock')}<span>{E(C['program'])}</span></li>
      </ul>
    </div>
    <div>
      <h4>Fii la curent cu noutăți despre spitalul nostru</h4>
      <p>Abonează-te la newsletter:</p>
      <form class="newsletter" data-form data-success="Te-ai abonat!"><input type="email" name="email" required placeholder="Adresa de email" aria-label="Email"><button class="btn btn-accent" type="submit">Trimite</button><span class="form-msg"></span></form>
    </div>
  </div>
  <div class="container footer-cta">
    <div><small>Sună-ne ({C['phone_hours']})</small><br><a class="big" href="tel:{C['phone_href']}">{C['phone']}</a></div>
    <a class="btn btn-white" href="{r}contact/#programari">Programează-te online {icon('arrow')}</a>
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
<script src="{r}static/js/main.js"></script>
</body>
</html>
"""
    dest = OUT / path / "index.html" if path else OUT / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html.replace("{{ROOT}}", r), encoding="utf-8")


def page_hero(title, crumbs=()):
    bc = '<a href="{{ROOT}}">Acasă</a>' + "".join(f' / <a href="{{{{ROOT}}}}{u}">{E(t)}</a>' if u else f" / {E(t)}" for t, u in crumbs)
    return f"""<section class="page-hero">
  <span class="hero-side">{E(CFG['legal_name'])}</span>
  <div class="hero-social socials">{socials()}</div>
  <div class="container"><h1>{E(title)}</h1><div class="breadcrumbs">{bc}</div></div>
  <a class="hero-phone" href="tel:{C['phone_href']}"><span class="ring">{icon('phone')}</span>{C['phone']}</a>
</section>"""


def contact_box():
    return f"""<div class="contact-box">
  <div class="card-icon">{icon('chat')}</div>
  <h3>Contactează-ne</h3>
  <a class="phone" href="tel:{C['phone_href']}">{C['phone']}</a>
  <a class="mail" href="mailto:{C['email']}">{C['email']}</a>
  <a class="btn btn-white" href="{{{{ROOT}}}}contact/#programari">Programări {icon('arrow')}</a>
</div>"""


def accordion(items, open_first=True):
    return '<div class="accordion">' + "".join(
        f'<details{" open" if open_first and i == 0 else ""}><summary>{E(q)}</summary><div class="acc-body">{a}</div></details>'
        for i, (q, a) in enumerate(items)) + "</div>"


def faq_block(title="Întrebări frecvente"):
    return f'<h2 class="h2">{title}</h2>' + accordion([(f["q"], f"<p>{E(f['a'])}</p>") for f in L["faq"]])


def doctor_card(d):
    photo = f'<img src="{{{{ROOT}}}}{d["photo"]}" alt="{E(d["name"])}" loading="lazy">' if d.get("photo") else icon("user")
    return f'<a class="doctor" href="{{{{ROOT}}}}{doc_url(d)}"><div class="doctor-photo">{photo}</div><h3>{E(d["name"])}</h3><span>{E(d["grade"])}</span></a>'


def spec_card(s):
    n = len([d for d in DOCS if d["specialty"] == s["slug"]])
    return f"""<a class="card" href="{{{{ROOT}}}}{spec_url(s)}">
  <div class="card-icon">{icon(s['icon'])}</div><h3>{E(s['name'])}</h3><p>{E(s['summary'])}</p>
  <div class="card-foot"><span>{n} {"Medic" if n == 1 else "Medici"}</span><span class="more">Detalii →</span></div></a>"""


def post_card(n):
    thumb = f'<img src="{{{{ROOT}}}}{n["image"]}" alt="" loading="lazy">' if n.get("image") else icon("hospital")
    return f"""<article class="post-card"><a class="post-thumb" href="{{{{ROOT}}}}{post_url(n)}" tabindex="-1">{thumb}</a>
  <div class="post-body"><div class="post-meta"><b>{E(n['category'])}</b><time datetime="{n['date']}">{fdate(n['date'])}</time></div>
  <h3><a href="{{{{ROOT}}}}{post_url(n)}">{E(n['title'])}</a></h3><p>{E(n['excerpt'])}</p>
  <a class="read-more" href="{{{{ROOT}}}}{post_url(n)}">Citește mai mult →</a></div></article>"""


def simple(path, title, content, crumbs=None, sidebar=True, desc=None, section="Pagini"):
    side = f'<aside class="sidebar">{contact_box()}</aside>' if sidebar else ""
    inner = f'<div class="with-sidebar right"><div class="prose">{content}</div>{side}</div>' if sidebar else content
    layout(path, title, page_hero(title, crumbs or [(title, None)]) + f'<section class="section"><div class="container">{inner}</div></section>',
           desc=desc, current=path, section=section)


TODO = '<p class="placeholder">[Conținut de completat de către spital.]</p>'
ABOUT_CRUMB = [("Despre noi", "despre-noi/")]
INFO_CRUMB = [("Informații utile", "informatii-utile/")]


# ---------------------------------------------------------------- pages
def home():
    stats = "".join(stat(s) for s in CFG["stats"])
    body = f"""
<section class="home-hero">
  <div class="container">
    <div>
      <span class="eyebrow" style="color:var(--accent)">{E(CFG['legal_name'])}</span>
      <h1>{E(CFG['hero_title'])}</h1>
      <p>{E(CFG['hero_subtitle'])}</p>
      <div class="hero-actions">
        <a class="btn btn-accent" href="{{{{ROOT}}}}contact/#programari">Programări</a>
        <a class="btn btn-outline" style="color:#fff" href="{{{{ROOT}}}}specialitati-medicale/">Specialități medicale</a>
      </div>
    </div>
    <div class="hero-contact">
      <h3>Contactează-ne</h3>
      <ul>
        <li>{icon('pin')}<span>{E(C['address'])}</span></li>
        <li>{icon('mail')}<a href="mailto:{C['email']}">{C['email']}</a></li>
        <li>{icon('phone')}<a href="tel:{C['phone_href']}">{C['phone']}</a></li>
        <li>{icon('clock')}<span>{E(C['program'])}</span></li>
      </ul>
      <a class="btn btn-white" href="{{{{ROOT}}}}contact/">Contact {icon('arrow')}</a>
    </div>
  </div>
</section>

<section class="section">
  <div class="container split">
    <div class="media">{icon('hospital')}<div class="media-badge"><strong>{CFG['years']}+</strong>ani de activitate</div></div>
    <div>
      <span class="eyebrow">Despre noi</span>
      <h2 class="h2">Un loc cu istorie, dar mai ales cu inimă.</h2>
      <p class="muted">Fiecare pas pe care îl facem pornește de la convingerea că sănătatea ta merită toată atenția noastră. De la prima consultație până la externare, echipa {E(NAME)} este alături de tine.</p>
      <div class="stats stats-light" style="grid-template-columns:repeat(2,1fr);text-align:left;margin:30px 0">
        {"".join(stat(s) for s in CFG["stats"][:4])}
      </div>
      <div class="hero-actions"><a class="btn btn-primary" href="{{{{ROOT}}}}despre-noi/">Află mai multe</a>
      <a class="btn btn-outline" style="color:var(--primary)" href="tel:{C['phone_href']}">{icon('phone')} {C['phone']}</a></div>
    </div>
  </div>
</section>

<section class="section-sm bg-primary"><div class="container stats">{stats}</div></section>

<section class="section bg-soft">
  <div class="container">
    <div class="section-head"><span class="eyebrow">Specialități medicale</span><h2>Sănătatea ta merită ce e mai bun</h2>
      <p>Secții cu paturi, ambulatoriu de specialitate și servicii paraclinice care lucrează împreună.</p></div>
    <div class="grid g4">{"".join(spec_card(s) for s in SPECS[:8])}</div>
    <div class="center mt-40"><a class="btn btn-primary" href="{{{{ROOT}}}}specialitati-medicale/">Vezi toate specialitățile medicale</a></div>
  </div>
</section>

<section class="section"><div class="container"><div class="cta-band">
  <div><h2>Analize gratuite</h2><p>Află ce investigații sunt decontate prin Casa de Asigurări de Sănătate și ce documente îți trebuie.</p></div>
  <a class="btn btn-white" href="{{{{ROOT}}}}servicii-decontate-prin-cas/">Mai multe detalii {icon('arrow')}</a>
</div></div></section>

<section class="section bg-soft">
  <div class="container split">
    <div>
      <span class="eyebrow">Contact</span><h2 class="h2">Ai nevoie de informații?</h2>
      <p class="muted">Dacă ai întrebări sau sugestii, ne poți scrie folosind formularul alăturat.</p>
      <div class="info-box"><span class="ring">{icon('phone')}</span><div><small>Telefon informații</small><strong>{C['phone']}</strong></div></div>
      <div class="info-box"><span class="ring">{icon('mail')}</span><div><small>Email</small><strong>{C['email']}</strong></div></div>
    </div>
    {contact_form()}
  </div>
</section>

<section class="section">
  <div class="container">
    <div class="section-head"><span class="eyebrow">De ce să ne alegi?</span><h2>Pentru că în centrul a tot ceea ce facem ești tu, pacientul nostru.</h2></div>
    <div class="grid g2">
      <div class="feature"><div class="card-icon">{icon('hospital')}</div><div><h3>Tradiție</h3><p>Decenii de experiență medicală în slujba comunității.</p></div></div>
      <div class="feature"><div class="card-icon">{icon('hands')}</div><div><h3>Grijă reală</h3><p>Aici nu doar tratăm: ascultăm, explicăm și găsim soluții împreună.</p></div></div>
      <div class="feature"><div class="card-icon">{icon('people')}</div><div><h3>Echipă excelentă</h3><p>Medici dedicați, empatici și bine pregătiți în toate domeniile.</p></div></div>
      <div class="feature"><div class="card-icon">{icon('cpu')}</div><div><h3>Tehnologie medicală</h3><p>Aparatură modernă, pentru servicii la standarde înalte.</p></div></div>
    </div>
  </div>
</section>

<section class="section bg-soft">
  <div class="container">
    <div class="section-head"><span class="eyebrow">Profesionalism și dăruire</span><h2>Cunoaște-ne echipa</h2>
      <p>Medici cu experiență, care lucrează împreună pentru un singur lucru: binele tău.</p></div>
    <div class="grid g4">{"".join(doctor_card(d) for d in DOCS[:8])}</div>
    <div class="center mt-40"><a class="btn btn-primary" href="{{{{ROOT}}}}team/">Toți medicii</a></div>
  </div>
</section>

<section class="section">
  <div class="container">
    <div class="section-head"><span class="eyebrow">Părerea pacienților</span><h2>Povești reale despre încredere și grijă</h2>
      <p class="placeholder">Secțiune demonstrativă – publicați doar recenzii reale, cu acordul pacienților.</p></div>
    <div class="grid g3">{"".join(f'<div class="quote"><div class="stars">★★★★★</div><p>„[Textul recenziei – de completat.]”</p><strong>[Nume pacient]</strong></div>' for _ in range(3))}</div>
  </div>
</section>

<section class="section bg-soft">
  <div class="container">
    <div class="section-head"><span class="eyebrow">Noutăți</span><h2>Noutăți și apariții media</h2></div>
    <div class="grid g3">{"".join(post_card(n) for n in NEWS[:3])}</div>
    <div class="center mt-40"><a class="btn btn-primary" href="{{{{ROOT}}}}noutati/">Vezi toate articolele</a></div>
  </div>
</section>"""
    layout("", NAME, body, current="", section="Acasă")


def contact_form(title="Contactează-ne"):
    return f"""<form class="form-card" data-form data-success="Mulțumim! Mesajul a fost trimis.">
  <h3>{title}</h3>
  <p class="notice"><strong>ATENȚIE!</strong> Programările nu se fac prin intermediul acestui formular!</p>
  <div class="form-grid">
    <div><label for="cf-nume">Nume</label><input id="cf-nume" name="nume" required></div>
    <div><label for="cf-prenume">Prenume</label><input id="cf-prenume" name="prenume" required></div>
    <div><label for="cf-email">Email</label><input id="cf-email" type="email" name="email" required></div>
    <div><label for="cf-tel">Telefon</label><input id="cf-tel" type="tel" name="telefon"></div>
    <div class="full"><label for="cf-msg">Mesaj</label><textarea id="cf-msg" name="mesaj" required></textarea></div>
    <div class="full"><label class="check"><input type="checkbox" required> Sunt de acord cu prelucrarea datelor personale conform <a href="{{{{ROOT}}}}confidentialitate/"><u>politicii de confidențialitate</u></a>.</label></div>
    <div class="full"><button class="btn btn-primary" type="submit">Trimite</button><span class="form-msg" role="status"></span></div>
  </div>
</form>"""


def about():
    tabs = f"""<div data-tabs>
  <div class="tabs-nav" role="tablist">
    <button role="tab" aria-selected="true" aria-controls="t-misiune" id="b-misiune">Misiunea noastră</button>
    <button role="tab" aria-selected="false" aria-controls="t-viziune" id="b-viziune">Viziunea noastră</button>
  </div>
  <div class="tab-panel" id="t-misiune" role="tabpanel"><h2>Misiunea noastră</h2><p>Să oferim servicii medicale sigure, accesibile și de calitate, cu respect pentru demnitatea fiecărui pacient.</p>{TODO}</div>
  <div class="tab-panel" id="t-viziune" role="tabpanel" hidden><h2>Viziunea noastră</h2><p>Să fim un spital de referință pentru comunitate, recunoscut pentru profesionalism, inovație și umanitate.</p>{TODO}</div>
</div>"""
    values = "".join(f'<div class="card"><div class="card-icon">{icon(i)}</div><h3>{E(v["title"])}</h3><p>{E(v["text"])}</p></div>'
                     for v, i in zip(L["values"], ["hands", "award", "cpu", "check"]))
    body = page_hero("Despre noi", [("Despre noi", None)]) + f"""
<section class="section"><div class="container split">
  <div class="media">{icon('hospital')}<div class="media-badge"><strong>{CFG['founded']}</strong>anul înființării</div></div>
  <div><span class="eyebrow">Istoric</span><h2 class="h2">{E(NAME)}.<br>Un loc cu istorie, dar mai ales cu inimă.</h2>
    <p class="muted">[Istoricul spitalului – de completat: anul înființării, momente importante, evoluția secțiilor și a infrastructurii.]</p>
    <div class="stats stats-light" style="grid-template-columns:repeat(3,1fr);text-align:left;margin-top:30px">
      {"".join(stat(s) for s in CFG["stats"][:3])}
    </div></div>
</div></section>
<section class="section bg-soft"><div class="container prose">{tabs}</div></section>
<section class="section"><div class="container"><div class="section-head"><h2>Valorile noastre</h2></div><div class="grid g4">{values}</div></div></section>"""
    layout("despre-noi/", "Despre noi", body, current="despre-noi/")


def management():
    mg = "".join(f'<div class="doctor"><div class="doctor-photo">{icon("user")}</div><h3>{E(m["name"])}</h3><span>{E(m["role"])}</span></div>' for m in L["management"])
    board = "".join(f'<div class="card"><h4>{E(b["group"])}</h4><ul class="list-check">{"".join(f"<li>{E(x)}</li>" for x in b["members"])}</ul></div>' for b in L["board"])
    body = page_hero("Echipa de management", ABOUT_CRUMB + [("Echipa de management", None)]) + f"""
<section class="section"><div class="container"><div class="section-head"><h2>Echipa de management</h2></div><div class="grid g3">{mg}</div></div></section>
<section class="section bg-soft"><div class="container"><div class="section-head"><h2>Membrii Consiliului de Administrație</h2></div><div class="grid g3">{board}</div>
<div class="center mt-40"><a class="btn btn-primary" href="#">{icon('download')} Componența Consiliului de Administrație (PDF)</a></div></div></section>"""
    layout("echipa-de-management/", "Echipa de management", body, current="despre-noi/")


def specialties_page():
    body = page_hero("Specialități medicale", [("Specialități medicale", None)]) + \
        f'<section class="section bg-soft"><div class="container"><div class="grid g4">{"".join(spec_card(s) for s in SPECS)}</div></div></section>'
    layout("specialitati-medicale/", "Specialități medicale", body, current="specialitati-medicale/")


def ambulatoriu():
    amb = [s for s in SPECS if s["ambulatoriu"]]
    body = page_hero("Ambulatoriu", [("Ambulatoriu", None)]) + f"""
<section class="section"><div class="container">
  <div class="section-head"><h2>Ambulatoriul de specialitate</h2><p>Consultații de specialitate fără internare. Pentru serviciile decontate este necesar biletul de trimitere.</p></div>
  <div class="info-box" style="max-width:640px;margin:0 auto 50px"><span class="ring">{icon('phone')}</span><div><small>Programări ambulatoriu</small><strong>{C['phone_appointments']}</strong></div></div>
  <div class="grid g4">{"".join(spec_card(s) for s in amb)}</div>
</div></section>"""
    layout("ambulatoriu/", "Ambulatoriu", body, current="ambulatoriu/")


def specialty(s):
    team = [d for d in DOCS if d["specialty"] == s["slug"]]
    side_items = "".join(f'<li><a class="{"active" if x["slug"] == s["slug"] else ""}" href="{{{{ROOT}}}}{spec_url(x)}">{E(x["name"])}</a></li>' for x in SPECS)
    days = ["Luni", "Marți", "Miercuri", "Joi", "Vineri"]
    rows = "".join(f'<tr><td><strong>{d}</strong></td><td>08:00 – 14:00</td><td>{E(team[i % len(team)]["name"]) if team else "[Medic]"}</td></tr>' for i, d in enumerate(days))
    ph = '<li class="placeholder">[De completat]</li>'
    prices = next((p for p in L["prices"] if p["group"] == "Consultații"), None)
    price_rows = "".join(f'<tr><td>{E(a)}</td><td class="price">{E(b)}</td></tr>' for a, b in prices["items"]) if prices else ""
    team_html = f'<h2>Echipa medicală</h2><div class="grid g3">{"".join(doctor_card(d) for d in team)}</div>' if team else ""
    content = f"""{team_html}
<p style="margin-top:40px">{E(s['summary'])}</p>
<p class="placeholder">[Descrierea detaliată a secției {E(s['name'])} – de completat: istoric, activitate, număr de paturi, colaborări.]</p>
<div class="info-box"><span class="ring">{icon('phone')}</span><div><small>Telefon programări (zilnic, 08:00 – 11:00)</small><strong>{C['phone_appointments']}</strong></div></div>
<h3>Program consultații</h3>
<div class="table-wrap"><table><thead><tr><th>Ziua</th><th>Ora</th><th>Medic</th></tr></thead><tbody>{rows}</tbody></table></div>
<h3>Afecțiuni tratate</h3><ul class="list-check cols">{ph * 6}</ul>
<h3>Servicii medicale</h3><ul class="list-check">{ph * 4}</ul>
<h3>Servicii medicale cu plată</h3>
<div class="table-wrap"><table><thead><tr><th>Serviciu</th><th style="text-align:right">Tarif</th></tr></thead><tbody>{price_rows}</tbody></table></div>
<h3>Dotări</h3><ul class="list-check">{ph * 3}</ul>
<div style="margin-top:50px">{faq_block()}</div>"""
    body = page_hero(s["name"], [("Specialități medicale", "specialitati-medicale/"), (s["name"], None)]) + f"""
<section class="section"><div class="container with-sidebar">
  <aside class="sidebar"><nav class="side-menu" aria-label="Specialități medicale"><h3>Specialități medicale</h3><ul>{side_items}</ul></nav>{contact_box()}</aside>
  <div class="prose">{content}</div>
</div></section>"""
    layout(spec_url(s), s["name"], body, desc=s["summary"], current="specialitati-medicale/", section="Specialități medicale")


def team_page():
    groups = [(s, [d for d in DOCS if d["specialty"] == s["slug"]]) for s in SPECS]
    groups = [(s, ds) for s, ds in groups if ds]
    filters = '<button class="active" data-filter="all">Toți</button>' + "".join(f'<button data-filter="{s["slug"]}">{E(s["name"])}</button>' for s, _ in groups)
    blocks = "".join(f'<div class="team-group" data-group="{s["slug"]}"><h2>{E(s["name"])}</h2><div class="grid g4">{"".join(doctor_card(d) for d in ds)}</div></div>' for s, ds in groups)
    body = page_hero("Medici", [("Medici", None)]) + f'<section class="section"><div class="container"><div class="filters" id="teamFilters">{filters}</div>{blocks}</div></section>'
    layout("team/", "Medici", body, current="team/")


def doctor_page(d):
    s = SPEC_BY.get(d["specialty"], {"name": "", "slug": ""})
    photo = f'<img src="{{{{ROOT}}}}{d["photo"]}" alt="{E(d["name"])}">' if d.get("photo") else icon("user")
    bio = f"<p>{E(d['bio'])}</p>" if d.get("bio") else TODO
    body = f"""<section class="section"><div class="container profile">
  <div><div class="doctor-photo">{photo}</div><div class="profile-spec"><a href="{{{{ROOT}}}}{spec_url(s) if s['slug'] else ''}">{E(s['name'])}</a></div>{contact_box()}</div>
  <div class="prose"><h1>{E(d['name'])}</h1><p class="grade">{E(d['grade'])}</p>{bio}</div>
</div></section>"""
    layout(doc_url(d), d["name"], body, desc=f"{d['name']} – {d['grade']}, {s['name']}", current="team/", section="Medici")


def news_list():
    recent = "".join(f'<li><a href="{{{{ROOT}}}}{post_url(n)}">{E(n["title"])}</a><time>{fdate(n["date"])}</time></li>' for n in NEWS[:6])
    body = page_hero("Noutăți și apariții media", ABOUT_CRUMB + [("Noutăți", None)]) + f"""
<section class="section"><div class="container with-sidebar right">
  <div class="grid g2">{"".join(post_card(n) for n in NEWS)}</div>
  <aside class="sidebar">
    <div class="widget"><h3>Caută</h3><form class="search-form" style="padding:0" action="{{{{ROOT}}}}cautare/"><input type="search" name="q" aria-label="Caută"><button class="btn btn-primary btn-sm" type="submit">{icon('search')}</button></form></div>
    <div class="widget"><h3>Articole recente</h3><ul>{recent}</ul></div>
  </aside>
</div></section>"""
    layout("noutati/", "Noutăți și apariții media", body, current="despre-noi/")


def post_page(n):
    related = [x for x in NEWS if x is not n][:2]
    recent = "".join(f'<li><a href="{{{{ROOT}}}}{post_url(x)}">{E(x["title"])}</a><time>{fdate(x["date"])}</time></li>' for x in NEWS[:6])
    paras = "".join(f"<p>{E(p)}</p>" for p in n["body"])
    body = page_hero(n["title"], [("Noutăți", "noutati/"), (n["category"], None)]) + f"""
<section class="section"><div class="container with-sidebar right">
  <article class="prose">
    <div class="post-meta"><b>{E(n['category'])}</b><time datetime="{n['date']}">{fdate(n['date'])}</time></div>
    {paras}
    <h3 style="margin-top:50px">Articole asemănătoare</h3><div class="grid g2">{"".join(post_card(x) for x in related)}</div>
  </article>
  <aside class="sidebar">
    <div class="widget"><h3>Caută</h3><form class="search-form" style="padding:0" action="{{{{ROOT}}}}cautare/"><input type="search" name="q" aria-label="Caută"><button class="btn btn-primary btn-sm" type="submit">{icon('search')}</button></form></div>
    <div class="widget"><h3>Articole recente</h3><ul>{recent}</ul></div>
  </aside>
</div></section>"""
    layout(post_url(n), n["title"], body, desc=n["excerpt"], current="despre-noi/", section="Noutăți")


def careers():
    rows = "".join(f'<tr><td>{E(c["title"])}</td><td>{fdate(c["date"])}</td><td>{E(c["status"])}</td><td><a href="#" class="read-more">{icon("download")} PDF</a></td></tr>' for c in L["contests"])
    content = f"""<h2>Alătură-te echipei noastre!</h2>
<p>Căutăm oameni care își doresc să facă medicină cu suflet. Posturile vacante sunt scoase la concurs conform legislației în vigoare, iar anunțurile sunt publicate pe această pagină.</p>
{TODO}
<h2>Află rezultatele concursurilor</h2>
<div class="table-wrap"><table><thead><tr><th>Concurs</th><th>Data</th><th>Etapa</th><th>Document</th></tr></thead><tbody>{rows}</tbody></table></div>"""
    simple("cariere/", "Cariere", content, ABOUT_CRUMB + [("Cariere", None)])


def info_hub():
    def tiles(items):
        return '<div class="grid g3">' + "".join(f'<a class="card" href="{{{{ROOT}}}}{u}"><div class="card-icon">{icon(i)}</div><h3>{t}</h3><span class="read-more">Află mai multe →</span></a>' for t, u, i in items) + "</div>"
    pac = [("Servicii decontate prin CAS", "servicii-decontate-prin-cas/", "check"), ("Servicii medicale cu plată", "servicii-medicale-cu-plata/", "money"),
           ("Drepturile pacienților", "drepturile-pacientilor/", "shield"), ("Educație pentru sănătate", "educatie-pentru-sanatate/", "award"),
           ("Chestionar de feedback", "chestionar-de-feedback/", "chat"), ("Întrebări frecvente", "intrebari-frecvente/", "clipboard")]
    viz = [("Reguli și program de vizită", "reguli-si-program-de-vizita/", "clock"), ("Chestionar de feedback", "chestionar-de-feedback-vizitatori/", "chat")]
    body = page_hero("Informații utile", INFO_CRUMB[:0] + [("Informații utile", None)]) + f"""
<section class="section"><div class="container"><h2 class="h2">Pentru pacienți</h2>{tiles(pac)}</div></section>
<section class="section bg-soft"><div class="container"><h2 class="h2">Pentru vizitatori și aparținători</h2>{tiles(viz)}</div></section>
<section class="section"><div class="container"><h2 class="h2">Interes public</h2>{tiles([("Informații de interes public", "interes-public/", "document"), ("Declarație privind accesibilitatea", "declaratie-privind-accesibilitatea/", "a11y")])}</div></section>"""
    layout("informatii-utile/", "Informații utile", body, current="informatii-utile/")


def visitors_hub():
    body = page_hero("Pentru vizitatori și aparținători", INFO_CRUMB + [("Pentru vizitatori și aparținători", None)]) + f"""
<section class="section"><div class="container"><div class="grid g2">
  <a class="card" href="{{{{ROOT}}}}reguli-si-program-de-vizita/"><div class="card-icon">{icon('clock')}</div><h3>Reguli și program de vizită</h3><p>Programul de vizită, numărul de vizitatori permis și regulile de acces în saloane.</p><span class="read-more">Află mai multe →</span></a>
  <a class="card" href="{{{{ROOT}}}}chestionar-de-feedback-vizitatori/"><div class="card-icon">{icon('chat')}</div><h3>Chestionar de feedback</h3><p>Spune-ne cum ți s-a părut experiența ca aparținător sau vizitator.</p><span class="read-more">Completează →</span></a>
</div></div></section>"""
    layout("pentru-vizitatori-si-apartinatori/", "Pentru vizitatori și aparținători", body, current="informatii-utile/")


def cas_page():
    feats = [("Medici cu experiență vastă", "people"), ("Tehnologie medicală modernă", "cpu"), ("Abordare centrată pe pacient", "hands"), ("Servicii medicale la standarde înalte", "award")]
    cats = [("Ambulatoriu", "stethoscope"), ("Laborator analize medicale", "flask"), ("Radiologie", "xray"), ("Anatomie Patologică", "microscope")]
    body = page_hero("Servicii decontate prin CAS", INFO_CRUMB + [("Servicii decontate prin CAS", None)]) + f"""
<section class="section"><div class="container split">
  <div><span class="eyebrow">Fără costuri pentru asigurați</span><h2 class="h2">Servicii medicale gratuite, decontate prin CAS</h2>
  <p class="muted">Ca pacient asigurat, ai acces gratuit la consultații, analize și investigații decontate de Casa de Asigurări de Sănătate, în limita fondurilor contractate.</p>
  <a class="btn btn-primary" href="tel:{C['phone_href']}">{icon('phone')} Programări: {C['phone']}</a></div>
  <div class="media">{icon('check')}</div>
</div></section>
<section class="section bg-soft"><div class="container"><div class="section-head"><h2>Ce beneficii gratuite ai la {E(NAME)}?</h2></div>
  <div class="grid g4">{"".join(f'<div class="card"><div class="card-icon">{icon(i)}</div><h3>{t}</h3></div>' for t, i in feats)}</div></div></section>
<section class="section"><div class="container prose"><h2>De ce documente ai nevoie pentru a beneficia de acces gratuit la serviciile medicale?</h2>
  <ul class="list-check"><li>Bilet de trimitere de la medicul de familie sau de la un medic specialist aflat în contract cu CAS</li><li>Act de identitate valabil</li><li>Card național de sănătate sau adeverință de asigurat</li></ul>
  <h3>Află care sunt toate serviciile medicale decontate prin CAS.</h3>
  <div class="grid g4" style="margin-top:20px">{"".join(f'<a class="card" href="#"><div class="card-icon">{icon(i)}</div><h4>{t}</h4><span class="read-more">{icon("download")} Lista serviciilor</span></a>' for t, i in cats)}</div>
</div></section>"""
    layout("servicii-decontate-prin-cas/", "Servicii decontate prin CAS", body, current="informatii-utile/")


def paid_page():
    items = [(p["group"], '<div class="table-wrap"><table><thead><tr><th>Serviciu</th><th style="text-align:right">Tarif</th></tr></thead><tbody>' +
              "".join(f'<tr><td>{E(a)}</td><td class="price">{E(b)}</td></tr>' for a, b in p["items"]) + "</tbody></table></div>") for p in L["prices"]]
    content = f"""<h2>Servicii medicale cu plată {date.today().year}</h2>
<p class="placeholder">Tarifele de mai jos sunt exemple – înlocuiți-le cu lista aprobată de spital.</p>
<div class="info-box"><span class="ring">{icon('phone')}</span><div><small>Toate analizele cu plată se efectuează cu programare la telefon</small><strong>{C['phone_appointments']}</strong></div></div>
{accordion(items)}"""
    simple("servicii-medicale-cu-plata/", "Servicii medicale cu plată", content, INFO_CRUMB + [("Servicii medicale cu plată", None)])


def rights_page():
    rights = ["Dreptul la îngrijiri medicale de cea mai înaltă calitate de care dispune societatea, conform resurselor disponibile.",
              "Dreptul de a fi respectat ca persoană umană, fără nicio discriminare.",
              "Dreptul la informare cu privire la serviciile medicale disponibile, identitatea și statutul profesional al personalului.",
              "Dreptul de a fi informat asupra stării de sănătate, a intervențiilor propuse, a riscurilor și alternativelor.",
              "Dreptul de a refuza sau de a opri o intervenție medicală, asumându-și responsabilitatea în scris.",
              "Dreptul la confidențialitatea informațiilor și la viața privată.",
              "Dreptul de a solicita o a doua opinie medicală.",
              "Dreptul de a primi, la externare, un rezumat scris al investigațiilor, diagnosticului și tratamentului.",
              "Dreptul la sprijinul familiei și al prietenilor și la suport spiritual pe durata spitalizării."]
    duties = ["Să respecte regulamentul intern al spitalului.", "Să păstreze curățenia și să respecte liniștea celorlalți pacienți.",
              "Să nu părăsească secția fără acordul medicului curant.", "Să nu fumeze în incinta spitalului.",
              "Să respecte personalul medical și ceilalți pacienți.", "Să furnizeze informații corecte despre starea de sănătate și tratamentele urmate."]
    content = f"""<h2>Informații privind drepturile și obligațiile pacienților</h2>
<p>Drepturile pacienților sunt reglementate de Legea nr. 46/2003 privind drepturile pacientului și de normele de aplicare ale acesteia. Mai jos găsiți un rezumat; textul complet al legii prevalează.</p>
<h2>Drepturile pacienților</h2><ul class="list-check">{"".join(f"<li>{E(x)}</li>" for x in rights)}</ul>
<h2>Obligațiile pacienților internați</h2><ul class="list-check">{"".join(f"<li>{E(x)}</li>" for x in duties)}</ul>"""
    simple("drepturile-pacientilor/", "Drepturile pacienților", content, INFO_CRUMB + [("Drepturile pacienților", None)])


def visit_rules():
    content = f"""<h2>Regulament vizită</h2>
<p>Pentru siguranța pacienților, accesul vizitatorilor se face doar în intervalele de mai jos, cu respectarea regulilor de igienă.</p>
<div class="table-wrap"><table><thead><tr><th>Zile</th><th>Interval</th></tr></thead><tbody>
<tr><td>Luni – Vineri</td><td>15:00 – 20:00</td></tr><tr><td>Sâmbătă, Duminică, sărbători legale</td><td>10:00 – 20:00</td></tr></tbody></table></div>
<h2>În secția ATI</h2><p>Vizita este permisă doar cu acordul medicului de gardă, zilnic între 13:00 – 14:00, cu echipament de protecție.</p>
<h2>Accesul vizitatorilor în saloane</h2>
<div class="grid g3"><div class="card"><div class="card-icon">{icon('user')}</div><h3>1 vizitator/pacient</h3><p>în saloanele cu mai mult de 2 paturi</p></div>
<div class="card"><div class="card-icon">{icon('clock')}</div><h3>Max. 30 de minute</h3><p>durata recomandată a unei vizite</p></div>
<div class="card"><div class="card-icon">{icon('shield')}</div><h3>Echipament de protecție</h3><p>halat și botoșei, la cererea personalului</p></div></div>
<h2>Nu este permis accesul vizitatorilor:</h2><ul class="list-check"><li>cu semne de boală infecto-contagioasă (febră, tuse, erupții)</li><li>sub influența alcoolului sau a substanțelor interzise</li><li>în perioadele de carantină declarate</li><li>copiilor sub 14 ani, cu excepția situațiilor aprobate de medicul curant</li></ul>
<h2>Vizitatorii au următoarele obligații:</h2><ul class="list-check"><li>să respecte indicațiile personalului medical</li><li>să nu introducă alimente interzise de regimul pacientului</li><li>să păstreze liniștea și curățenia</li><li>să părăsească salonul în timpul vizitei medicale și al procedurilor</li></ul>"""
    simple("reguli-si-program-de-vizita/", "Reguli și program de vizită", content, INFO_CRUMB + [("Pentru vizitatori", "pentru-vizitatori-si-apartinatori/"), ("Reguli și program de vizită", None)])


def feedback(path, title, intro, thanks, questions, crumbs):
    qs = "".join(f"""<div class="q-block"><p>{i}. {E(q)}</p><div class="rating" role="radiogroup" aria-label="{E(q)}">{"".join(f'<label><input type="radio" name="q{i}" value="{v}" {"required" if v == 1 else ""}><span>{v}</span></label>' for v in range(1, 6))}</div></div>"""
                 for i, q in enumerate(questions, 1))
    body = page_hero(title, crumbs) + f"""
<section class="section bg-soft"><div class="container" style="max-width:860px">
  <div class="section-head"><h2>{E(intro)}</h2><p>Evaluează de la 1 (deloc mulțumit) la 5 (foarte mulțumit). Chestionarul este anonim.</p></div>
  <form class="form-card" data-form data-success="{E(thanks)}">
    <div class="form-grid"><div><label for="fb-sec">Secția</label><select id="fb-sec" name="sectia"><option value="">Alege secția</option>{"".join(f"<option>{E(s['name'])}</option>" for s in SPECS)}</select></div>
    <div><label for="fb-date">Perioada</label><input id="fb-date" type="month" name="perioada"></div></div>
    {qs}
    <div style="margin-top:20px"><label for="fb-obs">Observații și sugestii</label><textarea id="fb-obs" name="observatii"></textarea></div>
    <div style="margin-top:20px"><button class="btn btn-primary" type="submit">Trimite chestionarul</button><span class="form-msg" role="status"></span></div>
  </form>
</div></section>"""
    layout(path, title, body, current="informatii-utile/")


def faq_page():
    simple("intrebari-frecvente/", "Întrebări frecvente", faq_block("Răspunsuri la cele mai frecvente întrebări"), INFO_CRUMB + [("Întrebări frecvente", None)])


def public_interest():
    tiles = "".join(f'<div class="card tile"><div class="card-icon">{icon(p["icon"])}</div><h3>{E(p["title"])}</h3><a class="btn btn-primary btn-sm" href="#">Află mai multe</a></div>' for p in L["public_interest"])
    body = page_hero("Interes public", INFO_CRUMB + [("Interes public", None)]) + f"""
<section class="section tiles-bg"><div class="container"><div class="grid g4">{tiles}</div></div></section>
<section class="section"><div class="container">
  <h2 class="h2">Solicitare informații de interes public</h2>
  <p>Persoana responsabilă de primirea solicitărilor în baza Legii nr. 544/2001 este <strong>{E(C['public_info_officer'])}</strong>.</p>
  <div class="req-grid" style="margin:24px 0 30px">
    <div class="req">{icon('mail')}<div><strong>Email</strong>{C['email']}<br>{C['email_public_info']}</div></div>
    <div class="req">{icon('phone')}<div><strong>Telefon</strong>{C['phone']}</div></div>
    <a class="req" href="#">{icon('document')}<div><strong>Formular reclamație</strong>Descarcă fișierul</div></a>
    <a class="req" href="#">{icon('document')}<div><strong>Formular solicitare</strong>Informații interes public<br>Descarcă fișierul</div></a>
  </div>
  <p>După completare, formularele pot fi transmise prin:</p>
  <div class="req-grid" style="grid-template-columns:repeat(3,1fr)">
    <div class="req">{icon('mail')}<div><strong>Email</strong>{C['email']}</div></div>
    <div class="req">{icon('phone')}<div><strong>Telefon</strong>{C['phone']}</div></div>
    <div class="req">{icon('building')}<div><strong>Depus la Registratura Spitalului</strong>{E(C['address_short'])}</div></div>
  </div>
</div></section>"""
    layout("interes-public/", "Interes public", body, current="informatii-utile/")


def contact():
    t = CFG["transport"]
    body = page_hero("Contact", [("Contact", None)]) + f"""
<section class="section"><div class="container">
  <div class="section-head"><h2>{E(CFG['legal_name'])}</h2></div>
  <div class="grid g4 contact-cards">
    <div class="card"><div class="card-icon">{icon('phone')}</div><h3>Telefon informații</h3><p><a href="tel:{C['phone_href']}">{C['phone']}</a></p></div>
    <div class="card"><div class="card-icon">{icon('mail')}</div><h3>Email</h3><p><a href="mailto:{C['email']}">{C['email']}</a></p></div>
    <div class="card"><div class="card-icon">{icon('clock')}</div><h3>Program</h3><p>{E(C['program'])}</p></div>
    <div class="card"><div class="card-icon">{icon('people')}</div><h3>Program de audiențe management</h3><p>{E(C['audiente'])}</p></div>
  </div>
</div></section>
<section class="section bg-soft" id="programari"><div class="container split" style="align-items:start">
  <div>
    <span class="eyebrow">Programări</span><h2 class="h2">Programează-te telefonic</h2>
    <div class="info-box"><span class="ring">{icon('phone')}</span><div><small>Programări ambulatoriu</small><strong>{C['phone_appointments']}</strong></div></div>
    <div class="info-box"><span class="ring">{icon('pin')}</span><div><small>Adresă</small><strong>{E(C['address'])}</strong></div></div>
    <h3 style="margin-top:30px">Accesul pacienților în spital</h3><p class="muted">[Intrări, acces persoane cu dizabilități, parcare – de completat.]</p>
  </div>
  {contact_form()}
</div></section>
<section class="section"><div class="container">
  <iframe class="map" title="Hartă – {E(NAME)}" loading="lazy" src="https://maps.google.com/maps?q={E(C['map_query'])}&output=embed"></iframe>
  <div class="grid g4 transport" style="margin-top:30px">
    <div class="card"><div class="card-icon">{icon('metro')}</div><h3>Metrou</h3><p>{E(t['metrou'])}</p></div>
    <div class="card"><div class="card-icon">{icon('bus')}</div><h3>Autobuz</h3><p>{E(t['autobuz'])}</p></div>
    <div class="card"><div class="card-icon">{icon('bus')}</div><h3>Troleibuz</h3><p>{E(t['troleibuz'])}</p></div>
    <div class="card"><div class="card-icon">{icon('tram')}</div><h3>Tramvai</h3><p>{E(t['tramvai'])}</p></div>
  </div>
</div></section>"""
    layout("contact/", "Contact", body, current="contact/")


def accessibility():
    content = f"""<h2>Angajamentul nostru privind accesibilitatea</h2>
<p>{E(CFG['legal_name'])} se angajează să asigure accesibilitatea website-ului său pentru toate persoanele, inclusiv pentru persoanele cu dizabilități, în conformitate cu legislația în vigoare și cu recomandările WCAG 2.1, nivel AA.</p>
<h2>Accesibilitatea pe site</h2><ul class="list-check"><li>structură semantică a paginilor și navigare din tastatură</li><li>texte alternative pentru imagini</li><li>contrast adecvat între text și fundal</li><li>design responsive, adaptat pentru dispozitive mobile</li></ul>
<h2>Activarea meniului pentru Accesibilitate</h2><p>Apăsați butonul rotund din colțul stânga-jos al ecranului pentru a mări sau micșora textul, a activa contrastul ridicat, tonurile de gri sau sublinierea linkurilor.</p>
<h2>Conținut neaccesibil</h2><p>Unele documente PDF mai vechi pot să nu fie complet accesibile. Le puteți solicita într-un format alternativ folosind datele de contact de mai jos.</p>
<h2>Declinarea responsabilității</h2><p>Depunem eforturi continue pentru îmbunătățirea accesibilității; unele secțiuni pot fi în curs de actualizare.</p>
<h2>Date de contact pentru utilizatori</h2><p>Email: <a href="mailto:{C['email']}">{C['email']}</a><br>Telefon: {C['phone']}</p>
<h2>Întocmirea declarației</h2><p>Prezenta declarație a fost întocmită la data de {fdate(date.today().isoformat())}.</p>"""
    simple("declaratie-privind-accesibilitatea/", "Declarație privind accesibilitatea", content, [("Declarație privind accesibilitatea", None)])


def generic_pages():
    pages = [
        ("indicatori-de-calitate/", "Indicatori de calitate", "Publicăm periodic indicatorii de performanță ai spitalului: durata medie de spitalizare, indicele de utilizare a paturilor, rata infecțiilor asociate asistenței medicale și gradul de satisfacție al pacienților.", ABOUT_CRUMB),
        ("grija-si-siguranta/", "Grijă și siguranță", "Siguranța pacientului este prioritatea noastră. Aplicăm proceduri standardizate pentru identificarea corectă a pacienților, prevenirea infecțiilor, administrarea în siguranță a medicației și prevenirea căderilor.", ABOUT_CRUMB),
        ("confidentialitate/", "Confidențialitate", "Prelucrăm datele cu caracter personal în conformitate cu Regulamentul (UE) 2016/679 (GDPR). Această pagină descrie ce date colectăm, în ce scop, cât timp le păstrăm și ce drepturi aveți.", ABOUT_CRUMB),
        ("cercetare-si-inovare/", "Cercetare și inovare", "Spitalul participă la proiecte de cercetare clinică și colaborează cu instituții universitare pentru a aduce pacienților cele mai noi metode de diagnostic și tratament.", ABOUT_CRUMB),
        ("centre-de-excelenta/", "Centre de excelență", "Centrele de excelență reunesc echipe multidisciplinare, aparatură de ultimă generație și protocoale moderne pentru afecțiuni complexe.", []),
        ("educatie-pentru-sanatate/", "Educație pentru sănătate", "Materiale informative despre prevenție, stil de viață sănătos și gestionarea bolilor cronice, realizate de medicii noștri.", INFO_CRUMB),
    ]
    for path, title, intro, crumbs in pages:
        simple(path, title, f"<h2>{E(title)}</h2><p>{E(intro)}</p>{TODO}", crumbs + [(title, None)])


def search_page():
    body = page_hero("Căutare", [("Căutare", None)]) + f"""
<section class="section"><div class="container" style="max-width:860px">
  <form class="search-form" action="" role="search"><input id="searchPageInput" type="search" name="q" aria-label="Caută"><button class="btn btn-primary" type="submit">Caută</button></form>
  <div class="results" id="searchResults" data-index="{{{{ROOT}}}}search-index.json" data-root="{{{{ROOT}}}}" aria-live="polite"></div>
</div></section>"""
    layout("cautare/", "Căutare", body)


def not_found():
    body = page_hero("Pagina nu a fost găsită") + f'<section class="section"><div class="container center"><p>Ne pare rău, pagina căutată nu există.</p><a class="btn btn-primary" href="{{{{ROOT}}}}">Înapoi la pagina principală</a></div></section>'
    layout("404/", "Pagina nu a fost găsită", body)
    shutil.copy(OUT / "404/index.html", OUT / "404.html")
    (OUT / "404.html").write_text((OUT / "404.html").read_text(encoding="utf-8").replace('"../', '"/'), encoding="utf-8")


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")
    for extra in ("uploads",):
        if (ROOT / extra).exists():
            shutil.copytree(ROOT / extra, OUT / extra)
    col = CFG["colors"]
    (OUT / "favicon.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="{col["primary"]}"/><path d="M16 8v16M8 16h16" stroke="{col["highlight"]}" stroke-width="5" stroke-linecap="round"/></svg>', encoding="utf-8")

    home(); about(); management(); specialties_page(); ambulatoriu(); team_page()
    for s in SPECS: specialty(s)
    for d in DOCS: doctor_page(d)
    news_list()
    for n in NEWS: post_page(n)
    careers(); info_hub(); visitors_hub(); cas_page(); paid_page(); rights_page(); visit_rules(); faq_page()
    feedback("chestionar-de-feedback/", "Chestionar de feedback", "Spune-ne părerea ta și ajută-ne să fim mai buni!",
             "Îți mulțumim că ne oferi încredere și că ne spui cum putem fi mai buni.",
             ["Cum apreciați modul în care ați fost primit la internare?", "Cum apreciați comunicarea cu medicul curant?",
              "Cum apreciați îngrijirile acordate de asistentele medicale?", "Cum apreciați curățenia din salon și grupurile sanitare?",
              "Cum apreciați calitatea mesei?", "Cât de probabil este să recomandați spitalul?"], INFO_CRUMB + [("Chestionar de feedback", None)])
    feedback("chestionar-de-feedback-vizitatori/", "Chestionar de feedback", "Știm cât de important este cum îi îngrijim pe cei dragi ție",
             "Îți mulțumim că ne ești alături în dorința noastră de a face medicina cu suflet.",
             ["Cum apreciați informațiile primite despre starea pacientului?", "Cum apreciați amabilitatea personalului?",
              "Cât de clare au fost regulile de vizită?", "Cum apreciați condițiile din spațiile de așteptare?"],
             INFO_CRUMB + [("Pentru vizitatori", "pentru-vizitatori-si-apartinatori/"), ("Chestionar de feedback", None)])
    public_interest(); contact(); accessibility(); generic_pages(); search_page(); not_found()

    (OUT / "search-index.json").write_text(json.dumps(SEARCH_INDEX, ensure_ascii=False), encoding="utf-8")
    base = CFG["base_url"].rstrip("/")
    urls = "".join(f"<url><loc>{base}/{p['url']}</loc></url>" for p in SEARCH_INDEX if not p["url"].startswith(("404", "cautare")))
    (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    print(f"Built {len(SEARCH_INDEX)} pages into {OUT}")


if __name__ == "__main__":
    build()
