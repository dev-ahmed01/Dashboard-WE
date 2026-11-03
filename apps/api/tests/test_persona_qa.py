"""Role-based admin acceptance tests with isolated temporary DB & fake object storage.

All accounts, objects and pages are synthetic. No external CMS/production site writes.
The regression checks document formerly failing defects, which must now pass.
"""
import os
from pathlib import Path
from tempfile import gettempdir
import pytest

os.environ.setdefault('DATABASE_URL','sqlite:///'+str(Path(gettempdir())/'emlen_test_v10.sqlite'))
os.environ.setdefault('JWT_SECRET','test_only_long_random_jwt_secret_for_v10_tests')
os.environ.setdefault('ADMIN_EMAIL','owner@example.test')
os.environ.setdefault('ADMIN_PASSWORD','local_test_only_password_12345')
os.environ['APP_ENVIRONMENT']='development'

from fastapi.testclient import TestClient
from app.db import Base,engine
from app import main

ASSETS=Path(os.getenv('WE_QA_ASSET_ROOT',str(Path(__file__).resolve().parents[3])))
REAL_TEMPLATES={
 'Managed Offices': ASSETS/'Workspace_by_Emlen_Managed_Offices_Premium_Glass_v26_final(1).html',
 'One Person Office': ASSETS/'Workspace_by_Emlen_One_Person_Office_Premium_V11.html',
}
SIMPLE=b'''<!doctype html><html><head><style>h1{color:#ED2024}</style></head><body><main>
<section id="hero"><h1>Private workspace</h1><p>Custom office summary</p></section>
<section id="benefits"><h2>Fixed benefits title</h2><p>Shared company benefit</p></section>
</main></body></html>'''

class FakeStore:
    files={}
    def ensure_bucket(self): pass
    def put(self,key,data,content_type): self.files[key]=data
    def get(self,key): return self.files[key]
    def delete(self,key): self.files.pop(key,None)

@pytest.fixture
def client(monkeypatch):
    FakeStore.files={}
    monkeypatch.setattr(main,'ObjectStore',FakeStore)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(main.app) as c: yield c

def put_page(c,page_id,auth,body,revision=None):
    if revision is None:
        revision=c.get(f'/api/pages/{page_id}',headers=auth).json()['page']['edit_version']
    return c.put(f'/api/pages/{page_id}',headers=auth,json={**body,'edit_version':revision})

def login(c,email='owner@example.test',password='local_test_only_password_12345'):
    res=c.post('/api/auth/login',json={'email':email,'password':password})
    assert res.status_code==200,res.text
    return {'Authorization':'Bearer '+res.json()['access_token']}

def imported(c,auth,source=SIMPLE,name='Sample'):
    res=c.post(f'/api/templates/import?name={name}',headers=auth,files={'file':('design.html',source,'text/html')})
    assert res.status_code==201,res.text
    return res.json()

def approve(c,auth,t,field_modes=None):
    field_modes=field_modes or {}
    fs=[]
    for f in t['fields']:
        mode=field_modes.get(f['default'],'static')
        fs.append({'key':f['key'],'label':f['label'],'mode':mode,
                   'global_key':'company_benefit' if mode=='global' else None})
    r=c.put(f"/api/templates/{t['id']}/mapping",headers=auth,json={'fields':fs,'approved':True})
    assert r.status_code==200,r.text
    return r.json()

def page(c,auth,t,name='Bengaluru Office'):
    r=c.post('/api/pages',headers=auth,json={'name':name,'template_id':t['id']})
    assert r.status_code==201,r.text
    return r.json()

def seo(c,auth,p,title='Managed Offices | Workspace by Emlen',noindex=False):
    r=put_page(c,p['id'],auth,{'seo':{
        'seo_title':title,'description':'Beautiful offices for business teams in Bengaluru.',
        'noindex':noindex,'nofollow':False}})
    assert r.status_code==200,r.text
    return r.json()

