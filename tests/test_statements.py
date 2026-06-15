"""Unit tests for the CSV statement pipeline (no Google/OpenAI/Telegram needed).

Run with:  .venv/bin/python -m tests.test_statements
"""

import os
import tempfile

# Point the DB at a throwaway file before importing anything that reads Config.
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DB_PATH"] = _TMP_DB.name

from app.db import init_db  # noqa: E402
from app.models.scenario import Scenario  # noqa: E402
from app.services import csv_transformer, filename_matcher, scenario_store  # noqa: E402

SAMPLE_CSV = (
    "Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance\n"
    "Card Payment,Current,2026-06-06 19:42:42,2026-06-07 14:54:46,Mercadona,-3.46,0.00,EUR,COMPLETED,20.03\n"
    "Card Payment,Current,2026-06-06 15:00:01,2026-06-07 14:55:27,Lousbury,-2.20,0.00,EUR,COMPLETED,17.83\n"
)


def test_filename_matcher():
    fn = "account-statement_2026-06-01_2026-06-15_en_6d52ac.csv"
    pattern = filename_matcher.suggest_pattern(fn)
    assert pattern == "account-statement_{date}_{date}_en_{any}.csv", pattern

    regex = filename_matcher.compile_pattern(pattern)
    import re

    # Same shape, different dates/hash -> matches.
    assert re.fullmatch(regex, "account-statement_2026-07-01_2026-07-31_en_ab12cd.csv")
    # The original file -> matches.
    assert re.fullmatch(regex, fn)
    # Unrelated file -> does not match.
    assert not re.fullmatch(regex, "mortgage-statement_2026-06-01.csv")
    print("✓ filename_matcher")


