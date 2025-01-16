# Changelog

## Version 0.1.*
Initial development release.

* Support fetching and caching from the NIST ASD
  * Cache-TTL defaults to 1 week for now
  * Caching hash is computed on all query parameters by default (`strict`=True)
    * Can be cached on only elements, ionization and wavelength range, with `strict` = False
* Enable retrieving all cached species/queries
* Give user the option to use `polars` instead of `pandas` as Dataframe backend if installed
* Start writing documentation
  * Auto-generated code reference included
  * Example usage using a jupyter notebook included
* Add citing information
* Add test using `pytest`
  * Also checks for consistentcy of results between `pandas` and `polars` backends.
* Set up CI/CD
  * Documentation automatic generation and deploy of latest version
  * Automated run of test suite
* Add bibliography lookups
* Archive releases to Zenodo
* Renamed project to `ASDCache`

## Version 0.2.*
Public release version

* Release to PyPI
* Update documentation only on new release
  
