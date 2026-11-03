"""Role-preserving V11 regression cases. All I/O is local synthetic data."""
from tests.test_persona_qa import client, login, imported, approve, page, seo, publish, put_page
from app import main


def test_seo_from_publication_snapshot_only(client):
    auth=login(client);t=approve(client,auth,imported(client,auth));p=page(client,auth,t)
    seo(client,auth,p,noindex=False);publish(client,auth,p)
    assert '/bengaluru-office/' in client.get('/sitemap.xml').text
    assert client.get('/api/seo/status',headers=auth).json()['indexable']==1
    changed=put_page(client,p['id'],auth,{'seo':{'noindex':True}})
    assert changed.status_code==200
    assert changed.json()['has_unpublished_changes'] is True
    assert '/bengaluru-office/' in client.get('/sitemap.xml').text
    assert client.get('/api/seo/status',headers=auth).json()['indexable']==1
    diff=client.get(f'/api/pages/{p["id"]}/publication-status',headers=auth).json()
    assert diff['draft']['seo']['noindex'] is True
    assert diff['published']['seo']['noindex'] is False
    publish(client,auth,p)
    assert '/bengaluru-office/' not in client.get('/sitemap.xml').text
    assert client.get('/api/seo/status',headers=auth).json()['noindex']==1


def test_unsaved_preview_renders_form_values_without_persisting(client):
    auth=login(client);t=approve(client,auth,imported(client,auth),{'Custom office summary':'page'});p=page(client,auth,t)
    field=next(f for f in t['fields'] if f['mode']=='page')
    proposal={'edit_version':p['edit_version'],'values':{field['key']:'Unsaved changed paragraph'},'seo':{'seo_title':'Temporary title','description':'Local preview only'}}
    render=client.post(f'/api/pages/{p["id"]}/preview',headers=auth,json=proposal)
    assert render.status_code==200,render.text
    assert 'Unsaved changed paragraph' in render.text
    assert '<title>Temporary title</title>' in render.text
    assert render.headers['x-robots-tag']=='noindex, nofollow'
    stored=client.get(f'/api/pages/{p["id"]}',headers=auth).json()['page']
    assert stored['values']=={} and stored['seo']['seo_title']=='' and stored['edit_version']==p['edit_version']
    invalid=client.post(f'/api/pages/{p["id"]}/preview',headers=auth,json={'edit_version':p['edit_version'],'values':{'static_bad':'Oops'}})
    assert invalid.status_code==422


def test_stale_revision_detected_after_saved_changes(client):
    auth=login(client);t=approve(client,auth,imported(client,auth));p=page(client,auth,t)
    a=client.get(f'/api/pages/{p["id"]}',headers=auth).json()['page']
    b=client.get(f'/api/pages/{p["id"]}',headers=auth).json()['page']
    first=put_page(client,p['id'],auth,{'title':'First writer'},a['edit_version'])
    assert first.status_code==200
    second=put_page(client,p['id'],auth,{'title':'Second writer'},b['edit_version'])
    assert second.status_code==409 and 'Reload' in second.text
    assert client.get(f'/api/pages/{p["id"]}',headers=auth).json()['page']['title']=='First writer'


def test_redirect_cannot_take_any_live_or_historical_published_url(client):
    auth=login(client);t=approve(client,auth,imported(client,auth));p=page(client,auth,t)
    seo(client,auth,p);publish(client,auth,p)
    for path in ['bengaluru-office']:
        r=client.post('/api/redirects',headers=auth,json={'from_path':path,'to_path':'somewhere-else'})
        assert r.status_code==409
    # A second page may not re-use a historical published slug after slug change.
    put_page(client,p['id'],auth,{'slug':'renamed-office'});publish(client,auth,p)
    second=page(client,auth,t,'Bengaluru Office')
    assert second['slug']!='bengaluru-office'
    assert client.get('/site/bengaluru-office/',follow_redirects=False).status_code==301


def test_auth_rotation_and_admin_reset_revoke_sessions(client):
    auth=login(client)
    create=client.post('/api/users',headers=auth,json={'email':'second@example.test','role':'editor','password':'editor_long_password_1234'})
    assert create.status_code==201
    second=login(client,'second@example.test','editor_long_password_1234')
    changed=client.post('/api/auth/change-password',headers=second,json={'old_password':'editor_long_password_1234','new_password':'editor_new_password_1234'})
    assert changed.status_code==200
    assert client.get('/api/auth/me',headers=second).status_code==401
    new=login(client,'second@example.test','editor_new_password_1234')
    reset=client.post(f'/api/users/{create.json()["id"]}/reset-password',headers=auth,json={'new_password':'admin_reset_password_12345'})
    assert reset.status_code==200
    assert client.get('/api/auth/me',headers=new).status_code==401
    after=login(client,'second@example.test','admin_reset_password_12345')
    disable=client.patch(f'/api/users/{create.json()["id"]}/status',headers=auth,json={'active':False})
    assert disable.status_code==200
    assert client.get('/api/auth/me',headers=after).status_code==401
    assert client.post('/api/auth/login',json={'email':'second@example.test','password':'admin_reset_password_12345'}).status_code==401
    restore=client.patch(f'/api/users/{create.json()["id"]}/status',headers=auth,json={'active':True})
    assert restore.status_code==200
    assert client.post('/api/auth/login',json={'email':'second@example.test','password':'admin_reset_password_12345'}).status_code==200
    assert client.patch('/api/users/1/status',headers=auth,json={'active':False}).status_code==409


