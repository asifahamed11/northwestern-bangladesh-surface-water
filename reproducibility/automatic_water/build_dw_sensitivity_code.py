"""Build a standalone GEE supplement pinned to the audited real scene roster."""
from pathlib import Path
import json, hashlib
from automatic_water.analyze import audit_downloads, canonical_scene_id

ROOT=Path(__file__).resolve().parents[1]

def build():
    import pandas as pd
    folder=ROOT/'NW_Bangladesh_automatic_water_2015_2024'
    _,settings,hashes=audit_downloads(folder)
    scenes=pd.read_csv(folder/'auto_scene_inventory.csv')
    canonical=[canonical_scene_id(r.sensor,r.scene_id)[0] for r in scenes.itertuples()]
    snapshot={'method':'automatic_dw_sensitivity_v1','base_method':'automatic_open_water_v2',
        'source_snapshot_sha256':hashlib.sha256((folder/'auto_scene_inventory.csv').read_bytes()).hexdigest(),
        'sar_track':settings.sar_track.iloc[0],'base_file_hashes':hashes,
        'canonical_scene_ids':sorted(canonical),'thresholds':[.5,.6,.7,.8],
        'threshold_selected':None,'ground_truth_labels_generated':False}
    (ROOT/'automatic_water/DW_SENSITIVITY_SNAPSHOT.json').write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8')
    s1=[a.removeprefix('COPERNICUS/S1_GRD/') for a in canonical if a.startswith('COPERNICUS/S1_GRD/')]
    dw=[a.removeprefix('GOOGLE/DYNAMICWORLD/V1/') for a in canonical if a.startswith('GOOGLE/DYNAMICWORLD/V1/')]
    original=(ROOT/'automatic_water/download_automatic_water.js').read_text(encoding='utf-8')
    prelude=original[original.index("var FOLDER ="):original.index('var AREA_NAMES =')]
    prelude=prelude.replace("'NW_Bangladesh_automatic_water_2015_2024'","'NW_Bangladesh_DW_sensitivity_2015_2024'")
    prelude=prelude.replace("var METHOD = 'automatic_open_water_v2';","var METHOD = 'automatic_dw_sensitivity_v1';")
    # Exactly the previous scene IDs: extra provider scenes cannot change the
    # controlled comparison, and missing retained scenes fail the later audit.
    prelude=prelude.replace(".map(function(i) { return dayProperties(i).set('_track'", 
        ".filter(ee.Filter.inList('system:index', SNAPSHOT_S1)).map(function(i) { return dayProperties(i).set('_track'")
    prelude=prelude.replace(".map(dayProperties);", ".filter(ee.Filter.inList('system:index', SNAPSHOT_DW)).map(dayProperties);")
    begin=prelude.index('// Metadata-only orbit proxy:')
    finish=prelude.index('var selectedSar =',begin)
    prelude=prelude[:begin]+"// Keep the audited v2 track fixed; do not rerank after seeing results.\nvar selectedTrack=ee.String(FROZEN_TRACK);\n"+prelude[finish:]
    # Keep median/fraction helpers exactly as in the original v2 calculation.
    # The actual probability probe found no median-branch rounding issue.
    header='''/* FULL 2015-2024 threshold sensitivity supplement, 2026-10-14.
 * NEW script -> Run -> Tasks -> Run all (12 tasks).
 * Keep the original 14 CSVs. New files go into a separate Drive folder.
 * Four thresholds are compared; none is selected/calibrated as best accuracy.
 * The real audited scene IDs and radar track are pinned for comparison.
 * Missing data stay unobserved. No manual or fabricated labels are used.
 * Heavy computations run only in batch; restricted quota mode can be slow.
 * This does not guarantee recovery identifiability or publication readiness.
 */
'''
    pinned='var FROZEN_TRACK='+json.dumps(snapshot['sar_track'])+';\n'
    pinned+='var SNAPSHOT_SHA='+json.dumps(snapshot['source_snapshot_sha256'])+';\n'
    pinned+='var SNAPSHOT_S1='+json.dumps(s1,separators=(',',':'))+';\n'
    pinned+='var SNAPSHOT_DW='+json.dumps(dw,separators=(',',':'))+';\n'
    template=(ROOT/'automatic_water/dw_sensitivity_template.js').read_text(encoding='utf-8')
    code=header+pinned+prelude+template
    (ROOT/'automatic_water/download_dw_sensitivity_2015_2024.js').write_text(code,encoding='utf-8')
    print(json.dumps({'script':'automatic_water/download_dw_sensitivity_2015_2024.js',
        'scene_ids_pinned':len(canonical),'radar_scenes':len(s1),'dw_scenes':len(dw),
        'base_metadata_audit':'PASS','planned_exports':12,'actual_new_exports_downloaded':False},indent=2))

if __name__=='__main__':build()
