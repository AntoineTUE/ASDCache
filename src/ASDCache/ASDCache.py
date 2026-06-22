"""The ASDCache module.

It contains both the [SpectraCache][(m).] and [BibCache][(m).] classes which allow you to interact with the ASD and the relevant bibliographic databases.
"""

import importlib.util
import logging
import re
import sys
import warnings
from datetime import timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Optional, Union
from urllib import parse

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from requests import Response
from requests_cache import CachedResponse, CachedSession, OriginalResponse

if importlib.util.find_spec("polars"):
    POLARS_AVAILABLE = True
    import polars as pl
else:
    POLARS_AVAILABLE = False

from ._version import version
from .utils import extract_species, extract_state_from_response, wavenumber_to_refractive_index

logger = logging.getLogger("ASDCache")

ASDSchema: dict[str, type] = {
    "element": str,
    "sp_num": int,
    "obs_wl_vac(nm)": float,
    "unc_obs_wl": float,
    "obs_wl_air(nm)": float,
    "ritz_wl_vac(nm)": float,
    "unc_ritz_wl": float,
    "ritz_wl_air(nm)": float,
    "wn(cm-1)": float,
    "intens": float,
    "Aki(s^-1)": float,
    "fik": float,
    "S(a.u.)": float,
    "log_gf": float,
    "Acc": str,
    "Ei(cm-1)": float,
    "Ek(cm-1)": float,
    "conf_i": str,
    "term_i": str,
    "J_i": str,
    "conf_k": str,
    "term_k": str,
    "J_k": str,
    "g_i": float,
    "g_k": float,
    "Type": str,
    "tp_ref": str,
    "line_ref": str,
}
"""Schema enforced by [SpectraCache][..]."""

ASDLevelSchema: dict[str, type] = {
    "element": str,
    "sp_num": int,
    "Configuration": str,
    "Term": str,
    "J": float,
    "g": float,
    "Level (cm-1)": float,
    "Uncertainty (cm-1)": float,
    "Splitting": float,
    "Lande": float,
    "L": float,
    "Level comment": str,
    "Ionization limit": bool,
    "Reference": str,
    "Leading percentages": str,
}
"""Schema enforced by [LevelCacheAccessor][..]."""

SCI_EXPR = r"([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)"
"""Regex pattern for processing scientific notation"""


class ASDQueryError(Exception):
    """Exception raised when the NIST ASD has indicated an error with a query."""


