# White-label hospital website – Spitalul Clinic „Nicolae Malaxa”

The site is currently populated with real data from https://www.spitalmalaxa.ro (crawled November 2026):
contacts, history, bed structure, management, board and ethics council, 16 sections and outpatient clinics with
their teams (67 specialists), schedules, equipment, photo galleries, the full price list (Decizia 188/06.11.2024, 361
services), patient rights and obligations, admission and discharge info, visiting hours, accreditations, the on-call
rota, job competitions and public-interest documents. All documents (175 PDFs, ~190 MB) and images were copied into
`uploads/` (documents under `uploads/docs/`, same folder structure as on the old site), so the site no longer depends on
spitalmalaxa.ro. Two documents were already missing (404) on the old site and were dropped. The only remaining link to the
old site is the "Declarații de avere" tile, which points to the old site's page.

Still to complete by the hospital: doctor photos (`photo` in `content/doctors.json`), the GDPR page text
(`confidentialitate`), dates for news items, and the mission/values texts in `content/lists.json`.

A complete static website for a Romanian public hospital. The page structure and navigation follow a typical
clinical-hospital site: about, management, specialties, outpatient clinic, doctors, patient and visitor info,
public-interest (Legea 544/2001) and contact. Everything brand-specific lives in one config file, so the same code can
be re-skinned for any hospital.

Pure Python 3 (standard library only). There's no framework and no `npm install`.

## Build & preview

```bash
python3 build.py
```

```bash
python3 -m http.server -d public 8000
```

Then open http://localhost:8000. The `public/` folder is the deployable site (GitHub Pages, Netlify, any web host).
It is generated and not committed; run `python3 build.py` (e.g. as the host's build command) to produce it.

## Deploy (GitHub Pages)

`.github/workflows/pages.yml` builds the site and publishes `public/` to GitHub Pages on every push to `main`, or on
demand from the Actions tab (*Deploy to GitHub Pages → Run workflow*). One-time setup: in the repository's
**Settings → Pages**, set **Source** to **GitHub Actions**.

The site is served from a sub-path (`https://<user>.github.io/<repo>/`); the workflow passes that path to the build as
`BASE_PATH` so the 404 page resolves correctly. All other links are relative and work under any path or custom domain.

## Re-branding (white-label)

| What | Where |
|---|---|
| Name, tagline, hero texts, logo, colors, contacts, transport, stats, social links | `site.config.json` |
| Medical specialties (one page each under `/service/<slug>/`) | `content/specialties.json` |
| Doctors (one profile each under `/team/<slug>/`) | `content/doctors.json` |
| News / announcements (`/YYYY/MM/DD/<slug>/`) | `content/news.json` |
| FAQ, price list, public-interest tiles, management, board, values, job contests | `content/lists.json` |
| Images (logo, doctor photos, news images, hero) | put files in `uploads/` and reference them as `uploads/…` |

- **Logo:** set `logo_image` (e.g. `uploads/logo.svg`), or leave it empty to use the text logo (`logo_text` / `logo_subtext`).
- **Hero background:** add `"hero_image": "uploads/hero.jpg"` to `site.config.json`.
- **Colors:** `colors.primary`, `accent`, `highlight`, etc. are injected as CSS variables on every page.

Text shown as `[… de completat]` (highlighted in yellow) is a placeholder to replace with the hospital's real content.
Publish only real patient reviews, with the patients' consent.

## Pages

Home · Despre noi · Echipa de management · Indicatori de calitate · Grijă și siguranță · Confidențialitate ·
Noutăți (list + article pages) · Cercetare și inovare · Cariere · Specialități medicale (+25 specialty pages) ·
Ambulatoriu · Medici (+ profile pages) · Centre de excelență · Informații utile · Servicii decontate prin CAS ·
Servicii medicale cu plată · Drepturile pacienților · Educație pentru sănătate · Chestionar de feedback (patients
and visitors) · Întrebări frecvente · Pentru vizitatori și aparținători · Reguli și program de vizită · Interes public ·
Contact · Declarație privind accesibilitatea · Căutare · 404. Also generates `sitemap.xml`, `robots.txt` and a search
index.

## Features

- Sticky header with dropdown menus, an off-canvas side menu (mobile navigation, contact, newsletter) and site search
- Specialty pages: sidebar menu, medical team, schedule table, treated conditions, services, prices, equipment, FAQ
- Doctors directory filterable by specialty
- Accessibility panel (text size, contrast, grayscale, underlined links)
- Responsive down to 360px

## Forms

The contact, newsletter and feedback forms are front-end only. To receive submissions, set the
`data-endpoint="https://…"` attribute on the `<form data-form>` elements in `build.py` (Formspree, Netlify Forms, your
own API, …). The form data is POSTed there.
