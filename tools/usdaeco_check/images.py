"""Small PNG content reader for usdrecord images; no imaging wheel is required."""
from pathlib import Path
import struct
import zlib
import numpy as np


def pixels(path, *, alpha=False):
    raw=Path(path).read_bytes()
    if raw[:8]!=b'\x89PNG\r\n\x1a\n':
        raise ValueError('Not a PNG image')
    offset=8;compressed=bytearray();header=None
    while offset<len(raw):
        length=struct.unpack('>I',raw[offset:offset+4])[0]
        kind=raw[offset+4:offset+8];data=raw[offset+8:offset+8+length]
        if kind==b'IHDR':header=struct.unpack('>IIBBBBB',data)
        if kind==b'IDAT':compressed.extend(data)
        offset+=length+12
    width,height,depth,colour,compression,filtering,interlace=header
    if depth!=8 or colour not in (2,6) or interlace:
        raise ValueError('Expected non-interlaced 8-bit RGB/RGBA from usdrecord')
    channels=3 if colour==2 else 4;stride=width*channels
    scan=zlib.decompress(compressed);decoded=np.zeros((height,stride),dtype=np.uint8)
    for y in range(height):
        mode=scan[y*(stride+1)];row=np.frombuffer(scan[y*(stride+1)+1:(y+1)*(stride+1)],dtype=np.uint8).copy()
        prior=decoded[y-1] if y else np.zeros(stride,dtype=np.uint8)
        if mode==1:
            for channel in range(channels):row[channel::channels]=np.cumsum(row[channel::channels],dtype=np.uint64)%256
        elif mode==2:row=(row.astype(np.uint16)+prior)%256
        elif mode in (3,4):
            for x in range(stride):
                a=int(row[x-channels]) if x>=channels else 0;b=int(prior[x]);c=int(prior[x-channels]) if x>=channels else 0
                if mode==3:predictor=(a+b)//2
                else:
                    p=a+b-c;pa,pb,pc=abs(p-a),abs(p-b),abs(p-c)
                    predictor=a if pa<=pb and pa<=pc else b if pb<=pc else c
                row[x]=(int(row[x])+predictor)%256
        elif mode!=0:raise ValueError('Unsupported PNG filter')
        decoded[y]=row
    return decoded.reshape(height,width,channels)[:,:,:4 if alpha else 3].astype(float)/255.


def write_png(path, array):
    """Encode 8-bit RGB/RGBA pixels with deterministic PNG chunks."""
    array = np.asarray(array)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ValueError("expected height × width × RGB/RGBA")
    if array.dtype != np.uint8:
        array = np.rint(np.clip(array, 0, 1) * 255).astype(np.uint8)
    height, width, channels = array.shape
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    header = struct.pack(">IIBBBBB", width, height, 8, 2 if channels == 3 else 6, 0, 0, 0)
    rows = b"".join(b"\0" + row.tobytes() for row in array)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(data)


def image_info(path):
    """Validate content/caps and return a hash and dimensions for the manifest."""
    import hashlib
    path = Path(path)
    raw = path.read_bytes()
    if len(raw) > 400000:
        raise ValueError("image exceeds 400000 bytes")
    if path.suffix == ".gif":
        from PIL import Image
        with Image.open(path) as image:
            width, height = image.size
            array = np.asarray(image.convert("RGB"))
    else:
        width, height = struct.unpack(">II", raw[16:24])
        if not (0 < width <= 1600 and 0 < height <= 1600):
            raise ValueError("image exceeds 1600 pixels")
        array = pixels(path)
    if not (0 < width <= 1600 and 0 < height <= 1600):
        raise ValueError("image exceeds 1600 pixels")
    if not np.any(array != array[0, 0]):
        raise ValueError("image has uniform pixels")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "width": width, "height": height, "bytes": len(raw)}