class SpectraCache:
    """A class acting as the entrypoint to retrieve data from the NIST Atomic Spectra Database that uses caching.

    The `SpectraCache` instance acts as an access point to the cache, which stores responses on the local system in a SQLite database.

    Data retrieval from cache is much faster (order milliseconds) than fetching from the internet (order of seconds to minutes), and avoids wastefull requests to the server.

    Cache time-to-live is two weeks by default.

    Since the NIST ASD is usually updated less frequently than that, this is a compromise between having the latest data, and overall fast performance.

    Note that the same cache is shared across different class-instances, thread-safety is not guaranteed.

    Example:
        ```python
        from ASDCache import SpectraCache
        asd = SpectraCache()
        df_lines_oxygen = asd.fetch("O I-III")
        ```
    """

    nist_url = "https://physics.nist.gov/cgi-bin/ASD/lines1.pl"
    query_params = {
        "submit": "Retrieve Data",
        "unit": "1",
        "de": "0",
        "I_scale_type": "1",
        "format": "3",
        "line_out": "0",
        "en_unit": "0",
        "output": "0",
        "bibrefs": "1",
        "show_obs_wl": "1",
        "show_calc_wl": "1",
        "show_wn": "1",
        "unc_out": "1",
        "order_out": "0",
        "show_av": "3",  # 3: wavelength in vac, 2: wavelength in air
        "tsb_value": "0",
        "A_out": "0",
        "S_out": "on",
        "f_out": "on",
        "loggf_out": "on",
        "intens_out": "on",
        "conf_out": "on",
        "term_out": "on",
        "enrg_out": "on",
        "J_out": "on",
        "g_out": "on",
        # "diag_out": "on",  # avoid diagnostic data, it leads to multi-species queries failing; which can appear as if keys below are needed. See issue #1
        "allowed_out": "1",
        "forbid_out": "1",
        "output_type": "0",
        # "show_diff_obs_calc": 1, # Does not appear mandatory in retrospect,  see issue #1
        # "include_Ritz_E1": 1, # Does not appear mandatory in retrospect,  see issue #1
    }
    """Request parameters used by the NIST ASD Lines form."""

    def __init__(
        self, use_polars_backend=False, cache_expiry=timedelta(weeks=2), cache_path: Optional[Path] = None, **kwargs
    ):
        """Initialize an instance that handles cached data lookup of the NIST ASD.

        Args:
            use_polars_backend (bool): Flag to use polars as DataFrame backend, if available
            cache_expiry (timedelta): Span of time beyond which an entry will be considered expired, and a refresh attempted. Use `-1` to disable expiry.
            cache_path (Path, Optional): Path to a location to store the cache in
        """
        if "strict_matching" in kwargs:
            print("The `strict_matching` kwargs has been deprecated")
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
        if (use_polars_backend) and (not POLARS_AVAILABLE):
            warnings.warn("Cannot find `polars` as a backend, falling back to `pandas`", stacklevel=2)
            self.use_polars = False
        else:
            self.use_polars = use_polars_backend
        self.levels = LevelCacheAccessor(self)
        """Accessor for ASD Energy Level database queries."""

    @property
    def cache_expiry(self) -> timedelta:
        """The cache expiry time.

        Queries that are older than this time are considered stale and marked for updating, by quering the NIST ASD.
        In case the query for new data fails, the stale, cached response will still be parsed.
        """
        return self.session.settings.expire_after

    def set_cache_expiry(self, new: Optional[timedelta] = None, **kwargs):
        """Set the cache expiry to a different interval (default: 1 week).

        Can be done by either passing in a `timedelta` object, or valid keyword arguments for `timedelta` itself.
        """
        if new is None:
            new = timedelta(**kwargs)
        self.session.settings.expire_after = new

    @staticmethod
    def _check_response_success(response: Response) -> bool:
        """Validate that data has been fetched succesfully.

        If this check fails, the cache should not update with this response, even when marked as stale.

        The first obvious way to check success is if an error is indicated by the HTTP status code.

        However, when a query for data is incorrect, the NIST ASD returns a HTML page indicating `<title>NIST ASD : Input Error</title>` in the `<head>` tag, or "Error Message".

        A successfull query would not receive HTML as a response, but raw ASCII values instead.

        We can thus check for the start of a HTML document.

        Note that this only works for data queries, not for bibliographic metadata by [BibCache][(m).].
        """
        return not (not response.ok or response.content.startswith(b"<!DOCTYPE"))

    @staticmethod
    def _parse_nist_error_message(response):
        body = BeautifulSoup(response.text, features="html.parser").text
        reason = body.strip().replace("\n", "") if body else ""
        return reason

    def _build_query(self, standard_query: dict[str, str], **kwargs):
        query_params = standard_query.copy()
        query_params.update(**kwargs)
        return query_params

    def _get_data(
        self, species: str, wl_range: tuple[float, float] = (170, 1000), throw_on_error=True, **kwargs
    ) -> Response:
        """Retrieve raw, ASCII-formatted data from the NIST ASD with a GET request.

        To retrieve data and parse it into a DataFrame, use [fetch][..] instead.

        Returns the raw response, which will be cached if it contains valid data (see [_check_response_success][..]).

        If the response does not contain ASCII data, but HTML instead, an [ASDQueryError][(m).] will be raised.

        It is possible to override any standard query parameter (see [query_params][..]]) by passing them as kwargs.
        """
        query_params = self._build_query(
            self.query_params, spectra=species, low_w=min(wl_range), upp_w=max(wl_range), **kwargs
        )
        response: Response = self.session.get(self.nist_url, params=query_params)
        response.raise_for_status()
        # Check if response is not a HTML document instead of ASCII formatted data, indicating query error.
        if not self._check_response_success(response) and throw_on_error:
            reason = self._parse_nist_error_message(response)
            logger.error(
                "NIST ASD responded with %s instead of ASCII-data for species=%s, wl_range=%s\nQuery: %s",
                reason,
                species,
                wl_range,
                response.url,
            )
            raise ASDQueryError(
                f"Query for {species=} {wl_range=} did not receive ASCII-data. {reason=} This means the ASD could not interpret your query. Check if your query is malformed."
            )
        return response

    @property
    def cached_species(self) -> list[str]:
        """A list of all cached species."""
        return self.list_cached_species()

    def list_cached_species(self) -> list[str]:
        """List all species in the cache, based on the string of the original query URL."""
        species = []
        for u in self.session.cache.urls():
            if self.nist_url in u:
                species.extend(extract_species(u))
        return species

    @property
    def responses(self):
        """Generator yielding responses from the cache that contain line data.

        Usefull to loop over all responses, while avoiding to load them all in memory.

        Example
            ```python
            cache = SpectraCache()
            for response in cache:
                df = cache.create_dataframe(response)
                ...
            ```
        """
        yield from (r for r in self.session.cache.filter() if self.nist_url in r.url)

    def fetch(self, species, wl_range=(170, 1000)) -> "pd.DataFrame|pl.DataFrame":
        """Fetch information on a species from the ASD and return it as a DataFrame, first checking the cache.

        This supports loading multiple species in one go by using the same notation as the NIST ASD form.

        Note however that cache keys are computed for unique options for `species` and `wl_range`.

        This means that you won't get caching benefits by using different queries.

        In other words: the cache cannot deduplicate queries such as `ASD.fetch('H', (200,1000))` followed by `ASD.fetch('H I', (650,660))` (or vice versa).

        Both these operations will fetch data online and be stored as separate cache entries.

        Likewise, when you first query "All spectra", and later "Ar I-II", the latter will not use the previously cached data.
        """
        # TODO: add kwargs for read-only/offline access etc.
        response = self._get_data(species, wl_range)
        return self.create_dataframe(response)

    def create_dataframe(self, response) -> "pd.DataFrame|pl.DataFrame":
        """Create a dataframe from the (cached) NIST ASD response, using the chosen backend at class instantiation."""
        if self.use_polars:
            return self._from_polars(response)
        return self._from_pandas(response)

    @classmethod
    def _from_pandas(cls, response: Response) -> "pd.DataFrame":
        r"""Transform a (cached) NIST ASD response into a pandas DataFrame.

        Calculates the air equivalent wavelength from the vacuum wavelength using the same Sellmeier equation as the NIST ASD.

        Note that this conversion is only performed for lines with $200\ nm < \lambda < 2000\ nm$, like the ASD.

        For lines outside of this range, it uses NaN values.
        """
        schema = {
            "obs_wl_vac(nm)": str,
            "ritz_wl_vac(nm)": str,
            "wn(cm-1)": float,
            "intens": str,
            "Aki(s^-1)": float,
            "fik": float,
            "S(a.u.)": float,
            "log_gf": float,
            "Acc": str,
            "Ei(cm-1)": str,
            "Ek(cm-1)": str,
            "conf_i": str,
            "conf_k": str,
            "term_i": str,
            "term_k": str,
            "g_i": float,
            "g_k": float,
            "J_i": str,
            "J_k": str,
            "Type": str,
            "tp_ref": str,
            "line_ref": str,
            "": str,
        }
        df = pd.read_csv(StringIO(response.text), sep="\t", dtype=schema)
        # Detect if pandas uses new `StringDtype`, or legacy `object` dtype for strings.
        # This affects NaN handling for strings.
        # Pandas 3.0 and up use the StringDtype, while pandas 2 can opt-in to this
        # The 'Type' column should exist, 'element' may not.
        uses_new_string_dtype = pd.api.types.is_string_dtype(df["Type"])
        for col in ["obs_wl_vac(nm)", "ritz_wl_vac(nm)", "intens", "Ei(cm-1)", "Ek(cm-1)"]:
            df[col] = df.loc[:, col].str.extract(SCI_EXPR).astype(float)
        # Any missing value implies line is an E1 (electric dipole) transition
        if uses_new_string_dtype:
            df["Type"] = df.loc[:, "Type"].fillna("E1")
        else:
            df["Type"] = df.loc[:, "Type"].astype(str).replace("nan", "E1")
        df["tp_ref"] = df.loc[:, "tp_ref"].fillna("")
        df["obs_wl_air(nm)"] = np.nan
        air_equiv_range = df["wn(cm-1)"].between(5000, 50000)  # range where air wavelength is computed.
        df["obs_wl_air(nm)"] = df.loc[air_equiv_range, "obs_wl_vac(nm)"] / wavenumber_to_refractive_index(
            df.loc[air_equiv_range, "wn(cm-1)"]
        )
        df["ritz_wl_air(nm)"] = np.nan
        df["ritz_wl_air(nm)"] = df.loc[air_equiv_range, "ritz_wl_vac(nm)"] / wavenumber_to_refractive_index(
            df.loc[air_equiv_range, "wn(cm-1)"]
        )
        df = df.drop([c for c in df.columns if "Unnamed" in c], axis=1).reset_index(drop=True)
        if "element" not in df.columns:
            # cast roman numerals to int for consistency with queries with multiple ionization states, e.g. Ar I vs Ar I-II
            # As 'element' and 'sp_num' columns are only missing for single-species queries, assign as constants, not vectors.
            element, numeric = extract_state_from_response(response)
            df["element"] = element
            df["sp_num"] = numeric
        df["unc_obs_wl"] = pd.to_numeric(df["unc_obs_wl"]) if "unc_obs_wl" in df.columns else np.nan
        df["unc_ritz_wl"] = pd.to_numeric(df["unc_ritz_wl"]) if "unc_ritz_wl" in df.columns else np.nan
        return df.loc[:, list(ASDSchema)]

    @classmethod
    def _from_polars(cls, response: Response) -> "pl.DataFrame":
        r"""Transform a (cached) NIST ASD response into a polars DataFrame.

        Calculates the air equivalent wavelength from the vacuum wavelength using the same Sellmeier equation as the NIST ASD.

        Note that this conversion is only performed for lines with $200\ nm < \lambda < 2000\ nm$, like the ASD.

        For lines outside of this range, it uses NaN values.
        """
        # initial schema when parsing from text
        schema = {
            "obs_wl_vac(nm)": pl.String,
            "ritz_wl_vac(nm)": pl.String,
            "wn(cm-1)": pl.Float64,
            "intens": pl.String,
            "Aki(s^-1)": pl.Float64,
            "fik": pl.Float64,
            "S(a.u.)": pl.Float64,
            "log_gf": pl.Float64,
            "Acc": pl.String,
            "Ei(cm-1)": pl.String,
            "Ek(cm-1)": pl.String,
            "conf_i": pl.String,
            "conf_k": pl.String,
            "term_i": pl.String,
            "term_k": pl.String,
            "g_i": pl.Float64,
            "g_k": pl.Float64,
            "J_i": pl.String,
            "J_k": pl.String,
            "": pl.String,
        }

        df = pl.read_csv(
            StringIO(response.text),
            separator="\t",
            schema_overrides=schema,
            null_values="",
        )
        sci_cols = ["obs_wl_vac(nm)", "Ei(cm-1)", "Ek(cm-1)", "intens", "ritz_wl_vac(nm)"]
        cast_to_scientific_notation = [
            pl.col(c).str.extract(SCI_EXPR).replace("", None).cast(pl.Float64).alias(c) for c in sci_cols
        ]
        df = df.with_columns(
            *cast_to_scientific_notation,
            pl.col("S(a.u.)").cast(pl.Float64),
            pl.col("Type").replace(None, "E1"),
            pl.col("tp_ref").replace(None, ""),
        ).drop([""])
        # compute air wavelengths between 5000 cm-1 and 50000 cm-1
        air_equiv_range = pl.col("wn(cm-1)").is_between(5000, 50000)
        df = df.with_columns(
            pl.when(air_equiv_range)
            .then(pl.col("obs_wl_vac(nm)") / wavenumber_to_refractive_index(pl.col("wn(cm-1)")))
            .otherwise(np.nan)
            .alias("obs_wl_air(nm)"),
            pl.when(air_equiv_range)
            .then(pl.col("ritz_wl_vac(nm)") / wavenumber_to_refractive_index(pl.col("wn(cm-1)")))
            .otherwise(np.nan)
            .alias("ritz_wl_air(nm)"),
        )
        if "element" not in df.columns:
            element, numeric = extract_state_from_response(response)
            df = df.with_columns(pl.lit(element).alias("element"), pl.lit(numeric, dtype=pl.Int64).alias("sp_num"))
        # Cast to float, or create column filled with `null` if missing.
        exprs = [
            (pl.col(c) if c in df.columns else pl.lit(None).alias(c)).cast(pl.Float64)
            for c in ["unc_obs_wl", "unc_ritz_wl"]
        ]
        df = df.with_columns(exprs)
        return df.match_to_schema(ASDSchema)  # force exception if not schema-compliant

    def get_all_cached(self) -> "pd.DataFrame|pl.DataFrame":
        """Retrieve all cached data into a single dataframe."""
        cached_frames = [self.create_dataframe(cached) for cached in self.responses]
        if self.use_polars:
            return (
                pl.concat(cached_frames).unique()
                if len(cached_frames) > 0
                else pl.DataFrame({k: [] for k in ASDSchema}, schema=ASDSchema)
            )
        return (
            pd.concat(cached_frames).drop_duplicates().reset_index(drop=True)
            if len(cached_frames) > 0
            else pd.DataFrame({k: pd.Series(dtype=v) for k, v in ASDSchema.items()})
        )


