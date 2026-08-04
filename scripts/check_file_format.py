"""Check the actual format of codal Excel files."""
import os

base = "codal_excel_files"
first_dir = sorted(os.listdir(base))[0]
first_file = sorted(os.listdir(os.path.join(base, first_dir)))[0]
fp = os.path.join(base, first_dir, first_file)

# Use ASCII-safe output
print(f"File name (safe): {first_file.encode('ascii', errors='replace').decode()}")
print(f"File size: {os.path.getsize(fp)} bytes")

with open(fp, "rb") as fh:
    header = fh.read(100)

print("Hex (first 40 bytes):")
hex_str = " ".join(f"{b:02x}" for b in header[:40])
print(hex_str)

print("\nPrintable ASCII:")
ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in header[:80])
print(ascii_str)

# Try to detect format
if header[:4] == b"PK\x03\x04":
    print("\nDETECTED: ZIP-based format (XLSX, DOCX, etc.)")
elif header[:4] == b"\xd0\xcf\x11\xe0":
    print("\nDETECTED: OLE2/CFB format (XLS, DOC, etc.)")
elif header[:4] == b"<?xm":
    print("\nDETECTED: XML format")
elif header[:4] == b"<htm" or header[:4] == b"<HTM":
    print("\nDETECTED: HTML format")
elif header[:2] == b"\xff\xfe" or header[:2] == b"\xfe\xff":
    print("\nDETECTED: UTF-16 text format")
elif header[:4] == b"\x00\x00\x00\x00":
    print("\nDETECTED: Binary format (possible TRR/TSETMC format?)")
else:
    # Check if it's a plain text file with Persian content
    try:
        content = header.decode("utf-8-sig")
        print("\nDETECTED: UTF-8 text file")
        print(f"Content preview: {content[:100]}")
    except UnicodeDecodeError:
        try:
            content = header.decode("windows-1256")
            print("\nDETECTED: Windows-1256 (Arabic) text file")
            print(f"Content preview: {content[:100]}")
        except UnicodeDecodeError:
            print("\nDETECTED: Unknown binary format")
