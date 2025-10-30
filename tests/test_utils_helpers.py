from types import SimpleNamespace
from src.utils.helpers import read_uploaded_text


def test_read_uploaded_text_bytes():
    class U:
        def read(self):
            return b'hello world'

    assert read_uploaded_text(U()) == 'hello world'


def test_read_uploaded_text_none():
    assert read_uploaded_text(None) is None
