"""Helpers for constructing HTTP response headers."""

from urllib.parse import quote


def attachment_content_disposition(
    filename: str,
    fallback: str = "adaptivedocument.pdf",
) -> str:
    """Return a Unicode-safe Content-Disposition attachment header."""
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    basename = "".join(
        char for char in basename if ord(char) >= 32 and ord(char) != 127
    )
    basename = basename.strip() or fallback

    try:
        basename.encode("ascii")
        ascii_filename = basename
    except UnicodeEncodeError:
        ascii_filename = fallback

    ascii_filename = ascii_filename.replace("\\", "\\\\").replace('"', '\\"')
    encoded_filename = quote(basename, safe="")
    return (
        f'attachment; filename="{ascii_filename}"; '
        f"filename*=UTF-8''{encoded_filename}"
    )
