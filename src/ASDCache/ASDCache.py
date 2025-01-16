r"""`ASDcache` is a module to fetch data from the  NIST Atomic Spectra Database (ASD), utlizing caching for fast responses.

To make the most use out of the cache, `ASDcache` is opinionated in the information it retrieves from the ASD; it always requests the same schema of information and locally computes additional fields.

Data is initially fetched from the online published NIST page, using the tab-separated ASCII output format.
The benefit of this format is that it is more 'machine readable' than the formatted ASCII of HTML options.
This means it requires far less bespoke parsing to get rid of 'human readable' features such as repeated page column headers, or empty lines.
To ensure a consistent schema of the retrieved data, lines are always retrieved as a function of wavelength, using `vacuum wavelength`, even between 200 to 2000 nm.
Wavenumbers and Ritz wavelength will be included in the response.

In the range $5000 \mathrm{cm}^{-1}<\nu<50000 \mathrm{cm}^{-1}$ the air equivalent observed and Ritz wavelengths are calculated using the same Sellmeier equation as the NIST ASD (see [here][ASDcache.readASD.ASDCache.wn_to_n_refractive]).
This is consistent with the approach of the ASD.

Each response from the NIST page is cached (1 week by default) on the local system.
This makes it much faster to load the same data, even across different script runs and/or user programs/sessions.
As an example: reading all spectra between 200 and 1000 nm can take over 2 minutes without using the cache, but can be as fast as 0.2 seconds using the `polars` backend.
In addition, it means that an internet connection is not required after initial data fetching.
The cached response is only updated upon succesfull retrieval of a new response of the NIST page.
If unable to succesfully fetch new data, we fall back to a 'stale' cached response.

The cache can be shared to another system, to give offline/airgapped systems access to the same data.
To that end, the file `NIST_ASD_cache.sqlite` in the user's cache directory has to be copied over.

The standard cache directories are as follows:

=== "Windows"
    `%USERPROFILE%/AppData/Local`
=== "Linux"
    `~/.cache/http_cache/`
=== "MacOS"
    `/Users/user/Library/Caches/http_cache/`

Queries to the NIST ASD are hashed by the keys (or parameters) of the requests.
This means that any change to either one of these parameters, will result in a new cache entry, even if the returned data is equivalent.
"""

import importlib
import warnings
import pandas as pd
from requests_cache import CachedSession, CachedResponse
from io import StringIO
from datetime import timedelta
import re
import numpy as np
import sys
import logging

if importlib.util.find_spec("polars"):
    POLARS_AVAILABLE = True
    """Check if `polars` is installed and available in the active environments"""
    import polars as pl
else:
    POLARS_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
    datefmt="%d/%b/%Y %H:%M:%S",
    stream=sys.stdout,
)


