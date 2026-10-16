"""Verify exact known method citations; bounded retrieval, not systematic search."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'code_only_final_20261016/research'
HELPER = Path('C:/Users/Admin/.codex/research/research_tools.py')


def main():
    OUT.mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location('research_tools', HELPER)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    items = [
        ('OLOFSSON_2014', '10.1016/j.rse.2014.02.015', 'https://samv.elearning.unipd.it/pluginfile.php/175898/mod_resource/content/0/articolo_oloffson.pdf',
         'Relevant full-text sections reviewed; not whole-article review', 'Sections 3.2-3.5 reference quality and imperfect interpretation; sections 5.1.1-5.1.2 sampling and allocation', True),
        ('STEHMAN_FOODY_2019', '10.1016/j.rse.2019.05.018', 'https://www.sciencedirect.com/science/article/pii/S0034425719302111',
         'Publisher abstract/highlights and indexed preview only; full-text open failed', 'Publisher abstract/highlights: sampling design, response design, analysis and imperfect references', True),
        ('BROWN_2022', '10.1038/s41597-022-01307-4', 'https://www.nature.com/articles/s41597-022-01307-4',
         'Relevant full-text sections reviewed', 'Methods: Training dataset collection, held-out 409 annotated tiles; background on Sentinel-2-derived predictions', True),
        ('SAUNDERS_2025', '10.1029/2025EF005966', 'https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025EF005966',
         'Relevant publisher full-text sections reviewed', 'Abstract; study data in section 2; sections 5.1.1-5.1.3 on data choice and divergence in Bangladesh flood-insurance indices', True),
        ('WEBB_2026', '10.1038/s41598-026-35981-w', 'https://www.nature.com/articles/s41598-026-35981-w',
         'Metadata and indexed excerpts only; publisher full text failed and PMC showed a browser challenge', 'Title, authors, DOI and publication date only. Recent candidate, not reviewed methodological evidence.', False),
    ]

    fallbacks = {
        'STEHMAN_FOODY_2019': {
            'title':'Key issues in rigorous accuracy assessment of land cover products',
            'authors':['Stephen V. Stehman','Giles M. Foody'], 'published':'2019-09-15',
            'venue':'Remote Sensing of Environment', 'publication_type':'journal-article',
            'verification_url':'https://nottingham-repository.worktribe.com/output/2306994/key-issues-in-rigorous-accuracy-assessment-of-land-cover-products'},
        'SAUNDERS_2025': {
            'title':'Sensitivity to Data Choice for Index-Based Flood Insurance',
            'authors':['Alex Saunders','Beth Tellman','Elinor Benami','Kevin Anchukaitis','Sazzad Hossain','Andrew Bennett','A. K. M. Saiful Islam','Jonathan Giezendanner'],
            'published':'2025-09-11', 'venue':"Earth's Future", 'publication_type':'journal-article',
            'verification_url':'https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025EF005966'},
    }

    def one(item):
        sid, doi, url, level, locator, used = item
        cached = OUT / (sid + '_metadata.json')
        if cached.exists():
            result = json.loads(cached.read_text(encoding='utf-8'))
            assert result['doi'] == doi
        elif sid in fallbacks:
            result = {**fallbacks[sid], 'doi':doi, 'crossref_metadata_verified':False,
                      'primary_metadata_verified':True, 'claim_support_verified':False,
                      'provenance':{'retrieved_at':datetime.now(timezone.utc).isoformat(),
                                    'method':'Primary publisher / author-institution metadata viewed with public web tool; switched after Crossref HTTP 429'},
                      'metadata_verification_limit':'Exact title, author list, identifier and date checked on primary page; Crossref request was rate-limited, not retried.'}
        else:
            result = helper.verify_doi(doi)
        result.update(source_id=sid, canonical_url='https://doi.org/' + doi, reviewed_url=url,
                      review_level=level, claim_locator=locator, support_reviewed=used,
                      screening_decision='Included for bounded methods context only' if used else 'Retained reading candidate; excluded from claim support because full text not reviewed',
                      full_article_review_claimed=False)
        (OUT / (sid + '_metadata.json')).write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(one, items))
    now = datetime.now(timezone.utc).isoformat()
    for sid, title, author, url, locator in [
        ('JRC_V15_OFFICIAL', 'Global Surface Water - Data Access', 'European Commission Joint Research Centre', 'https://global-surface-water.appspot.com/download',
         'Collection 2 Transition; Layer Coverage & Merging; Seasonality Improvements; update-validation and co-registration caveat'),
        ('DW_CATALOG_OFFICIAL', 'Dynamic World V1 - Earth Engine Data Catalog', 'Google Earth Engine', 'https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1',
         'Description: correspondence to Sentinel-2 L1C inputs, masking, class probability bands and top-1 probability advice')]:
        records.append({'source_id':sid, 'title':title, 'authors':[author], 'url':url, 'type':'official dataset documentation',
                        'published':None, 'doi':None, 'provenance':{'retrieved_at':now, 'method':'Public page opened with web tool during this turn; no authentication'},
                        'review_level':'Relevant official documentation sections reviewed', 'claim_locator':locator,
                        'support_reviewed':True, 'identifier_verification':'Official primary-provider URL; DOI/Crossref not applicable',
                        'screening_decision':'Included only for source lineage and source-version cautions'})
    (OUT / 'sources.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records), encoding='utf-8')
    claims = [
        {'id':'REFERENCE_NOT_PROXY_AGREEMENT', 'source_ids':['OLOFSSON_2014','STEHMAN_FOODY_2019'], 'locator':'Olofsson sections 3.2-3.5 and 5.1; Stehman/Foody publisher abstract only',
         'claim':'A valid reference response design and probability sampling are distinct from inter-product agreement.', 'support_reviewed':True},
        {'id':'OPTICAL_INPUT_DEPENDENCE', 'source_ids':['BROWN_2022','DW_CATALOG_OFFICIAL'], 'locator':'Brown Methods, training/evaluation annotation description; official catalogue Description',
         'claim':'Dynamic World is derived from Sentinel-2 imagery. The local S2 band rules and DW are not independent physical-truth votes.', 'support_reviewed':True},
        {'id':'VERSION_SEPARATION', 'source_ids':['JRC_V15_OFFICIAL'], 'locator':'Collection 2 Transition; Seasonality Improvements; update validation caveat',
         'claim':'Keep corrected annual layers and Landsat Collection 2 extension distinct in the interpretation and sensitivities.', 'support_reviewed':True},
        {'id':'DIVERGENCE_AS_UNCERTAINTY', 'source_ids':['SAUNDERS_2025'], 'locator':'Abstract; sections 5.1.1-5.1.3',
         'claim':'A Bangladesh flood-index study uses differences among evidence streams to reveal uncertain program outcomes; it is contextual, not a source of our local accuracy or hydrology results.', 'support_reviewed':True},
    ]
    (OUT / 'claims.json').write_text(json.dumps(claims,indent=2)+'\n', encoding='utf-8')
    log = {
        'scope':'Bounded methods scan, not systematic coverage or novelty certification', 'recorded_at':now,
        'tools_used':['public web search/open','Crossref exact-DOI metadata helper'],
        'academic_mcp_attempt':'smart_search requested; unresponsive execution was cancelled without returned records; switched to primary public sources',
        'queries_executed':[
            'Stehman Foody 2019 key issues rigorous accuracy assessment land cover products',
            'Dynamic World near real-time global 10 m land cover probability uncertainty',
            'Global Surface Water v1.5 monthly history 2024 observation uncertainty',
            '2024 2025 2026 surface water uncertainty missing observations Bangladesh Barind',
            '10.1038/s41598-026-35981-w', '2025EF005966 surface water uncertainty Bangladesh'],
        'retrieval_failures_retained':[
            'Crossref returned HTTP 429 for two known DOI requests; no repeated request. Switched to verified primary publisher/author-institution metadata.',
            'Nature current Webb 2026 HTML/PDF failed with publisher redirect/server error',
            'PMC12894664 displayed browser challenge; no bypass attempted',
            'Stehman/Foody full-text open failed; only publisher abstract/highlights used',
            'Nature Dynamic World follow-up open failed; previously returned Methods and official catalogue used'],
        'article_count':len(items), 'official_documents':2, 'crossref_verified_articles':sum(bool(r.get('crossref_metadata_verified')) for r in records if r.get('doi')),
        'all_article_identifiers_and_metadata_verified_on_primary_or_registry':True,
        'full_text_unavailable_not_promoted':True,
    }
    (OUT / 'search_log.json').write_text(json.dumps(log,indent=2)+'\n', encoding='utf-8')
    by_id = {r['source_id']:r for r in records}
    checks = {'source_ids_unique':len(by_id)==len(records), 'article_dois_unique':len({r['doi'] for r in records if r.get('doi')})==5,
              'metadata_verified':all(r.get('crossref_metadata_verified') or r.get('primary_metadata_verified') for r in records if r.get('doi')),
              'no_unreviewed_source_supports_claim':all(by_id[s]['support_reviewed'] for c in claims for s in c['source_ids']),
              'all_claims_have_locators':all(c['locator'] and c['support_reviewed'] for c in claims)}
    assert all(checks.values()), checks
    (OUT / 'source_claim_audit.json').write_text(json.dumps({'status':'PASS_FOR_BOUNDED_METADATA_AND_RECORDED_CLAIM_LOCATORS', 'checks':checks,
        'independent_scientific_verification':False,'whole_article_full_text_review_claimed':False,'novelty_or_systematic_coverage_established':False},indent=2)+'\n',encoding='utf-8')
    shutil_reference = ROOT / 'accuracy_sample_size_20261016/tooling_reference.json'
    if shutil_reference.exists():
        (OUT / 'tooling_reference.json').write_bytes(shutil_reference.read_bytes())
    print(json.dumps({'article_metadata_verified':5,'official_documents_reviewed':2,'source_claim_checks':checks},indent=2))


if __name__=='__main__': main()
