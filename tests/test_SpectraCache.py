import pytest
import importlib

import pandas as pd
from numpy.testing import assert_almost_equal

if importlib.util.find_spec("polars"):
    import polars as pl

    WITH_POLARS = True
else:
    WITH_POLARS = False
import re
from datetime import timedelta
from io import StringIO
from requests_cache import CachedSession
from ASDCache import SpectraCache


def test_check_response_success(mock_response):
    assert SpectraCache._check_response_success(mock_response) is True


def test_check_response_status_not_200(mock_response_status_not_200):
    assert SpectraCache._check_response_success(mock_response_status_not_200) is False


def test_check_response_contains_error(mock_response_error_in_content):
    assert SpectraCache._check_response_success(mock_response_error_in_content) is False


def test_from_pandas(mock_response):
    result = SpectraCache._from_pandas(mock_response)
    assert isinstance(result, pd.DataFrame)


def test_from_polars(mock_response):
    print(WITH_POLARS, importlib.util.find_spec("polars"))
    result = SpectraCache(use_polars_backend=True)._from_polars(mock_response)
    assert isinstance(result, pl.DataFrame)


def test_create_dataframe(mock_response):
    asd = SpectraCache(use_polars_backend=False)
    result = asd.create_dataframe(mock_response)
    assert isinstance(result, pd.DataFrame)

    # Test Polars backend
    if WITH_POLARS:
        asd_polars = SpectraCache(use_polars_backend=True)
        result_polars = asd_polars.create_dataframe(mock_response)
        assert isinstance(result_polars, pl.DataFrame)


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
    result = SpectraCache.roman_to_int(roman)
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
    assert round(1e7 / wavenumber / SpectraCache.wn_to_n_refractive(wavenumber), decimals) == air_equivalent


@pytest.mark.parametrize(
    "wavenumber, air_equivalent",
    [
        (124554.9, 80.2859),  # Ar I
        (93750.6, 106.6660),  # Ar I
        (82259.16, 121.56701),  # H I
    ],
)
def test_wn_to_lambda_air_not_valid(wavenumber, air_equivalent):
    """ "In this case the values are outside of the validity range of the used Sellmeier equation.
    This range is 185-1700 nm (fit range of source paper), or 5000 - 50000 cm^-1 (ASD convention).
    The ASD will report/fall back to vacuum wavelengths.
    For values below 185, $n$ tends to be !=1, thus values will deviate."""
    decimals = len(str(air_equivalent).split(".")[1])
    assert round(1e7 / wavenumber / SpectraCache.wn_to_n_refractive(wavenumber), decimals) != air_equivalent


@pytest.mark.full
def test_equivalent_result_for_backends(full_nist_backends):
    nist_pandas, nist_polars, interval = full_nist_backends
    df_all = nist_pandas.fetch("All spectra", wl_range=interval)
    pdf_all = nist_polars.fetch("All spectra", wl_range=interval)
    assert df_all.shape == pdf_all.shape
    for col in df_all.columns:
        if df_all[col].dtype != object:
            assert_almost_equal(pdf_all[col].to_numpy(), df_all[col].to_numpy())
        else:
            assert (df_all[col].fillna("").to_numpy() == pdf_all.select(pl.col(col).fill_null("")).to_numpy().T).all()


@pytest.mark.full
def test_list_cached_species(full_nist_backends):
    nist_pandas, nist_polars, interval = full_nist_backends
    cached_species_pandas = nist_pandas.list_cached_species()
    cached_species_polars = nist_polars.list_cached_species()
    for cached in [cached_species_pandas, cached_species_polars]:
        assert len(cached) > 0
        assert "All spectra" in cached


@pytest.mark.filterwarnings("ignore::pandas.errors.DtypeWarning")
@pytest.mark.full
def test_get_all_cached_pandas(full_nist_backends):
    nist_pandas, _, interval = full_nist_backends
    df_all = nist_pandas.get_all_cached()
    assert df_all.shape[0] > 0
    assert df_all["element"].nunique() > 0


@pytest.mark.full
def test_get_all_cached_polars(full_nist_backends):
    _, nist_polars, interval = full_nist_backends
    df_all = nist_polars.get_all_cached()
    assert df_all.shape[0] > 0
    assert df_all["element"].n_unique() > 0
