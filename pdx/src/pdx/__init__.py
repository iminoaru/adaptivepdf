"""
pdx — the .off adaptive document format.

Quick usage:
    from pdx import pdf_to_markdown, create_off, read_markdown

    md = pdf_to_markdown("resume.pdf")
    create_off("resume.pdf", md)       # → resume.off
    print(read_markdown("resume.off"))
"""
from pdx.converter import pdf_to_markdown
from pdx.format import create_off, build_off_bytes, read_markdown, open_pdf

__all__ = ["pdf_to_markdown", "create_off", "build_off_bytes", "read_markdown", "open_pdf"]


def main() -> None:
    """
    CLI entry point — registered as `off` command in pyproject.toml.

    off convert <file.pdf>    convert PDF → .off (markdown + embedded PDF)
    off read    <file.off>    print the markdown layer to stdout
    off open    <file.off>    extract PDF layer and open in system viewer
    off setup                 register .off file association on macOS
    """
    import sys
    from pathlib import Path

    args = sys.argv[1:]

    def _usage() -> None:
        print("usage: off <command> [file]")
        print("commands:")
        print("  convert <file.pdf>   convert PDF to .off")
        print("  read    <file.off>   print markdown layer to stdout")
        print("  open    <file.off>   open PDF layer in system viewer")
        print("  setup                register .off with system (macOS)")
        sys.exit(1)

    if not args:
        _usage()

    if args[0] == "setup":
        _setup_file_association()
        return

    if len(args) < 2:
        _usage()

    cmd, path_arg = args[0], Path(args[1])

    if not path_arg.exists():
        print(f"error: file not found: {path_arg}", file=sys.stderr)
        sys.exit(1)

    if cmd == "convert":
        if path_arg.suffix.lower() != ".pdf":
            print("error: convert expects a .pdf file", file=sys.stderr)
            sys.exit(1)
        print(f"converting {path_arg.name}…", file=sys.stderr)
        md = pdf_to_markdown(path_arg)
        out = create_off(path_arg, md)
        print(f"written: {out}", file=sys.stderr)

    elif cmd == "read":
        md = read_markdown(path_arg)
        sys.stdout.write(md)
        if not md.endswith("\n"):
            sys.stdout.write("\n")

    elif cmd == "open":
        open_pdf(path_arg)

    else:
        print(f"error: unknown command: {cmd!r}", file=sys.stderr)
        _usage()


def _setup_file_association() -> None:
    """Register .off with a handler app on macOS so double-click works."""
    import sys
    import subprocess
    import tempfile
    import os
    from pathlib import Path

    if sys.platform != "darwin":
        print("File association setup is only supported on macOS.", file=sys.stderr)
        return

    # .off files ARE valid PDFs — just register the extension with Preview.
    # Same approach that worked for .pdx.
    app_dir = Path(tempfile.mkdtemp()) / "OffPreview.app"
    contents = app_dir / "Contents"
    macos_dir = contents / "MacOS"
    macos_dir.mkdir(parents=True)

    (contents / "Info.plist").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>io.off.preview</string>
  <key>CFBundleName</key><string>OffPreview</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleExecutable</key><string>open-off</string>
  <key>CFBundleDocumentTypes</key><array><dict>
    <key>CFBundleTypeName</key><string>OFF Document</string>
    <key>CFBundleTypeRole</key><string>Viewer</string>
    <key>CFBundleTypeExtensions</key><array><string>off</string></array>
    <key>LSHandlerRank</key><string>Owner</string>
  </dict></array>
  <key>UTExportedTypeDeclarations</key><array><dict>
    <key>UTTypeIdentifier</key><string>io.off.document</string>
    <key>UTTypeConformsTo</key><array><string>com.adobe.pdf</string></array>
    <key>UTTypeTagSpecification</key><dict>
      <key>public.filename-extension</key><array><string>off</string></array>
    </dict>
  </dict></array>
</dict></plist>""")

    launcher = macos_dir / "open-off"
    # .off IS a PDF — pass it straight to Preview
    launcher.write_text('#!/bin/bash\nexec /usr/bin/open -a Preview "$@"\n')
    launcher.chmod(0o755)

    lsregister = (
        "/System/Library/Frameworks/CoreServices.framework"
        "/Frameworks/LaunchServices.framework/Support/lsregister"
    )
    subprocess.run([lsregister, "-f", str(app_dir)], check=True)
    subprocess.run(["killall", "Finder"], check=False)

    print("✓ .off files are now associated with Preview.")
    print("  Double-click any .off file to open it as a PDF.")
