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
    invalid=client.request('DELETE','/api/templates',headers=auth,json={'confirmation':'delete'})
    assert invalid.status_code==422
    assert len(client.get('/api/templates',headers=auth).json())==2
    missing=client.request('DELETE','/api/templates',json={'confirmation':'DELETE ALL TEMPLATES'})
    assert missing.status_code in (401,403)
    confirm=client.request('DELETE','/api/templates',headers=auth,
                           json={'confirmation':'DELETE ALL TEMPLATES'})
    assert confirm.status_code==200,confirm.text
    assert confirm.json()=={'deleted':2,'storage_cleanup_failed':0}
    assert client.get('/api/templates',headers=auth).json()==[]
    assert not keys.intersection(FakeStore.files)


def test_delete_all_refuses_templates_used_by_any_page_including_archived(client):
    auth=login(client)
    first=imported(client,auth,name='Old Linked Template')
    template=approve(client,auth,first)
    draft=page(client,auth,template,name='Archived Draft For Protection')
    assert client.post(f"/api/pages/{draft['id']}/archive",headers=auth).status_code==200
    assert client.get('/api/pages',headers=auth).json()==[]
    deletion=client.request('DELETE','/api/templates',headers=auth,
                            json={'confirmation':'DELETE ALL TEMPLATES'})
    assert deletion.status_code==409
    assert 'archived or published' in deletion.text
    assert len(client.get('/api/templates',headers=auth).json())==1
    assert client.get(f"/api/pages/{draft['id']}",headers=auth).status_code==200


def test_delete_one_template_requires_exact_name_and_preserves_other_templates(client):
    auth=login(client)
    first=imported(client,auth,name='Managed Offices Layout')
    second=imported(client,auth,name='One Person Office Layout')
    all_keys=set(FakeStore.files)
    assert len(all_keys)==2
    url=f"/api/templates/{first['id']}"
    invalid=client.request('DELETE',url,headers=auth,
                           json={'confirmation':'DELETE Managed Offices'})
    assert invalid.status_code==422
    assert len(client.get('/api/templates',headers=auth).json())==2
    missing=client.request('DELETE',url,json={'confirmation':'DELETE Managed Offices Layout'})
    assert missing.status_code in (401,403)
    result=client.request('DELETE',url,headers=auth,
                          json={'confirmation':'DELETE Managed Offices Layout'})
    assert result.status_code==200,result.text
    assert result.json()['deleted']==1
    remaining=client.get('/api/templates',headers=auth).json()
    assert [t['id'] for t in remaining]==[second['id']]
    assert len(FakeStore.files)==1
    assert set(FakeStore.files).issubset(all_keys)
    assert client.request('DELETE',url,headers=auth,
                          json={'confirmation':'DELETE Managed Offices Layout'}).status_code==404


def test_delete_one_refuses_template_with_archived_page(client):
    auth=login(client)
    first=imported(client,auth,name='Protected Office Template')
    approved=approve(client,auth,first)
    linked_page=page(client,auth,approved,name='Office Draft To Keep')
    archive=client.post(f"/api/pages/{linked_page['id']}/archive",headers=auth)
    assert archive.status_code==200,archive.text
    result=client.request('DELETE',f"/api/templates/{first['id']}",headers=auth,
                          json={'confirmation':'DELETE Protected Office Template'})
    assert result.status_code==409
    assert 'page(s)' in result.text
    assert len(client.get('/api/templates',headers=auth).json())==1
    assert client.get(f"/api/pages/{linked_page['id']}",headers=auth).status_code==200
    assert len(FakeStore.files)==1