def test_csv_transformer():
    with tempfile.TemporaryDirectory() as d:
        in_path = os.path.join(d, "in.csv")
        out_path = os.path.join(d, "out.csv")
        with open(in_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_CSV)

        transform = {
            "keep": ["Completed Date", "Description", "Amount"],
            "rename": {"Completed Date": "Date"},
            "order": ["Date", "Description", "Amount"],
        }
        header, n_rows = csv_transformer.apply_transform(in_path, out_path, transform, True)
        assert header == ["Date", "Description", "Amount"], header
        assert n_rows == 2, n_rows

        with open(out_path, encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
        assert lines[0] == "Date,Description,Amount"
        assert lines[1] == "2026-06-07 14:55:27,Mercadona,-3.46" or "Mercadona" in lines[1]
        # Reordering: Description comes before Amount, Date first.
        assert lines[1].split(",")[1] == "Mercadona"
        assert lines[1].split(",")[2] == "-3.46"
    print("✓ csv_transformer")


def test_csv_transformer_constants_and_sort():
    with tempfile.TemporaryDirectory() as d:
        in_path = os.path.join(d, "in.csv")
        out_path = os.path.join(d, "out.csv")
        with open(in_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_CSV)

        transform = {
            "keep": ["Description", "Amount"],
            "constants": {"Source": "Revolut"},
            "order": ["Source", "Description", "Amount"],
            "sort": {"by": "Amount", "descending": False},  # numeric: -3.46 before -2.20
        }
        header, n_rows = csv_transformer.apply_transform(in_path, out_path, transform, True)
        assert header == ["Source", "Description", "Amount"], header
        assert n_rows == 2

        with open(out_path, encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
        assert lines[0] == "Source,Description,Amount"
        # Constant column applied to every row.
        assert lines[1].startswith("Revolut,") and lines[2].startswith("Revolut,")
        # Numeric ascending sort: -3.46 (Mercadona) comes before -2.20 (Lousbury).
        assert lines[1] == "Revolut,Mercadona,-3.46"
        assert lines[2] == "Revolut,Lousbury,-2.20"

        # Descending sort flips the order.
        transform["sort"]["descending"] = True
        csv_transformer.apply_transform(in_path, out_path, transform, True)
        with open(out_path, encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
        assert lines[1] == "Revolut,Lousbury,-2.20"
    print("✓ csv_transformer constants + sort")


def test_transform_ai_sanitize():
    from app.services.transform_ai_service import TransformAIService

    columns = ["Completed Date", "Amount", "Fee"]
    raw = {
        "keep": ["Completed Date", "Amount", "Bogus"],  # Bogus dropped
        "rename": {"Completed Date": "Date", "Ghost": "X"},  # Ghost dropped
        "constants": {"Source": "Revolut"},
        "order": ["Date", "Source", "Amount"],
        "sort": {"by": "Date", "descending": True},
    }
    clean = TransformAIService._sanitize(raw, columns)
    assert clean["keep"] == ["Completed Date", "Amount"]
    assert clean["rename"] == {"Completed Date": "Date"}
    assert clean["constants"] == {"Source": "Revolut"}
    assert clean["order"] == ["Date", "Source", "Amount"]
    assert clean["sort"] == {"by": "Date", "descending": True}

    # A sort.by that isn't an output name is dropped.
    bad = TransformAIService._sanitize(
        {"keep": ["Amount"], "sort": {"by": "Nope"}}, columns
    )
    assert "sort" not in bad
    print("✓ transform_ai sanitize")


def test_scenario_store():
    init_db()
    scenario = Scenario(
        name="account-statement",
        filename_pattern="account-statement_{date}_{date}_en_{any}.csv",
        pattern_regex=filename_matcher.compile_pattern(
            "account-statement_{date}_{date}_en_{any}.csv"
        ),
        transform_json='{"keep": ["Amount"]}',
        dest_sheet=True,
        sheet_spreadsheet_id="sheet123",
        sheet_tab="Revolut",
        created_at="2026-06-15T00:00:00",
    )
    new_id = scenario_store.add_scenario(scenario)
    assert new_id

    match = scenario_store.find_matching("account-statement_2026-08-01_2026-08-31_en_zz99zz.csv")
    assert match is not None and match.id == new_id
    assert match.transform == {"keep": ["Amount"]}
    assert scenario_store.find_matching("something-else.csv") is None

    # Settings round-trip + receipts toggle default.
    assert scenario_store.receipts_enabled() is True
    scenario_store.set_receipts_enabled(False)
    assert scenario_store.receipts_enabled() is False
    scenario_store.set_setting("k", "v")
    assert scenario_store.get_setting("k") == "v"
    assert scenario_store.get_setting("missing", "dflt") == "dflt"

    assert scenario_store.delete_scenario(new_id) is True
    assert scenario_store.find_matching("account-statement_2026-08-01_2026-08-31_en_zz99zz.csv") is None

    # Known sheets: insert, list, and upsert label.
    scenario_store.add_known_sheet("ss_abc", "Revolut Log")
    scenario_store.add_known_sheet("ss_def", "Investments")
    known = scenario_store.list_known_sheets()
    assert ("ss_def", "Investments") in known and ("ss_abc", "Revolut Log") in known
    scenario_store.add_known_sheet("ss_abc", "Revolut Log 2026")  # upsert label
    labels = dict(scenario_store.list_known_sheets())
    assert labels["ss_abc"] == "Revolut Log 2026"
    print("✓ scenario_store")


def test_spreadsheet_id_extraction():
    from app.bot.csv_handlers import _extract_spreadsheet_id

    url = "https://docs.google.com/spreadsheets/d/1AbC-dEfG_hiJklmnopqrstuvwxyz12345/edit#gid=0"
    assert _extract_spreadsheet_id(url) == "1AbC-dEfG_hiJklmnopqrstuvwxyz12345"
    raw = "1AbC-dEfG_hiJklmnopqrstuvwxyz12345"
    assert _extract_spreadsheet_id(raw) == raw
    assert _extract_spreadsheet_id("not a sheet") is None
    print("✓ spreadsheet_id extraction")


def test_action_log():
    init_db()
    uid = 42
    assert scenario_store.last_undoable_action(uid) is None

    a1 = scenario_store.record_action(
        uid, "statement", "Statement: Revolut (2 rows)",
        {"sheet": {"spreadsheet_id": "ss1", "range": "Sheet1!A5:H6"}},
    )
    a2 = scenario_store.record_action(
        uid, "receipt", "Receipt: Mercadona ($3.46)",
        {"drive_file_id": "fileX", "sheet": {"spreadsheet_id": "ss2", "range": "Sheet1!A2:H2"}},
    )

    # Most recent first.
    last = scenario_store.last_undoable_action(uid)
    assert last["id"] == a2 and last["kind"] == "receipt"

    # Undo it -> previous becomes the candidate.
    scenario_store.mark_action_undone(a2)
    last = scenario_store.last_undoable_action(uid)
    assert last["id"] == a1

    # Another user is isolated.
    assert scenario_store.last_undoable_action(99) is None

    scenario_store.mark_action_undone(a1)
    assert scenario_store.last_undoable_action(uid) is None
    print("✓ action_log")


def test_parse_a1_rows():
    from app.services.google_sheets import parse_a1_rows

    assert parse_a1_rows("Sheet1!A5:H6") == ("Sheet1", 5, 6)
    assert parse_a1_rows("'My Tab'!A2:C2") == ("My Tab", 2, 2)
    assert parse_a1_rows("A2:C3") == (None, 2, 3)
    print("✓ parse_a1_rows")


if __name__ == "__main__":
    test_filename_matcher()
    test_csv_transformer()
    test_csv_transformer_constants_and_sort()
    test_transform_ai_sanitize()
    test_scenario_store()
    test_spreadsheet_id_extraction()
    test_action_log()
    test_parse_a1_rows()
    os.unlink(_TMP_DB.name)
    print("\nAll tests passed.")
