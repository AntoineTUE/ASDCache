import pytest
import importlib.util

import pandas as pd
from numpy.testing import assert_almost_equal
from pandas.testing import assert_frame_equal as pandas_assert_frame_equal

# if importlib.util.find_spec("polars"):
import polars as pl
from polars.testing import assert_frame_equal as polars_assert_frame_equal
import re
from datetime import timedelta
from io import StringIO
from ASDCache import SpectraCache


def test_check_response_success(mock_response):
    assert SpectraCache._check_response_success(mock_response) is True


def test_check_response_status_not_ok(mock_response_status_not_OK):
    assert SpectraCache._check_response_success(mock_response_status_not_OK) is False


def test_check_response_contains_error(mock_response_HTML_in_content):
    assert SpectraCache._check_response_success(mock_response_HTML_in_content) is False


def test_from_pandas(mock_response):
    result = SpectraCache._from_pandas(mock_response)
    assert isinstance(result, pd.DataFrame)


def test_from_polars(mock_response):
    result = SpectraCache(use_polars_backend=True)._from_polars(mock_response)
    assert isinstance(result, pl.DataFrame)


def test_create_dataframe(mock_response):
    asd = SpectraCache(use_polars_backend=False)
    result = asd.create_dataframe(mock_response)
    assert isinstance(result, pd.DataFrame)

    # Test Polars backend
    asd_polars = SpectraCache(use_polars_backend=True)
    result_polars = asd_polars.create_dataframe(mock_response)
    assert isinstance(result_polars, pl.DataFrame)


@pytest.mark.full
def test_equivalent_result_for_backends(full_nist_backends):
    nist_pandas, nist_polars, interval, species = full_nist_backends
    df_all = nist_pandas.fetch(species, wl_range=interval)
    pdf_all = nist_polars.fetch(species, wl_range=interval)
    assert df_all.shape == pdf_all.shape
    polars_assert_frame_equal(pl.from_pandas(df_all), pdf_all)
    pandas_assert_frame_equal(pdf_all.to_pandas(), df_all)


@pytest.mark.full
def test_list_cached_species(full_nist_backends):
    nist_pandas, nist_polars, interval, species = full_nist_backends
    cached_species_pandas = nist_pandas.list_cached_species()
    cached_species_polars = nist_polars.list_cached_species()
    for cached in [cached_species_pandas, cached_species_polars]:
        assert len(cached) > 0
        assert species in cached


@pytest.mark.filterwarnings("ignore::pandas.errors.DtypeWarning")
@pytest.mark.full
def test_get_all_cached_pandas(full_nist_backends):
    nist_pandas, *_ = full_nist_backends
    df_all = nist_pandas.get_all_cached()
    assert df_all.shape[0] > 0
    assert df_all["element"].nunique() > 0


@pytest.mark.full
def test_get_all_cached_polars(full_nist_backends):
    _, nist_polars, *_ = full_nist_backends
    df_all = nist_polars.get_all_cached()
    assert df_all.shape[0] > 0
    assert df_all["element"].n_unique() > 0
