# Project Overview

## Key Directories

- `fitness/` – FastAPI application code, routers, services, metadata, and templates.
- `fitness/static/` – Front-end assets (CSS, certification PDFs).
- `fitness/templates/` – Jinja2 templates for the public and admin UI.
- `tests/` – Pytest suite with smoke and integration coverage.
- `scripts/` – Developer utilities such as the DRY checker.
- `docs/` – Project documentation (this directory).

## Application Flow

1. `fitness/main.py` boots the FastAPI app, mounts static assets, seeds certification metadata from `fitness/static/certs`, and exposes UI/API/admin routers.
2. Public routes live in `fitness/routers/ui.py`, which render Jinja templates via `fitness/templates`.
3. Certification metadata lives in `fitness/constants.py`, which also handles provider-specific verification labels.
4. PDF résumé generation uses `fitness/services/pdf_resume.py`, reporting defaults taken from `fitness/config.py`.
5. Database access is centralized through `fitness/database.py` with SQLAlchemy models defined under `fitness/models/`.

## Data Sources

- Certifications are seeded from PDFs placed in `fitness/static/certs/`.
- Résumé content is read from `fitness/data/resume-data.yaml` (with sane fallbacks if the file is missing).
