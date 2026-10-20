# NIGHTBITE — IAB207 Assignment 2, Group 25

NIGHTBITE is a Flask application for discovering Brisbane food events. The integrated source includes accounts, event browsing and filtering, event creation/editing/cancellation, ticket bookings, comments, semantic search and related-event recommendations.

Repository: https://github.com/LauraGalloway38/IAB207-Assignment-2-Group-25

## Run locally

Use a Python version supported by the installed Flask, PyTorch and sentence-transformers packages. The dependency files do not establish a verified minimum Python version. Create an isolated environment from the extracted project folder (the folder containing `main.py`):

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app nightbite:create_app init-db
python -m flask --app nightbite:create_app seed-events
python -m flask --app nightbite:create_app run
```

On Windows, use `py -m venv .venv`, then `.venv\Scripts\Activate.ps1` in PowerShell instead of the first two commands. Open http://127.0.0.1:5000. Register an account and sign in with its email and password. After initialisation, `python main.py` is an alternative launch command.

`init-db` creates missing tables and categories; it does not migrate old tables. Back up existing data before any schema migration. The default database is `nightbite/sitedata.sqlite`; `NIGHTBITE_DATABASE_URI` overrides its location. A generated development session key is stored in `instance/secret-key`.

`seed-events` is optional demo setup. It creates synthetic events and a seed organiser; that organiser is not a usable demonstration login. Register your own account to create/edit events. Seed dates are fixed in 2026, so some events may be past or unavailable for booking. Re-running the command also resets dates of matching sample events. Use a future-dated event you create for a booking demonstration.

## AI discovery

`nightbite/ai_search.py` uses `sentence-transformers/all-MiniLM-L6-v2` for local embeddings, combined with keyword matching. The first model load may require an internet download and additional time. The model cache is external to the submission. No hosted AI API key is configured by this implementation.

Search has a keyword fallback for model execution errors. This does not make the Python dependencies optional: NumPy and sentence-transformers are imported at startup. Install `requirements.txt` even when demonstrating fallback behaviour. `requirements-ai-installed.txt` is a captured environment inventory, not a verified portable lockfile.

## Configuration and data

- `SECRET_KEY`: private stable session key for deployment.
- `NIGHTBITE_HTTPS=1`: enables secure session cookies when the application is served over HTTPS.
- `NIGHTBITE_DATABASE_URI`: optional SQLAlchemy database connection URI.

Do not include private environment files, session keys or personal databases in a submission. Uploaded event images live under `nightbite/static/uploads/`, which Git ignores. If an approved demonstration database references uploads, package the corresponding approved images as well.

## Project layout

| Path | Purpose |
| --- | --- |
| `main.py` | Application launch entry point |
| `nightbite/` | Application factory, models, routes, forms, templates and static resources |
| `requirements.txt` | Runtime dependencies |
| `requirements-ai-installed.txt` | Existing dependency inventory |
| `tests/` | Account, browsing, event, booking/comment and AI tests |
| `evaluate_ai_search.py` | Model-based search evaluation script |
| `AI_DECLARATION.md` | Draft AI-use record requiring member completion |
| `SUBMISSION_CHECKLIST.md` | ZIP contents, evidence and unresolved requirements |

## Verification

```sh
python -m pip install pytest
python -m pytest -q
```

Use pytest to collect both pytest-style and unittest-style tests. Several AI tests mock embeddings; a passing suite alone does not prove real-model operation. For a separate real-model evaluation, run `python evaluate_ai_search.py` (model download may be required).

Before submission, extract the ZIP into a fresh folder and follow the setup instructions. Check registration/login/logout, browsing, a future event, booking history, comments, ownership restrictions, event editing/cancellation and both generic/enhanced Acknowledgement of Country input. Record actual results in the checklist.

## Submission status

See [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md). The official assessment brief and declaration template were not available in the inspected repository or synced sources. This README describes the code; it does not certify assessment compliance, deployment or team approval.
