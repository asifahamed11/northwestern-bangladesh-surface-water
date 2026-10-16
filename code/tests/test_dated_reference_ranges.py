"""Transport/calibration safeguards; these are not accuracy tests."""
import io, sys, unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import numpy as np
import rasterio
from rasterio.transform import from_origin
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'postprocessing'))
from http_range_raster import HTTPRangeReader
from render_dated_reference_pilot import read_band


class Response:
    def __init__(self,headers,content=b'',status=206):
        self.headers=headers;self.content=content;self.status_code=status
    def raise_for_status(self):pass


class RangeTests(unittest.TestCase):
    def reader(self,data,broken=False,changed=False):
        def get(url,headers,timeout):
            a,b=map(int,headers['Range'][6:].split('-'))
            payload=data[a:b+1]
            if broken:payload=payload[:-1]
            return Response({'Content-Range':f'bytes {a}-{b}/{len(data)}','ETag':'other' if changed else 'fixed'},payload)
        return patch('http_range_raster.requests.head',return_value=Response({'Content-Length':str(len(data)),'ETag':'fixed'})),patch('http_range_raster.requests.get',side_effect=get)

    def test_cross_block_and_eof_equal_original_bytes(self):
        data=bytes(range(256))*2500
        head,get=self.reader(data)
        with head,get,HTTPRangeReader('https://example.invalid/source.tif') as f:
            f.seek(262130)
            self.assertEqual(f.read(70000),data[262130:332130])
            f.seek(-57,2)
            self.assertEqual(f.read(100),data[-57:])
            self.assertEqual(f.read(4),b'')
            f.seek(19)
            self.assertEqual(f.read(21),data[19:40])

    def test_truncated_ranges_are_rejected(self):
        head,get=self.reader(b'x'*1000,broken=True)
        with head,get,HTTPRangeReader('https://example.invalid/source.tif') as f:
            with self.assertRaises(IOError):f.read(50)

    def test_object_change_is_rejected(self):
        head,get=self.reader(b'x'*1000,changed=True)
        with head,get,HTTPRangeReader('https://example.invalid/source.tif') as f:
            with self.assertRaises(IOError):f.read(50)

    def test_nodata_not_converted_into_negative_reflectance_or_land(self):
        with TemporaryDirectory() as td:
            path=Path(td)/'band.tif'
            a=np.array([[0,1000],[2000,500]],dtype='uint16')
            with rasterio.open(path,'w',driver='GTiff',width=2,height=2,count=1,dtype='uint16',nodata=0,transform=from_origin(0,20,10,10),crs='EPSG:32645') as ds:ds.write(a,1)
            converted,_=read_band(path,{'scale':.0001,'offset':-.1})
            self.assertTrue(np.isnan(converted[0,0]))
            np.testing.assert_allclose(converted[0,1],0,atol=1e-7)
            np.testing.assert_allclose(converted[1,0],.1,atol=1e-7)
            self.assertLess(converted[1,1],0)


if __name__=='__main__':unittest.main()
