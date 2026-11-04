"""Static mapping persistence and guarded template-library cleanup."""
from tests.test_persona_qa import client, login, imported, approve, page, put_page, FakeStore


def test_saved_static_mapping_is_not_editable_in_new_page(client):
    auth=login(client)
    template=imported(client,auth)
    fields=[]
    for item in template['fields']:
        # Simulates locking the entire section with the Static toggle,
        # then approving and saving the template mapping.
        fields.append({
            'key':item['key'], 'label':item['label'], 'mode':'static',
            'global_key':None, 'heading_tag':item.get('heading_tag'),
        })
    saved=client.put(
        f"/api/templates/{template['id']}/mapping",
        headers=auth, json={'fields':fields,'sections':template['sections'],'approved':True}
    )
    assert saved.status_code==200,saved.text
    assert all(f['mode']=='static' for f in saved.json()['fields'])
    assert all(f['mode']=='static' for f in client.get('/api/templates',headers=auth).json()[0]['fields'])

    new_page=page(client,auth,saved.json(),name='Locked Office')
    loaded=client.get(f"/api/pages/{new_page['id']}",headers=auth)
    assert loaded.status_code==200
    snapshot=loaded.json()['template']
    assert snapshot['approved'] is True
    assert not [field for field in snapshot['fields'] if field['mode']=='page']
    locked_key=snapshot['fields'][0]['key']
    changed=put_page(client,new_page['id'],auth,{'values':{locked_key:'Cannot edit static text'}})
    assert changed.status_code==422
    assert 'static or shared' in changed.text
    assert 'Cannot edit static text' not in client.get(f"/api/pages/{new_page['id']}/preview",headers=auth).text


def test_delete_all_templates_requires_confirmation_and_admin(client):
    auth=login(client)
    first=imported(client,auth,name='Previous Template A')
    second=imported(client,auth,name='Previous Template B')
    keys=set(FakeStore.files)
    assert len(keys)==2
    invalid=client.request('DELETE','/api/templates',headers=auth,json={'confirm':False})
    assert invalid.status_code==422
    assert len(client.get('/api/templates',headers=auth).json())==2
    missing=client.request('DELETE','/api/templates',json={'confirm':True})
    assert missing.status_code in (401,403)
    confirm=client.request('DELETE','/api/templates',headers=auth,json={'confirm':True})
    assert confirm.status_code==200,confirm.text
    assert confirm.json()=={'removed':2,'retained_for_pages':0,'storage_cleanup_failed':0}
    assert client.get('/api/templates',headers=auth).json()==[]
    assert not keys.intersection(FakeStore.files)


def test_delete_all_hides_linked_templates_and_preserves_archived_pages(client):
    auth=login(client)
    first=imported(client,auth,name='Old Linked Template')
    template=approve(client,auth,first)
    draft=page(client,auth,template,name='Archived Draft For Protection')
    assert client.post(f"/api/pages/{draft['id']}/archive",headers=auth).status_code==200
    keys_before=set(FakeStore.files)
    deleted=client.request('DELETE','/api/templates',headers=auth,json={'confirm':True})
    assert deleted.status_code==200,deleted.text
    assert deleted.json()['retained_for_pages']==1
    assert client.get('/api/templates',headers=auth).json()==[]
    assert client.get(f"/api/pages/{draft['id']}",headers=auth).status_code==200
    assert client.get(f"/api/pages/{draft['id']}/preview",headers=auth).status_code==200
    assert keys_before==set(FakeStore.files)
    blocked=client.post('/api/pages',headers=auth,json={'name':'Forbidden new page','template_id':template['id']})
    assert blocked.status_code==409


def test_delete_one_template_needs_confirm_and_keeps_other_templates(client):
    auth=login(client)
    first=imported(client,auth,name='Managed Offices Layout')
    second=imported(client,auth,name='One Person Office Layout')
    url=f"/api/templates/{first['id']}"
    assert client.request('DELETE',url,headers=auth,json={'confirm':False}).status_code==422
    assert client.request('DELETE',url,json={'confirm':True}).status_code in (401,403)
    result=client.request('DELETE',url,headers=auth,json={'confirm':True})
    assert result.status_code==200,result.text
    assert result.json()['removed']==1
    assert result.json()['retained_for_pages']==0
    remaining=client.get('/api/templates',headers=auth).json()
    assert [t['id'] for t in remaining]==[second['id']]
    assert len(FakeStore.files)==1
    assert client.request('DELETE',url,headers=auth,json={'confirm':True}).status_code==404


def test_delete_one_used_template_keeps_page_edit_and_publication(client):
    auth=login(client)
    first=imported(client,auth,name='Protected Office Template')
    approved=approve(client,auth,first,{'Private workspace':'page'})
    linked_page=page(client,auth,approved,name='Existing Office Draft')
    saved_keys=set(FakeStore.files)
    removal=client.request('DELETE',f"/api/templates/{first['id']}",headers=auth,json={'confirm':True})
    assert removal.status_code==200,removal.text
    assert removal.json()['retained_for_pages']==1
    assert client.get('/api/templates',headers=auth).json()==[]
    assert set(FakeStore.files)==saved_keys
    assert client.get(f"/api/pages/{linked_page['id']}",headers=auth).json()['template']['approved'] is True
    changed=put_page(client,linked_page['id'],auth,{'values':{next(f['key'] for f in approved['fields'] if f['default']=='Private workspace'):'New office headline'}})
    assert changed.status_code==200,changed.text
    preview=client.get(f"/api/pages/{linked_page['id']}/preview",headers=auth)
    assert preview.status_code==200 and 'New office headline' in preview.text
    blocked=client.post('/api/pages',headers=auth,json={'name':'Not allowed now','template_id':first['id']})
    assert blocked.status_code==409