class SpectraCache:
    """A class acting as the entrypoint to retrieve data from the NIST Atomic Spectra Database that uses caching.

    The `ASDCache` instance acts as an access point to the cache, which stores responses on the local system in a SQLite database.

    Data retrieval from cache is much faster (order milliseconds) than fetching from the internet (order seconds), and avoids wastefull requests to the server.

    Cache time-to-live is one week by default.

    Since the NIST ASD is usually updated less frequently than that, this is a compromise between having the latest data, and overall fast performance.

    Note that the same cache is shared across different class-instances, thread-safety is not guaranteed.
    """

    nist_url = "https://physics.nist.gov/cgi-bin/ASD/lines1.pl"
    species_expr = re.compile(r"spectra=([\w\+\-\%3]+)&")
    query_params = {
        "unit": 1,
        "de": 0,
        "plot_out": 0,
        "I_scale_type": 1,
        "format": 3,
        "line_out": 0,
        "remove_js": "on",
        "no_spaces": "on",
        "en_unit": 0,
        "output": 0,
        "bibrefs": 1,
        "show_obs_wl": 1,
        "show_calc_wl": 1,
        "show_wn": 1,
        "unc_out": 1,
        "order_out": 0,
        "show_av": 3,  # 3: wavelength in vac, 2: wavelength in air
        "tsb_value": 0,
        "A_out": 0,
        "S_out": "on",
        "f_out": "on",
        "loggf_out": "on",
        "intens_out": "on",
        "conf_out": "on",
        "term_out": "on",
        "enrg_out": "on",
        "J_out": "on",
        "g_out": "on",
        "diag_out": "on",
        "allowed_out": 1,
        "forbid_out": 1,
        "submit": "Retrieve Data",
    }
    """Request parameters used by the NIST ASD form."""
    column_order = [
        "element",
        "sp_num",
        "obs_wl_vac(nm)",
        "unc_obs_wl",
        "obs_wl_air(nm)",
        "ritz_wl_vac(nm)",
        "unc_ritz_wl",
        "ritz_wl_air(nm)",
        "wn(cm-1)",
        "intens",
        "Aki(s^-1)",
        "fik",
        "S(a.u.)",
        "log_gf",
        "Acc",
        "Ei(cm-1)",
        "Ek(cm-1)",
        "conf_i",
        "term_i",
        "J_i",
        "conf_k",
        "term_k",
        "J_k",
        "g_i",
        "g_k",
        "Type",
        "tp_ref",
        "line_ref",
    ]
    """Fixed order of columns for consistent schema of data."""

    def __init__(self, use_polars_backend=False, cache_expiry=timedelta(weeks=1), strict_matching=True):
        """Initialize an instance that handles cached data lookup of the NIST ASD."""
        self.strict_matching = strict_matching
        self.cache_expiry = cache_expiry
        self.session = CachedSession(
            "NIST_ASD_cache",
            use_cache_dir=True,
            expire_after=cache_expiry,
            stale_if_error=True,
            filter_fn=self._check_response_success,
            ignored_parameters=list(self.query_params.keys()) if self.strict_matching is False else None,
        )
        if (use_polars_backend) & (not POLARS_AVAILABLE):
            warnings.warn("Cannot find `polars` as a backend, falling back to `pandas`", stacklevel=2)
            self.use_polars = False
        else:
            self.use_polars = use_polars_backend

        self.known_species = self.list_cached_species()

    @staticmethod
    def _check_response_success(response: "CachedResponse") -> bool:
        """Validate that data has been fetched succesfully.

        If this check fails, the cache should not update with this response, even when marked as stale.
        """
        return (response.status_code == 200) & (b"Error Message" not in response.content)

    def list_cached_species(self) -> list[str]:
        """List all species in the cache, based on the string of the original query URL."""
        return [
            elem.replace("+", " ")
            for u in self.session.cache.urls()
            for elem in self.species_expr.search(u).group(1).split("%3B")
        ]

    def fetch(self, species, wl_range=(170, 1000), **kwargs) -> "pd.DataFrame|pl.DataFrame|CachedResponse":
        """Fetch information on a species from the ASD, first checking the cache.

        This supports loading multiple species in one go by using the same notation as the NIST ASD page.

        Note however that cache keys are computed for unique options for `species` and `wl_range`.

        This means that you won't get caching benefits by using different queries.

        In other words: the cache cannot deduplicate queries such as `ASD.fetch('H', (200,1000))` followed by `ASD.fetch('H I', (650,660))`.

        Both these operations will fetch data online and be stored as separate cache entries.
        """
        query_params = {
            "spectra": species,
            "output_type": 0,
            "low_w": min(wl_range),
            "upp_w": max(wl_range),
            **self.query_params,
        }
        response = self.session.get(self.nist_url, params=query_params)

        if response.status_code == 200:
            return self.create_dataframe(response)
        else:
            print(f"Error: Received status code {response.status_code}")
            print(response.url)
            return response

    def create_dataframe(self, response) -> "pd.DataFrame|pl.DataFrame":
        """Create a dataframe from the (cached) NIST ASD response, using the chosen backend at class instantiation."""
        if self.use_polars:
            return self._from_polars(response)
        return self._from_pandas(response)

    @classmethod
    def _from_pandas(cls, response: "CachedResponse") -> "pd.DataFrame":
        r"""Transform a (cached) NIST ASD response into a pandas DataFrame.

        Calculates the air equivalent wavelength from the vacuum wavelength using the same Sellmeier equation as the NIST ASD.

        Note that this conversion is only performed for lines with $200 nm < \lambda < 2000 nm$, like the ASD.

        For lines outside of this range, the conversion falls back to their vacuum wavelength.
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
            "": str,
        }
        df = pd.read_csv(StringIO(response.text), sep="\t", dtype=schema)
        for col in ["obs_wl_vac(nm)", "ritz_wl_vac(nm)", "intens", "Ei(cm-1)", "Ek(cm-1)"]:
            df[col] = df.loc[:, col].str.extract(r"([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)").astype(float)
        df["Type"] = df.loc[:, "Type"].astype(str).replace("nan", "E1")
        df["tp_ref"] = df.loc[:, "tp_ref"].fillna("")
        df["obs_wl_air(nm)"] = df["obs_wl_vac(nm)"]
        df["obs_wl_air(nm)"] = df[df["wn(cm-1)"].between(5000, 50000)]["obs_wl_air(nm)"] / cls.wn_to_n_refractive(
            df[df["wn(cm-1)"].between(5000, 50000)]["wn(cm-1)"]
        )
        df["ritz_wl_air(nm)"] = df["ritz_wl_vac(nm)"]
        df["ritz_wl_air(nm)"] = df[df["wn(cm-1)"].between(5000, 50000)]["ritz_wl_air(nm)"] / cls.wn_to_n_refractive(
            df[df["wn(cm-1)"].between(5000, 50000)]["wn(cm-1)"]
        )
        df = df.drop([c for c in df.columns if "Unnamed" in c], axis=1).reset_index(drop=True)
        if "element" not in df.columns:
            expr = re.compile(r"spectra=([\w]+)\+?([IVX]+)?")
            element, numeral = expr.search(response.url).groups()
            df["element"] = element
            df["sp_num"] = numeral
            # cast roman numerals to int for consistency with queries with multiple ionization states, e.g. Ar I vs Ar I-II
            df["sp_num"] = df["sp_num"].map(cls.roman_to_int)
        df = (
            df.assign(unc_obs_wl=df["unc_obs_wl"].astype(float), unc_ritz_wl=df["unc_ritz_wl"].astype(float))
            if "unc_obs_wl" in df.columns
            else df.assign(unc_obs_wl=np.nan, unc_ritz_wl=np.nan)
        )
        return df.loc[:, cls.column_order]

    @classmethod
    def _from_polars(cls, response: "CachedResponse") -> "pl.DataFrame":
        r"""Transform a (cached) NIST ASD response into a polars DataFrame.

        Calculates the air equivalent wavelength from the vacuum wavelength using the same Sellmeier equation as the NIST ASD.

        Note that this conversion is only performed for lines with $200 nm < \lambda < 2000 nm$, like the ASD.

        For lines outside of this range, the conversion falls back to their vacuum wavelength.
        """
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
        # annotation_chars_to_strip = "(?i)()[]?*w,bGhilmprsq:+xzgacHd "
        df = (
            pl.read_csv(
                StringIO(response.text),
                separator="\t",
                schema_overrides=schema,
                null_values="",
            )
            .with_columns(
                pl.col("obs_wl_vac(nm)", "Ei(cm-1)", "Ek(cm-1)", "intens")
                # .str.strip_chars(annotation_chars_to_strip).str.replace("&dagger;", "", literal=True)
                .str.extract(r"([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)")
                # .str.extract(r"([+-]?\d*\.?\d+e[+-]?\d+)")
                .replace("", None)
                .cast(pl.Float64),
                pl.col("ritz_wl_vac(nm)").str.strip_chars('"+*').replace("", None).cast(pl.Float64),
                pl.col("S(a.u.)").cast(pl.Float64),
                pl.col("Type").replace(None, "E1"),
                pl.col("tp_ref").replace(None, ""),
            )
            .drop([""])
        ).with_columns(
            pl.when(pl.col("wn(cm-1)").is_between(5000, 50000))
            .then(
                pl.col("obs_wl_vac(nm)").cast(pl.Float64)
                / pl.col("wn(cm-1)").map_elements(cls.wn_to_n_refractive, return_dtype=pl.Float64)
            )
            .otherwise(pl.col("obs_wl_vac(nm)"))
            .cast(pl.Float64)
            .alias("obs_wl_air(nm)"),
            pl.when(pl.col("wn(cm-1)").is_between(5000, 50000))
            .then(
                pl.col("ritz_wl_vac(nm)").cast(pl.Float64)
                / pl.col("wn(cm-1)").map_elements(cls.wn_to_n_refractive, return_dtype=pl.Float64)
            )
            .otherwise(pl.col("ritz_wl_vac(nm)"))
            .cast(pl.Float64)
            .alias("ritz_wl_air(nm)"),
        )
        if "element" not in df.columns:
            expr = re.compile(r"spectra=([\w]+)\+?([IVX]+)?")
            element, numeral = expr.search(response.url).groups()
            # cast roman numerals to int for consistency with queries with multiple ionization states, e.g. Ar I vs Ar I-II
            df = df.with_columns(
                pl.lit(element).alias("element"),
                pl.lit("I" if numeral is None else numeral)
                .cast(pl.String)
                .alias("sp_num")
                .map_elements(cls.roman_to_int, return_dtype=pl.Int64),
            )
        df = (
            df.with_columns(pl.col("unc_obs_wl").cast(pl.Float64), pl.col("unc_ritz_wl").cast(pl.Float64))
            if "unc_obs_wl" in df.columns
            else df.with_columns(
                pl.lit(None).cast(pl.Float64).alias("unc_obs_wl"), pl.lit(None).cast(pl.Float64).alias("unc_ritz_wl")
            )
        )

        return df.select(*cls.column_order)

    @staticmethod
    def roman_to_int(roman: str) -> int:
        """Transform Roman numerals to integers.

        Does only support numerals including up to `L`.
        """
        roman_numerals = {"I": 1, "V": 5, "X": 10, "L": 50}
        total = 0
        previous = 0
        for char in reversed(roman):
            current_value = roman_numerals[char]
            if current_value < previous:
                total -= current_value  # Subtract if the current value is less than the previous value
            else:
                total += current_value
            previous = current_value
        return total

    @staticmethod
    def wn_to_n_refractive(wavenumbers: float) -> float:
        r"""Calculate the refractive index $n$ in air for a transition, using the 5-term Sellmeier formula used by NIST.

        The used Sellmeier formula is the one from E.R. Peck and K. Reeder [J. Opt. Soc. Am. 62, 958 (1972)](http://dx.doi.org/10.1364/JOSA.62.000958).

        This formula is fitted to data in the range of 185 nm to 1700 nm for  air at 15 °C, 101 325 Pa pressure, with 0.033 % CO2.

        This is the same formula used by the NIST ASD to calculate air wavelengths in the interval of 200 nm to 2000 nm.

        See also [the ASD documentation on the topic](https://physics.nist.gov/PhysRefData/ASD/Html/lineshelp.html#Conversion%20between%20air%20and%20vacuum%20wavelengths).

        Using this refractive index, air equivalent wavelengths consistent with the ASD can be calculated, without the need to query them separately.
        """
        sigma = wavenumbers * 1e-4  # um^-1
        return 1 + 1e-8 * (8060.51 + 2480990 / (132.274 - sigma**2) + 17455.7 / (39.32957 - sigma**2))

    def get_all_cached(self) -> "pd.DataFrame|pl.DataFrame":
        """Retrieve all cached data into a single dataframe."""
        cached_frames = [self.create_dataframe(cached) for cached in self.session.cache.filter()]
        if self.use_polars:
            return pl.concat(cached_frames).unique()
        return pd.concat(cached_frames).drop_duplicates().reset_index(drop=True)
