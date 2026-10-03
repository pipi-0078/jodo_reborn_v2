"""Check protected geometry and all animation data against approved source GLBs."""
import gzip
import hashlib
import json
import struct
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

class GLB:
    def __init__(self, path):
        b = path.read_bytes()
        if b[:2] == b'\x1f\x8b':
            b = gzip.decompress(b)
        self.sha = hashlib.sha256(b).hexdigest()
        n = struct.unpack_from('<I', b, 12)[0]
        self.doc = json.loads(b[20:20+n])
        self.bin = b[28+n:]

    def accessor(self, index):
        a = self.doc['accessors'][index]
        v = self.doc['bufferViews'][a['bufferView']]
        dtype = {5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']]
        width = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        return np.ndarray((a['count'], width), dtype=dtype, buffer=self.bin,
                          offset=v.get('byteOffset',0)+a.get('byteOffset',0),
                          strides=(v.get('byteStride',np.dtype(dtype).itemsize*width),np.dtype(dtype).itemsize))

    def image(self, index):
        v = self.doc['bufferViews'][self.doc['images'][index]['bufferView']]
        off = v.get('byteOffset',0)
        return self.bin[off:off+v['byteLength']]

reports = []
for source, target in [
    ('karyobinga-design/karyobinga-floating-v11.glb','karyobinga/karyobinga-flute-v11.glb.gz'),
    ('karyobinga-biwa-design/karyobinga-biwa-floating-v2.glb','karyobinga-biwa/karyobinga-biwa-floating-v2.glb.gz'),
]:
    a, b = GLB(ROOT.parent/source), GLB(ROOT/'public/assets'/target)
    assert a.doc['nodes'] == b.doc['nodes'], 'Node transforms or hierarchy changed'
    assert a.doc['materials'] == b.doc['materials'], 'Approved materials changed'
    protected = 0
    for i in range(1,len(a.doc['meshes'])):
        x,y=a.doc['meshes'][i]['primitives'][0],b.doc['meshes'][i]['primitives'][0]
        ix,iy=a.accessor(x['indices']).ravel(),b.accessor(y['indices']).ravel()
        assert len(ix)==len(iy)
        for left,right in [(x['attributes'],y['attributes']),*zip(x.get('targets',[]),y.get('targets',[]))]:
            assert left.keys()==right.keys()
            for key in left:
                assert np.array_equal(a.accessor(left[key])[ix],b.accessor(right[key])[iy]), (i,key)
        protected+=len(ix)//3
    for x,y in zip(a.doc['animations'],b.doc['animations']):
        assert x['channels']==y['channels'] and x['name']==y['name']
        assert len(x['samplers'])==len(y['samplers'])
        for sx,sy in zip(x['samplers'],y['samplers']):
            assert sx.get('interpolation')==sy.get('interpolation')
            for key in ['input','output']:
                assert np.array_equal(a.accessor(sx[key]),b.accessor(sy[key]))
    for x,y in zip(a.doc.get('skins',[]),b.doc.get('skins',[])):
        assert x['joints']==y['joints']
        assert np.array_equal(a.accessor(x['inverseBindMatrices']),b.accessor(y['inverseBindMatrices']))
    assert all(a.image(i)==b.image(i) for i in [3,4])
    reports.append({'file':target,'sha256':b.sha,'protectedTrianglesExact':protected,'animationExact':True,'faceAndFiberTexturesExact':True})
print(json.dumps({'passed':True,'models':reports},indent=2))