class BibCache:
    r"""A class for handling lookups of bibliographic metadata from the NIST ASD.

    Supports both bibliographic reference databases curated by NIST:

    * Atomic Transition Probability Bibliographic Database: [10.18434/T46C7N](https://doi.org/10.18434/T46C7N)

    * Atomic Energy Levels and Spectral Bibliographic Database: [10.18434/T40K53](https://doi.org/10.18434/T40K53)

    References to these databases in the NIST ASD data can be looked up and will be cached.
    """

    nist_url = "https://physics.nist.gov/cgi-bin/ASBib1/get_ASBib_ref.cgi"
    reference_expr = re.compile(r"([A-Z])?([\d]+)?([a-z]+[\d]*)?")

    def __init__(self, cache_expiry=timedelta(weeks=1)):
        """Initialize an instance that handles cached retrieval of ASD bibliographic references."""
        self.session = CachedSession(
            "NIST_ASD_Bibliography_cache",
            use_cache_dir=True,
            expire_after=cache_expiry,
            stale_if_error=True,
            filter_fn=self._check_response_success,
            ignored_parameters=["element", "spectr_charge", "type", "ref"],
        )
        self.session.headers.update({"User-Agent": f"ASDCache/{version}"})

    @property
    def cache_expiry(self) -> timedelta:
        """The cache expiry time.

        Queries that are older than this time are considered stale and marked for updating, by quering the NIST ASD.
        In case the query for new data fails, the stale, cached response will still be parsed.
        """
        return self.session.settings.expire_after

    def set_cache_expiry(self, new: Optional[timedelta] = None, **kwargs):
        """Set the cache expiry to a different interval (default: 1 week).

        Can be done by either passing in a `timedelta` object, or valid keyword arguments for `timedelta` itself.
        """
        if new is None:
            new = timedelta(**kwargs)
        self.session.settings.expire_after = new

    @staticmethod
    def _check_response_success(response: Response) -> bool:
        """Validate that data has been fetched succesfully.

        If this check fails, the cache should not update with this response, even when marked as stale.
        """
        is_success = (response.status_code == 200) & (b"There was a problem" not in response.content)
        if not is_success:
            logger.warning(f"Request was unsuccesful status:{response.status_code} , url:{response.url}")
        return is_success

    @classmethod
    def parse_reference_code(cls, reference_code: str) -> tuple[str, Optional[str], str]:
        r"""Parse a reference code from the NIST ASD into the constituent parts that can be used to look up references.

        Args:
            reference_code (str): A NIST ASD bibliographic reference string, such as `L13456n3`, or `T6936n`.

        Returns:
            db (str):   A label for which bibliographic database to target
            ref (str|None):   The database ID for the reference to look up
            comment (str):   An additional comment included in the reference, can be fetched separately.
        """
        if reference_code.startswith("n"):
            return ("T", None, "n")
        matched = cls.reference_expr.match(reference_code)
        if (not reference_code.startswith("LS")) and (matched is not None):
            db, ref, comment = matched.groups()
            comment = comment if "LS" not in reference_code else "LS"
        else:
            db, ref, comment = "T", None, "LS"
        return db, ref, comment if comment is not None else ""

    def lookup(self, element: str, sp_num: int, reference_code: str) -> dict[str, Any]:
        """Look up a reference code for a given element state.

        Args:
            element (str):   The element name, e.g. `H`
            sp_num (int):   The ionization state of the element, with 1 corresponding to the atom
            reference_code (str):   The bibliographic reference code from the ASD columns `tp_ref` or `line_ref`.

        Returns:
            bib_data (dict[str,Any]): A dictionary containing bibliographic metadata for the reference, if available/applicable. Contains a url to look it up.
        """
        db, ref, comment = self.parse_reference_code(reference_code)
        params = {
            "db": "tp" if db == "T" else "el",
            "db_id": ref,
            "comment_code": "",
            "element": element,
            "spectr_charge": sp_num,
        }
        if ref is not None:
            response = self.session.get(self.nist_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, features="html.parser")
            title = soup.find("font", {"size": "+1"})
            doi = soup.find("a", {"id": "ad"})
            authors = soup.find_all("a", {"id": "aa"})
            title = "" if title is None else title.text.replace("\xa0", " ").strip()
            doi = "" if doi is None else doi.text.strip()
            authors = authors if authors == [] else [author.text.replace("\xa0", " ").strip() for author in authors]
            text = "\n".join([tr.text.strip() for tr in soup.find("table").find_all("tr")]).strip()
            url = (
                response.url.replace("REDACTED", f"{element}", 1).replace("REDACTED", f"{sp_num}", 1)
                + f"&comment_code={comment}"
            )
        else:
            title = ""
            doi = ""
            authors = []
            text = ""
            url = None

        # separately look up comments such that we benefit from the cache here as well
        if comment != "":
            comment_params = {
                "db": "tp" if db == "T" else "el",
                "db_id": "",
                "comment_code": comment,
                "element": "H",  # not cached
                "spectr_charge": 1,  # not cached
            }
            comment_response = self.session.get(self.nist_url, params=comment_params)
            comment_response.raise_for_status()
            text += BeautifulSoup(comment_response.text, features="html.parser").table.find("td", {"colspan": "2"}).text
            url = (
                comment_response.url.replace("REDACTED", f"{element}", 1).replace("REDACTED", f"{sp_num}", 1)
                + f"&db_id={'' if ref is None else ref}"
            )

        bib_data = {
            "title": title,
            "doi": doi,
            "authors": authors,
            "text": text,
            "url": url,
        }
        return bib_data


