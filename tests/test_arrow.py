import pyarrow as pa
import pyarrow.compute as pc
import pytest

from ASDCache import Schemas, SpectraCache, arrow


def test_read_level_responses(cache_location):
    cache = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    for r in cache.levels.responses:
        data = arrow.read_response(r, Schemas.level_parsing_schema)
        assert "element" in data.column_names
        assert "sp_num" in data.column_names
        for k in Schemas.level_parsing_schema:
            assert k.name in data.column_names


@pytest.mark.parametrize("species,size,max_level", [("H I", 106, 109678.77174307)])
def test_read_level_response_detailed(cache_location, species, size, max_level):
    cache = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    resp = cache.levels._get_data(species)
    data = arrow.read_response(resp, Schemas.level_parsing_schema)
    assert data.shape[1] == len(Schemas.level_parsing_schema)
    assert data.shape[0] == size
    assert len(data["element"].unique()) == 1
    assert data["element"].unique()[0].as_py() == species.split(" ", 1)[0]
    assert pc.min(data["Level (cm-1)"]).as_py() == 0.0
    assert pc.max(data["Level (cm-1)"]).as_py() == max_level


def test_read_line_responses(cache_location):
    cache = SpectraCache(cache_path=cache_location, cache_expiry=-1)
    for r in cache.responses:
        data = arrow.read_response(r, Schemas.line_parsing_schema)
        assert "element" in data.column_names
        assert "sp_num" in data.column_names
        for k in Schemas.line_parsing_schema:
            assert k.name in data.column_names
        assert len(data["element"].unique()) > 0
        assert len(data["sp_num"].unique()) > 0
