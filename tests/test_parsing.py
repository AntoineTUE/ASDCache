import re
from urllib import parse

import pytest

from ASDCache.ASDCache import SCI_EXPR, SpectraCache
from ASDCache.utils import extract_species


@pytest.mark.parametrize(
    "species,expected",
    [
        ("H I", ["H I"]),
        ("H I;O I-III", ["H I", "O I-III"]),
        ("Sc;Fe", ["Sc", "Fe"]),
        ("Sc-Fe", ["Sc-Fe"]),
        ("Ca-like", ["Ca-like"]),
        ("198Hg I;mg i-iii", ["198Hg I", "mg i-iii"]),
    ],
)
def test_species_parsing(species, expected):
    """Test extracting the species information from a query URL.

    Note that `Ca-like` and `Sc-Fe`, are valid ways to query the NIST ASD Lines database, even though they may include many species.

    Since these queries will all return a `element` column, they should not prove too problematic for the cache, though may yield duplicates.
    """
    query_url = SpectraCache.nist_url + f"?spectra={species.replace(' ', '+').replace(';', '%3B')}&low_w=200&upp_w=900"
    assert extract_species(query_url) == expected


@pytest.mark.parametrize(
    "value_string,expected",
    [
        ("1e3", 1e3),
        ("+1e4", 1e4),
        ("1e+5", 1e5),
        ("1.2E-4", 1.2e-4),
        ("-9.98e-78", -9.98e-78),
        ("600d?", 600),
        ("(-1E3)", -1e3),
        (" 270d,bl(Fe I)?", 270),
        ("4*", 4),
    ],
)
def test_scientific_notation_expr(value_string, expected):
    expr = re.compile(SCI_EXPR)
    found = expr.search(value_string).group(1)
    assert float(found) == expected
