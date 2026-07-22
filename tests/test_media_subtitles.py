import json

from omnireach.media.subtitles import (
    parse_bilibili_json,
    parse_json3,
    parse_vtt_or_srt,
    transcript_markdown,
)


def test_parse_vtt_strips_tags_decodes_entities_and_deduplicates():
    content = """WEBVTT

00:00:01.000 --> 00:00:02.500
<c>Hello &amp; welcome</c>

00:00:02.500 --> 00:00:03.500
Hello &amp; welcome

00:01:03.000 --> 00:01:04.000
Next line
"""

    segments = parse_vtt_or_srt(content)

    assert [segment.text for segment in segments] == ["Hello & welcome", "Next line"]
    assert segments[0].start_ms == 1000
    assert segments[1].start_ms == 63000


def test_parse_json3_combines_chunks():
    content = json.dumps({
        "events": [{
            "tStartMs": 250,
            "dDurationMs": 1000,
            "segs": [{"utf8": "hello "}, {"utf8": "world"}],
        }],
    })

    segments = parse_json3(content)

    assert segments[0].text == "hello world"
    assert segments[0].end_ms == 1250
    assert "**00:00:00** hello world" in transcript_markdown(segments)


def test_parse_bilibili_json_body():
    content = json.dumps({
        "body": [{"from": 1.25, "to": 2.5, "content": "你好 &amp; hello"}],
    })

    segments = parse_bilibili_json(content)

    assert segments[0].start_ms == 1250
    assert segments[0].end_ms == 2500
    assert segments[0].text == "你好 & hello"
