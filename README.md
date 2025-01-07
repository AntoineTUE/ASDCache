# readASD

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.svg)](https://doi.org/10.5281/zenodo)
[![GitHub License](https://img.shields.io/github/license/AntoineTUE/readASD)](https//www.github.com/AntoineTUE/readasd/blob/main/LICENSE)
![GitHub Workflow Status build](https://img.shields.io/github/actions/workflow/status/AntoineTUE/readASD/build.yml?label=PyPI%20build)
![GitHub Workflow Status docs](https://img.shields.io/github/actions/workflow/status/AntoineTUE/readASD/documentation.yml?label=Documentation%20build)
[![PyPI - Version](https://img.shields.io/pypi/v/readASD)](https://pypi.python.org/pypi/readASD)
[![PyPI - Python versions](https://img.shields.io/pypi/pyversions/readASD.svg)](https://pypi.python.org/pypi/readASD)
[![PyPI - Downloads](https://img.shields.io/pypi/dw/readasd)](https://pypistats.org/packages/readasd)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)

`readASD` is a Python project to retrieve data from the NIST Atomic Spectra Database (ASD), using caching for fast, efficient data handling.

To make the most use out of the cache, `readASD` is opinionated in the information it retrieves from the ASD; it always requests the same schema of information and locally computes additional fields, to provide a more 'machine-useable' experience.

It also coerces most of the retrieved data to be of a strictly numeric type, which strips out footnotes and annotations, but preserves e.g. bibliographic reference labels.

You should thus still be sure to check and attribute the NIST ASD when making use of `readASD`!

The main goals and benefits of `readASD` are:

- [x] Make the data from the NIST ASD locally accessible as a Dataframe for use in analysis of spectra
- [x] Retrieve a consistent schema of the data that represents the 'human readable' format, but enforce strictly numeric data for important columns
  - [ ] This removes footnotes and other annotations, be sure to check the ASD itself as well for this information.
- [x]  Use caching to dramatically speed up data retrieval, from minutes down to milliseconds in some cases
    - [x] Cache time-to-live is 1 week by default, meaning you still get updates to the ASD in a reasonable time frame
    - [x] The cache time-to-live can be adjusted
- [x]  Cache data to allow working offline, or even transfering the ASD data to an offline system.
    - [x] The cache is only updated when a request for new data succeeds
- [x] Limit repeated queries for the same information, avoiding network overhead and server load.

`readASD` is not affiliated with NIST or the NIST ASD in any way, it simply tries to help make it more accessible.

## Installing
`readASD` can be installed with `pip`.

```console
pip install readasd
```

Further optional features can be installed by specifying the `polars` or `docs` feature flag, as defined in [pyproject.toml](./pyproject.toml).

To install all dependencies to locally serve and update the documentation for instance, you can run:

```console
pip install readasd[docs]
```

Installing the `polars` feature is not required, in case `polars` is already installed in the active environment, it is possible to use `polars` instead of `pandas` as a Dataframe backend for `readasd`.

## Documentation

Documentation for `readASD` is available on [this page](https://antoinetue.github.io/readasd).

### Example
A brief example below demonstrates how to use `readASD` to query the NIST ASD for spectroscopic data for different species and plot their respective relative intensities.

Note that these relative intensities are in principle not comparable between different species or sources and merely serve as a guide.

More elaborate examples can be found in the [example section of the documentation](https://antoinetue.github.io/readasd/examples)

```python
from readasd.readASD import ASDCache
import matplotlib.pyplot as plt

nist = ASDCache()
lines_H_I = nist.fetch("H I")


plt.plot(lines_H_I['obs_wl_air(nm)'], lines_H_I['intens'], label=f"{lines_H_I['element'].unique()[0]} {lines_H_I['sp_num'].unique()[0]}")


nist.fetch("O I-III") # caches data from NIST but does not assign to a variable

# Oxygen I-III will still be plotted, each ionization state separately.
lines_all_cached = nist.get_all_cached()
for species,lines in lines_all_cached.groupby(["element","sp_num"]):
    plt.plot(lines['obs_wl_air(nm)'], lines['intens'], label=f"{species[0]} {species[1]}", marker='x', ls='none')
plt.legend()
```

## Citing

Be sure to cite the NIST ASD when using `readasd` in your work, since it is the source of the data.

`readasd` itself can be cited using the following DOI provided via Zenodo:

See also

## License

readASD is licensed under the MIT license.

See [LICENSE](./LICENSE).
