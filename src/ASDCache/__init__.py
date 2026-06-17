r"""`ASDCache` is a package to fetch data from the  NIST Atomic Spectra Database (ASD), utlizing caching for fast responses.

To make the most use out of the cache, `ASDCache` is opinionated in the information it retrieves from the ASD; it always requests the same schema of information and locally computes additional fields.

Data is initially fetched from the online published NIST page, using the tab-separated ASCII output format.

The benefit of this format is that it is more 'machine readable' than the formatted ASCII of HTML options.

This means it requires far less bespoke parsing to get rid of 'human readable' features such as repeated page column headers, or empty lines.

## Air wavelength
To ensure a consistent schema of the retrieved data, lines are always retrieved as a function of wavelength, using `vacuum wavelength`, even between 200 to 2000 nm.

Wavenumbers and Ritz wavelength will be included in the response.

In the range $5000\ \mathrm{cm}^{-1}<\nu<50000\ \mathrm{cm}^{-1}$ the air equivalent observed and Ritz wavelengths are calculated using the same Sellmeier equation as the NIST ASD (see [here][.utils.wavenumber_to_refractive_index]).
This is consistent with the approach of the ASD.

## Making use of the cache

Each response from the NIST page is cached (2 weeks by default) on the local system.

This makes it much faster to load the same data, even across different script runs and/or user programs/sessions.

As an example: retrieving and parsing the data for all spectra between 200 and 1000 nm can take over 2 minutes without using the cache, but can be as fast as 0.2 seconds using the `polars` backend.

In addition, it means that an internet connection is not required after initial data fetching.

The cached response is only updated upon succesfull retrieval of a new response of the NIST page.

If unable to succesfully fetch new data, we fall back to a 'stale' cached response.

The cache can be shared to another system, to give offline/airgapped systems access to the same data.

To that end, the file `NIST_ASD_cache.sqlite` in the user's cache directory has to be copied over.

### Default cache locations

The standard cache directories are as follows:

=== "Windows"
    `%USERPROFILE%/AppData/Local`
=== "Linux"
    `~/.cache/http_cache/`
=== "MacOS"
    `/Users/user/Library/Caches/http_cache/`

### Cache keys and uniqueness

Queries to the NIST ASD are hashed by the keys (or parameters) of the requests.

This means that any change to either one of these parameters, will result in a new cache entry, even if the returned data is equivalent.

In other words: the cache cannot deduplicate queries such as `SpectraCache().fetch('H', (200,1000))` followed by `SpectraCache().fetch('H I', (650,660))` (or vice versa).

It is often better (and faster) to fetch a range of data beyond what you need, and then filter down the dataframe you retrieve according to your needs.
"""

from .ASDCache import BibCache, SpectraCache

__all__ = ["BibCache", "SpectraCache"]
