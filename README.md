# PharmaCore — Smart Pharmacy Management for Odoo

**AI-assisted, region-configurable pharmacy & drugstore management** built natively
on Odoo Inventory, Sales, Accounting and Contacts.

> By **SA Systems** — _Where Business Grows Smarter._
> Support: [info@sasystems.solutions](mailto:info@sasystems.solutions) · https://www.sasystems.solutions

---

## Why PharmaCore

Generic Odoo inventory was never designed for a pharmacy. PharmaCore closes the
real-world clinical and regulatory gaps:

| Capability | What it does |
|---|---|
| **FEFO batch control** | First-Expiry-First-Out removal so the closest-to-expiry stock leaves first. |
| **Prescription (Rx) lifecycle** | Refills, validity windows, prescriber registry, dispensing with batch traceability. |
| **Clinical screening** | Drug–drug interaction checks + patient allergy alerts the moment items are added. |
| **🤖 AI decision support** | Clinical risk scoring, therapeutic substitution suggestions, demand forecasting / smart reorder, and a clinical assistant. |
| **🌍 Region profiles** | US / EU / UK / PK / AE / Global presets for drug scheduling, language, currency, temperature units and receipt format. |
| **🧾 Thermal & A4 receipts** | 80 mm / 58 mm thermal-printer receipts plus standard A4. |
| **Controlled substances** | Scheduled / narcotic register with full audit trail and patient-ID enforcement. |
| **Expiry dashboard** | Near-expiry batches, automated alerts and write-off suggestions. |

---

## Odoo version compatibility

PharmaCore ships as **three dedicated builds** from one source of truth, so you
install the one that matches your Odoo series:

| Odoo series | Module folder | Module technical name | Manifest version |
|---|---|---|---|
| **18.0** (recommended) | `sa_pharmacy_management` | `sa_pharmacy_management` | `18.0.2.0.0` |
| **19.0** | `sa_pharmacy_management_19` | `sa_pharmacy_management` | `19.0.2.0.0` |
| **17.0** | `sa_pharmacy_management_17` | `sa_pharmacy_management` | `17.0.2.0.0` |

All three builds are functionally identical. They differ only in version-specific
Odoo internals (storable-product flags, list/tree view tag, kanban template syntax,
the FEFO removal hook, and the manifest version string).

---

## Quick start (Docker)

A production-ready stack lives in [`deploy/`](deploy/).

```bash
cd deploy
cp .env.example .env
#  edit .env  → choose ODOO_VERSION + matching PHARMACY_MODULE_DIR,
#               and set a strong POSTGRES_PASSWORD
#  edit odoo.conf → set admin_passwd (master password) + db_password

docker compose up -d

# install the module
docker compose exec odoo \
  odoo -c /etc/odoo/odoo.conf -d "$POSTGRES_DB" \
       -i "$PHARMACY_MODULE" --stop-after-init
docker compose restart odoo
```

Open **http://localhost:8069** (or your `ODOO_PORT`), create/select the database,
and install **PharmaCore** from Apps if it isn't already.

> To **upgrade** after pulling a new build: replace `-i` with `-u`, then
> `docker compose restart odoo`.

### Manual install (existing Odoo)

1. Copy the folder for your series into your `addons_path`.
2. Restart Odoo with `-u all` or update the Apps list.
3. Install **PharmaCore — Smart Pharmacy Management**.

**Dependencies** (all standard Odoo modules, auto-installed):
`base`, `mail`, `product`, `stock`, `product_expiry`, `sale_management`,
`account`, `contacts`, `board`, `barcodes`.

---

## Configuration

Everything is under **Pharmacy → Configuration → Settings** (the *Pharmacy* tab).

### 🌍 Region & Localisation

1. Pick an **Active Region** (US, EU, UK, PK, AE, or Global).
2. Applying a region writes the regulatory profile: control scheme
   (DEA / UK / EU / WHO), narcotic-register requirement, Rx validity limits,
   temperature unit, currency, language and the **regulatory footer** printed on
   receipts.
3. Choose the **Receipt Format**: `Thermal 80 mm`, `Thermal 58 mm`, or `A4`.

Regions are editable records under **Pharmacy → Configuration → Regions** — add
your own country profile in seconds (no code).

### 🤖 Artificial Intelligence

PharmaCore's AI is **provider-agnostic** and safe by default:

| Provider | Behaviour |
|---|---|
| **Built-in** (default) | A fully **offline, deterministic** clinical engine. No API key, no external calls, no data leaves your server. Always available. |
| **OpenAI-compatible** | Point **Endpoint / Model / API Key** at OpenAI or any compatible gateway (Azure OpenAI, local LLM servers, etc.). |

If an external provider is unreachable or errors, PharmaCore **automatically falls
back to the built-in engine** — features never break.

> The OpenAI provider uses the `requests` library bundled with Odoo; no extra
> Python packages are required.

**AI features:**

- **AI Risk Check** on a prescription → scored clinical risk (low → critical) with
  the contributing factors (interactions, geriatric/pediatric flags, etc.).
- **AI Assistant** dialog → ask free-text clinical questions, pre-filled with the
  current Rx and patient context.
- **Smart Reorder** (AI Tools) → demand forecasting from dispensing velocity, with
  near-expiry awareness and suggested order quantities.
- **Find AI Alternatives** on a medicine → in-stock therapeutic substitutes sharing
  the same active ingredients, ranked by availability and price.

### 🧾 Thermal printing

With **Receipt Format** set to a thermal size, the **Print Receipt** button on a
dispensing produces a monospaced, narrow-roll receipt (batch + expiry + SIG lines,
totals, controlled-substance warning, and your region footer). A4 is used when the
region/format is set to A4. Both run on the standard Odoo (wkhtmltopdf) report
engine — no special driver required for the PDF; send it to any thermal printer.

---

## Key screens

- **Prescriptions** — status **kanban** board with AI-risk badges and
  interaction / allergy flags, plus list, form and search.
- **Dispensing** — pharmacist workflow with batch traceability, printable labels
  and receipts.
- **AI Tools** — Smart Reorder and the AI Assistant.
- **Dashboard** — dispensing trend (graph), analysis (pivot) and near-expiry board.
- **Inventory & Expiry** — near-expiry batches and write-off suggestions.

---

## Repository layout

```
.
├── sa_pharmacy_management/        # Odoo 18 build (primary)
├── sa_pharmacy_management_17/     # Odoo 17 build
├── sa_pharmacy_management_19/     # Odoo 19 build
├── deploy/                        # production Docker stack (.env-driven)
│   ├── docker-compose.yml
│   ├── .env.example
│   └── odoo.conf
├── _demo/                         # local demo stack (Odoo 18, port 8073)
├── CHANGELOG.md
└── README.md
```

---

## Security notes for production

- Set a strong **`admin_passwd`** (master password) in `deploy/odoo.conf`.
- Set a strong **`POSTGRES_PASSWORD`** in `deploy/.env` (the stack refuses to start
  without one).
- `list_db = False` and `proxy_mode = True` are pre-set in the production config;
  terminate TLS at a reverse proxy (nginx/traefik).
- The built-in AI engine keeps **all clinical data on-premise**. Only enable an
  external AI provider if your data-governance policy allows it.

---

## License

OPL-1. © SA Systems. See the module manifest for details.
