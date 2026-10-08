"""Bounded text extraction; PDF parsing runs in a time-limited separate process."""

import multiprocessing
import sys
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.config import Settings


class MaterialError(ValueError):
    pass


def _read_pdf(content: bytes, max_pages: int, max_chars: int) -> str:
    reader = PdfReader(BytesIO(content), strict=True)
    if reader.is_encrypted:
        raise MaterialError("不支持加密 PDF，请先在本机解密")
    if len(reader.pages) > max_pages:
        raise MaterialError("PDF 最多支持 40 页")
    parts, total = [], 0
    for page in reader.pages:
        streams = page.get_contents()
        if streams is not None and len(streams.get_data()) > 2_000_000:
            raise MaterialError("PDF 单页内容过大，请拆分后上传")
        part = page.extract_text() or ""
        total += len(part)
        if total > max_chars:
            raise MaterialError("提取后的资料最多 30000 字符，请拆分后上传")
        parts.append(part)
    text = "\n".join(parts)
    if len(text.strip()) < 20:
        raise MaterialError("PDF 没有足够文本层；扫描件需自行 OCR 后上传，本系统不提供 OCR")
    return text


def _pdf_worker(connection, content: bytes, max_pages: int, max_chars: int):
    try:
        # Linux provides hard process resource limits. Other platforms retain wall-clock timeout
        # and decoder caps, but are not suitable for hostile, publicly uploaded PDFs.
        if sys.platform.startswith("linux"):
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
            resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
        import pypdf.filters as filters

        for name in (
            "ZLIB_MAX_OUTPUT_LENGTH",
            "LZW_MAX_OUTPUT_LENGTH",
            "RUN_LENGTH_MAX_OUTPUT_LENGTH",
            "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH",
            "JBIG2_MAX_OUTPUT_LENGTH",
        ):
            if hasattr(filters, name):
                setattr(filters, name, 2_000_000)
        connection.send((True, _read_pdf(content, max_pages, max_chars)))
    except MaterialError as exc:
        connection.send((False, str(exc)))
    except Exception:
        connection.send((False, "无法读取 PDF，可能损坏、过于复杂或超过解析资源限制"))
    finally:
        connection.close()


def _bounded_pdf(content: bytes, settings: Settings) -> str:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_pdf_worker,
        args=(sender, content, settings.max_pdf_pages, settings.max_material_chars),
        daemon=True,
    )
    try:
        process.start()
        sender.close()
        if not receiver.poll(12):
            raise MaterialError("PDF 解析超时，请拆分文件或改传 UTF-8 文本")
        try:
            success, value = receiver.recv()
        except EOFError as exc:
            raise MaterialError("PDF 超过解析资源限制或无法读取") from exc
        if not success:
            raise MaterialError(value)
        return value
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
        receiver.close()
        sender.close()


def extract_text(filename: str, content: bytes, settings: Settings) -> str:
    if not content or len(content) > settings.upload_limit_bytes:
        raise MaterialError("文件为空或超过 5 MB 上限")
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise MaterialError("文本文件请保存为 UTF-8 编码后上传") from exc
    elif suffix == ".pdf":
        text = _bounded_pdf(content, settings)
    else:
        raise MaterialError("只支持 .txt、.md 和包含文本层的 .pdf 文件")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if "\x00" in text or not 20 <= len(text) <= settings.max_material_chars:
        raise MaterialError("资料应为 20 到 30000 字符的文本，且不能包含 NUL 字符")
    return text
