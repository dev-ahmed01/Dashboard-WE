"""V21: upgrades existing pages and validates visual card sizing without affecting published HTML."""
import json
from bs4 import BeautifulSoup
from tests.test_persona_qa import client,login,imported,approve,page,put_page,seo,publish,FakeStore
from tests.test_repeaters_v20 import PAGE_HTML
from app.db import SessionLocal
from app.models import Page


def test_existing_page_upgrade_recovers_missing_fields_and_preserves_publication(client):
    auth=login(client)
    t=imported(client,auth,PAGE_HTML.encode(),name='Original office layout')
    mapped=approve(client,auth,t,{'Workspaces for your team':'page'})
    p=page(client,auth,mapped)
    seo(client,auth,p)
    published=publish(client,auth,p)
    original=client.get(published['url']).text
    with SessionLocal() as db:
        saved=db.get(Page,p['id'])
        snapshot=dict(saved.template_snapshot)
        # Simulate an older saved snapshot that did not map FAQ answer fields
        # or store updated repeater metadata.
        snapshot['sections']=[{k:v for k,v in sec.items() if k!='repeaters'} for sec in snapshot['sections']]
        removed=[f for f in snapshot['fields'] if f['tag']=='div' and 'managed office is ready' in f['default'].lower()]
        assert removed
        snapshot['fields']=[f for f in snapshot['fields'] if f not in removed]
        saved.template_snapshot=snapshot
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(saved,'template_snapshot')
        db.commit()
    before=client.get(f"/api/pages/{p['id']}",headers=auth).json()
    assert any(sec.get('repeaters') for sec in before['template']['sections'])
    refresh=client.post(f"/api/pages/{p['id']}/upgrade-repeaters",headers=auth,
        json={'edit_version':before['page']['edit_version']})
    assert refresh.status_code==200,refresh.text
    data=refresh.json()
    assert data['new_fields']>=1
    assert data['repeaters']>=5
    found=next(f for f in data['template']['fields']
               if f['default']=='A managed office is ready to use.')
    assert found['mode']=='page'
    # Previously saved page remains published and the original snapshot is
    # served until the owner explicitly publishes a fresh version.
    assert client.get(published['url']).text==original
    assert client.post(f"/api/pages/{p['id']}/upgrade-repeaters",headers=auth,
                       json={'edit_version':before['page']['edit_version']}).status_code==409
    assert len(FakeStore.files)>=2


def test_visual_columns_spans_font_sizes_and_locks_save_to_draft(client):
    auth=login(client)
    source=imported(client,auth,PAGE_HTML.encode(),name='Flexible layout')
    t=approve(client,auth,source,{'Workspaces for your team':'page',
                                  'Prime locations':'page',
                                  'Flexible pricing':'page'})
    p=page(client,auth,t)
    loaded=client.get(f"/api/pages/{p['id']}",headers=auth).json()
    groups={g['kind']:g for sec in loaded['template']['sections'] for g in sec.get('repeaters',[])
            if g['kind']!='benefit_bullets'}
    highlight=groups['highlights']
    solution=groups['solutions']
    title=next(f for f in t['fields'] if f['default']=='Workspaces for your team')
    design={'groups':{highlight['id']:{'columns':5,'gap':12},solution['id']:{'columns':4}},
            'items':{solution['items'][2]['id']:{'span':2,'height':390,'locked':True}},
            'fields':{title['key']:{'fontPx':46,'locked':True}}}
    result=put_page(client,p['id'],auth,{'values':{'__design__':json.dumps(design)}})
    assert result.status_code==200,result.text
    rendered=client.get(f"/api/pages/{p['id']}/preview",headers=auth)
    assert rendered.status_code==200,rendered.text
    soup=BeautifulSoup(rendered.text,'html.parser')
    css=soup.select_one('#we-editor-safe-layout').get_text()
    assert 'repeat(5,minmax(0,1fr))' in css
    title_html=soup.select_one('h1')
    assert 'font-size:46px!important' in title_html.get('style','')
    third=soup.select('#solutions .office-grid > a')[2]
    assert 'grid-column:span 2!important' in third.get('style','')
    assert 'height:390px!important' in third.get('style','')
    assert put_page(client,p['id'],auth,{'values':{
        '__design__':json.dumps({'groups':{highlight['id']:{'columns':9}}})}}).status_code==422
    assert put_page(client,p['id'],auth,{'values':{
        '__design__':json.dumps({'groups':{'arbitrary-selector':{'columns':3}}})}}).status_code==422
    assert put_page(client,p['id'],auth,{'values':{
        '__design__':json.dumps({'fields':{title['key']:{'fontPx':'999px;position:absolute'}}})}}).status_code==422
