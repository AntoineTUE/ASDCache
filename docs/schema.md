# Data schema overview

!!! info
    The schema of the data used in `readasd` in principle reflects that of the NIST ASD Line Table, using the tab-separated format.
    You can find the relevant information on the included data on [this page](https://physics.nist.gov/PhysRefData/ASD/Html/lineshelp.html#OUTPUT_LINE) of the NIST ASD documentation.

| Column name | Description | Note |
| --- | --- | --- | 
| `element` | atomic element |  |
| `sp_num` | ionization degree, starting with 1 for the unionized atom | Only integers, not roman numerals |
| `obs_wl_vac(nm)` | Observed vacuum wavelength |  |
| `unc_obs_wl` | Uncertainty in observed vacuum wavelength |  |
| `obs_wl_air(nm)` | Observed wavelength in air | Calculated from `obs_wl_vac(nm)`, not retrieved from ASD |
| `ritz_wl_vac(nm)` | Ritz wavelength in vacuum|  |
| `unc_ritz_wl` | Uncertainty in Ritz wavelength |  |
| `ritz_wl_air(nm)` | Ritz wavelength in air | Calculated from `ritz_wl_vac(nm)`, not retrieved from ASD |
| `wn(cm-1)` | Observed wavenumbers |  |
| `intens` | Guideline for strenght of a line in an emission spectrum | Also known as 'Rel. Intens.' in the HTML table. Does not include any of the footnotes available in the ASD. |
| `Aki(s^-1)` | Einstein A coefficient of transition |  |
| `fik` | Absorption oscillator strength |  |
| `S(a.u.)` | Line strenght |  |
| `log_gf` | $\log_{10}\ g_{i}f_{ik}$ |  |
| `Acc` | Estimated accuracy of transition strength |  |
| `Ei(cm-1)` | Lower state energy |  |
| `Ek(cm-1)` | Upper state energy |  |
| `conf_i` | Lower state configuration |  |
| `term_i` | Lower state term symbol |  |
| `J_i` | Lower state total electronic angular momentum |  |
| `conf_k` | Upper state configuration |  |
| `term_k` | Upper state term symbol |  |
| `J_k` | Upper state total electronic angular momentum |  |
| `g_i` | Lower Landé $g$ factor |  |
| `g_k` | Upper Landé $g$ factor |  |
| `Type` | The type of transition | Allowed electric-dipole transitions are explicitly labeled as `E1` |
| `tp_ref` | Atomic Transition Probability Bibliographic Database Reference |  |
| `line_ref` | Energy Levels and Wavelengths Bibliographic Reference |  |
