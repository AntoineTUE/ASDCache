"""
Test configuration for `readASD`
"""

import pytest

# from unittest.mock import MagicMock
import importlib
import re
from requests_cache import CachedResponse
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
def mock_response(mocker):
    contents = r"""obs_wl_vac(nm)	unc_obs_wl	ritz_wl_vac(nm)	unc_ritz_wl	obs-ritz	wn(cm-1)	intens	Aki(s^-1)	fik	S(a.u.)	log_gf	Acc	Ei(cm-1)	Ek(cm-1)	conf_i	term_i	J_i	conf_k	term_k	J_k	g_i	g_k	Type	tp_ref	line_ref	
"656.4522552"	"0.0000024"	"656.4522556"	"0.0000009"	"-0.0000004"	"15233.40033"	""	"5.3877e+07"	"6.9614e-01"	"3.0089e+01"	"0.14373"	AAA	"82258.9191133"	"97492.319433"	"2p"	"2P*"	"1/2"	"3d"	"2D"	"3/2"	2	4		"T7771"	"L2752"	
""	""	"656.4527"	"0.0004"	""	"15233.390"	""	""	""	""	""		""	""	""	""	""	""	""	""				""	"c67"	
""	""	"656.4535"	"0.0009"	""	"15233.372"	""	""	""	""	""		""	""	""	""	""	""	""	""				""	"c68"	
"656.4537684"	"0.0000004"	"656.4537685"	"0.0000003"	"-0.0000001"	"15233.365214"	""	"2.2448e+07"	"2.9005e-01"	"1.2537e+01"	"-0.23650"	AAA	"82258.9543992821"	"97492.319611"	"2s"	"2S"	"1/2"	"3p"	"2P*"	"3/2"	2	4		"T7771"	"L6891c38"	
""	""	"656.4564672"	"0.0000003"	""	"15233.302588"	""	"2.1046e+06"	"1.3597e-02"	"5.8769e-01"	"-1.56553"	AAA	"82258.9191133"	"97492.221701"	"2p"	"2P*"	"1/2"	"3s"	"2S"	"1/2"	2	2		"T7771"	""	
""	""	"656.4579878"	"0.0000003"	""	"15233.267302"	""	""	""	""	""		"82258.9543992821"	"97492.221701"	"2s"	"2S"	"1/2"	"3s"	"2S"	"1/2"	2	2	M1	""	""	
""	""	"656.4583"	"0.0006"	""	"15233.260"	""	""	""	""	""		""	""	""	""	""	""	""	""				""	"c66"	
"656.4584404"	"0.0000004"	"656.4584403"	"0.0000003"	"0.0000001"	"15233.256799"	""	"2.2449e+07"	"1.4503e-01"	"6.2687e+00"	"-0.53750"	AAA	"82258.9543992821"	"97492.211200"	"2s"	"2S"	"1/2"	"3p"	"2P*"	"1/2"	2	2		"T7771"	"L6891c38"	
"656.460"	"0.003"	"656.4632"	"0.0007"	"-0.003"	"15233.21"	"500000"	"4.4101e+07"	"6.4108e-01"	"1.1084e+02"	"0.71000"	AAA	"82259.158"	"97492.304"	"2"	""	""	"3"	""	""	8	18		"T8637"	"L7400c29"	
""	""	"656.4608"	"0.0009"	""	"15233.202"	""	""	""	""	""		""	""	""	""	""	""	""	""				""	"c69"	
"656.466464"	"0.000006"	"656.4664660"	"0.0000003"	"-0.000002"	"15233.07061"	""	"6.4651e+07"	"6.2654e-01"	"5.4162e+01"	"0.39901"	AAA	"82259.2850014"	"97492.355566"	"2p"	"2P*"	"3/2"	"3d"	"2D"	"5/2"	4	6		"T7771"	"L2752"	
""	""	"656.46662"	"0.00003"	""	"15233.0670"	""	""	""	""	""		""	""	""	""	""	""	""	""				""	"c71"	
""	""	"656.4667"	"0.0003"	""	"15233.065"	""	""	""	""	""		""	""	""	""	""	""	""	""				""	"c70"	
""	""	"656.4680232"	"0.0000009"	""	"15233.034432"	""	"1.0775e+07"	"6.9615e-02"	"6.0180e+00"	"-0.55524"	AAA	"82259.2850014"	"97492.319433"	"2p"	"2P*"	"3/2"	"3d"	"2D"	"3/2"	4	4		"T7771"	""	
""	""	"656.4722349"	"0.0000003"	""	"15232.936700"	""	"4.2097e+06"	"1.3599e-02"	"1.1756e+00"	"-1.26443"	AAA	"82259.2850014"	"97492.221701"	"2p"	"2P*"	"3/2"	"3s"	"2S"	"1/2"	4	2		"T7771"	""	
"""

    # Create the mock response object
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {}
    mock_response.text = contents
    mock_response.status_code = 200
    mock_response.url = "https://physics.nist.gov/cgi-bin/ASD/lines1.pl?spectra=H+I&output_type=0&low_w=655&upp_w=657&unit=1&de=0&plot_out=0&I_scale_type=1&format=3&line_out=0&remove_js=on&no_spaces=on&en_unit=0&output=0&bibrefs=1&page_size=15&show_obs_wl=1&show_calc_wl=1&show_diff_obs_calc=1&show_wn=1&unc_out=1&order_out=0&max_low_enrg=&show_av=2&max_upp_enrg=&tsb_value=0&min_str=&A_out=0&f_out=on&S_out=on&loggf_out=on&intens_out=on&max_str=&allowed_out=1&forbid_out=1&min_accur=&min_intens=&conf_out=on&term_out=on&enrg_out=on&J_out=on&g_out=on&submit=Retrieve+Data"

    return mock_response


