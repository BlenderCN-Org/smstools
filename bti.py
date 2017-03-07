import sys, os
from struct import unpack, pack
from texture import *

if len(sys.argv) != 2:
    sys.stderr.write("Usage: %s <bti>\n"%sys.argv[0])
    exit(1)

fin = open(sys.argv[1], 'rb')

format, width, height, wrapS, wrapT, paletteFormat, paletteNumEntries, paletteOffset, minFilter, magFilter, mipmapCount, dataOffset = unpack('>BxHHBBxBHL4xBB2xBx2xL', fin.read(32))

mipmapCount = max(mipmapCount, 1)

print("%dx%d, fmt=%d, mips=%d, pfmt=%d" % (width, height, format, mipmapCount, paletteFormat))

palette = None
if format in (GX_TF_C4, GX_TF_C8, GX_TF_C14X2):
    fin.seek(paletteOffset)
    palette = readPaletteData(fin, paletteFormat, paletteNumEntries)

fin.seek(dataOffset)
data = readTextureData(fin, format, width, height, mipmapCount)
fin.close()

images = decodeTexturePIL(data, format, width, height, paletteFormat, palette, mipmapCount)
im.ages[0][0].save(os.path.splitext(sys.argv[1])[0]+'.png')

fout = open(os.path.splitext(sys.argv[1])[0]+".dds", 'wb')
decodeTextureDDS(fout, data, format, width, height, paletteFormat, palette, mipmapCount)
fout.close()
