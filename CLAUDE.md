# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the bot (long-polling Telegram client; blocks until Ctrl+C)
python -m app.main          # or ./run.sh (creates .venv + installs deps on first run)

# One-time Google OAuth (writes credentials/token.pickle). Re-run after invalid_grant.
python authenticate.py

# Tests — pure CSV pipeline, no Google/OpenAI/Telegram credentials needed
python -m tests.test_statements     # runs every test, prints ✓ per test
pytest tests                        # also works (pytest is configured in .vscode)

# Verbose logging
LOG_LEVEL=DEBUG python -m app.main
```

There is no single-test runner script; `tests/test_statements.py` calls each `test_*` function from its `__main__` block. To run one in isolation, import and call it, or use `pytest tests/test_statements.py::test_csv_transformer`.

Formatting follows **black** + **isort (black profile)** (see `.vscode/settings.json`); these aren't enforced in CI but match the existing style. Always run from the repo root with it on `PYTHONPATH` — the code uses absolute `app.*` imports.

## Big picture

BillBuddy is a Telegram bot with **two independent processing directions** that share Google Drive/Sheets plumbing and an undo log:

1. **Receipts** (photo/PDF) → GPT‑4 Vision OCR → store file in Drive + log row to Sheets. Can be toggled off (`/receipts_off`) so the bot runs statements-only.
2. **CSV statements** → recognized by filename pattern → deterministic column transform → append to a Sheet tab and/or upload to Drive.

`app/main.py` wires everything: validates `Config`, calls `init_db()`, then registers handlers. **Handler registration order matters** — the CSV `ConversationHandler` (`build_csv_conversation()`) is registered before the PDF document handler so `.csv` files route to the statement wizard, not the receipt path.

### The recurring "AI proposes, code executes" pattern

This is the central design idea for statements. OpenAI is used *only* to translate a user's plain-language instruction into a small JSON transform schema (`transform_ai_service.py`); the user confirms it; then the transform always runs in deterministic stdlib code (`csv_transformer.py`). The schema is sanitized against the real CSV headers (`TransformAIService._sanitize`) so hallucinated column names can never reach the executor. When changing transform behavior, change the **executor and the schema docstring/prompt together** — `csv_transformer.py`'s module docstring is the source of truth for the schema shape (`keep`/`rename`/`constants`/`order`/`sort`).

### Lazy initialization everywhere

Google services (`GenericSheetsService`, `GoogleDriveService`) and the OpenAI clients are constructed lazily, inside methods, not at import or process start. This is deliberate: it lets the bot boot and run a statements-only or receipts-only deployment without forcing the unused side's credentials. Preserve this — don't hoist a service construction to module scope or `__init__` if it triggers auth.

### Scenarios (the statement model)

A **Scenario** (`app/models/scenario.py`, persisted in the `scenarios` SQLite table) describes how one recurring file kind is handled: a filename pattern, its compiled regex, the transform JSON, and destination(s). The setup wizard is a python-telegram-bot `ConversationHandler` in `app/bot/csv_handlers.py` with states `ASK_PATTERN → ASK_NAME → ASK_TRANSFORM → CONFIRM_TRANSFORM → ASK_DESTINATION → [ASK_SPREADSHEET → ASK_SHEET_TAB] → finalize`.

- **Multiple scenarios can share one pattern.** `find_matches()` returns all; on upload, one match auto-processes, several prompt the user to choose (`ASK_SCENARIO_CHOICE`), and `/add_scenario` forces a new scenario for an already-matched pattern (via `force_new_scenario` in `user_data`).
- Filename matching: `filename_matcher.suggest_pattern()` turns an example into a `{date}`/`{any}` template; `compile_pattern()` compiles it to a regex matched with `re.fullmatch`.
- Known spreadsheets the user has picked are remembered in the `known_sheets` table and offered during setup.

### Undo

Every receipt and statement that writes anything records a reversal payload via `scenario_store.record_action()` (the `actions` table): the Drive file id and/or the Sheet A1 range that was appended. `/undo` pops the user's most-recent un-undone action and `UndoService` deletes that Drive file and removes those Sheet rows. Undo is per-user and walks backward one action at a time. If you add a new destination/side-effect to the statement or receipt processor, record its reversal in the same `undo` dict or it won't be undoable.

## Layout

- `app/bot/` — Telegram handlers. `handlers.py` (receipt photo/PDF/text), `commands.py` (/start /help /status), `csv_handlers.py` (CSV wizard), `settings_commands.py` (/receipts_on|off, /scenarios, /add_scenario, /delete_scenario, /undo).
- `app/services/` — `receipt_processor.py` / `statement_processor.py` are the two orchestrators; `openai_service.py` (receipt OCR) and `transform_ai_service.py` (transform schema) are the two AI callers; `csv_transformer.py` / `filename_matcher.py` are pure deterministic logic; `scenario_store.py` is all SQLite CRUD + settings; `google_auth.py`/`google_drive.py`/`google_sheets.py` are the Google layer.
- `app/config.py` — all env config via a `Config` class; `Config.validate()` enforces required vars at startup.
- `app/db.py` — schema (`CREATE TABLE IF NOT EXISTS`, so `init_db()` is idempotent) for `scenarios`, `settings`, `known_sheets`, `actions`.

## Config & auth notes

- Required env (validated at boot): `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `GOOGLE_OAUTH_CLIENT_PATH` (file must exist), `GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_SHEET_ID`. Statement-specific `STATEMENTS_DRIVE_FOLDER_ID`/`STATEMENTS_SHEET_ID` are optional and fall back to the receipt folder/sheet.
- Auth is **OAuth user credentials**, not a service account. `credentials/token.pickle` is created by `authenticate.py`; delete and re-run it on `invalid_grant`. Scope is `drive.file`, so the bot only sees files/folders it created or that were opened with it.
- `.env`, `credentials/`, `data/`, `logs/`, `temp_*` are git-ignored. The SQLite DB lives at `DB_PATH` (default `data/billbuddy.db`).
- Telegram runtime state (the runtime receipts on/off toggle) lives in the `settings` table, not env.
