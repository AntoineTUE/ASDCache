"""Module that facilitates IO using pyarrow.

Utilities for reading, parsing and transforming ASD (Atomic Spectra Database) ASCII table data using pyarrow.

The module centralises IO and lightweight vectorised parsing operations so pandas and polars backends can interoperate through arrow tables/arrays without surprising dtype mismatches.

Since both pandas and polars can work with pyarrow natively, it makes matters more simple to handle data parsing with pyarrow and then convert to the desired kind of dataframe.

In addition, the [pyarrow.Table][pyarrow.Table] can be converted to many other dataframe libraries, if so desired.

This module provides a generic [read_response][(m).read_response] function, that will read a (cached response) and parse it according to a provided schema (see [Schemas][(p).Schemas]).

The resulting [pyarrow.Table][pyarrow.Table] can then be processed further into the desired output schema.

For this, there are several helper function provided to aid in parsing or updating the table.
"""

from io import BytesIO

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
from pyarrow import csv
from requests import Response

from ASDCache.utils import extract_state_from_response


def map_arrow_to_pandas_types(dtype) -> pa.DataType:
    """Map arrow-native types to pandas-equivalent arrow-backed types (see [pandas.ArrowDtype][pandas.ArrowDtype]).

    This is small wrapper that forces any instance of [pyarrow.large_string][pyarrow.large_string] to be down-cast to [pyarrow.string][pyarrow.string].

    For other types it falls back to the default behaviour defined by [pandas.ArrowDtype][pandas.ArrowDtype].

    The main use if this function is to ensure consistency between dataframes created by polars and pandas (which is only relevant for testing in practise).

    When converting using [polars.DataFrame.to_pandas][polars.DataFrame.to_pandas] the conversion happens through an [arrow.Table][pyarrow.Table].

    By design polars enforces [pyarrow.large_string][pyarrow.large_string] for strings when converting to arrow, to handle larger than 2 GB columns.

    It is up to the user to cast/covert to normal strings, see discussion in: https://github.com/pola-rs/polars/issues/15047.

    From the ASD we do not expect such large columns, so they are converted to regular-length strings.

    This ensures consistency between schema and content of dataframes regardless of backend.

    Example:
    ```python
    from ASDCache import SpectraCache
    from ASDCache.arrow import map_arrow_to_pandas_types
    from pandas.testing import assert_frame_equal

    cache_polars = SpectraCache(use_polars_backend=True)
    data = cache.fetch("H I")
    manual_as_pandas = data.to_pandas(types_mapper = map_arrow_to_pandas_types)

    cache_pandas = SpectraCache(use_polars_backend=False)

    assert_frame_equal(manual_as_pandas, cache_pandas.fetch("H I"))

    # without applying map_arrow_to_pandas_types the test fails due to type mismatch
    assert_frame_equal(data.to_pandas(), cache_pandas.fetch("H I"))
    ```
    """
    if dtype == pa.large_string():
        dtype = pa.string()
    elif dtype == pa.dictionary(pa.int64(), pa.large_string()):
        dtype = pa.dictionary(pa.int32(), pa.string())
    return pd.ArrowDtype(dtype)


def set_column(table: pa.Table, colname: str, values: pa.Array) -> pa.Table:
    """Return a copy of `table` with column `colname` replaced by `values`.

    It does not modify it in-place, but returns a new `Table`; don't forget to assign it!

    This is a convenience method to be a little less verbose.

    `colname` must already occur in the table; it's datatype may be altered however.

    Example:
    ```python
    table = ...
    table = set_column(table, "my_column", table["my_column"].cast(pa.float64()))
    ```
    """
    index = table.schema.get_field_index(colname)
    if index < 0:
        raise ValueError(f"{colname} does not appear in {table.column_names=}")
    return table.set_column(index, colname, values)


