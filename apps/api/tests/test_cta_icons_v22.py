"""V22: External CTA links, icon choices and old-page permissions in local preview."""
from bs4 import BeautifulSoup
from tests.test_persona_qa import client, login, imported, approve, page, put_page, seo, publish

SOURCE=b"""<!doctype html><html><head></head><body><main>
<section id="hero"><h1>Flexible offices</h1>
<a class="btn" href="#enquiry">Request a callback <svg viewBox="0 0 20 20"
 width="20" height="20"><path d="M1 1 L9 9"/></svg></a>
<button onclick="window.location.href='#enquiry'">Contact team</button>
</section><section id="enquiry"><h2>Enquire</h2></section>
</main></body></html>"""
RECORDING='https://kommodo.ai/i/sCYKuA1fO4ob1o92TkHk'


def test_enable_link_icon_editing_and_preview_real_external_url(client):
    auth=login(client)
    t=imported(client,auth,SOURCE,name="Office links and icons")
    t=approve(client,auth,t,{'Flexible offices':'page'})
    p=page(client,auth,t)
    before=client.get(f"/api/pages/{p['id']}",headers=auth).json()
    assert any(f['kind']=='icon' and f['mode']=='static' for f in before['template']['fields'])
    assert any(f['kind']=='link' and f['mode']=='static' for f in before['template']['fields'])
    blocked=put_page(client,p['id'],auth,{'values':{
        next(f['key'] for f in t['fields'] if f['kind']=='link'):RECORDING
    }})
    assert blocked.status_code==422
    stale=client.post(f"/api/pages/{p['id']}/enable-link-icon-editing",headers=auth,
        json={'edit_version':before['page']['edit_version']+1})
    assert stale.status_code==409
    enabled=client.post(f"/api/pages/{p['id']}/enable-link-icon-editing",headers=auth,
        json={'edit_version':before['page']['edit_version']})
    assert enabled.status_code==200,enabled.text
    upgraded=enabled.json()
    assert upgraded['enabled_count']>=3
    link=next(f for f in upgraded['template']['fields']
              if f['kind']=='link' and f['default']=='#enquiry' and f['tag']=='a')
    icon=next(f for f in upgraded['template']['fields'] if f['kind']=='icon')
    assert link['mode']==icon['mode']=='page'
    edits={link['key']:RECORDING,icon['key']:'icon:arrow-up-right'}
    rev=upgraded['page']['edit_version']
    unsaved=client.post(f"/api/pages/{p['id']}/preview",headers=auth,
        json={'edit_version':rev,'values':edits})
    assert unsaved.status_code==200,unsaved.text
    html=BeautifulSoup(unsaved.text,'html.parser')
    a=html.select_one('a.btn')
    assert a['href']==RECORDING
    assert a['rel']==['noopener','noreferrer'] or 'noopener' in a['rel']
    svg=a.find('svg')
    assert svg and svg['viewBox']=='0 0 24 24'
    assert len(svg.select('path'))==2
    assert svg.get('width')=='20' and svg.get('height')=='20'
    assert html.select_one('button') is None
    assert html.find('a',string=lambda s:s and 'Contact team' in s)['href']=='#enquiry'
    assert 'img-src' in unsaved.headers['content-security-policy']
    assert "'self'" in unsaved.headers['content-security-policy']
    updated=put_page(client,p['id'],auth,{'values':edits},revision=rev)
    assert updated.status_code==200,updated.text
    persisted=client.get(f"/api/pages/{p['id']}/preview",headers=auth)
    assert persisted.status_code==200
    assert RECORDING in persisted.text
    assert 'viewBox="0 0 24 24"' in persisted.text
    assert put_page(client,p['id'],auth,{'values':{icon['key']:'icon:script'}}).status_code==422
    assert put_page(client,p['id'],auth,{'values':{link['key']:'javascript:alert(1)'}}).status_code==422
    assert put_page(client,p['id'],auth,{'values':{icon['key']:'https://example.com/icon.png'}}).status_code==200


def test_published_version_unchanged_by_page_only_icon_unlock(client):
    auth=login(client)
    t=approve(client,auth,imported(client,auth,SOURCE,name="Locked published CTA"),
              {'Flexible offices':'page'})
    p=page(client,auth,t)
    seo(client,auth,p)
    result=publish(client,auth,p)
    prior=client.get(result['url']).text
    rev=client.get(f"/api/pages/{p['id']}",headers=auth).json()['page']['edit_version']
    unlock=client.post(f"/api/pages/{p['id']}/enable-link-icon-editing",headers=auth,
                       json={'edit_version':rev})
    assert unlock.status_code==200
    assert client.get(result['url']).text==prior
    # Shared approved template remains locked for new pages.
    current=client.get('/api/templates',headers=auth).json()
    assert any(f['kind']=='icon' and f['mode']=='static' for f in current[0]['fields'])
