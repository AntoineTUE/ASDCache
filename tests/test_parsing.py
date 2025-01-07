import pytest
import re
import readasd.readASD as ASDCache


@pytest.mark.parametrize(
    "species,expected", [("H I", ["H+I"]), ("H I;O I-III", ["H+I", "O+I-III"]), ("Sc;Fe", ["Sc", "Fe"])]
)
def test_species_expr(nist_pandas, species, expected):
    query_url = nist_pandas.nist_url + f"?spectra={species.replace(' ','+').replace(';','%3B')}&low_w=200&upp_w=900"
    assert nist_pandas.species_expr.search(query_url).group(1).split("%3B") == expected


@pytest.mark.parametrize(
    "species,expected,intention", [("Sc-Fe", ["Sc-Fe"], ["Sc", "Fe"]), ("Ca-like", ["Ca-like"], ["Ca", "like"])]
)
def test_species_expr_unsupported(nist_pandas, species, expected, intention):
    """ "Though valid as input to the NIST ASD form, these are deliberately not considered valid input for parsing.

    This is because we cannot determine all included species that will be returned from the URL of the request.
    The request will still succeed and a result will thus be cached, with the appropriate hash.
    It is however not a case that is considered 'supported'.

    Since these queries will all return a `element` column, they should not prove too problematic.
    Because in these instances we do not parse the `-` as separator for element ionization state.
    """
    query_url = nist_pandas.nist_url + f"?spectra={species.replace(' ','+').replace(';','%3B')}&low_w=200&upp_w=900"
    assert nist_pandas.species_expr.search(query_url).group(1).split("%3B") == expected
    assert nist_pandas.species_expr.search(query_url).group(1).split("%3B") != intention


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
    expr = re.compile(r"([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)")
    found = expr.search(value_string).group(1)
    assert float(found) == expected


@pytest.mark.parametrize("url_part,expected", [("H+I", ("H", "I")), ("3H+I", ("3H", "I")), ("Fe+IV", ("Fe", "IV"))])
def test_extract_species_and_numeral_from_url(nist_pandas, url_part, expected):
    query_url = nist_pandas.nist_url + f"?spectra={url_part.replace(' ','+')}&low_w=200&upp_w=900"
    expr = re.compile(r"spectra=([\w\d]+)\+?([IVX]+)?")
    element, numeral = expr.search(query_url).groups()
    print(url_part, element, numeral)
    assert element == expected[0]
    assert numeral == expected[1]
