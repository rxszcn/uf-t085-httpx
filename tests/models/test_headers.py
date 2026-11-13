import pytest

import httpx


def test_headers():
    h = httpx.Headers([("a", "123"), ("a", "456"), ("b", "789")])
    assert "a" in h
    assert "A" in h
    assert "b" in h
    assert "B" in h
    assert "c" not in h
    assert h["a"] == "123, 456"
    assert h.get("a") == "123, 456"
    assert h.get("nope", default=None) is None
    assert h.get_list("a") == ["123", "456"]

    assert list(h.keys()) == ["a", "b"]
    assert list(h.values()) == ["123, 456", "789"]
    assert list(h.items()) == [("a", "123, 456"), ("b", "789")]
    assert h.multi_items() == [("a", "123"), ("a", "456"), ("b", "789")]
    assert list(h) == ["a", "b"]
    assert dict(h) == {"a": "123, 456", "b": "789"}
    assert repr(h) == "Headers([('a', '123'), ('a', '456'), ('b', '789')])"
    assert h == [("a", "123"), ("b", "789"), ("a", "456")]
    assert h == [("a", "123"), ("A", "456"), ("b", "789")]
    assert h == {"a": "123", "A": "456", "b": "789"}
    assert h != "a: 123\nA: 456\nb: 789"

    h = httpx.Headers({"a": "123", "b": "789"})
    assert h["A"] == "123"
    assert h["B"] == "789"
    assert h.raw == [(b"a", b"123"), (b"b", b"789")]
    assert repr(h) == "Headers({'a': '123', 'b': '789'})"


def test_header_mutations():
    h = httpx.Headers()
    assert dict(h) == {}
    h["a"] = "1"
    assert dict(h) == {"a": "1"}
    h["a"] = "2"
    assert dict(h) == {"a": "2"}
    h.setdefault("a", "3")
    assert dict(h) == {"a": "2"}
    h.setdefault("b", "4")
    assert dict(h) == {"a": "2", "b": "4"}
    del h["a"]
    assert dict(h) == {"b": "4"}
    assert h.raw == [(b"b", b"4")]


def test_copy_headers_method():
    headers = httpx.Headers({"custom": "example"})
    headers_copy = headers.copy()
    assert headers == headers_copy
    assert headers is not headers_copy


def test_copy_headers_init():
    headers = httpx.Headers({"custom": "example"})
    headers_copy = httpx.Headers(headers)
    assert headers == headers_copy


def test_headers_insert_retains_ordering():
    headers = httpx.Headers({"a": "a", "b": "b", "c": "c"})
    headers["b"] = "123"
    assert list(headers.values()) == ["a", "123", "c"]


def test_headers_insert_appends_if_new():
    headers = httpx.Headers({"a": "a", "b": "b", "c": "c"})
    headers["d"] = "123"
    assert list(headers.values()) == ["a", "b", "c", "123"]


def test_headers_insert_removes_all_existing():
    headers = httpx.Headers([("a", "123"), ("a", "456")])
    headers["a"] = "789"
    assert dict(headers) == {"a": "789"}


def test_headers_delete_removes_all_existing():
    headers = httpx.Headers([("a", "123"), ("a", "456")])
    del headers["a"]
    assert dict(headers) == {}


def test_headers_dict_repr():
    """
    Headers should display with a dict repr by default.
    """
    headers = httpx.Headers({"custom": "example"})
    assert repr(headers) == "Headers({'custom': 'example'})"


def test_headers_encoding_in_repr():
    """
    Headers should display an encoding in the repr if required.
    """
    headers = httpx.Headers({b"custom": "example ☃".encode("utf-8")})
    assert repr(headers) == "Headers({'custom': 'example ☃'}, encoding='utf-8')"


def test_headers_list_repr():
    """
    Headers should display with a list repr if they include multiple identical keys.
    """
    headers = httpx.Headers([("custom", "example 1"), ("custom", "example 2")])
    assert (
        repr(headers) == "Headers([('custom', 'example 1'), ('custom', 'example 2')])"
    )


def test_headers_decode_ascii():
    """
    Headers should decode as ascii by default.
    """
    raw_headers = [(b"Custom", b"Example")]
    headers = httpx.Headers(raw_headers)
    assert dict(headers) == {"custom": "Example"}
    assert headers.encoding == "ascii"


