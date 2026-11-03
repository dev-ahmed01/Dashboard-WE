"""End-to-end permission, publication and SEO regression tests with fake object storage."""
import os
import tempfile
from pathlib import Path
os.environ['DATABASE_URL'] = 'sqlite:///'+str(Path(tempfile.gettempdir())/'emlen_test_v10.sqlite')
os.environ['JWT_SECRET'] = 'test_only_long_random_jwt_secret_for_v10_tests'
os.environ['ADMIN_EMAIL'] = 'owner@example.test'
os.environ['ADMIN_PASSWORD'] = 'local_test_only_password_12345'
os.environ['APP_ENVIRONMENT']='development'

from fastapi.testclient import TestClient
from app.db import Base, engine
from app import main


class FakeStore:
    files={}
    def __init__(self):pass
    def ensure_bucket(self):pass
    def put(self,key,data,content_type):self.files[key]=data
    def get(self,key):return self.files[key]


def test_template_mapping_page_edit_and_published_snapshot(monkeypatch):
    monkeypatch.setattr(main,'ObjectStore',FakeStore)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    html=b'''<!doctype html><html><head><title>Original</title><style>.hero{color:red}</style></head><body><main><section id="hero"><h1>Fixed office headline</h1><p>Changing subcopy</p></section><section id="benefits"><h2>Benefits</h2><p>Shared footer benefit</p></section></main></body></html>'''
    with TestClient(main.app) as client:
        login=client.post('/api/auth/login',json={'email':'owner@example.test','password':'local_test_only_password_12345'})
        assert login.status_code==200,login.text
        H={'Authorization':'Bearer '+login.json()['access_token']}
        upload=client.post('/api/templates/import?name=Approved&category=Solution%20Category',headers=H,files={'file':('office.html',html,'text/html')})
        assert upload.status_code==201,upload.text
        t=upload.json()
        assert len(t['sections'])==2
        assert all(f['mode']=='static' for f in t['fields'])
        # An unapproved template cannot create pages.
        assert client.post('/api/pages',json={'name':'One Person Office','template_id':t['id']},headers=H).status_code==409
        fields=[]
        for f in t['fields']:
            mode='page' if f['default']=='Changing subcopy' else 'global' if f['default']=='Shared footer benefit' else 'static'
            fields.append({'key':f['key'],'label':f['label'],'mode':mode,'global_key':'company_benefit' if mode=='global' else None})
        mapped=client.put(f"/api/templates/{t['id']}/mapping",json={'fields':fields,'approved':True},headers=H)
        assert mapped.status_code==200,mapped.text
        shared=client.put('/api/shared',json={'items':{'company_benefit':'Same everywhere'}},headers=H)
        assert shared.status_code==200
        made=client.post('/api/pages',json={'name':'One Person Office','template_id':t['id']},headers=H)
        assert made.status_code==201,made.text
        p=made.json()
        locked=next(f for f in t['fields'] if f['default']=='Fixed office headline')
        editable=next(f for f in t['fields'] if f['default']=='Changing subcopy')
        bad=client.put(f"/api/pages/{p['id']}",json={'values':{locked['key']:'HACK'}},headers=H)
        assert bad.status_code==422
        saved=client.put(f"/api/pages/{p['id']}",json={'values':{editable['key']:'Custom office copy'},'seo':{'seo_title':'One Person Office | Emlen','description':'Tailored one-person private offices in Bengaluru.','noindex':False,'nofollow':True}},headers=H)
        assert saved.status_code==200,saved.text
        preview=client.get(f"/api/pages/{p['id']}/preview",headers=H)
        assert 'Custom office copy' in preview.text
        assert 'Same everywhere' in preview.text
        assert 'Fixed office headline' in preview.text
        assert preview.headers['x-robots-tag']=='noindex, nofollow'
        pub=client.post(f"/api/pages/{p['id']}/publish",headers=H)
        assert pub.status_code==200,pub.text
        current=client.get('/site/one-person-office/')
        assert current.status_code==200
        assert 'index,nofollow' in current.text
        assert 'Same everywhere' in current.text
        assert 'BreadcrumbList' in current.text
        assert 'one-person-office/' in client.get('/sitemap.xml').text
        # Later draft changes and global changes do not mutate the published snapshot.
        assert client.put(f"/api/pages/{p['id']}",json={'values':{editable['key']:'Second draft text'}},headers=H).status_code==200
        assert client.put('/api/shared',json={'items':{'company_benefit':'New global copy'}},headers=H).status_code==200
        assert 'Second draft text' not in client.get('/site/one-person-office/').text
        assert 'New global copy' not in client.get('/site/one-person-office/').text
        # The page remains tied to the mapping version at the time of creation.
        fields_locked=[dict(f,mode='static',global_key=None) for f in fields]
        assert client.put(f"/api/templates/{t['id']}/mapping",json={'fields':fields_locked,'approved':True},headers=H).status_code==200
        assert client.put(f"/api/pages/{p['id']}",json={'values':{editable['key']:'Still allowed by snapshot'}},headers=H).status_code==200
        # Unpublished slug is not allowed to serve the old published content.
        assert client.put(f"/api/pages/{p['id']}",json={'slug':'renamed-office'},headers=H).status_code==200
        assert client.get('/site/renamed-office/').status_code==404
        assert client.get('/site/one-person-office/').status_code==200
        assert client.post(f"/api/pages/{p['id']}/publish",headers=H).status_code==200
        redirect=client.get('/site/one-person-office/',follow_redirects=False)
        assert redirect.status_code==301
        assert redirect.headers['location']=='/site/renamed-office/'
        assert client.get('/site/renamed-office/').status_code==200


