import pytest

from libretranslate import glossary


def roundtrip(text, terms, text_format="text", translate=lambda t: t):
    pattern = glossary.compile_terms(glossary.merge_terms(terms), text_format)
    masked, mapping = glossary.protect(text, pattern, text_format)
    return masked, glossary.restore(translate(masked), mapping)


def test_masks_and_restores():
    masked, (out, missing) = roundtrip("Acme Corp opened in Paris.", ["Acme Corp", "Paris"])
    assert masked == "XTERM0X opened in XTERM1X."
    assert out == "Acme Corp opened in Paris."
    assert missing == []


def test_no_terms():
    assert glossary.compile_terms([]) is None
    assert glossary.protect("Hello", None) == ("Hello", {})
    assert glossary.restore("Hello", {}) == ("Hello", [])


def test_case_insensitive_keeps_spelling_of_source():
    masked, (out, _) = roundtrip("ACME and acme and Acme.", ["Acme"])
    assert masked == "XTERM0X and XTERM1X and XTERM2X."
    assert out == "ACME and acme and Acme."


def test_same_spelling_shares_a_placeholder():
    masked, _ = roundtrip("Acme, then Acme.", ["Acme"])
    assert masked == "XTERM0X, then XTERM0X."


def test_whole_words_only():
    masked, _ = roundtrip("Acmeology is not Acme.", ["Acme"])
    assert masked == "Acmeology is not XTERM0X."


def test_longest_term_wins():
    masked, (out, _) = roundtrip("Bali Beach Club in Bali", ["Bali", "Bali Beach Club"])
    assert masked == "XTERM0X in XTERM1X"
    assert out == "Bali Beach Club in Bali"


def test_terms_with_regex_characters_and_flexible_spaces():
    masked, (out, _) = roundtrip("C++ and Acme  Corp (Inc.)", ["C++", "Acme Corp", "(Inc.)"])
    assert masked == "XTERM0X and XTERM1X XTERM2X"
    assert out == "C++ and Acme  Corp (Inc.)"


@pytest.mark.parametrize("damaged", ["xterm0x", "Xterm0X", "XTERM 0 X", "X TERM0X"])
def test_restore_tolerates_model_damage(damaged):
    _, (out, missing) = roundtrip("Acme", ["Acme"], translate=lambda t: f"Halo {damaged}.")
    assert out == "Halo Acme."
    assert missing == []


def test_restore_keeps_suffix():
    _, (out, _) = roundtrip("Acme", ["Acme"], translate=lambda t: f"{t}-ul")
    assert out == "Acme-ul"


def test_restore_reports_lost_terms():
    _, (out, missing) = roundtrip("Acme and Paris", ["Acme", "Paris"], translate=lambda t: "XTERM1X")
    assert out == "Paris"
    assert missing == ["Acme"]


def test_lookalike_in_source_is_left_alone():
    masked, (out, _) = roundtrip("XTERM0X and Acme", ["Acme"])
    assert masked == "XTERM0X and XTERM1X"
    assert out == "XTERM0X and Acme"


def test_html_masks_text_nodes_only():
    html = '<a href="https://acme.example/Acme" title="Acme">Visit Acme</a>'
    masked, (out, _) = roundtrip(html, ["Acme"], "html")
    assert masked == '<a href="https://acme.example/Acme" title="Acme">Visit XTERM0X</a>'
    assert out == html


def test_html_matches_escaped_term():
    masked, (out, _) = roundtrip("<b>AT&amp;T</b> call", ["AT&T"], "html")
    assert masked == "<b>XTERM0X</b> call"
    assert out == "<b>AT&amp;T</b> call"


def test_merge_dedupes_ignoring_case_and_skips_blanks():
    assert glossary.merge_terms(["Acme", " acme ", ""], "Paris", None) == ["Acme", "Paris"]


@pytest.mark.parametrize("bad", [5, {"a": 1}, ["ok", 5]])
def test_merge_rejects_other_types(bad):
    with pytest.raises(ValueError):
        glossary.merge_terms(bad)


def test_merge_rejects_too_many_terms():
    with pytest.raises(ValueError):
        glossary.merge_terms([f"t{i}" for i in range(glossary.MAX_TERMS + 1)])


def test_load_file(tmp_path):
    path = tmp_path / "glossary.txt"
    path.write_text("# brands\nAcme Corp\n\n  Paris  \n", encoding="utf-8")
    assert glossary.load_file(path) == ["Acme Corp", "Paris"]
