# Spitalul Clinic „Nicolae Malaxa” – Craft CMS version

The same website as the static generator in the repository root, rebuilt on **Craft CMS 5** so the hospital's staff can
edit everything from the control panel (`/admin`): pages, sections, doctors, prices, news, documents and the global
settings (contacts, logo, colors, visiting hours, links).

It produces the same pages at the same URLs, with the same design. The CSS and JS are shared with the static site through
the `web/static` symlink. Files live in the repository's `uploads/` folder, which `web/uploads` points to.

## Requirements

- PHP 8.2+ with the extensions Craft needs (including `bcmath`, `intl`, `gd`/`imagick`, `pdo_pgsql` or `pdo_mysql`)
- Composer 2
- PostgreSQL 13+ (what this was built and tested with) or MySQL 8

## Local setup

```bash
cd craft
```

```bash
composer install
```

```bash
cp .env.example.dev .env
```

```bash
php craft setup/keys
```

Edit `.env` with your database credentials. The defaults expect a PostgreSQL database `craft` with user and password
`craft`. Then install Craft. This applies the committed project config, so all fields, sections, entry types, the
`uploads` volume, the global settings and the CKEditor plugin are created automatically:

```bash
php craft install --email=you@example.com --username=admin --site-name="Spitalul Clinic „Nicolae Malaxa”" --site-url='$PRIMARY_SITE_URL' --language=ro
```

Register the files in `uploads/` as assets, then import the hospital's content from `../site.config.json` and
`../content/*.json`:

```bash
php craft index-assets/one uploads
```

```bash
php craft malaxa/import
```

```bash
php craft serve --port=8080
```

The site is at http://localhost:8080 and the control panel at http://localhost:8080/admin.

`malaxa/import` matches entries by slug, so running it again updates them instead of creating duplicates. After the
first import, Craft is the source of truth for the content. Edit in the control panel, not in the JSON files.

## Content model

| Section (control panel) | Type | What it holds | URL |
|---|---|---|---|
| **Pagina principală** | single | Homepage texts and the "why us" cards | `/` |
| **Pagini** | structure (2 levels) | Every content page. The structure is the navigation: top-level pages are menu items and their children form the submenu (with optional group labels). A child page with a **Link** is only a menu shortcut (e.g. "Misiune, viziune, valori" → `despre-noi/#misiune`). Pages are built from content blocks. | `/{slug}` |
| **Spital – secții și servicii** | structure | Hospital structures, grouped by **Categorie** (clinical sections, paraclinical services, other): description, beds, blocks, equipment, hours, doctors' schedule, contact lines, gallery, linked price group, matching cabinet | `/service/{slug}` |
| **Ambulatoriu – cabinete** | structure | Outpatient cabinets, with the same fields as the hospital structures and the matching hospital section. **Informații în curs de actualizare** shows the "being updated" note on cards. | `/ambulatoriu/{slug}` |
| **Medici** | structure | Doctors: grade, role, hospital section and/or outpatient cabinet, photo, bio. Lists are always alphabetical by surname, then first name. | `/team/{slug}` |
| **Noutăți** | channel | News and campaigns | `/noutati/{slug}` |
| **Tarife** | structure | Price groups (service, price) shown on the payment page and on each structure or cabinet | – |
| **Documente de interes public** | structure | The tiles and document lists on the "Interes public" page | – |
| **Setări site** (global set) | – | Name, logo, hero, stats, contacts, booking/feedback links, visiting hours, transport, social and useful links, brand colors, and the **Ultima actualizare** date shown on pages with schedules, prices and contacts | – |

Hospital structures and outpatient cabinets share one template (`_units/entry.twig`), so both present the same
information in the same order: description, medical team, services, equipment, schedule, appointments and contact,
required documents, prices, gallery, see also.

**Content blocks** (`contentBlocks`) are available on pages, hospital structures and cabinets. Every block has an
optional **Ancoră** (anchor id) for direct links such as `conducere/#ca`:

