"""Build separate local triage UI; preserves the independent review artifacts."""
import json
from pathlib import Path
from screen_water_colors import ROOT,OUT,digest,write_json,now


def main():
    dataset=json.loads((OUT/'screening_dataset.json').read_text(encoding='utf-8'))
    template=ROOT/'postprocessing/assisted_water_review.html'
    core=ROOT/'postprocessing/assisted_water_core.js';app=ROOT/'postprocessing/assisted_water_app.js'
    page=template.read_text(encoding='utf-8')
    for token,value in [('__DATASET__',json.dumps(dataset,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')),('__CORE__',core.read_text(encoding='utf-8')),('__APP__',app.read_text(encoding='utf-8'))]:
        if page.count(token)!=1:raise ValueError('Page marker mismatch')
        page=page.replace(token,value)
    target=ROOT/'Water_Only_Confused_Review.html';target.write_text(page,encoding='utf-8')
    write_json(OUT/'review_manifest.json',{'created_at':now(),'dataset_id':dataset['id'],'schema':dataset['schema'],
        'ui_sha256':digest(target),'dataset_sha256':digest(OUT/'screening_dataset.json'),
        'source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in (template,core,app,Path(__file__))},
        'independent_reference_eligible':False,'old_or_independent_local_storage_namespace_used':False,
        'actual_human_labels_created':0,'publication_ready':False})
    print('READY: Water_Only_Confused_Review.html; assisted screening only.')


if __name__=='__main__':main()
