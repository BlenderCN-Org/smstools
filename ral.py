#!/usr/bin/env python

from struct import unpack
import sys

def getString(pos, f):
    t = f.tell()
    f.seek(pos)
    ret = ''

    c = f.read(1)
    while c != '\0':
        ret += c
        c = f.read(1)

    f.seek(t)

    return ret.decode('shift-jis')

if len(sys.argv) != 2:
	sys.stderr.write("Usage: %s scene.ral\n"%sys.argv[0])
	exit(1)

fin = open(sys.argv[1], 'rb')
while True:
    sectionCount, strOffset, sectionOffset = unpack('>III', fin.read(12))
    if sectionCount == 0: break
    sectionSize = sectionCount * 68
    name = getString(strOffset, fin)
    print(u"%s @ 0x%X+0x%X"%(name, sectionOffset, sectionSize))
fin.close()