- **Text:** rich text
- **Text cu imagine:** text with an image (alternating sides on full-width pages)
- **Listă:** a list
- **Tabel:** a table (headings separated by `|`)
- **Acordeon:** collapsible items
- **Documente:** files from the volume plus external links
- **Carduri:** title, text, icon and link; icon `user` makes a person card
- **Galerie:** photo gallery
- **Atenționare:** a highlighted notice
- **Tip de prezentare:** one way of coming to the hospital (title, icon, rows such as Specificații, Condiții, Documente)

In plain-text fields, a line starting with `– ` becomes a dashed list item, and text in `[[double brackets]]` is shown
highlighted as a draft the hospital still has to confirm. Set `HIDE_PLACEHOLDERS=1` in the environment to show drafts as
plain text.

**Page types** with special templates in the "Pagini" section:

- `hospitalIndex`: the hospital structures, grouped by category (Spital)
- `ambulatoryIndex`: the outpatient cabinets (Ambulatoriu)
- `doctorsIndex`: all doctors, alphabetical, with the Toți / Spital / Ambulatoriu filter
- `newsIndex`: the news list
- `pricesPage`: payment information plus the searchable price list
- `presentationPage`: the "Tipuri de prezentare" page, built from **Tip de prezentare** blocks
- `publicInterest`: document tiles plus the Law 544 section
- `contactPage`: contact page

Everything else uses the generic `page` type. Its **Cuprins** switch adds buttons to the blocks that have an anchor
(used on Conducere).

## Code

| Path | What |
|---|---|
| `config/project/` | Project config: the content model as YAML. Commit it and deploy it with `php craft up`. |
| `modules/malaxa/console/controllers/SchemaController.php` | `php craft malaxa/schema`, which created the content model (and moved an existing install from the old combined "Specialități medicale" section to Spital / Ambulatoriu). It isn't needed for a normal install, because project config is applied by `install`/`up`. |
| `modules/malaxa/console/controllers/ImportController.php` | `php craft malaxa/import`, the content import from `../content/*.json` |
| `modules/malaxa/twig/Extension.php` | Twig filters shared with the static generator's rules: `rich`/`drafts` (draft highlighting), `lines` (dashed lists), `byName` (alphabetical doctors), `fileLabel` (document format and size) |
| `templates/_layout.twig` | Header, navigation (from the page structure), mobile menu, footer |
| `templates/_partials/ui.twig` | Shared macros (cards, documents, accordions, content block renderer…) |
| `templates/_partials/icons.twig` | Inline SVG icon set |
| `templates/_pages/`, `_units/`, `_doctors/`, `_news/` | Entry templates (`_units/` serves both hospital structures and outpatient cabinets) |
| `config/redirects.php` | Old addresses (e.g. `specialitati-medicale` → `spital`) |
| `templates/cautare.twig`, `templates/404.twig` | Search results (Craft's search index) and the 404 page |

## Deploying

GitHub Pages can't run Craft. It needs a PHP host with a database, for example Craft Cloud, Servd, Fortrabbit, Laravel
Forge, or any VPS / shared hosting with PHP 8.2+ and MySQL/PostgreSQL. A typical deploy:

```bash
composer install --no-dev --optimize-autoloader
```

```bash
php craft up
```

- Point the web server's document root at `craft/web`.
- Set `CRAFT_ENVIRONMENT=production`, `CRAFT_DEV_MODE=false`, `CRAFT_ALLOW_ADMIN_CHANGES=false` and a real `PRIMARY_SITE_URL`
  (see `.env.example.production`).
- Uploaded files: `web/uploads` is a symlink to the repository's `uploads/` folder. On a server, either deploy the whole
  repository so the symlink resolves, or replace the symlink with the folder itself and keep it outside of deployments
  (new uploads made in the control panel are written there).
