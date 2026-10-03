from src import transcript
from src.transcript import fetch_transcript, parse_vtt

VTT = """WEBVTT
Kind: captions
Language: en

1
00:00:00.000 --> 00:00:02.000
<c>Hello</c> and welcome

2
00:00:02.000 --> 00:00:04.000
Hello and welcome

3
00:00:04.000 --> 00:00:06.000
to the <00:00:05.000>show
"""


def test_parse_vtt_strips_and_dedups():
    out = parse_vtt(VTT)
    assert out == "Hello and welcome to the show"


def test_fetch_prefers_api(monkeypatch):
    monkeypatch.setattr(transcript, "_from_api", lambda vid: "api text")
    monkeypatch.setattr(transcript, "_from_ytdlp", lambda vid: "ytdlp text")
    assert fetch_transcript("v") == "api text"


def test_fetch_falls_back_to_ytdlp(monkeypatch):
    monkeypatch.setattr(transcript, "_from_api", lambda vid: None)
    monkeypatch.setattr(transcript, "_from_ytdlp", lambda vid: "ytdlp text")
    assert fetch_transcript("v") == "ytdlp text"


def test_fetch_returns_none_when_both_fail(monkeypatch):
    monkeypatch.setattr(transcript, "_from_api", lambda vid: None)
    monkeypatch.setattr(transcript, "_from_ytdlp", lambda vid: None)
    assert fetch_transcript("v") is None


class _Snip:
    def __init__(self, text):
        self.text = text


def test_from_api_joins_snippets(monkeypatch):
    class FakeApi:
        def fetch(self, video_id, languages=None):
            return [_Snip("part one"), _Snip("part two")]

    import youtube_transcript_api
    monkeypatch.setattr(youtube_transcript_api, "YouTubeTranscriptApi", FakeApi)
    assert transcript._from_api("v") == "part one part two"


def test_from_api_falls_back_to_any_available_language(monkeypatch):
    class FakeTranscript:
        def fetch(self):
            return [_Snip("hindi text")]

    class FakeApi:
        def fetch(self, video_id, languages=None):
            raise RuntimeError("no preferred lang")

        def list(self, video_id):
            return [FakeTranscript()]

    import youtube_transcript_api
    monkeypatch.setattr(youtube_transcript_api, "YouTubeTranscriptApi", FakeApi)
    assert transcript._from_api("v") == "hindi text"
