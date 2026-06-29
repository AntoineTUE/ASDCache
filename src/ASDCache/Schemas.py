"""Schema definitions used by ASDCache in the parsing and validation.

When parsing text data, a specific schema may be enforced initially, to guarantee that specific columns will be of certain types.

For instance, the Lande factor is useful to treat as a string during parsing, so it can be processed reliably.

Other schemas are used to guarantee that after parsing, all data is of the expected type.
"""

import pyarrow as pa

level_parsing_schema = pa.schema(
    [
        ("element", pa.string()),
        ("sp_num", pa.int16()),
        ("Configuration", pa.string()),
        ("Term", pa.string()),
        ("J", pa.string()),
        ("g", pa.float64()),
        ("Prefix", pa.string()),
        ("Level (cm-1)", pa.float64()),
        ("Suffix", pa.string()),
        ("Uncertainty (cm-1)", pa.float64()),
        ("Splitting", pa.float64()),
        ("Lande", pa.string()),
        ("Leading percentages", pa.string()),
        ("Reference", pa.string()),
    ]
)

line_parsing_schema = pa.schema(
    [
        ("element", pa.string()),
        ("sp_num", pa.int16()),
        ("obs_wl_vac(nm)", pa.string()),
        ("unc_obs_wl", pa.float64()),
        ("obs_wl_air(nm)", pa.float64()),  # will create empty column when parsing
        ("ritz_wl_vac(nm)", pa.string()),
        ("unc_ritz_wl", pa.float64()),
        ("ritz_wl_air(nm)", pa.float64()),  # will create empty column when parsing
        ("wn(cm-1)", pa.float64()),
        ("intens", pa.string()),
        ("Aki(s^-1)", pa.float64()),
        ("fik", pa.float64()),
        ("S(a.u.)", pa.float64()),
        ("log_gf", pa.float64()),
        ("Acc", pa.dictionary(pa.int32(), pa.string())),
        ("Ei(cm-1)", pa.string()),
        ("Ek(cm-1)", pa.string()),
        ("conf_i", pa.string()),
        ("term_i", pa.string()),
        ("J_i", pa.string()),
        ("conf_k", pa.string()),
        ("term_k", pa.string()),
        ("J_k", pa.string()),
        ("g_i", pa.float64()),
        ("g_k", pa.float64()),
        ("Type", pa.dictionary(pa.int32(), pa.string())),
        ("tp_ref", pa.dictionary(pa.int32(), pa.string())),
        ("line_ref", pa.dictionary(pa.int32(), pa.string())),
    ]
)

ASDLevelOutputSchema = pa.schema(
    [
        ("element", pa.string()),
        ("sp_num", pa.int16()),
        ("Configuration", pa.string()),
        ("Term", pa.string()),
        ("J", pa.float64()),
        ("g", pa.float64()),
        ("Level (cm-1)", pa.float64()),
        ("Uncertainty (cm-1)", pa.float64()),
        ("Splitting", pa.float64()),
        ("Lande", pa.float64()),
        ("L", pa.int8()),
        ("Ionization limit", pa.bool_()),
        ("Leading percentages", pa.string()),
        ("Reference", pa.string()),
    ]
)