@pytest.fixture
def mock_response_status_not_200(mocker):
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {}
    mock_response.text = ""
    mock_response.content = b""
    mock_response.status_code = 400
    mock_response.url = "https://physics.nist.gov/cgi-bin/ASD/lines1.pl?spectra=H+I&output_type=0&low_w=655&upp_w=657&unit=1&de=0&plot_out=0&I_scale_type=1&format=3&line_out=0&remove_js=on&no_spaces=on&en_unit=0&output=0&bibrefs=1&page_size=15&show_obs_wl=1&show_calc_wl=1&show_diff_obs_calc=1&show_wn=1&unc_out=1&order_out=0&max_low_enrg=&show_av=2&max_upp_enrg=&tsb_value=0&min_str=&A_out=0&f_out=on&S_out=on&loggf_out=on&intens_out=on&max_str=&allowed_out=1&forbid_out=1&min_accur=&min_intens=&conf_out=on&term_out=on&enrg_out=on&J_out=on&g_out=on&submit=Retrieve+Data"
    return mock_response


@pytest.fixture
def mock_response_error_in_content(mocker):
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {}
    mock_response.text = b"Error Message"
    mock_response.content = b"Error Message:"
    mock_response.status_code = 200
    mock_response.url = "https://physics.nist.gov/cgi-bin/ASD/lines1.pl?spectra=H+I&output_type=0&low_w=655&upp_w=657&unit=1&de=0&plot_out=0&I_scale_type=1&format=3&line_out=0&remove_js=on&no_spaces=on&en_unit=0&output=0&bibrefs=1&page_size=15&show_obs_wl=1&show_calc_wl=1&show_diff_obs_calc=1&show_wn=1&unc_out=1&order_out=0&max_low_enrg=&show_av=2&max_upp_enrg=&tsb_value=0&min_str=&A_out=0&f_out=on&S_out=on&loggf_out=on&intens_out=on&max_str=&allowed_out=1&forbid_out=1&min_accur=&min_intens=&conf_out=on&term_out=on&enrg_out=on&J_out=on&g_out=on&submit=Retrieve+Data"
    return mock_response


@pytest.fixture(scope="session")
def full_nist_backends():
    interval = (500, 600)
    expr_all = re.compile(rf".*low_w=({interval[0]}).*spectra=(All\+spectra).*upp_w=({interval[1]}).*")
    expr_F = re.compile(rf".*low_w=({interval[0]}).*spectra=(F\+I\-II).*upp_w=({interval[1]}).*")
    nist_pandas = SpectraCache()
    nist_polars = SpectraCache(use_polars_backend=True)
    nist_pandas.fetch("All spectra", wl_range=interval)
    yield (nist_pandas, nist_polars, interval)
    # clean up of the two limited-range queries above such that tests run with a clean slate and we don't polute the cache
    for expr in [expr_all, expr_F]:
        keys = [cached.cache_key for cached in nist_pandas.session.cache.filter() if expr.search(cached.url)]
        if len(keys) > 0:
            for key in keys:
                nist_pandas.session.cache.delete(key)
