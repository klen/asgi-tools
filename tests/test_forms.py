async def test_form_parser():
    from asgi_tools.forms import FormParser

    class FakeRequest:

        async def stream(self):
            yield b'answer=42&na'
            yield b'mes=bob&test'
            yield b'&names=alice'

    parser = FormParser()
    formdata = await parser.parse(FakeRequest())
    assert formdata['answer'] == '42'
    assert formdata['test'] == ''
    assert formdata.getall('names') == ['bob', 'alice']


async def test_multipart_parser(app, client):
    from asgi_tools.forms import MultipartParser
    from asgi_tools.tests import encode_multipart

    data, content_type = encode_multipart({
        'file1': open(__file__),
        'file2': open(__file__),
    })

    class FakeRequest:

        headers = {'content-type': content_type}
        charset = 'utf-8'

        async def stream(self):
            for chunk in data.split(b'\n'):
                yield chunk
                yield b'\n'

    parser = MultipartParser()
    formdata = await parser.parse(FakeRequest())
    assert formdata['file1']
    assert formdata['file1'].filename == __file__
    assert formdata['file1'].content_type == 'text/x-python'
    assert formdata['file2']
    assert b'test_multipart_parser' in formdata['file2'].read()
