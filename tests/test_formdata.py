from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest
import yaml


async def test_formdata(gen_request, tmp_path):
    from asgi_tools.forms import read_formdata
    from asgi_tools.tests import encode_multipart

    request = gen_request(body=[b"answer=42&na", b"mes=bob&test", b"&names=alice"])
    formdata = await read_formdata(request, 0, None, 0)
    assert formdata["answer"] == "42"
    assert formdata["test"] == ""
    assert formdata.getall("names") == ["bob", "alice"]

    test_bytes = Path(__file__).read_bytes()
    data, content_type = encode_multipart(
        {
            "file1": io.BytesIO(test_bytes),
            "file2": io.BytesIO(test_bytes),
        },
    )
    body = [chunk + b"\n" for chunk in data.split(b"\n")]
    request = gen_request(body=body, headers={"content-type": content_type})
    formdata = await read_formdata(request, 0, None, 0)
    assert formdata["file1"]
    assert formdata["file1"].name == Path(__file__).name
    assert formdata["file1"].content_type == "text/x-python"
    assert formdata["file2"]
    assert b"test_multipart_parser" in formdata["file2"].read()

    request = gen_request(body=body, headers={"content-type": content_type})
    upload_to = lambda f: f"{tmp_path}/{f}"  # noqa
    formdata = await read_formdata(request, 0, upload_to, 0)
    assert formdata["file1"]
    assert formdata["file1"].name == str(tmp_path / Path(__file__).name)
    assert formdata["file1"].content_type == "text/x-python"
    assert formdata["file2"]
    assert formdata["file2"].name.startswith(str(tmp_path))
    assert b"test_multipart_parser" in formdata["file2"].read()


@pytest.mark.parametrize(
    "sample",
    [
        (b"foo=bar", {"foo": "bar"}),
        (b"&foo=bar", {"foo": "bar"}),
        (b"foo=bar&", {"foo": "bar"}),
        (b"foo=bar&asdf=baz", {"foo": "bar", "asdf": "baz"}),
        (b"foo=bar;asdf=baz", {"foo": "bar", "asdf": "baz"}),
        (b"foo=bar&&another=asdf", {"foo": "bar", "another": "asdf"}),
        (b"foo=bar&blank&another=asdf", {"another": "asdf", "blank": "", "foo": "bar"}),
        (b"value=test%20passed", {"value": "test passed"}),
    ],
)
def test_query(sample):
    from asgi_tools.forms import FormReader

    data, expected = sample

    reader = FormReader("utf-8")
    parser = reader.init_parser(None, 0)
    feed(parser, data)
    assert dict(reader.form) == expected


DATA = Path(__file__).parent / "fixtures/multipart"


@pytest.mark.parametrize(
    "basename",
    [
        "single_field",
        "single_field_longer",
        "single_field_single_file",
        "single_field_with_leading_newlines",
        "single_file",
        "utf8_filename",
        "multiple_fields",
        "multiple_files",
        "almost_match_boundary",
        "almost_match_boundary_without_CR",
        "almost_match_boundary_without_LF",
        "almost_match_boundary_without_final_hyphen",
        "bad_initial_boundary",
        "bad_end_of_headers",
        "CR_in_header",
        "CR_in_header_value",
        "empty_header",
    ],
)
def test_multipart(basename, gen_request):
    from asgi_tools.forms import MultipartReader

    data, meta = loader(basename)

    # Initialize parsers
    reader = MultipartReader("utf-8", None, 0)
    request = gen_request(
        headers={"content-type": f"multipart/form-data; boundary={meta['boundary']}"},
    )
    parser = reader.init_parser(request, 0)
    try:
        feed(parser, data)
    except ValueError:
        assert meta["expected"]["error"]

    parser.finalize()

    for (field, data), expected in zip(reader.form.items(), meta["expected"]):
        assert field == expected["name"]
        if expected["type"] == "field":
            assert isinstance(data, str)
            assert data == expected["data"].decode("utf-8")

        else:
            assert isinstance(data, tempfile.SpooledTemporaryFile)
            assert data.name == expected["file_name"]
            data = data.read()
            assert data == expected["data"]


# Utils
# -----


def feed(parser, data):
    for n in range(0, len(data), 5):
        parser.write(data[n : n + 5])
    parser.finalize()


def loader(basename):
    data = (DATA / basename).with_suffix(".http").read_bytes()
    meta = (DATA / basename).with_suffix(".yaml")
    with meta.open("rb") as f:
        meta = yaml.load(f, Loader=yaml.SafeLoader)
    return data, meta