def test_importer_does_not_execute_scripts():
    from app.template_engine import extract
    src='<html><body><section id="hero" onclick="alert(1)"><h1>Private offices</h1><script>window.evil=1</script><a href="javascript:alert(2)">Enquire now</a></section></body></html>'
    safe,sects,fields=extract(src)
    assert len(sects)==1 and len(fields)>=1
    assert 'window.evil' not in safe and 'onclick=' not in safe and 'javascript:' not in safe


def test_team_account_permissions_and_password_change(monkeypatch):
    monkeypatch.setattr(main,'ObjectStore',FakeStore)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(main.app) as client:
        primary=client.post('/api/auth/login',json={'email':'owner@example.test','password':'local_test_only_password_12345'}).json()['access_token']
        admin_headers={'Authorization':'Bearer '+primary}
        new=client.post('/api/users',json={'email':'writer@example.test','password':'editor_password_very_long','role':'editor'},headers=admin_headers)
        assert new.status_code==201,new.text
        assert len(client.get('/api/users',headers=admin_headers).json())==2
        auth=client.post('/api/auth/login',json={'email':'writer@example.test','password':'editor_password_very_long'})
        assert auth.status_code==200
        editor_headers={'Authorization':'Bearer '+auth.json()['access_token']}
        assert client.get('/api/users',headers=editor_headers).status_code==403
        assert client.post('/api/users',json={'email':'other@example.test','password':'long_enough_password_123','role':'admin'},headers=editor_headers).status_code==403
        wrong=client.post('/api/auth/change-password',json={'old_password':'wrong','new_password':'different_password_123'},headers=editor_headers)
        assert wrong.status_code==403
        good=client.post('/api/auth/change-password',json={'old_password':'editor_password_very_long','new_password':'different_password_123'},headers=editor_headers)
        assert good.status_code==200
        assert client.post('/api/auth/login',json={'email':'writer@example.test','password':'editor_password_very_long'}).status_code==401
        assert client.post('/api/auth/login',json={'email':'writer@example.test','password':'different_password_123'}).status_code==200
