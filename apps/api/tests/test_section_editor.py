from tests.test_persona_qa import client, login, imported, approve, page
from app.section_editor import edit_sections

def test_import_delete_preserves_source_and_unique_keys():
    html='<html><head><style>.card{color:red}</style></head><body><main><section data-we-section="s1"><h2 data-we-field="f1">Original</h2></section><section data-we-section="s2"><h2 data-we-field="f2">Second</h2></section></main></body></html>'
    sections=[{'id':'s1','name':'First','order':1},{'id':'s2','name':'Second','order':2}]
    fields=[{'key':'f1','section_id':'s1','mode':'page'},{'key':'f2','section_id':'s2','mode':'static'}]
    result, meta, mapped=edit_sections(html,sections,fields,'import','s1',(html,sections,fields))
    assert len(meta)==3 and meta[-1]['id']!='s1'
    assert len({f['key'] for f in mapped})==3
    assert mapped[-1]['mode']=='page'
    assert 'data-we-imported-section' in result
    result, meta, mapped=edit_sections(result,meta,mapped,'delete',meta[-1]['id'])
    assert len(meta)==2 and len(mapped)==2
    assert 'data-we-imported-section' not in result
    assert len(sections)==2 and len(fields)==2

def test_delete_section_does_not_change_existing_page_snapshot(client):
    auth=login(client)
    original=approve(client,auth,imported(client,auth))
    assert len(original['sections'])>=2
    existing=page(client,auth,original,name='Before section change')
    sid=original['sections'][0]['id']
    url=f"/api/templates/{original['id']}/sections"
    payload={'operation':'delete','section_id':sid,'version':original['version']}
    assert client.post(url,json=payload).status_code in (401,403)
    result=client.post(url,headers=auth,json=payload)
    assert result.status_code==200,result.text
    assert sid not in [s['id'] for s in result.json()['sections']]
    old=client.get(f"/api/pages/{existing['id']}",headers=auth).json()['template']
    assert sid in [s['id'] for s in old['sections']]
    assert client.post(url,headers=auth,json=payload).status_code==409

def test_cross_template_import_api(client):
    auth=login(client)
    target=approve(client,auth,imported(client,auth))
    donor=client.post('/api/templates/import?name=Donor&category=Property',headers=auth,
        files={'file':('donor.html',b'<html><body><main><section><h2>Imported benefits</h2><p>Distinct content</p></section></main></body></html>','text/html')}).json()
    donor=approve(client,auth,donor,{'Distinct content':'page'})
    result=client.post(f"/api/templates/{target['id']}/sections",headers=auth,json={
        'operation':'import','source_template_id':donor['id'],'section_id':donor['sections'][0]['id'],'version':target['version']})
    assert result.status_code==200,result.text
    edited=result.json()
    assert len(edited['sections'])==len(target['sections'])+1
    assert len({f['key'] for f in edited['fields']})==len(edited['fields'])
    assert any(f['default']=='Distinct content' and f['mode']=='page' for f in edited['fields'])
    assert 'Distinct content' in client.get(f"/api/templates/{target['id']}/preview",headers=auth).text
    assert client.get('/api/templates',headers=auth).json()[1]['version']==donor['version']