def test_headers_decode_utf_8():
    """
    Headers containing non-ascii codepoints should default to decoding as utf-8.
    """
    raw_headers = [(b"Custom", "Code point: ☃".encode("utf-8"))]
    headers = httpx.Headers(raw_headers)
    assert dict(headers) == {"custom": "Code point: ☃"}
    assert headers.encoding == "utf-8"


def test_headers_decode_iso_8859_1():
    """
    Headers containing non-UTF-8 codepoints should default to decoding as iso-8859-1.
    """
    raw_headers = [(b"Custom", "Code point: ÿ".encode("iso-8859-1"))]
    headers = httpx.Headers(raw_headers)
    assert dict(headers) == {"custom": "Code point: ÿ"}
    assert headers.encoding == "iso-8859-1"


def test_headers_decode_explicit_encoding():
    """
    An explicit encoding may be set on headers in order to force a
    particular decoding.
    """
    raw_headers = [(b"Custom", "Code point: ☃".encode("utf-8"))]
    headers = httpx.Headers(raw_headers)
    headers.encoding = "iso-8859-1"
    assert dict(headers) == {"custom": "Code point: â\x98\x83"}
    assert headers.encoding == "iso-8859-1"


# A code point above U+00FF cannot be represented as ISO-8859-1 and therefore
# cannot be sent on the wire, whereas every ASCII and Latin-1 code point can.
NON_LATIN1_VALUE = "héllo→世界"  # contains the non-Latin-1 code points →, 世, 界


class TestInvalidHeaderValues:
    """
    Outgoing header values are validated up front, at the single point every
    header write funnels through, so an unencodable value raises an explicit
    `InvalidHeader` naming the field and offending value rather than an opaque
    low-level codec error. Both the constructor (single-value and multi-value
    shapes) and the mutation write paths must behave identically.
    """

    def test_single_value_mapping_constructor(self):
        with pytest.raises(httpx.InvalidHeader) as exc_info:
            httpx.Headers({"X-Custom-Header": NON_LATIN1_VALUE})
        message = str(exc_info.value)
        # The business-side field spelling (with its original casing) is kept.
        assert "X-Custom-Header" in message
        # The offending value is summarized in the message.
        assert repr(NON_LATIN1_VALUE) in message
        assert "ISO-8859-1" in message

    def test_single_value_sequence_constructor(self):
        with pytest.raises(httpx.InvalidHeader, match="X-Custom-Header"):
            httpx.Headers([("X-Custom-Header", NON_LATIN1_VALUE)])

    def test_multi_value_sequence_constructor_points_at_offending_value(self):
        headers = [
            ("X-Multi", "ascii-ok"),
            ("X-Multi", NON_LATIN1_VALUE),
            ("X-Multi", "also-ascii"),
        ]
        with pytest.raises(httpx.InvalidHeader) as exc_info:
            httpx.Headers(headers)
        message = str(exc_info.value)
        assert "X-Multi" in message
        assert repr(NON_LATIN1_VALUE) in message
        # The compliant values must not be quoted as the offender.
        assert "ascii-ok" not in message

    def test_setitem_single_value_write_path(self):
        headers = httpx.Headers()
        with pytest.raises(httpx.InvalidHeader, match="X-Custom-Header"):
            headers["X-Custom-Header"] = NON_LATIN1_VALUE
        # A failed pre-check must not leave a partial write behind.
        assert "X-Custom-Header" not in headers

    def test_setitem_replacing_existing_header_is_atomic(self):
        headers = httpx.Headers({"X-Custom-Header": "original-ascii"})
        with pytest.raises(httpx.InvalidHeader):
            headers["X-Custom-Header"] = NON_LATIN1_VALUE
        # The previously valid value is retained.
        assert headers["X-Custom-Header"] == "original-ascii"

    def test_update_write_path(self):
        headers = httpx.Headers({"Keep": "ascii"})
        with pytest.raises(httpx.InvalidHeader, match="X-Updated"):
            headers.update([("X-Updated", NON_LATIN1_VALUE)])
        assert headers["Keep"] == "ascii"

    def test_field_name_keeps_original_spelling(self):
        # The lookup key is normalized to lowercase internally, but the error
        # message must surface the spelling the caller provided.
        with pytest.raises(httpx.InvalidHeader, match="X-MyWeird-Header"):
            httpx.Headers([("X-MyWeird-Header", NON_LATIN1_VALUE)])

    def test_long_value_is_summarized_not_dumped_verbatim(self):
        long_value = "世" * 100
        with pytest.raises(httpx.InvalidHeader) as exc_info:
            httpx.Headers({"X-Long": long_value})
        # The full value must not appear verbatim; it is truncated with an
        # ellipsis, keeping the embedded summary bounded regardless of length.
        assert repr(long_value) not in str(exc_info.value)
        assert "..." in str(exc_info.value)

    @pytest.mark.parametrize("value", ["", "plain ascii", "café", "ÿ", "À" * 10])
    def test_ascii_and_latin1_values_are_accepted_on_every_path(self, value):
        # Constructor, mapping and sequence shapes ...
        from_mapping = httpx.Headers({"X-Field": value})
        from_sequence = httpx.Headers([("X-Field", value)])
        assert from_mapping["X-Field"] == value
        assert from_sequence["X-Field"] == value
        # ... and the mutation write path.
        headers = httpx.Headers()
        headers["X-Field"] = value
        assert headers["X-Field"] == value
        # Latin-1 values are stored as their ISO-8859-1 byte representation.
        assert headers.raw[0][1] == value.encode("iso-8859-1")

    def test_bytes_values_are_not_prechecked(self):
        # Raw bytes are passed through untouched, preserving the existing
        # behaviour for callers that already hold encoded header bytes.
        raw_value = NON_LATIN1_VALUE.encode("utf-8")
        headers = httpx.Headers({b"X-Bytes": raw_value})
        assert headers.raw == [(b"X-Bytes", raw_value)]

    def test_invalid_header_is_a_value_error(self):
        with pytest.raises(ValueError):
            httpx.Headers({"X-Field": NON_LATIN1_VALUE})