def test_media_alt_upload_and_edit(client):
    auth=login(client)
    upload=client.post('/api/media',headers=auth,files={'file':('office.png',b'\x89PNG\r\n\x1a\nsynthetic-data','image/png')},data={'alt_text':'Office entrance'})
    assert upload.status_code==201,upload.text
    mid=upload.json()['id']
    assert upload.json()['alt_text']=='Office entrance'
    updated=client.patch(f'/api/media/{mid}',headers=auth,json={'alt_text':'Glass partition meeting room'})
    assert updated.status_code==200
    assert client.get('/api/media',headers=auth).json()[0]['alt_text']=='Glass partition meeting room'


def test_archive_and_restore_only_unpublished_drafts(client):
    auth=login(client);t=approve(client,auth,imported(client,auth));p=page(client,auth,t)
    assert client.post(f'/api/pages/{p["id"]}/archive',headers=auth).status_code==200
    assert client.get('/api/pages',headers=auth).json()==[]
    assert client.get('/api/pages?include_archived=true',headers=auth).json()[0]['archived'] is True
    assert put_page(client,p['id'],auth,{'title':'Should not save'}).status_code==409
    assert client.post(f'/api/pages/{p["id"]}/restore',headers=auth).status_code==200
    assert len(client.get('/api/pages',headers=auth).json())==1
    seo(client,auth,p);publish(client,auth,p)
    assert client.post(f'/api/pages/{p["id"]}/archive',headers=auth).status_code==409


def test_template_annotations_and_highlight_preview(client):
    auth=login(client)
    source=b'''<html><head><style>.hero{color:red}</style></head><body><main>
      <section data-we-section="hero" data-we-name="Hero / Arrival"><h1 data-we-field="hero_heading" data-we-label="Main headline">Office spaces</h1><p>Stay flexible</p></section>
      <section data-we-section="faqs"><h2>Frequently asked questions</h2><p>Some answers</p></section>
      </main></body></html>'''
    t=imported(client,auth,source,'Annotation Test')
    assert [x['id'] for x in t['sections']]==['hero','faqs']
    assert t['fields'][0]['key']=='hero_heading' and t['fields'][0]['label']=='Main headline'
    assert t['fields'][1]['label'].startswith('Paragraph:')
    preview=client.get(f'/api/templates/{t["id"]}/preview?focus_field=hero_heading',headers=auth)
    assert preview.status_code==200 and 'data-we-qa-focus' in preview.text
    assert 'Office spaces' in preview.text and 'Frequently asked questions' not in preview.text


def test_media_alt_flows_into_variable_image_preview_and_shared_usage(client):
    auth=login(client)
    img=b'\x89PNG\r\n\x1a\nsynthetic-image'
    media=client.post('/api/media',headers=auth,files={'file':('office.png',img,'image/png')},data={'alt_text':'Shared meeting room'}).json()
    html=b'''<html><head></head><body><main><section id="hero"><h1>Office space</h1><img src="https://example.com/original.png" alt="Old default alt" /></section></main></body></html>'''
    t=imported(client,auth,html,'Office photo')
    t=approve(client,auth,t,{'https://example.com/original.png':'page'})
    p=page(client,auth,t)
    imagefield=next(f for f in t['fields'] if f['kind']=='image')
    update=put_page(client,p['id'],auth,{'values':{imagefield['key']:media['url']}})
    assert update.status_code==200
    preview=client.get(f'/api/pages/{p["id"]}/preview',headers=auth)
    assert preview.status_code==200 and 'alt="Shared meeting room"' in preview.text
    client.patch(f'/api/media/{media["id"]}',headers=auth,json={'alt_text':'Updated team meeting room'})
    assert 'alt="Updated team meeting room"' in client.get(f'/api/pages/{p["id"]}/preview',headers=auth).text
    assert client.get('/api/shared/usage',headers=auth).status_code==200


def test_shared_usage_counts_affected_pages_not_immediate_public_rewrites(client):
    auth=login(client)
    t=approve(client,auth,imported(client,auth),{'Shared company benefit':'global'})
    p=page(client,auth,t)
    usage=client.get('/api/shared/usage',headers=auth).json()
    assert {'key':'company_benefit','pages':1,'published_pages':0} in usage
    seo(client,auth,p);publish(client,auth,p)
    usage=client.get('/api/shared/usage',headers=auth).json()
    assert {'key':'company_benefit','pages':1,'published_pages':1} in usage
    old=client.get('/site/bengaluru-office/').text
    changed=client.put('/api/shared',headers=auth,json={'items':{'company_benefit':'New copy requires republishing'}})
    assert changed.status_code==200
    assert client.get('/site/bengaluru-office/').text==old
