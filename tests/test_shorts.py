import requests
import responses

from src.shorts import SHORTS_URL, is_short


@responses.activate
def test_status_200_is_short():
    responses.add(responses.GET, SHORTS_URL.format("SHORTID"), status=200)
    assert is_short("SHORTID") is True


@responses.activate
def test_redirect_is_not_short():
    responses.add(
        responses.GET,
        SHORTS_URL.format("NORMALID"),
        status=303,
        headers={"Location": "https://www.youtube.com/watch?v=NORMALID"},
    )
    assert is_short("NORMALID") is False


@responses.activate
def test_network_error_fails_open():
    responses.add(
        responses.GET,
        SHORTS_URL.format("BOOM"),
        body=requests.ConnectionError("down"),
    )
    assert is_short("BOOM") is False
