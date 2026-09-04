# ty:ignore[unresolved-attribute]
"""Module containing mixins for handling the cache."""

import importlib.util
from datetime import timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from requests import Response
from requests_cache import CachedSession

if importlib.util.find_spec("polars"):
    POLARS_AVAILABLE = True
    import polars as pl
else:
    POLARS_AVAILABLE = False

from ._version import version
from .arrow import map_arrow_to_pandas_types
from .utils import extract_species


class GenericCacheMixin:
    """Base mixin for cache handling that provides cache management utilities for ASDCache classes, to be used as a parent class for other mixins.

    It exposes functionality to control cache expiration, response retrieval and cache clearing.

    Implementing classes are expected to provide:

    * a suitable `CachedSession` object as `self.session`

    * a string attribute `self.nist_url` that contains the base url of the NIST ASD
    """

    def _build_query(self, standard_query: dict[str, str], **kwargs):
        query_params = standard_query.copy()
        query_params.update(**kwargs)
        return query_params

    def set_cache_expiry(self, new: Optional[timedelta] = None, **kwargs):
        """Set the cache expiry to a different interval.

        Can be done by either passing in a `timedelta` object, or valid keyword arguments for `timedelta` itself.

        If no arguments are provided, the default expiry time of 2 weeks is used.

        Example:
            ```python
            # set expiry to 3 days
            cache = ...
            cache.set_cache_expiry(timedelta(days=3))
            cache.set_cache_expiry(days=3)
            cache.cache_expiry = timedelta(days=3)  # only accepts a timedelta
            ```
        """
        if not isinstance(new, timedelta):
            kwargs = kwargs if len(kwargs) > 0 else {"weeks": 2}
            new = timedelta(**kwargs)
        self.session.settings.expire_after = new

    @property
    def cache_expiry(self) -> timedelta:
        """The cache expiry time.

        Queries that are older than this time are considered stale and marked for updating, by quering the NIST ASD.
        In case the query for new data fails, the stale, cached response will still be parsed.
        """
        return self.session.settings.expire_after

    @cache_expiry.setter
    def cache_expiry(self, new: timedelta):
        """Set the cache expiry to a different interval.

        Can be done by either passing in a `timedelta` object, or valid keyword arguments for `timedelta` itself.
        """
        if not isinstance(new, timedelta):
            raise TypeError(f"Expected a timedelta object, got {type(new)} instead.")
        self.set_cache_expiry(new)

    @property
    def responses(self):
        """Generator yielding responses from the cache that contain line data.

        Usefull to loop over all responses, while avoiding to load them all in memory.

        Example:
            ```python
            cache = SpectraCache()
            for response in cache:
                df = cache.create_dataframe(response)
                ...
            ```
        """
        yield from (r for r in self.session.cache.filter() if self.nist_url in r.url)

    def clear_cache(self):
        """Clear responses from the cache.

        This will remove all responses from the cache that belong to the corresponding cache class.

        Any response that belongs to a different type of cache (such as bibliographic responses, in case of a SpectraCache) will not be removed.
        """
        self.session.cache.delete(*(r.cache_key for r in self.responses))

    @property
    def cache_path(self) -> Path:
        """The path to the cache database file."""
        return self.session.cache.db_path


class CacheSessionMixin(GenericCacheMixin):
    """Mixin that initializes and manages a persistent cache of NIST ASD responses.

    Creates a `CachedSession` object under the `session` attribute, which is the entry point for all requests to the NIST ASD.

    Implementing classes are expected to provide:

    * a `self.nist_url` string attribute that contains the base url of the NIST ASD

    * a `self._check_response_success` method that checks if a response is successful and can be cached.
    """

    def __init__(self, *args, cache_expiry=timedelta(weeks=2), cache_path: Optional[Path] = None, **kwargs):
        """Instantiate a standalone cache.

        Args:
            cache_expiry (timedelta, optional): The expiry time for cached responses. Defaults to 2 weeks.
            cache_path (Path, optional): The path to the cache directory. If None, a default path is used. Defaults to None.
        """
        # `filter_fn` keeps responses with errors out of the cache, error must still be raised
        self.session = CachedSession(
            "NIST_ASD_cache" if cache_path is None else cache_path,
            use_cache_dir=True,
            expire_after=cache_expiry,
            stale_if_error=True,
            filter_fn=self._check_response_success,
        )
        self.session.stream = True
        self.session.headers.update({"User-Agent": f"ASDCache/{version}"})
        super().__init__(*args, **kwargs)