def publish(c,auth,p):
    r=c.post(f"/api/pages/{p['id']}/publish",headers=auth)
    assert r.status_code==200,r.text
    return r.json()


def test_persona_01_first_time_owner_import_and_publish(client):
    a=login(client)
    assert client.get('/api/pages',headers=a).json()==[]
    assert client.get('/api/templates',headers=a).json()==[]
    t=imported(client,a)
    assert len(t['sections'])==2
    assert all(f['mode']=='static' for f in t['fields'])
    assert client.post('/api/pages',headers=a,json={'name':'New page','template_id':t['id']}).status_code==409
    t=approve(client,a,t,{'Custom office summary':'page','Shared company benefit':'global'})
    assert client.put('/api/shared',headers=a,json={'items':{'company_benefit':'Enterprise support'}}).status_code==200
    p=page(client,a,t)
    edit=next(f for f in t['fields'] if f['mode']=='page')
    assert put_page(client,p['id'],a,{'values':{edit['key']:'Flexible workspaces in Bengaluru'}}).status_code==200
    assert client.get(f"/api/pages/{p['id']}/preview",headers=a).status_code==200
    preview=client.get(f"/api/pages/{p['id']}/preview",headers=a).text
    assert 'Flexible workspaces in Bengaluru' in preview and 'Enterprise support' in preview
    seo(client,a,p)
    pub=publish(client,a,p)
    assert client.get(pub['url']).status_code==200
    assert 'bengaluru-office/' in client.get('/sitemap.xml').text
    assert pub['message'].lower().find('live website unchanged')>=0


def test_persona_02_editor_permission_boundary(client):
    a=login(client)
    t=approve(client,a,imported(client,a),{'Custom office summary':'page'})
    created=client.post('/api/users',headers=a,json={'email':'editor@example.test','password':'sample_editor_password_123','role':'editor'})
    assert created.status_code==201
    e=login(client,'editor@example.test','sample_editor_password_123')
    assert client.post('/api/templates/import',headers=e,files={'file':('test.html',SIMPLE,'text/html')}).status_code==403
    assert client.put(f"/api/templates/{t['id']}/mapping",headers=e,json={'fields':[]}).status_code==403
    assert client.get('/api/users',headers=e).status_code==403
    assert client.put('/api/shared',headers=e,json={'items':{'company_benefit':'oops'}}).status_code==403
    assert client.post('/api/redirects',headers=e,json={'from_path':'a','to_path':'b'}).status_code==403
    p=page(client,e,t,'Editor Created Page')
    editable=next(f for f in t['fields'] if f['mode']=='page')
    locked=next(f for f in t['fields'] if f['mode']=='static')
    assert put_page(client,p['id'],e,{'values':{editable['key']:'Editor copy'}}).status_code==200
    assert put_page(client,p['id'],e,{'values':{locked['key']:'Change fixed text'}}).status_code==422
    seo(client,e,p)
    assert client.get(f"/api/pages/{p['id']}/preview",headers=e).status_code==200
    assert client.post(f"/api/pages/{p['id']}/publish",headers=e).status_code==403
    assert client.post(f"/api/pages/{p['id']}/publish",headers=a).status_code==200


def test_persona_03_admin_accounts_and_password_rotation(client):
    a=login(client)
    cr=client.post('/api/users',headers=a,json={'email':'second-admin@example.test','password':'long_secure_admin_password','role':'admin'})
    assert cr.status_code==201
    assert client.post('/api/users',headers=a,json={'email':'second-admin@example.test','password':'long_secure_admin_password','role':'admin'}).status_code==409
    b=login(client,'second-admin@example.test','long_secure_admin_password')
    assert client.get('/api/users',headers=b).status_code==200
    change=client.post('/api/auth/change-password',headers=b,json={'old_password':'long_secure_admin_password','new_password':'rotated_admin_password_secure'})
    assert change.status_code==200
    assert client.post('/api/auth/login',json={'email':'second-admin@example.test','password':'long_secure_admin_password'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'second-admin@example.test','password':'rotated_admin_password_secure'}).status_code==200


