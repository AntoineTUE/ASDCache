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
from pandas.testing import assert_frame_equal as pandas_assert_frame_equal
from polars.testing import assert_frame_equal as polars_assert_frame_equal

from ASDCache import SpectraCache
from ASDCache.ASDCache import ASDSchema


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
    assert list(result.columns) == list(ASDSchema)


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
    """Trivial test to check if the test cache is set up"""
    assert cache_location == Path(__file__).parent.joinpath("test_cache.sqlite").resolve()
    nist_pandas = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    assert len(nist_pandas.cached_species) == 4
    queries = {
        v["spectra"][0]: (v["low_w"][0], v["upp_w"][0])
        for v in [parse.parse_qs(u.split("?")[1]) for u in nist_pandas.session.cache.urls()]
    }
    assert queries["All spectra"] == ("550", "580")
    assert queries["Kr I"] == ("170", "1000")
    assert queries["H I"] == ("170", "1000")
    assert queries["Ar I-II"] == ("170", "1000")


@pytest.mark.parametrize("species", [("All spectra", (550, 580)), ("Kr I",), ("H I",), ("Ar I-II",)])
def test_equivalent_result_for_backends(cache_location, species):
    nist_pandas = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    nist_polars = SpectraCache(use_polars_backend=True, cache_path=cache_location, cache_expiry=-1)
    df_all = nist_pandas.fetch(*species)
    pdf_all = nist_polars.fetch(*species)
    polars_as_pandas = pdf_all.to_pandas()
    pandas_as_polars = pl.from_pandas(df_all)
    assert df_all.shape == pdf_all.shape
    pandas_assert_frame_equal(polars_as_pandas, df_all)
    # assert_schema_equal(pandas_as_polars.schema, pdf_all.schema)  # experimental and not supported on python 3.9
    # Treatment of nan/null differs between polars and pandas; replace all NaN for Null for this check.
    # Else the column 'obs_wl_air(nm)' seems to give issues, despite having equivalent content with np.testing.assert_equal
    polars_assert_frame_equal(pandas_as_polars, pdf_all.fill_nan(None))


def test_list_cached_species(cache_location):
    nist_pandas = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    nist_polars = SpectraCache(use_polars_backend=True, cache_path=cache_location, cache_expiry=-1)
    cached_species_pandas = nist_pandas.list_cached_species()
    cached_species_polars = nist_polars.list_cached_species()
    assert cached_species_pandas == cached_species_polars
    for cached in [cached_species_pandas, cached_species_polars]:
        assert len(cached) > 0
        for species in ["Kr I", "Ar I-II", "H I", "All spectra"]:
            assert species in cached


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
