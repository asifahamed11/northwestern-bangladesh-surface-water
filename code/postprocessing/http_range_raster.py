"""Bounded, validated HTTPS range reader for rasterio's file-object bridge."""
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import io, requests


class HTTPRangeReader(io.RawIOBase):
    BLOCK = 262144

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.name = url.rsplit('/',1)[-1]
        self.pos = 0
        self.cache = OrderedDict()
        head = requests.head(url, timeout=(15,30))
        head.raise_for_status()
        self.size = int(head.headers['Content-Length'])
        self.etag = head.headers.get('ETag')

    def readable(self): return True
    def seekable(self): return True
    def writable(self): return False
    def tell(self): return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        if self.pos<0: raise ValueError('Negative seek')
        return self.pos

    def _fetch(self, block):
        start = block*self.BLOCK
        end = min(start+self.BLOCK,self.size)-1
        last_error = None
        for attempt in range(3):
            try:
                r=requests.get(self.url,headers={'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'},timeout=(15,40))
                r.raise_for_status()
                expected=f'bytes {start}-{end}/{self.size}'
                if r.status_code!=206 or r.headers.get('Content-Range')!=expected or len(r.content)!=end-start+1:
                    raise IOError('Incomplete or incorrect HTTP byte range')
                if self.etag and r.headers.get('ETag')!=self.etag:
                    raise IOError('Remote object changed during retrieval')
                return block,r.content
            except Exception as exc:
                last_error=exc
        raise IOError(f'Range retrieval failed: {self.name} block {block}: {last_error}')

    def read(self,size=-1):
        if size is None or size<0: size=self.size-self.pos
        size=min(size,max(0,self.size-self.pos))
        if size>16*1024*1024: raise IOError('Refuse accidental whole-raster download')
        if not size: return b''
        start=self.pos
        end=start+size
        blocks=list(range(start//self.BLOCK,(end-1)//self.BLOCK+1))
        missing=[b for b in blocks if b not in self.cache]
        if missing:
            with ThreadPoolExecutor(max_workers=4) as pool:
                for block,content in pool.map(self._fetch,missing):
                    self.cache[block]=content
        result=b''.join(self.cache[b] for b in blocks)
        result=result[start-blocks[0]*self.BLOCK:start-blocks[0]*self.BLOCK+size]
        if len(result)!=size: raise IOError('Range assembly length mismatch')
        self.pos=end
        while len(self.cache)>32: self.cache.popitem(last=False)
        return result

    def readinto(self,b):
        data=self.read(len(b)); b[:len(data)]=data; return len(data)
