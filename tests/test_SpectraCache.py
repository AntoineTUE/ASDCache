import importlib.util
import re
from datetime import timedelta
from io import StringIO
from pathlib import Path
from urllib import parse

import pandas as pd
import polars as pl
import pytest
from numpy.testing import assert_almost_equal
from pandas.testing import assert_frame_equal as pandas_equal
from polars.testing import assert_frame_equal as polars_equal

from ASDCache import SpectraCache
from ASDCache.Schemas import ASDLineOutputSchema


def test_check_response_success(example_response):
    assert SpectraCache._check_response_success(example_response) is True
    assert example_response.expires is None
    assert example_response.from_cache


def test_check_response_status_not_ok(mock_response_status_not_OK):
    assert SpectraCache._check_response_success(mock_response_status_not_OK) is False


def test_check_response_contains_error(mock_response_HTML_in_content):
    assert SpectraCache._check_response_success(mock_response_HTML_in_content) is False


def test_from_pandas(example_response):
    result = SpectraCache._from_pandas(example_response)
    assert isinstance(result, pd.DataFrame)
    assert result.shape[0] > 0
    assert list(result.columns) == list(ASDLineOutputSchema.names)


def test_from_polars(example_response):
    result = SpectraCache(use_polars_backend=True)._from_polars(example_response)
    assert isinstance(result, pl.DataFrame)
    assert result.shape[0] > 0
    # assert_schema_equal(result.schema, pl.schema.Schema(ASDSchema)) # experimental and not supported on python 3.9


def test_create_dataframe(example_response):
    asd = SpectraCache(use_polars_backend=False, cache_expiry=-1)
    result = asd.create_dataframe(example_response)
    assert isinstance(result, pd.DataFrame)

    # Test Polars backend
    asd_polars = SpectraCache(use_polars_backend=True, cache_expiry=-1)
    result_polars = asd_polars.create_dataframe(example_response)
    assert isinstance(result_polars, pl.DataFrame)


def test_cache_setup(cache_location):
    """Trivial test to check if the test cache is set up.

    This checks if the expected species in the expected intervals are present.

    If this test fails, either the contents of the `test_cache` file have been altered, or the test configuration is changed.

    In either case, this warrants checking.
    """
    assert cache_location == Path(__file__).parent.joinpath("test_cache.sqlite").resolve()
    nist_pandas = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    assert len(nist_pandas.cached_species) == 4
    queries = {
        v["spectra"][0]: (v["low_w"][0], v["upp_w"][0])
        for v in [parse.parse_qs(u.url.split("?")[1]) for u in nist_pandas.responses]
    }
    assert queries["All spectra"] == ("550", "580")
    assert queries["Kr I"] == ("170", "1000")
    assert queries["H I"] == ("170", "1000")
    assert queries["Ar I-II"] == ("170", "1000")


@pytest.mark.parametrize("species", [("All spectra", (550, 580)), ("Kr I",), ("H I",), ("Ar I-II",)])
def test_equivalent_result_for_backends_with_pandas(cache_location, species):
    cache = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    response = cache._get_data(*species)
    df_pandas = cache._from_pandas(response)
    df_polars = cache._from_polars(response)
    polars_as_pandas = df_polars.to_pandas()
    assert df_pandas.shape == df_polars.shape
    pandas_equal(polars_as_pandas, df_pandas)


@pytest.mark.parametrize("species", [("All spectra", (550, 580)), ("Kr I",), ("H I",), ("Ar I-II",)])
def test_equivalent_result_for_backends_with_polars(cache_location, species):
    cache = SpectraCache(use_polars_backend=True, cache_path=cache_location, cache_expiry=-1)
    response = cache._get_data(*species)
    df_pandas = cache.levels._from_pandas(response)
    df_polars = cache.levels._from_polars(response)
    pandas_as_polars = pl.from_pandas(df_pandas)
    assert df_pandas.shape == df_polars.shape
    # assert_schema_equal(pandas_as_polars.schema, pdf_all.schema)  # experimental and not supported on python 3.9
    polars_equal(pandas_as_polars, df_polars)


def test_list_cached_species(cache_location):
    nist = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    cached = nist.list_cached_species()
    assert len(cached) == 4
    for species in ["Kr I", "Ar I-II", "H I", "All spectra"]:
        assert species in cached


def test_cached_spectra(cache_location):
    """Test if the set of cached species matches what we expect in the test cache file."""
    nist = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    cached = nist.cached_spectra
    assert len(cached) == 4
    for spectrum in [
        ("Kr I", (170.0, 1000.0)),
        ("H I", (170.0, 1000.0)),
        ("Ar I-II", (170.0, 1000.0)),
        ("All spectra", (550.0, 580.0)),
    ]:
        assert spectrum in cached


@pytest.mark.filterwarnings("ignore::pandas.errors.DtypeWarning")
def test_get_all_cached_pandas(cache_location):
    nist_pandas = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    df_all = nist_pandas.get_all_cached()
    assert df_all.shape[0] > 0
    assert df_all["element"].nunique() > 0


def test_get_all_cached_polars(cache_location):
    nist_polars = SpectraCache(use_polars_backend=True, cache_path=cache_location, cache_expiry=-1)
    assert len(nist_polars.cached_species) == 4
    df_all = nist_polars.get_all_cached()
    assert df_all.shape[0] > 0
    assert df_all["element"].n_unique() > 0


@pytest.mark.online
@pytest.mark.parametrize("species", [("Kr I", (500, 600)), ("H I", (600, 700))])
def test_online_lookup(cache_location, species):
    """Test that has to do an online lookup against the NIST ASD.

    Once complete, the entry is removed from the cache to avoid pollution.

    The goal of this test is to still have a way to validate if we remain compatible with the ASD form.

    It does not seem like breaking changes to the backend are communicated on the website.

    This test should only perform lookups of small data samples to avoid server load or latency issues.

    These test can be deselected by using `pytest -m "not online"` or equivalent.
    """
    nist_pandas = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    already_cached = set(nist_pandas.session.cache.responses)
    nist_pandas.fetch(*species)
    for key in set(nist_pandas.session.cache.responses) - already_cached:
        nist_pandas.session.cache.delete(key)
