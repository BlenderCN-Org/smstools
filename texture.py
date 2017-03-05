GX_TF_I4 = 0x0
GX_TF_I8 = 0x1
GX_TF_IA4 = 0x2
GX_TF_IA8 = 0x3
GX_TF_RGB565 = 0x4
GX_TF_RGB5A3 = 0x5
GX_TF_RGBA8 = 0x6
GX_TF_C4 = 0x8
GX_TF_C8 = 0x9
GX_TF_C14X2 = 0xA
GX_TF_CMPR = 0xE # S3TC/DXT

formatBytesPerPixel = {
GX_TF_I4:   0.5,
GX_TF_I8:     1,
GX_TF_IA4:    1,
GX_TF_IA8:    2,
GX_TF_RGB565: 2,
GX_TF_RGB5A3: 2,
GX_TF_RGBA8:  4,
GX_TF_C4:   0.5,
GX_TF_C8:     1,
GX_TF_C14X2:  2,
GX_TF_CMPR: 0.5
}

formatBlockWidth = {
GX_TF_I4:     8,
GX_TF_I8:     8,
GX_TF_IA4:    8,
GX_TF_IA8:    4,
GX_TF_RGB565: 4,
GX_TF_RGB5A3: 4,
GX_TF_RGBA8:  4,
GX_TF_C4:     8,
GX_TF_C8:     8,
GX_TF_C14X2:  4,
GX_TF_CMPR:   8
}

formatBlockHeight = {
GX_TF_I4:     8,
GX_TF_I8:     4,
GX_TF_IA4:    4,
GX_TF_IA8:    4,
GX_TF_RGB565: 4,
GX_TF_RGB5A3: 4,
GX_TF_RGBA8:  4,
GX_TF_C4:     8,
GX_TF_C8:     4,
GX_TF_C14X2:  4,
GX_TF_CMPR:   8
}

def decodeBlock(format, data, dataidx, im, xoff, yoff):
    if format == GX_TF_I4:
        for y in range(yoff, yoff+8):
            for x in range(xoff, xoff+8, 2):
                if dataidx >= len(data): break
                c = data[dataidx]
                dataidx += 1
                if x < im.width and y < im.height:
                    t = c&0xF0
                    im.putpixel((x, y), t | (t >> 4))
                    t = c&0x0F
                    im.putpixel((x+1, y), (t << 4) | t)
    
    elif format == GX_TF_I8:
        for y in range(yoff, yoff+4):
            for x in range(xoff, xoff+8):
                if dataidx >= len(data): break
                c = data[dataidx]
                dataidx += 1
                if x < im.width and y < im.height:
                    im.putpixel((x, y), c)
    
    elif format == GX_TF_IA4:
        for y in range(yoff, yoff+4):
            for x in range(xoff, xoff+8):
                if dataidx >= len(data): break
                c = data[dataidx]
                dataidx += 1
                if x < im.width and y < im.height:
                    t = c&0xF0
                    a = c&0x0F
                    im.putpixel((x, y), (t | (t >> 4),(a << 4) | a))
    
    elif format == GX_TF_IA8:
        for y in range(yoff, yoff+4):
            for x in range(xoff, xoff+4):
                if dataidx >= len(data): break
                c = data[dataidx]
                dataidx += 1
                if x < im.width and y < im.height:
                    c1, c2 = ord(fin.read(1)), ord(fin.read(1))
                    im.putpixel((x, y), (c1,c2))
    
    elif format == GX_TF_RGB565:
        for y in range(yoff, yoff+4):
            for x in range(xoff, xoff+4):
                rgb, = unpack('>H', fin.read(2))
                if x < im.width and y < im.height:
                    di = 2*(width*(y + dy) + x + dx)
                    r = (rgb & 0xf100) >> 11
                    g = (rgb & 0x7e0) >> 5
                    b = (rgb & 0x1f)
                    im.putpixel((x, y), (r<<3,g<<2,b<<3))
    
    elif format == GX_TF_RGB5A3:
        for y in range(yoff, yoff+4):
            for x in range(xoff, xoff+4):
                c, = unpack('>H', fin.read(2))
                if x < im.width and y < im.height:
                    im.putpixel((x, y), unpackRGB5A3(c))
    elif format == GX_TF_RGBA8:
        for y in range(yoff, yoff+4):
            for x in range(xoff, xoff+4):
                if dataidx >= len(data): break
                c = data[dataidx:dataidx+4]
                dataidx += 4
                if x + dx < mipwidth and y + dy < mipheight:
                    im.putpixel((x+dx, y+dy), c)
    else:
        raise Exception("Unsupported format")
    return dataidx
