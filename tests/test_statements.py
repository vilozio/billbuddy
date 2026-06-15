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
    print("✓ scenario_store")


if __name__ == "__main__":
    test_filename_matcher()
    test_csv_transformer()
    test_scenario_store()
    os.unlink(_TMP_DB.name)
    print("\nAll tests passed.")
