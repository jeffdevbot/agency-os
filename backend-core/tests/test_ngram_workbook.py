from app.services.ngram.workbook import make_unique_sheet_name


def test_make_unique_sheet_name_strips_edge_apostrophe_after_truncate():
    used: set[str] = set()
    out = make_unique_sheet_name("Vendo | B07PLRLJR9 | Men | Men'", used)
    assert out == "Vendo | B07PLRLJR9 | Men | Men"
    assert len(out) <= 31


def test_make_unique_sheet_name_falls_back_when_only_apostrophes():
    used: set[str] = set()
    out = make_unique_sheet_name("''", used)
    assert out == "Sheet"


def test_make_unique_sheet_name_dedupes_sheet_fallback():
    used: set[str] = set()
    first = make_unique_sheet_name("''", used)
    second = make_unique_sheet_name("''''''''''''''''''''''''''''''''''''", used)
    assert first == "Sheet"
    assert second == "Sheet (2)"

