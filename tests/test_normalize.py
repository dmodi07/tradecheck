from ingest.normalize import normalize_name


def test_strips_legal_suffixes():
    assert normalize_name("Acme Foods Ltd.") == "acme foods"
    assert normalize_name("ACME FOODS") == "acme foods"
    assert normalize_name("Zürich Trading GmbH") == "zurich trading"


def test_multiword_suffix_and_accents():
    # accent fold + strip "SA de CV"
    assert normalize_name("AgroDistribuidora del Bajío SA de CV") == "agrodistribuidora del bajio"


def test_never_normalizes_to_empty():
    # a bare suffix token must survive rather than vanish
    assert normalize_name("Ltd") == "ltd"
    assert normalize_name("") == ""