class CacheAccessorMixin(GenericCacheMixin):
    """Mixin providing access to a parent cache instance.

    A CacheAccessor does not create or own its own cache session.

    Instead, it reuses the `CachedSession` instance from a parent object that inherits from [CacheSessionMixin][(m).].

    This allows CacheAccessor classes to share the same cache configuration, expiration settings, and storage backend as the parent cache object.
    """

    def __init__(self, parent, *args, **kwargs):
        """Initialize the cache accessor.

        Args:
            parent (CacheSessionMixin): The parent cache instance from which to access the cache session.
            *args: Additional positional arguments to pass to the parent class.
            **kwargs: Additional keyword arguments to pass to the parent class.

        Raises:
            TypeError: If the `parent` argument is not an instance of [CacheSessionMixin][(m).].
        """
        if not isinstance(parent, CacheSessionMixin):
            raise TypeError(f"parent must be an instance of CacheSessionMixin, got {type(parent)} instead.")
        self.parent = parent
        super().__init__(*args, **kwargs)

    @property
    def session(self) -> CachedSession:
        """Reference to the parent's cache session."""
        return self.parent.session

    @property
    def use_polars(self) -> bool:
        """Flag if `polars` is to be used, if present in the environment."""
        return self.parent.use_polars


class DataHandlerMixin:
    """Mixin providing data extraction and DataFrame conversion utilities, for classes that handle parsing data from the NIST ASD databases.

    It adds functionality to convert from [pyarrow.Table][pyarrow.Table] to either [pandas.DataFrame][pandas.DataFrame] or [polars.DataFrame](https://docs.pola.rs/api/python/stable/reference/dataframe/index.html#dataframe), depending on the `use_polars` attribute.

    Implementing classes are expected to provide:

    * `session`: A cache-enabled session object.

    * `nist_url`: The ASD endpoint associated with the cache.

    * `_parse_response()`: class method that converts a response into an Apache Arrow table.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the data handler mixin."""
        self._use_polars = kwargs.pop("use_polars_backend", False) and POLARS_AVAILABLE
        super().__init__(*args, **kwargs)

    @property
    def use_polars(self):
        """Flag if `polars` is to be used, if present in the environment."""
        return self._use_polars

    @use_polars.setter
    def use_polars(self, value: bool):
        if value and not POLARS_AVAILABLE:
            raise ImportError("polars is not installed in the environment, cannot set use_polars to True.")
        self._use_polars = value

    @property
    def cached_species(self) -> list[str]:
        """A list of all cached species for which energy levels have been cached."""
        return self.list_cached_species()

    def list_cached_species(self) -> list[str]:
        """List all species in the cache, for which energy level information is stored.

        This is determined based on the string of the original query URL.
        """
        species = []
        for u in self.session.cache.urls():
            if self.nist_url in u:
                species.extend(extract_species(u))
        return species

    @classmethod
    def _from_pandas(cls, response) -> "pd.DataFrame":
        """Process a response into a DataFrame using pandas, with datatypes backed by pyarrow."""
        return cls._parse_response(response).to_pandas(types_mapper=map_arrow_to_pandas_types)

    @classmethod
    def _from_polars(cls, response) -> "pl.DataFrame":
        """Process a response into a DataFrame using polars."""
        return pl.from_arrow(cls._parse_response(response))  # ty:ignore[invalid-return-type]

    def create_dataframe(self, response: Response) -> "pd.DataFrame|pl.DataFrame":
        """Create a dataframe from the (cached) NIST ASD response.

        Will decide on the backend to use based on the `use_polars` attribute.

        Will check that it is processing the correct type of response, based on the `nist_url` attribute.

        Note:
            If `polars` is not installed in the environment, the `use_polars` attribute will always be `False`.
        """
        if not response.url.startswith(self.nist_url):
            msg = f"Invalid response, only the {self.nist_url} endpoint is supported, got {response.url}"
            raise ValueError(msg)
        if self.use_polars:
            return self._from_polars(response)
        return self._from_pandas(response)
