# Data schema overview

!!! info
    The schema of the data used in `ASDCache` in principle reflects that of the NIST ASD Line Table, using the tab-separated format.
    You can find the relevant information on the included data on [this page](https://physics.nist.gov/PhysRefData/ASD/Html/lineshelp.html#OUTPUT_LINE) of the NIST ASD documentation.

| Column name | Data type | Description | Note |
| --- | --- | --- | --- | 
| `element` |  `str` | atomic element |  |
| `sp_num` |  `int` | ionization degree, starting with 1 for the unionized atom | Only integers, not roman numerals |
| `obs_wl_vac(nm)` | `float`  | Observed vacuum wavelength |  |
| `unc_obs_wl` | `float`  | Uncertainty in observed vacuum wavelength |  |
| `obs_wl_air(nm)` |  `float` | Observed wavelength in air | Calculated from `obs_wl_vac(nm)`, not retrieved from ASD |
| `ritz_wl_vac(nm)` |  `float` | Ritz wavelength in vacuum|  |
| `unc_ritz_wl` |  `float`  | Uncertainty in Ritz wavelength |  |
| `ritz_wl_air(nm)` |  `float` | Ritz wavelength in air | Calculated from `ritz_wl_vac(nm)`, not retrieved from ASD |
| `wn(cm-1)` |  `float` | Observed wavenumbers |  |
| `intens` |  `float` | Guideline for strenght of a line in an emission spectrum | Also known as 'Rel. Intens.' in the HTML table. Does not include any of the footnotes available in the ASD. |
| `Aki(s^-1)` |  `float` | Einstein A coefficient of transition |  |
| `fik` |  `float` | Absorption oscillator strength |  |
| `S(a.u.)` | `float`  | Line strenght |  |
| `log_gf` | `float`  | $\log_{10}\ g_{i}f_{ik}$ |  |
| `Acc` | `str`  | Estimated accuracy of transition strength |  |
| `Ei(cm-1)` |  `float` | Lower state energy |  |
| `Ek(cm-1)` | `float`  | Upper state energy |  |
| `conf_i` |  `str` | Lower state configuration |  |
| `term_i` |  `str` | Lower state term symbol |  |
| `J_i` |  `str` | Lower state total electronic angular momentum |  |
| `conf_k` |  `str` | Upper state configuration |  |
| `term_k` |  `str` | Upper state term symbol |  |
| `J_k` | `str`  | Upper state total electronic angular momentum |  |
| `g_i` | `float`  | Lower Landé $g$ factor |  |
| `g_k` | `float`  | Upper Landé $g$ factor |  |
| `Type` |  `str` | The type of transition | Allowed electric-dipole transitions are explicitly labeled as `E1` |
| `tp_ref` |  `str` | Atomic Transition Probability Bibliographic Database Reference |  |
| `line_ref` |  `str` | Energy Levels and Wavelengths Bibliographic Reference |  |
