import pytest

from ASDCache.utils import roman_to_int, wavenumber_to_refractive_index, extract_state_from_response


@pytest.mark.parametrize(
    "roman, expected",
    [
        ("I", 1),
        ("V", 5),
        ("X", 10),
        ("IV", 4),
        ("IX", 9),
        ("XX", 20),
    ],
)
def test_roman_to_int(roman, expected):
    result = roman_to_int(roman)
    assert result == expected


@pytest.mark.parametrize(
    "wavenumber,air_equivalent",
    [
        (31237.4, 320.037),  # Ar I
        (8099.284, 1234.3393),  # Ar I
        (6252.40, 1598.949),  # Ar I
        (10217.441, 978.4503),  # Ar I
    ],
)
def test_wn_to_lambda_air(wavenumber, air_equivalent):
    decimals = len(str(air_equivalent).split(".")[1])
    assert round(1e7 / wavenumber / wavenumber_to_refractive_index(wavenumber), decimals) == air_equivalent


@pytest.mark.parametrize(
    "wavenumber, air_equivalent",
    [
        (124554.9, 80.2859),  # Ar I
        (93750.6, 106.6660),  # Ar I
        (82259.16, 121.56701),  # H I
    ],
)
def test_wn_to_lambda_air_not_valid(wavenumber, air_equivalent):
    """In this case the values are outside of the validity range of the used Sellmeier equation.
    This range is 185-1700 nm (fit range of source paper), or 5000 - 50000 cm^-1 (ASD convention).
    The ASD will report/fall back to vacuum wavelengths.
    For values below 185, $n$ tends to be !=1, thus values will deviate."""
    decimals = len(str(air_equivalent).split(".")[1])
    assert round(1e7 / wavenumber / wavenumber_to_refractive_index(wavenumber), decimals) != air_equivalent


class MockResponse:
    def __init__(self, url: str):
        self.url = url


@pytest.mark.parametrize("url_part, expected", [("H+I", ("H", 1)), ("3H+I", ("3H", 1)), ("Fe+IV", ("Fe", 4))])
def test_extract_state_from_response(url_part, expected):
    query_url = f"https://physics.nist.gov/cgi-bin/ASD/lines1.pl?spectra={url_part}&low_w=200&upp_w=900"
    response = MockResponse(query_url)
    element, numeric = extract_state_from_response(response)
    assert element == expected[0]
    assert numeric == expected[1]
