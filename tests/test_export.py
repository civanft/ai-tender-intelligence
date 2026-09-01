from __future__ import annotations

import pandas as pd

from tender_intelligence.export import export_notices_csv, neutralize_spreadsheet_formula


def test_neutralize_spreadsheet_formula_prefixes_untrusted_formulas() -> None:
    assert neutralize_spreadsheet_formula("=HYPERLINK(\"bad\")") == "'=HYPERLINK(\"bad\")"
    assert neutralize_spreadsheet_formula("  @SUM(A1:A2)") == "'  @SUM(A1:A2)"
    assert neutralize_spreadsheet_formula("Normal buyer") == "Normal buyer"
    assert neutralize_spreadsheet_formula(42) == 42


def test_export_notices_csv_limits_columns_and_uses_utf8_bom() -> None:
    frame = pd.DataFrame(
        [
            {
                "notice_id": "123-2026",
                "title": "=2+2",
                "buyer_name": "Helsinki",
                "private_internal_value": "must not export",
            }
        ]
    )

    payload = export_notices_csv(frame)

    assert payload.startswith(b"\xef\xbb\xbf")
    decoded = payload.decode("utf-8-sig")
    assert "'=2+2" in decoded
    assert "private_internal_value" not in decoded
    assert "must not export" not in decoded
