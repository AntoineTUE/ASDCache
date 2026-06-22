"""Tests for the LevelCacheAccessor class that handles the NIST ASD Energy Level Database."""

import polars as pl
import pytest
from pandas.testing import assert_frame_equal as pandas_assert_frame_equal
from polars.testing import assert_frame_equal as polars_assert_frame_equal

from ASDCache import SpectraCache


def test_accessor_linked_to_parent(cache_location):
    cache = SpectraCache(cache_path=cache_location, cache_expiry=-1)

    assert cache.use_polars == cache.levels.use_polars
    cache.use_polars = True
    assert cache.use_polars
    assert cache.use_polars == cache.levels.use_polars

    with pytest.raises(AttributeError):  # Avoid matching regex, as it is different between python versions.
        cache.levels.use_polars = False

    assert cache.session == cache.levels.session


def test_list_cached_species(cache_location):
    cache_pandas = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    cached_species = cache_pandas.levels.list_cached_species()
    assert set(cached_species) == {"H I", "Sn II", "Ti I"}


@pytest.mark.parametrize("species", [("H I"), ("Sn II"), ("Ti I")])
def test_equivalent_results_for_backends(cache_location, species):
    cache_pandas = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    cache_polars = SpectraCache(use_polars_backend=True, cache_path=cache_location, cache_expiry=-1)
    df_pandas = cache_pandas.levels.fetch(species)
    df_polars = cache_polars.levels.fetch(species)
    polars_as_pandas = df_polars.to_pandas()
    pandas_as_polars = pl.from_pandas(df_pandas)

    assert df_pandas.shape == df_polars.shape
    pandas_assert_frame_equal(polars_as_pandas, df_pandas)
    # Treatment of nan/null differs between polars and pandas; replace all NaN for Null for this check.
    polars_assert_frame_equal(pandas_as_polars, df_polars.fill_nan(None))