class LevelCacheAccessor:
    """Accessor for the Energy Level data from the ASD, sharing cache with its parent [SpectraCache][..].

    This accessor is not meant for stand-alone use, but to extend a `parent` [SpectraCache][(m).] instance.

    The [SpectraCache.levels][..] attribute can be used to access all these level-related queries and helper methods.

    Example:
        ```python
        from ASDCache import SpectraCache
        cache = SpectraCache()
        df_levels_hydrogen = cache.levels.fetch("H I")
        ```
    """

    nist_url = "https://physics.nist.gov/cgi-bin/ASD/energy1.pl"
    query_params = {
        "de": "0",
        "submit": "Retrieve Data",
        "units": "0",
        "format": "3",
        "output": "0",
        "multiplet_ordered": "0",
        "conf_out": "on",
        "term_out": "on",
        "level_out": "on",
        "unc_out": "1",
        "j_out": "on",
        "g_out": "on",
        "lande_out": "on",
        "perc_out": "on",
        "splitting": "1",
        "biblio": "on",
    }  # Request parameters used by the NIST ASD Levels form.

    expr_L = re.compile(r"([spdfghij])[0-9A-Z()/]*$")  # Regex for extracting L from the Term of a state.
    map_L = {c: i for i, c in enumerate("spdfghij")}  # Mapping of Term-labels for L to integers.

    def __init__(self, parent: SpectraCache):
        """Initialize a LevelCacheAccessor that shares the same cache session as the provided SpectraCache."""
        self.parent = parent

    @property
    def use_polars(self) -> bool:
        """Flag if `polars` is to be used, if present in the environment."""
        return self.parent.use_polars

    @property
    def session(self) -> CachedSession:
        """Reference to the cache session."""
        return self.parent.session

    def _get_data(self, species, throw_on_error=True, **kwargs):
        """Retreive raw, ASCII-formatted data from the NIST ASD with a GET request.

        To retrieve data and process it into a DataFrame, use [fetch][..] instead.

        Returns the raw response, which will be cached, if it is valid, see [SpectraCache._check_response_success][(m).]

        If the response does not contain ASCII-data, but HTML intstead, an [ASDQueryError][(m).] will be raised.
        """
        query = self.parent._build_query(self.query_params, spectrum=species)
        response: Response = self.session.get(self.nist_url, params=query)
        response.raise_for_status()
        if not self.parent._check_response_success(response) and throw_on_error:
            reason = self.parent._parse_nist_error_message(response)
            logger.error(
                "NIST ASD responded with %s instead of ASCII-data for species=%s\nQuery: %s",
                reason,
                species,
                response.url,
            )
            raise ASDQueryError(
                f"Query for {species=} did nor receive ASCII data.{reason=} This means the ASD could not interpret your query. Check if your query is malformed."
            )
        return response

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
    def _from_pandas(cls, response) -> pd.DataFrame:
        """Process a response into a DataFrame using pandas.

        Will produce a DataFrame that adheres to [ASDLevelSchema][(m).].
        """
        parse_schema = {
            "Configuration": str,
            "Term": str,
            "J": str,
            "g": float,
            "Prefix": str,
            "Level (cm-1)": float,
            "Suffix": str,
            "Uncertainty (cm-1)": float,
            "Splitting": float,
            "Lande": str,
            "Leading percentages": str,
            "Reference": str,
        }  # Force initial schema when parsing for reliable data handling; coerce J as str initially etc.
        element, sp_num = extract_state_from_response(response)
        df = pd.read_csv(
            StringIO(response.text),
            sep="\t",
            dtype=parse_schema,
        )
        df["element"] = element
        df["sp_num"] = sp_num
        df["Level comment"] = df.Prefix.str.replace({"(": "Theoretical", "[": "Derived"}).fillna("")
        df["Ionization limit"] = df.Term.str.contains("Limit")
        # Extract and compute fractions
        fracs = df["J"].str.replace("---", "nan").str.split("/", expand=True).astype(float)

        # Below does not handle when J is either uncertain (content like: `J1 or J2 or J3`), or when J is unresolved (content like: `J1,J2`)
        df["J"] = fracs.loc[:, 0] / (fracs.loc[:, 1].fillna(1)) if fracs.shape[1] > 1 else fracs
        df["L"] = df.Configuration.str.extract(cls.expr_L, expand=False).map(cls.map_L).astype(float)
        df = df.drop(["Prefix", "Suffix"], axis=1)

        if "Lande" in df.columns:
            # TODO: Lande: trailing `:` denotes significantly less accurate value; trailing `?` denotes tentative
            # Not documented about Lande column: a final digit between () for significance, e.g. encoutered for Sn II.
            df["Lande"] = df.loc[:, "Lande"].str.extract(SCI_EXPR).astype(float)
        # Insert missing columns as NaN for now
        for c in set(ASDLevelSchema) - set(df.columns):
            df[c] = np.nan
        return df.loc[:, [c for c in ASDLevelSchema if c in df.columns]]

    @classmethod
    def _from_polars(cls, response) -> "pl.DataFrame":
        """Process a response into a DataFrame using polars.

        Will produce a DataFrame that adheres to [ASDLevelSchema][(m).].
        """
        parse_schema = {
            "Configuration": pl.String(),
            "Term": pl.String(),
            "J": pl.String(),
            "g": pl.Float64(),
            "Prefix": pl.String(),
            "Level (cm-1)": pl.Float64(),
            "Suffix": pl.String(),
            "Uncertainty (cm-1)": pl.Float64(),
            "Splitting": pl.Float64(),
            "Lande": pl.String(),
            "Leading percentages": pl.String(),
            "Reference": pl.String(),
        }
        element, sp_num = extract_state_from_response(response)

        df = pl.read_csv(
            StringIO(response.text),
            separator="\t",
            schema_overrides=parse_schema,
        )
        df = df.with_columns(
            pl.lit(element).alias("element"),
            pl.lit(sp_num).alias("sp_num").cast(pl.Int64()),
            pl.col("Prefix").str.replace(r"\(", "Theoretical").str.replace(r"\[", "Derived").alias("Level comment"),
            pl.col("Term").str.contains("Limit").alias("Ionization limit"),
            pl.col("Configuration").str.extract(cls.expr_L.pattern).replace(cls.map_L).cast(pl.Float64).alias("L"),
        ).drop(["Prefix", "Suffix"])
        # Extract and compute fractions
        fracs = df.select(pl.col("J").replace("---", "").replace("", "nan")).select(
            pl.col("J").str.split_exact("/", 1).struct.unnest().cast(pl.Float64)
        )
        df = df.with_columns(
            fracs.with_columns(pl.col("field_1").fill_null(1)).select(
                (pl.col("field_0") / pl.col("field_1")).alias("J")
            )
        )
        if "Lande" in df.columns:
            # TODO: Lande: trailing `:` denotes significantly less accurate value; trailing `?` denotes tentative
            # Not documented about Lande column: a final digit between () for significance, e.g. encoutered for Sn II.
            # For now: simply parse SCI_EXPR
            df = df.with_columns(pl.col("Lande").str.extract(SCI_EXPR).replace("", None).cast(pl.Float64))

        # Force empty strings as null for compatibility with pandas; implies values are missing
        str_as_null = ["Configuration", "Term", "Reference"]
        expr_as_null = [pl.when(pl.col(c) == "").then(pl.lit(None)).otherwise(pl.col(c)).alias(c) for c in str_as_null]
        df = df.with_columns(*expr_as_null)

        # Handle missing columns; ASD omits columns if no data available, such as Lande factors
        df = df.with_columns([pl.lit(None).cast(t).alias(c) for c, t in ASDLevelSchema.items() if c not in df.columns])

        return df.match_to_schema(ASDLevelSchema)

    def create_dataframe(self, response: Response) -> "pd.DataFrame|pl.DataFrame":
        """Create a dataframe from the (cached) NIST ASD response.

        Will only successfully process queries to the ASD Energy Level Database url, else raises a ValueError.

        Will decide on the backend to use based on [use_polars][..].
        """
        if not response.url.startswith(self.nist_url):
            raise ValueError("Invalid response, only the %s endpoint is supported, got %s", self.nist_url, response.url)
        if self.use_polars:
            return self._from_polars(response)
        return self._from_pandas(response)

    def fetch(self, species: str) -> "pd.DataFrame|pl.DataFrame":
        """Fetch the energy levels of a species from the NIST ASD Energy Levels Database, first checking the cache.

        Only a single species can be queried per call, due to the inner workings of the ASD (unlike [SpectraCache.fetch][(m).]).

        Args:
            species (str): A single species query string, e.g. `'H I'` or `'198Hg II'`.
        """
        response = self._get_data(species)
        return self.create_dataframe(response)
