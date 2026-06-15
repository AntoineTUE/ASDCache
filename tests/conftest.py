"""
Test configuration for `readASD`
"""

import pytest

from pathlib import Path
import importlib
import re
from requests_cache import CachedResponse, CachedSession
from ASDCache import SpectraCache


@pytest.fixture(scope="session")
def nist_pandas():
    nist = SpectraCache()
    yield nist


@pytest.fixture(scope="session")
def nist_polars():
    nist = SpectraCache(use_polars_backend=True)
    yield nist


@pytest.fixture
def mock_response_status_not_OK(mocker):
    # IMPORTANT: make sure that you set the attribute `content` not `contents`! (note the lack of 's')
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {}
    mock_response.text = ""
    mock_response.content = b""
    mock_response.ok = False
    mock_response.url = "https://physics.nist.gov/cgi-bin/ASD/lines1.pl?spectra=H+I&output_type=0&low_w=655&upp_w=657&unit=1&de=0&plot_out=0&I_scale_type=1&format=3&line_out=0&remove_js=on&no_spaces=on&en_unit=0&output=0&bibrefs=1&page_size=15&show_obs_wl=1&show_calc_wl=1&show_diff_obs_calc=1&show_wn=1&unc_out=1&order_out=0&max_low_enrg=&show_av=2&max_upp_enrg=&tsb_value=0&min_str=&A_out=0&f_out=on&S_out=on&loggf_out=on&intens_out=on&max_str=&allowed_out=1&forbid_out=1&min_accur=&min_intens=&conf_out=on&term_out=on&enrg_out=on&J_out=on&g_out=on&submit=Retrieve+Data"
    return mock_response


@pytest.fixture
def mock_response_HTML_in_content(mocker):
    # IMPORTANT: make sure that you set the attribute `content` not `contents`! (note the lack of 's')
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {}
    mock_response.text = "<!DOCTYPE"
    mock_response.content = b"<!DOCTYPE"
    mock_response.ok = True
    mock_response.url = "https://physics.nist.gov/cgi-bin/ASD/lines1.pl?spectra=H+I&output_type=0&low_w=655&upp_w=657&unit=1&de=0&plot_out=0&I_scale_type=1&format=3&line_out=0&remove_js=on&no_spaces=on&en_unit=0&output=0&bibrefs=1&page_size=15&show_obs_wl=1&show_calc_wl=1&show_diff_obs_calc=1&show_wn=1&unc_out=1&order_out=0&max_low_enrg=&show_av=2&max_upp_enrg=&tsb_value=0&min_str=&A_out=0&f_out=on&S_out=on&loggf_out=on&intens_out=on&max_str=&allowed_out=1&forbid_out=1&min_accur=&min_intens=&conf_out=on&term_out=on&enrg_out=on&J_out=on&g_out=on&submit=Retrieve+Data"
    return mock_response


@pytest.fixture()
def cache_location():
    cache_file = Path(__file__).parent.joinpath("test_cache.sqlite").resolve()
    yield cache_file


@pytest.fixture
def example_response(cache_location):
    ses = CachedSession(cache_location)
    key = list(ses.cache.responses)[0]
    yield ses.cache.get_response(key)