def test_multiple_headers():
    """
    `Headers.get_list` should support both split_commas=False and split_commas=True.
    """
    h = httpx.Headers([("set-cookie", "a, b"), ("set-cookie", "c")])
    assert h.get_list("Set-Cookie") == ["a, b", "c"]

    h = httpx.Headers([("vary", "a, b"), ("vary", "c")])
    assert h.get_list("Vary", split_commas=True) == ["a", "b", "c"]


@pytest.mark.parametrize("header", ["authorization", "proxy-authorization"])
def test_sensitive_headers(header):
    """
    Some headers should be obfuscated because they contain sensitive data.
    """
    value = "s3kr3t"
    h = httpx.Headers({header: value})
    assert repr(h) == "Headers({'%s': '[secure]'})" % header


@pytest.mark.parametrize(
    "headers, output",
    [
        ([("content-type", "text/html")], [("content-type", "text/html")]),
        ([("authorization", "s3kr3t")], [("authorization", "[secure]")]),
        ([("proxy-authorization", "s3kr3t")], [("proxy-authorization", "[secure]")]),
    ],
)
def test_obfuscate_sensitive_headers(headers, output):
    as_dict = {k: v for k, v in output}
    headers_class = httpx.Headers({k: v for k, v in headers})
    assert repr(headers_class) == f"Headers({as_dict!r})"


@pytest.mark.parametrize(
    "value, expected",
    (
        (
            '<http:/.../front.jpeg>; rel=front; type="image/jpeg"',
            [{"url": "http:/.../front.jpeg", "rel": "front", "type": "image/jpeg"}],
        ),
        ("<http:/.../front.jpeg>", [{"url": "http:/.../front.jpeg"}]),
        ("<http:/.../front.jpeg>;", [{"url": "http:/.../front.jpeg"}]),
        (
            '<http:/.../front.jpeg>; type="image/jpeg",<http://.../back.jpeg>;',
            [
                {"url": "http:/.../front.jpeg", "type": "image/jpeg"},
                {"url": "http://.../back.jpeg"},
            ],
        ),
        ("", []),
    ),
)
def test_parse_header_links(value, expected):
    all_links = httpx.Response(200, headers={"link": value}).links.values()
    assert all(link in all_links for link in expected)


def test_parse_header_links_no_link():
    all_links = httpx.Response(200).links
    assert all_links == {}
