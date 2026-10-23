"""Bounded, read-only TIFF/DNG compression diagnostics for the Smart Preview pilot.

This parser reads only TIFF directory metadata, not compressed image bytes.
Unknown/malformed layouts fail closed; no private paths or image IDs returned.
"""
from __future__ import annotations

import struct
from pathlib import Path

MAX_IFDS = 8
MAX_ENTRIES_PER_IFD = 1024
MAX_SUBIFDS = 4
TAG_COMPRESSION = 259
TAG_SUBIFDS = 330
# SHORT, LONG, IFD (13), LONG8, IFD8 (18). SubIFDs may legally be written as type IFD: tifffile does,
# and without it the JPEG XL image in the SubIFD is never seen and the file is wrongly routed to LibRaw.
TIFF_TYPES = {3: 2, 4: 4, 13: 4, 16: 8, 18: 8}


def inspect_dng_compression(path: Path) -> dict:
    try:
        size = path.stat().st_size
        if size < 8:
            return {"state": "short_tiff", "compression_codes": []}
        with path.open("rb") as stream:
            def read_at(offset: int, length: int) -> bytes:
                if offset < 0 or length < 1 or length > 16384 or offset + length > size:
                    raise ValueError("offset out of bounds")
                stream.seek(offset)
                data = stream.read(length)
                if len(data) != length:
                    raise ValueError("short read")
                return data

            h = read_at(0, 8)
            if h[:2] not in (b"II", b"MM"):
                return {"state": "not_tiff", "compression_codes": []}
            endian = "<" if h[:2] == b"II" else ">"
            magic = struct.unpack(endian + "H", h[2:4])[0]
            if magic == 43:
                # BigTIFF is not typical in Smart Previews. Don't guess.
                return {"state": "bigtiff_not_inspected", "compression_codes": []}
            if magic != 42:
                return {"state": "unsupported_tiff_header", "compression_codes": []}

            def u16(b: bytes) -> int:
                return struct.unpack(endian + "H", b)[0]

            def u32(b: bytes) -> int:
                return struct.unpack(endian + "I", b)[0]

            queue = [u32(h[4:8])]
            seen: set[int] = set()
            compressions: list[int] = []

            def numeric_values(entry: bytes) -> list[int]:
                kind, n = u16(entry[2:4]), u32(entry[4:8])
                width = TIFF_TYPES.get(kind)
                if not width or not 1 <= n <= MAX_SUBIFDS:
                    return []
                bytecount = width * n
                data = (entry[8:12][:bytecount] if bytecount <= 4
                        else read_at(u32(entry[8:12]), bytecount))
                fmt = {3: "H", 4: "I", 13: "I", 16: "Q", 18: "Q"}[kind]
                return list(struct.unpack(endian + fmt * n, data))

            while queue and len(seen) < MAX_IFDS:
                offset = queue.pop(0)
                if offset == 0 or offset in seen:
                    continue
                seen.add(offset)
                count = u16(read_at(offset, 2))
                if count > MAX_ENTRIES_PER_IFD:
                    raise ValueError("unreasonable IFD entry count")
                raw = read_at(offset + 2, count * 12) if count else b""
                for index in range(count):
                    entry = raw[index * 12:(index + 1) * 12]
                    tag = u16(entry[:2])
                    if tag == TAG_COMPRESSION:
                        compressions.extend(numeric_values(entry))
                    elif tag == TAG_SUBIFDS:
                        queue.extend(numeric_values(entry))
                next_ifd = u32(read_at(offset + 2 + count * 12, 4))
                if next_ifd:
                    queue.append(next_ifd)
        return {
            "state": "tiff_ifd_read",
            "compression_codes": sorted(set(compressions)),
        }
    except (OSError, ValueError, struct.error, OverflowError):
        return {"state": "tiff_ifd_unreadable", "compression_codes": []}
