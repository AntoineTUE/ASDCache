"""Tests for the LevelCacheAccessor class that handles the NIST ASD Energy Level Database."""

import polars as pl
import pytest
from pandas.testing import assert_frame_equal as pandas_equal
from polars.testing import assert_frame_equal as polars_equal

from ASDCache import SpectraCache
from ASDCache.arrow import map_arrow_to_pandas_types


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
def test_equivalent_results_for_backends_with_pandas(cache_location, species):
    """Test if several different real examples can be parsed reliably and consistently between pandas and polars.

    Here we test if conversion to a pandas dataframe yields the same dataframe as pandas itself.

    Note: The pandas dataframes use pyarrow-backed types, providing consisten nan/null handling.
    """
    cache = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    response = cache.levels._get_data(species)
    df_pandas = cache.levels._from_pandas(response)
    df_polars = cache.levels._from_polars(response)
    polars_as_pandas = df_polars.to_pandas(types_mapper=map_arrow_to_pandas_types)

    assert df_pandas.shape == df_polars.shape
    pandas_equal(polars_as_pandas, df_pandas)


@pytest.mark.parametrize("species", [("H I"), ("Sn II"), ("Ti I")])
def test_equivalent_results_for_backends_with_polars(cache_location, species):
    """Test if several different real examples can be parsed reliably and consistently between pandas and polars.

    Here we test if conversion to a polars dataframe yields the same dataframe as polars itself.

    Note: The pandas dataframes use pyarrow-backed types, providing consisten nan/null handling.
    """
    cache = SpectraCache(use_polars_backend=True, cache_path=cache_location, cache_expiry=-1)
    response = cache.levels._get_data(species)
    df_pandas = cache.levels._from_pandas(response)
    df_polars = cache.levels._from_polars(response)
    pandas_as_polars = pl.DataFrame(df_pandas)

    assert df_pandas.shape == df_polars.shape
    polars_equal(pandas_as_polars, df_polars)
