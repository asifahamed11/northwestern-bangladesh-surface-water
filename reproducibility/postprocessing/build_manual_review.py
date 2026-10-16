"""Build a standalone, blinded human-review UI from existing genuine artifacts.

No analysis is rerun, reference labels inferred, or scientific files overwritten.
"""
from pathlib import Path
import argparse
import base64
import csv
import hashlib
import json
import re
import struct
from datetime import datetime, timezone

import rasterio

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / 'research_outputs/analysis_20261013_completed_data'


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def build(run=DEFAULT_RUN, output=ROOT / 'Water_Review.html'):
    run, output = Path(run).resolve(), Path(output).resolve()
    evidence = run / 'independent_sensor_evidence'
    old = evidence / 'review.html'
    labels = run / 'reference_labels_to_complete.csv'
    with labels.open(encoding='utf-8-sig', newline='') as f:
        template = list(csv.DictReader(f))
    old_rows = json.loads(re.search(r'const rows=(\[.*?\]);', old.read_text(encoding='utf-8'), re.S)[1])
    ids = [r['sample_id'] for r in template]
    order = [r['id'] for r in old_rows]
    if len(ids) != len(set(ids)) or len(order) != len(set(order)) or set(ids) != set(order):
        raise ValueError('Review and label-template IDs are not a unique one-to-one match')
    records = {r['sample_id']: r for r in template}
    manifests = [labels, old, evidence / 'reference_scene_inventory.csv', evidence / 'reference_source_hash_manifest.csv']
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in manifests}
    rows = []
    raster = ROOT / 'NW_Bangladesh_2000_2024/jrc_monthly_2000.tif'
    # Header only: exact sampled JRC cells, not inferred buffers around a point.
    with rasterio.open(raster) as grid:
        if grid.crs.to_epsg() != 4326:
            raise ValueError('Expected the verified JRC EPSG:4326 source grid')
        source_grid = {'path':str(raster.relative_to(ROOT)), 'crs':str(grid.crs),
                       'transform':list(grid.transform), 'width':grid.width, 'height':grid.height}
        for item in old_rows:
            r = records[item['id']]
            year, month = int(r['year']), int(r['month'])
            lon, lat = float(r['longitude']), float(r['latitude'])
            period = f'{year}-{month:02}'
            if item['period'] != period or item['region'] != r['region']:
                raise ValueError('ID metadata mismatch')
            if any(r.get(k, '').strip() for k in ['reference_water','reference_quality','reference_date']):
                raise ValueError('Expected the untouched blank template; genuine labels must be imported by user')
            row, col = grid.index(lon, lat)
            if not (0 <= row < grid.height and 0 <= col < grid.width):
                raise ValueError('Sample outside source raster')
            left, top = grid.transform * (col, row)
            right, bottom = grid.transform * (col + 1, row + 1)
            if not (left <= lon <= right and bottom <= lat <= top):
                raise ValueError('Invalid pixel footprint')
            image = evidence / 'chips' / (r['sample_id'] + '.png')
            image_bytes = image.read_bytes()
            if image_bytes[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', image_bytes[16:24]) != (560, 560):
                raise ValueError('Chip dimensions do not match the reviewed crop layout')
            image_sha = hashlib.sha256(image_bytes).hexdigest()
            source_hashes[str(image.relative_to(ROOT))] = image_sha
            rows.append({'id':r['sample_id'], 'region':r['region'], 'year':year, 'month':month,
                         'period':period, 'latitude':lat, 'longitude':lon,
                         'bounds':[left,bottom,right,top], 'image_sha256':image_sha,
                         'image':'data:image/png;base64,' + base64.b64encode(image_bytes).decode('ascii')})
    identity = {'rows':[{k:v for k,v in r.items() if k!='image'} for r in rows],
                'export_order':ids, 'source_grid':source_grid}
    dataset_id = hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    dataset = {'id':dataset_id, 'rows':rows, 'export_order':ids, 'source_grid':source_grid}
    asset_dir = Path(__file__).parent
    assets = [asset_dir / name for name in ['manual_review.html','manual_review_core.js','manual_review_app.js','manual_review_hover.js']]
    page = assets[0].read_text(encoding='utf-8')
    payload = json.dumps(dataset,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    for marker, value in [('__DATASET__',payload),('__CORE__',assets[1].read_text(encoding='utf-8')),('__APP__',assets[2].read_text(encoding='utf-8')),('__HOVER__',assets[3].read_text(encoding='utf-8'))]:
        if page.count(marker)!=1:
            raise ValueError('Template substitution mismatch')
        page=page.replace(marker,value)
    if output.exists():
        raise FileExistsError(f'Existing viewer is preserved; choose a new output path: {output}')
    output.write_text(page,encoding='utf-8')
    # Recheck all source files. Generating UI must not modify study inputs.
    for path, original in source_hashes.items():
        if sha(ROOT / path)!=original:
            raise ValueError('Source changed while building: '+path)
    manifest = {'artifact':'standalone manual review UI; no scientific validation performed',
                'created_utc':datetime.now(timezone.utc).isoformat(), 'dataset_id':dataset_id,
                'sample_count':len(rows), 'unique_ids':len(set(ids)), 'original_order_differs_from_viewer':ids!=order,
                'identity_join':'sample_id', 'export_order':'original blank reference template',
                'embedded_images':len(rows), 'all_source_hashes_rechecked':True,
                'source_sha256':source_hashes, 'source_grid':source_grid,
                'software_sha256':{str(p.relative_to(ROOT)):sha(p) for p in assets+[Path(__file__)]},
                'output':str(output), 'output_sha256':sha(output), 'output_bytes':output.stat().st_size,
                'genuine_reference_labels_created':False, 'scientific_pipeline_rerun':False,
                'scope':'Four selected months; monthly binary JRC sample plan only; not annual classes or recovery'}
    manifest_path=output.with_suffix('.manifest.json')
    if manifest_path.exists():raise FileExistsError(manifest_path)
    manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=DEFAULT_RUN)
    parser.add_argument('--output',type=Path,default=ROOT/'Water_Review.html')
    args=parser.parse_args()
    result=build(args.run,args.output)
    print(json.dumps({k:result[k] for k in ['sample_count','dataset_id','output','output_sha256','output_bytes','all_source_hashes_rechecked']},indent=2))
