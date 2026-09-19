"""Module containing small helper utility functions for extracting and processing input from the ASD."""

import re
from typing import TYPE_CHECKING
from urllib import parse

if TYPE_CHECKING:
    from requests import Response

ROMAN_NUMERALS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(roman: str) -> int:
    """Parse a Roman numeral into an integer.

    Supports numerals up to "M".
    """
    roman = roman.upper().strip()
    total = 0
    previous = 0
    for char in reversed(roman):
        current_value = ROMAN_NUMERALS[char]
        if current_value < previous:
            total -= current_value  # Subtract if the current value is less than the previous value
        else:
            total += current_value
        previous = current_value
    return total


def wavenumber_to_refractive_index(wavenumbers: float) -> float:
    r"""Calculate the refractive index $n$ in air for a transition, using the 5-term Sellmeier formula used by NIST.

    The used Sellmeier formula is the one from E.R. Peck and K. Reeder [J. Opt. Soc. Am. 62, 958 (1972)](http://dx.doi.org/10.1364/JOSA.62.000958).

    This formula is fitted to data in the range of 185 nm to 1700 nm for  air at 15 °C, 101 325 Pa pressure, with 0.033 % CO2.

    This is the same formula used by the NIST ASD to calculate air wavelengths in the interval of 200 nm to 2000 nm.

    See also [the ASD documentation on the topic](https://physics.nist.gov/PhysRefData/ASD/Html/lineshelp.html#Conversion%20between%20air%20and%20vacuum%20wavelengths).

    Using this refractive index, air equivalent wavelengths consistent with the ASD can be calculated, without the need to query them separately.
    """
    sigma = wavenumbers * 1e-4  # um^-1
    return 1 + 1e-8 * (8060.51 + 2480990 / (132.274 - sigma**2) + 17455.7 / (39.32957 - sigma**2))


def extract_query_parameters(url_or_response: "str | Response") -> dict[str, str]:
    """Extract the query parameters from a url.

    Args:
        url_or_response (str,Response): Either a url string or Response-object

    Returns:
        params (dict[str,str]): a dictionary containing all query key-value pairs as strings.
    """
    query = parse.urlsplit(url_or_response if isinstance(url_or_response, str) else url_or_response.url).query
    params = dict(parse.parse_qsl(query))
    return params


def extract_spectra(url_or_response: "str | Response") -> list[tuple[str, tuple[float, ...]]]:
    """Extract a list of `(element,wavelength_range)` tuples from a url-string, or a Response.

    Each tuple contains an element string (e.g. `'H'`) and a tuple of `(minimum_wavelength, maximum_wavelength)`.

    The wavelength range limits are floats.

    Args:
        url_or_response (str,Response): Either a url string or Response-object

    """
    params = extract_query_parameters(url_or_response)
    wls = tuple(map(float, [params["low_w"], params["upp_w"]]))
    return [(name, wls) for name in params["spectra"].split(";")]


def extract_species(url_or_response: "str | Response") -> list[str]:
    """Extract the queried species (or in NIST terminology 'spectra') from a URL request for the NIST ASD.

    This will be a list of strings, looking like: `['H I','O I-III','All spectra','198Hg I']`

    For the NIST ASD Lines database, this corresponds to the `spectra` parameter.

    For the NIST ASD Levels database, this corresponds to the `spectrum` parameter, as it only supports single spectrum lookup.
    """
    params = extract_query_parameters(url_or_response)
    if "spectra" in params:
        return params["spectra"].split(";")
    # NIST Levels database only supports single spectrum
    return [params["spectrum"]]


def extract_state_from_response(url_or_response: "Response") -> tuple[str, int]:
    """Extract the element and ionization state from the url of a response.

    Only supports queries for a single species, i.e. `'H I'` is valid, but `'Ar I-III'` is not (3 species).

    When querying only a single state, e.g. 'H I', this information will not be present as a column in data: the `element` and `sp_num` columns will not be included.

    This information is parsed from the query url instead, so it can be added.

    Since the `sp_num` column is of an integer type, the roman numerals in the url are converted to integers.
    """
    species = extract_species(url_or_response)
    if len(species) > 1:
        raise ValueError("Must use a single-species query, but got %s", species)
    element, numeral = species[0].rsplit(" ", 1)
    numeric: int = roman_to_int(numeral) if numeral else 1
    return element, numeric