def read_response(r: Response, schema: pa.Schema) -> pa.Table:
    """Read a Response that contains ASD ASCII data, adhering to the provided `schema`.

    The schema must be a [pyarrow.Schema][pyarrow.Schema] that specifies the column names and types (in pyarrow-native types).

    Any column that is specified in the schema, but missing in the content of the response, will be added filled with `null` values.

    If the columns `element` or `sp_num` are part of the schema but contain null values, they will be added/filled based on information extracted from the response url.

    This should only be the case when querying a single combination of both, e.g. 'H I' or `O III` (and not for 'Ar I-II' for instance).
    """
    data = csv.read_csv(
        BytesIO(r.content),
        read_options=csv.ReadOptions(),
        parse_options=csv.ParseOptions(delimiter="\t"),
        convert_options=csv.ConvertOptions(
            column_types=schema, strings_can_be_null=True, include_columns=schema.names, include_missing_columns=True
        ),
    )
    if ("element" in schema.names) and (data["element"].null_count > 0):
        element, _ = extract_state_from_response(r)
        data = data.set_column(data.column_names.index("element"), "element", pa.repeat(element, data.shape[0]))
    if ("sp_num" in schema.names) and (data["sp_num"].null_count > 0):
        _, sp_num = extract_state_from_response(r)
        data = data.set_column(
            data.column_names.index("sp_num"), "sp_num", pa.repeat(sp_num, data.shape[0]).cast(pa.int16())
        )

    return data


def parse_fraction_from_strings(col: pa.Array) -> pa.Array:
    """Parse a PyArrow column that contains strings, that can be fractions, into floats.

    Example of supported content: ["1","","5/7"]

    Extraction happens by splitting on "/", and dividing all elements that match a regex.

    Args:
        col (pa.Array): String-types pyarrow array to parse.

    Returns:
        fractions (pa.Array): A pyarrow array with floating point data.
    """
    # make contiguous if chunked
    if isinstance(col, pa.ChunkedArray):
        col = col.combine_chunks()
    # Build a string array containing only plain numeric strings,
    # with fractions and empty strings replaced by null.
    is_empty = pc.equal(col, "")
    is_fraction = pc.match_substring(col, "/")
    numeric_strings = pc.if_else(pc.or_(is_fraction, is_empty), pa.nulls(len(col), type=col.type), col)

    # Parse fractions to struct with field `num` and `den`
    extracted = pc.extract_regex(col, r"^(?P<num>\d+(?:\.\d+)?)/(?P<den>\d+(?:\.\d+)?)$")
    fraction_values = pc.divide(
        pc.cast(pc.struct_field(extracted, "num"), pa.float64()),
        pc.cast(pc.struct_field(extracted, "den"), pa.float64()),
    )

    numeric_values = pc.cast(numeric_strings, pa.float64())

    return pc.if_else(is_fraction, fraction_values, numeric_values)


def parse_sci_expr(col: pa.Array) -> pa.Array:
    """Extract scientific expression from a column using regex.

    The input array must be of a type like [pyarrow.string][pyarrow.string] or similar.

    The output array will be cast to [pyarrow.float64][pyarrow.float64].
    """
    return pc.struct_field(pc.extract_regex(col, r"(?P<value>[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)"), "value").cast(
        pa.float64()
    )


def wn_to_n(wn: pa.Array) -> pa.Array:
    """Convert wavenumber to refractive index, vectorized form for pyarrow.

    It uses the same calculation as [utils.wavenumber_to_refractive_index][(p).], which is the 5-term Sellmeier equation used by the NIST ASD.
    """
    sigma = pc.multiply(wn, pa.scalar(1e-4, pa.float64()))
    return pc.add(
        pa.scalar(1, pa.float64()),
        pc.multiply(
            pa.scalar(1e-8),
            pc.add(
                8060.51,
                pc.add(
                    pc.divide(pa.scalar(2480990), pc.subtract(pa.scalar(132.274), pc.power(sigma, 2))),
                    pc.divide(pa.scalar(17455.7), pc.subtract(pa.scalar(39.32957), pc.power(sigma, 2))),
                ),
            ),
        ),
    )