def test_persona_04_import_real_designs(client):
    if not all(path.exists() for path in REAL_TEMPLATES.values()):
        pytest.skip('Private reference HTML files are not part of public GitHub repository')
    a=login(client)
    for name,path in REAL_TEMPLATES.items():
        assert path.exists(),str(path)
        t=imported(client,a,path.read_bytes(),name)
        assert len(t['sections'])==8
        assert all(f['mode']=='static' for f in t['fields'])
        approve(client,a,t)
        p=page(client,a,t,name+' Test')
        preview=client.get(f"/api/pages/{p['id']}/preview",headers=a)
        assert preview.status_code==200
        assert preview.headers['x-robots-tag']=='noindex, nofollow'
        assert '<html' in preview.text


def test_persona_05_media_workflow(client):
    a=login(client)
    bad=client.post('/api/media',headers=a,files={'file':('bad.jpg',b'not jpeg','image/jpeg')})
    assert bad.status_code==422
    valid=client.post('/api/media',headers=a,files={'file':('logo.png',b'\x89PNG\r\n\x1a\nsynthetic-data','image/png')},data={'alt_text':'Workspace logo'})
    assert valid.status_code==201
    media=client.get('/api/media',headers=a).json()
    assert len(media)==1 and media[0]['alt_text']=='Workspace logo'
    content=client.get(media[0]['url'])
    assert content.status_code==200 and content.headers['content-type']=='image/png'


def test_persona_06_seo_and_redirect(client):
    a=login(client)
    t=approve(client,a,imported(client,a))
    p=page(client,a,t)
    seo(client,a,p)
    publish(client,a,p)
    change=put_page(client,p['id'],a,{'slug':'new-location'})
    assert change.status_code==200
    assert client.get('/site/bengaluru-office/').status_code==200
    assert client.get('/site/new-location/').status_code==404
    publish(client,a,p)
    r=client.get('/site/bengaluru-office/',follow_redirects=False)
    assert r.status_code==301 and r.headers['location']=='/site/new-location/'


def test_known_defect_draft_noindex_must_not_remove_published_page_from_sitemap(client):
    a=login(client);t=approve(client,a,imported(client,a));p=page(client,a,t)
    seo(client,a,p,noindex=False);publish(client,a,p)
    assert '/bengaluru-office/' in client.get('/sitemap.xml').text
    changed=put_page(client,p['id'],a,{'seo':{'noindex':True}})
    assert changed.status_code==200
    assert '/bengaluru-office/' in client.get('/sitemap.xml').text


def test_known_defect_password_change_should_invalidate_previous_token(client):
    a=login(client)
    changed=client.post('/api/auth/change-password',headers=a,json={'old_password':'local_test_only_password_12345','new_password':'new_password_to_rotate_12345'})
    assert changed.status_code==200
    assert client.get('/api/auth/me',headers=a).status_code==401


def test_known_defect_redirect_should_not_shadow_published_page(client):
    a=login(client);t=approve(client,a,imported(client,a));p=page(client,a,t)
    seo(client,a,p);publish(client,a,p)
    r=client.post('/api/redirects',headers=a,json={'from_path':'bengaluru-office','to_path':'somewhere-else'})
    assert r.status_code in (409,422)


def test_known_defect_concurrent_edit_should_detect_stale_version(client):
    a=login(client);t=approve(client,a,imported(client,a));p=page(client,a,t)
    etag=client.get(f"/api/pages/{p['id']}",headers=a).json()['page']['edit_version']
    first=put_page(client,p['id'],a,{'title':'Writer A'},revision=etag)
    assert first.status_code==200
    stale=put_page(client,p['id'],a,{'title':'Writer B'},revision=etag)
    assert stale.status_code==409
