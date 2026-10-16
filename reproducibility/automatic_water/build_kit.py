"""Package the new supplement explicitly, excluding datasets and developer SDKs."""
from pathlib import Path
import json,zipfile,hashlib,argparse

ROOT=Path(__file__).resolve().parents[1]
names=['requirements.txt','requirements-dev.txt','tests/test_automatic_water.py','tests/test_dw_sensitivity.py']
names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'research_pipeline').glob('*.py')]
names.append('research_pipeline/config.json')
for pattern in ['*.py','*.js','*.md','*.json','*.ps1','*.cmd']:
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'automatic_water').glob(pattern)]
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);arguments=parser.parse_args()
names=sorted(set(names));archive=arguments.output.resolve() if arguments.output else ROOT/'NW_Bangladesh_Automatic_Timeout_Fix_20261013.zip'
hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in names:z.write(ROOT/name,name)
    guide=(ROOT/'automatic_water/START_HERE_BN.md').read_bytes()
    z.writestr('NEW_AUTOMATIC_START_BN.md',guide)
    hashes['NEW_AUTOMATIC_START_BN.md']=hashlib.sha256(guide).hexdigest()
    z.writestr('file_checksums_SHA256.json',json.dumps(hashes,indent=2))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,h in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==h,name
checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.sha256').write_text(checksum+'  '+archive.name+'\n',encoding='ascii')
# Existing download links now also resolve to the corrected payload. The original
# failing release is preserved under code-verification/before_automatic_timeout_fix_20261013.
compatible=ROOT/'NW_Bangladesh_New_Automatic_Code_20261013.zip'
compatible.write_bytes(archive.read_bytes())
compatible.with_suffix('.sha256').write_text(checksum+'  '+compatible.name+'\n',encoding='ascii')
print(json.dumps({'archive':str(archive),'payload_files':len(hashes)+1,'bytes':archive.stat().st_size,'sha256':checksum,'all_payload_hashes_verified':True},indent=2))
