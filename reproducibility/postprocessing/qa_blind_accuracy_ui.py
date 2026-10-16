"""Isolated headless UI tests. Test answers never become research references."""
from pathlib import Path
from tempfile import TemporaryDirectory
import csv,hashlib,io,json,sys
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'postprocessing'))
from prepare_blind_accuracy import OUT,now,write_json,digest


def loaded(page):
    page.wait_for_function("window.blindReviewReady && document.querySelector('#image').complete && document.querySelector('#image').naturalWidth===800")


def main():
    target=ROOT/'Water_Independent_Accuracy_Review.html'
    dataset=json.loads((OUT/'public/review_dataset.json').read_text(encoding='utf-8'))
    # Selection uses quality metadata only, never the private prediction.
    def eligible(r):
        from datetime import date
        dates=[date.fromisoformat(s['date']) for s in r['scenes'] if s['clear_fraction']>=.95]
        return len(dates)>=2 and (max(dates)-min(dates)).days>=14
    selected=max((r for r in dataset['rows'] if eligible(r)),key=lambda r:len(r['scenes']))
    qa=OUT/'qa';qa.mkdir(exist_ok=True)
    errors=[];checks={}
    with TemporaryDirectory(prefix='water_ui_TEST_ONLY_') as temporary,sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        context=browser.new_context(viewport={'width':1280,'height':1100},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(target.as_uri());loaded(page)
        assert '0/720' in page.locator('#counts').inner_text()
        assert page.locator('.answer button.selected').count()==0
        assert not page.locator('#attested').is_checked()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(qa/'review_desktop_initial.png'),full_page=True)
        checks['initial_blank_and_desktop_layout']=True
        page.locator('.zone[data-kind=ir]').hover()
        assert 'ছায়া' in page.locator('#tip').inner_text()
        page.locator('#help').click();assert page.locator('#helpDialog').is_visible()
        page.locator('#closeHelp').click()
        checks['panel_help_and_simple_rules']=True
        page.locator('#reviewer').fill('TEST_REVIEWER_SOFTWARE_ONLY')
        page.locator('#toggleList').click();page.locator('#jump').fill(str(selected['number']))
        page.locator('#goJump').click();loaded(page)
        page.locator('[data-label="0"]').click()
        assert 'অসম্পূর্ণ' in page.locator('#state').inner_text()
        assert 'যাচাই করা binary: 0' in page.locator('#counts').inner_text()
        for button in page.locator('#dates button').all():
            button.click();loaded(page)
        assert page.locator('#dates button.seen').count()==len(selected['scenes'])
        page.locator('#attested').check()
        assert 'dated binary reference' in page.locator('#state').inner_text()
        assert 'যাচাই করা binary: 1' in page.locator('#counts').inner_text()
        checks['all_added_dates_required_and_zero_preserved']=True
        page.locator('summary').filter(has_text='নোট').click()
        page.locator('#notes').fill('=TEST_FORMULA_SOFTWARE_ONLY')
        page.locator('#notes').blur()
        with page.expect_download() as d:page.locator('#backup').click()
        backup_path=Path(temporary)/'TEST_ONLY_BACKUP.json';d.value.save_as(backup_path)
        backup=json.loads(backup_path.read_text(encoding='utf-8'))
        assert backup['schema']==dataset['schema'] and backup['dataset_id']==dataset['id']
        assert len(backup['records'])==720
        assert sum(bool(e['label']) for e in backup['records'])==1
        with page.expect_download() as d:page.locator('#csv').click()
        csv_path=Path(temporary)/'TEST_ONLY_LABELS.csv';d.value.save_as(csv_path)
        records=list(csv.DictReader(io.StringIO(csv_path.read_text(encoding='utf-8-sig'))))
        current=next(e for e in records if e['sample_id']==selected['sample_id'])
        assert len(records)==720 and current['reference_water']=='0'
        assert current['reference_quality']=='VERIFIED' and current['notes'].startswith("'=")
        assert sum(e['reference_quality']=='PENDING' for e in records)==719
        checks['backup_csv_full_id_set_and_formula_safety']=True
        page.reload();loaded(page)
        assert page.locator('[data-label="0"]').get_attribute('class')=='selected'
        assert page.locator('#notes').input_value()=='=TEST_FORMULA_SOFTWARE_ONLY'
        assert page.locator('#attested').is_checked()
        checks['browser_save_reload']=True
        clean=browser.new_context(viewport={'width':1280,'height':1100})
        other=clean.new_page();other.on('pageerror',lambda e:errors.append(str(e)))
        other.goto(target.as_uri());loaded(other)
        assert '0/720' in other.locator('#counts').inner_text()
        other.locator('#importFile').set_input_files(str(backup_path))
        other.locator('#importDialog').wait_for(state='visible')
        assert '0/720' in other.locator('#counts').inner_text()
        other.locator('#confirmImport').click();loaded(other)
        assert 'যাচাই করা binary: 1' in other.locator('#counts').inner_text()
        bad={**backup,'schema':'OLD_SCHEMA'}
        bad_path=Path(temporary)/'FOREIGN_TEST_BACKUP.json';bad_path.write_text(json.dumps(bad),encoding='utf-8')
        other.locator('#importFile').set_input_files(str(bad_path))
        other.locator('#error').wait_for(state='visible')
        assert not other.locator('#importDialog').is_visible()
        assert 'যাচাই করা binary: 1' in other.locator('#counts').inner_text()
        checks['new_context_import_confirmation_and_foreign_backup_rejection']=True
        # Isolated tabs only: establish the write-conflict guard.
        tab=context.new_page();tab.goto(target.as_uri());loaded(tab)
        page.locator('#error').wait_for(state='visible')
        assert 'অন্য tab' in page.locator('#error').inner_text()
        checks['cross_tab_write_guard']=True
        mobile=browser.new_context(viewport={'width':390,'height':1040},is_mobile=True,has_touch=True)
        m=mobile.new_page();m.goto(target.as_uri());loaded(m)
        assert '0/720' in m.locator('#counts').inner_text()
        assert m.evaluate('document.documentElement.scrollWidth<=innerWidth')
        m.screenshot(path=str(qa/'review_mobile_initial.png'),full_page=True)
        checks['mobile_layout_and_clean_initial_storage']=True
        assert not errors,errors
        browser.close()
    write_json(OUT/'software_ui_checks.json',{'status':'PASS','checked_at':now(),
        'scope':'Isolated headless software tests with clearly identified TEST_REVIEWER; no real human reference decisions.',
        'checks':checks,'browser':'Installed Chrome, isolated temporary Playwright contexts; user browser profile not accessed',
        'ui_sha256':digest(target),'javascript_page_errors':errors,
        'test_backups_stored_as_scientific_evidence':False,'test_contexts_and_downloads_discarded':True,
        'actual_human_labels_created':0,'independent_scientific_validation':False})
    print(json.dumps({'status':'PASS','checks':len(checks),'actual_human_labels_created':0}))


if __name__=='__main__':main()
