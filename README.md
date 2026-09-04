# PathoLab Pro — Cloud (Multi-Tenant SaaS)

A multi-tenant pathology lab management platform: any number of labs can
register and use it independently, with completely isolated data, all
running from one shared deployment. Built with **Streamlit** and
**PostgreSQL** (designed for **Neon**'s serverless Postgres), ready to
deploy on **Streamlit Community Cloud** straight from a **GitHub** repo.

There is **no free trial** — a lab can only register by entering a valid
Monthly or Yearly license key, generated and controlled entirely by you
(the vendor). Keys are never exposed inside the app itself.

## 1. How it works

- **One deployment, many labs.** Each pathology lab that registers
  becomes a "tenant" with its own Lab Code, users, patients, samples,
  billing, etc. — completely isolated from every other lab, in the same
  shared database.
- **Registration requires a license key.** A new lab enters a Monthly
  (30-day) or Yearly (365-day) key at sign-up. The key is single-use and
  tied to that lab from then on.
- **One admin per lab.** The person who registers the lab becomes its
  administrator immediately. Every other staff member (Receptionist,
  Lab Technician, Doctor, Accountant) joins afterwards via "Join
  Existing Lab" using the Lab Code, and stays pending until that lab's
  admin approves them.
- **Login needs three things:** Lab Code + Username + Password. Usernames
  only need to be unique *within* a lab, not across the whole platform.

## 2. One-time setup: create your Neon database

1. Go to [neon.tech](https://neon.tech) and create a free account and a
   new project.
2. Copy the **connection string** Neon gives you — it looks like:
   ```
   postgresql://user:password@ep-xxxx.region.aws.neon.tech/dbname?sslmode=require
   ```
3. Keep this safe — you'll paste it into Streamlit Cloud's secrets in
   step 4 below. You do **not** need to create any tables yourself; the
   app creates them automatically the first time it runs.

## 3. Push this project to GitHub

```bash
cd patholab_saas
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git push -u origin main
```

`.streamlit/secrets.toml` is intentionally **not** included (see
`.gitignore`) — never commit real secrets to GitHub. You'll set the
database connection string directly in Streamlit Cloud instead.

## 4. Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in
   with GitHub.
2. Click **New app**, pick your repository, branch `main`, and set the
   main file path to `app.py`.
3. Before (or right after) deploying, open **Settings → Secrets** for
   the app and paste:
   ```toml
   DATABASE_URL = "postgresql://user:password@ep-xxxx.region.aws.neon.tech/dbname?sslmode=require"
   ```
   (your actual Neon connection string from step 2).
4. Click **Deploy**. The first load creates all the database tables
   automatically — this takes a few seconds.
5. Your app is now live at `https://your-app-name.streamlit.app` —
   share this link with any lab that wants to register.

## 5. Issuing license keys (you, the vendor — never the labs)

Labs cannot see or generate keys from inside the app — that list only
ever exists on your side. To create keys:

1. On your own computer (not deployed anywhere):
   ```bash
   pip install sqlalchemy psycopg2-binary openpyxl
   export DATABASE_URL="same connection string as your Streamlit secret"
   python generate_license_keys.py          # 50 monthly + 50 yearly
   python generate_license_keys.py 100      # 100 of each
   python generate_license_keys.py 20 monthly
   ```
2. This inserts the keys directly into your live Neon database *and*
   writes `license_keys.xlsx` (Monthly Keys / Yearly Keys / Summary
   tabs) for you to keep and hand out one key per new lab.
3. Each key works once — the moment a lab registers with it, it's
   marked used and can't be reused, even if that lab is later deleted.

## 6. Local development (optional)

```bash
cd patholab_saas
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml and set your own DATABASE_URL
streamlit run app.py
```

Any Postgres works for local development (a local install, a Neon
branch, Docker, etc.) — it doesn't have to be your production Neon
database.

## 7. What's built and working

- **Registration & licensing:** Register New Lab (license key required,
  no trial), Join Existing Lab (pending approval), Log In (Lab Code +
  username + password), subscription renewal for admins.
- **Multi-tenancy:** every table is scoped by `tenant_id`; verified that
  two labs can use identical usernames with zero data leakage between
  them.
- **Clinical workflow:** Patient Registration, Test Master (single
  tests + packages), Sample Collection, Result Entry (with flags),
  Report Verification with **PDF report generation and download**.
- **Business operations:** Billing (itemized, discounts, partial
  payments), Doctors & Pathologists, Staff & Attendance, Inventory
  (with low-stock indicators), Expenses.
- **Reports:** Patient, Sample, Collection, Pending Payments, Expense,
  Test-wise, Doctor-wise — each with Excel export.
- **Settings:** lab name/address/contact/report disclaimer, used on
  every generated PDF report.
- **User Management:** admin approves/deactivates staff accounts within
  their own lab.

Every one of these has been tested directly against a real Postgres
database (registration, licensing, login, multi-tenant isolation, the
full patient → sample → result → verified PDF → billing workflow) and
through the actual browser UI (registration form, login, patient
registration, navigation).

## 8. What to build next

This is a strong, working foundation covering the core SaaS workflow —
a few things are natural next additions rather than included here:

- **Audit log UI** — the data model (`AuditLog`) is already there and
  being written to (`utils/helpers.log_action`), but there's no page to
  browse it yet.
- **QR/barcode sample labels** — the desktop version had these; not
  included in this cloud rebuild.
- **Bulk data export / tenant-level backup** — Neon itself supports
  point-in-time restore and branching, which covers most of this, but
  an in-app "export my lab's data" button would be a nice addition.
- **Payments for renewal** — right now a lab's admin renews by typing in
  a key you've sent them manually; wiring this to an actual payment
  gateway (Razorpay/Stripe) so keys are issued automatically after
  payment is a natural next step if you want self-serve renewals.
- **Password reset flow** — there's no "forgot password" self-service
  yet; a lab's admin can be given a new password by editing the
  database directly, or this can be added as a page.

## 9. Project structure

```
app.py                        Entry point: Login / Register Lab / Join Lab
db/
  connection.py                 SQLAlchemy engine (reads DATABASE_URL)
  models.py                      All tables (Tenant, LicenseKey, + every tenant-scoped table)
  init_db.py                      Creates tables on first run
pages/                         One file per module (numbered for sidebar order)
utils/
  auth.py                          Password hashing, login, staff join-lab logic
  license_manager.py                Tenant registration, license validation, renewal
  session.py                         Streamlit session-state helpers (login state, tenant context)
  helpers.py                          ID generators, audit logging, settings
  pdf_report.py                        Report PDF generation
generate_license_keys.py       VENDOR-ONLY — run locally, never deploy
requirements.txt
.streamlit/
  config.toml                     Theme
  secrets.toml.example             Template — copy to secrets.toml for local dev
```
