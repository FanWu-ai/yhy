from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.config import Settings
from app.materials import MaterialError, extract_text


def pdf_bytes(text: str | None = None, pages: int = 1, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=600, height=800)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 10 700 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = stream
    if encrypted:
        writer.encrypt("not-a-real-password")
    target = BytesIO()
    writer.write(target)
    return target.getvalue()


def test_utf8_and_newline_normalization():
    assert (
        extract_text(
            "note.MD", b"\xef\xbb\xbfA long sample line for testing\r\nsecond line", Settings()
        )
        == "A long sample line for testing\nsecond line"
    )


def test_real_text_pdf():
    content = pdf_bytes("An original educational sample about Python lists.")
    assert "Python lists" in extract_text("note.pdf", content, Settings())


@pytest.mark.parametrize(
    "filename,content",
    [
        ("bad.txt", b"\xff"),
        ("bad.exe", b"x" * 100),
        ("empty.txt", b""),
        ("short.txt", b"short"),
        ("long.txt", b"x" * 30001),
        ("huge.txt", b"x" * (5 * 1024 * 1024 + 1)),
        ("null.txt", b"x" * 20 + b"\x00"),
        ("bad.pdf", b"not a PDF"),
    ],
)
def test_bad_files(filename, content):
    with pytest.raises(MaterialError):
        extract_text(filename, content, Settings())


@pytest.mark.parametrize("content", [pdf_bytes(), pdf_bytes(pages=41), pdf_bytes(encrypted=True)])
def test_unsupported_pdf_variants(content):
    with pytest.raises(MaterialError):
        extract_text("note.pdf", content, Settings())


def test_upload_api_rejects_invalid_file(client):
    response = client.post(
        "/api/materials/upload",
        data={"title": "test", "course": "sample"},
        files={"file": ("bad.pdf", b"not a PDF")},
    )
    assert response.status_code == 422
    assert client.get("/api/materials").json() == []
