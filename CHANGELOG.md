# Changelog

All notable changes to **PharmaCore — Smart Pharmacy Management** are documented here.

## [2.0.0] — 2026-06

Major release: AI decision support, region configurability, thermal printing,
multi-version support and UX upgrades.

### Added
- **AI decision support (provider-agnostic).**
  - Offline, deterministic **built-in** clinical engine (default, no API key).
  - Optional **OpenAI-compatible** provider (Endpoint / Model / API Key) with
    automatic fallback to the built-in engine on any failure.
  - **AI Risk Check** — clinical risk scoring (low → critical) with contributing
    factors on every prescription.
  - **AI Assistant** dialog — free-text clinical Q&A pre-filled with Rx/patient.
  - **Smart Reorder** — demand forecasting from dispensing velocity with
    near-expiry awareness and suggested quantities.
  - **Find AI Alternatives** — in-stock therapeutic substitutes ranked by
    availability and price.
- **Region & Localisation.**
  - `pharmacy.region` model + 6 seeded profiles (Global, US, EU, UK, PK, AE).
  - Applying a region writes control scheme, narcotic-register rule, Rx validity,
    temperature unit, currency, language and regulatory footer.
  - Editable from **Configuration → Regions** (no code).
- **Printable receipts.** Thermal **80 mm** / **58 mm** and **A4** dispensing
  receipts, selectable per region. Controlled-substance warning + region footer.
- **UX.** Status-grouped **kanban** for prescriptions with AI-risk and
  interaction / allergy badges.
- **Multi-version builds.** Dedicated builds for **Odoo 17, 18 and 19**.
- **Deployment.** Production `.env`-driven Docker stack under `deploy/`,
  hardened `odoo.conf` (`list_db=False`, `proxy_mode=True`), README and changelog.

### Changed
- `res.config.settings` extended with region and AI configuration.
- Manifest enriched (summary, description) and bumped to the `*.2.0.0` line per
  series (`18.0.2.0.0`, `19.0.2.0.0`, `17.0.2.0.0`).

### Fixed
- `res.config.settings` regulatory-footer field changed from `Text` to `Char`
  (settings models reject `Text`).
- AI settings labels given `for=` attributes (Odoo requires it on setting labels).
- Manifest load order: region/AI views now load before the prescription and
  dispense views that reference their actions.

### Compatibility
- Odoo **18.0** — primary build, live-verified.
- Odoo **19.0** — `card` kanban template, `<list>` views, storable-product flags.
- Odoo **17.0** — legacy `kanban-box` template, `<tree>` views, `type='product'`.
