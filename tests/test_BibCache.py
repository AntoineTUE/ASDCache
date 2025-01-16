import pytest
from ASDCache import BibCache


@pytest.mark.parametrize(
    "reference, expected",
    [
        ("T1788", ("T", "1788", "")),
        ("L13456n3", ("L", "13456", "n3")),
        ("T8888c478", ("T", "8888", "c478")),
        ("u38", (None, None, "u38")),
        ("T6936n", ("T", "6936", "n")),
        ("LS", ("T", None, "LS")),
    ],
)
def test_bib_ref_expression(reference, expected):
    assert BibCache.parse_reference_code(reference) == expected


@pytest.mark.parametrize("status,content", [(503, b"Service Unavailable"), (200, b"There was a problem")])
def test_bib_check_response_success_failed(mocker, status, content):
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {}
    mock_response.content = content
    mock_response.status_code = status
    assert BibCache._check_response_success(mock_response) is False
