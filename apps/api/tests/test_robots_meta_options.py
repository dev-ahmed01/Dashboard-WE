"""Extended robots directives: editable draft, published metadata, and validation."""
from bs4 import BeautifulSoup
import pytest

from app.seo import metadata_html
from test_persona_qa import client, imported, approve, login, page, put_page, publish


def test_robots_meta_generates_all_enabled_directives_and_replaces_old_tag():
    initial = '<html><head><meta name="robots" content="noindex,nofollow"></head><body>Office</body></html>'
    html = metadata_html(
        initial, 'Private offices', 'private-offices',
        {'seo_title':'Private Offices','description':'Modern flexible offices.',
         'noindex':False,'nofollow':True,'noarchive':True,
         'noimageindex':True,'nosnippet':True},
        'https://workspacebyemlen.co.in',
    )
    tags = BeautifulSoup(html,'html.parser').find_all('meta',attrs={'name':'robots'})
    assert len(tags) == 1
    assert tags[0]['content'] == 'index,nofollow,noarchive,noimageindex,nosnippet'


def test_extended_robots_save_preview_publish_and_sitemap(client):
    auth = login(client)
    template = approve(client, auth, imported(client,auth))
    draft = page(client,auth,template)
    settings = {
        'seo_title':'Managed Office | Workspace by Emlen',
        'description':'Flexible private offices in Bengaluru for growing teams.',
        'noindex':False,'nofollow':True,'noarchive':True,
        'noimageindex':True,'nosnippet':True,
    }
    saved = put_page(client,draft['id'],auth,{'seo':settings})
    assert saved.status_code == 200,saved.text
    assert all(saved.json()['seo'][key] == value for key,value in settings.items())
    preview = client.post(f"/api/pages/{draft['id']}/preview",headers=auth,
                          json={"edit_version":saved.json()["edit_version"]})
    assert preview.status_code == 200
    assert 'index,nofollow,noarchive,noimageindex,nosnippet' in preview.text
    assert preview.headers['x-robots-tag']=='noindex, nofollow'
    publish(client,auth,draft)
    public = client.get('/site/bengaluru-office/')
    assert public.status_code == 200
    soup = BeautifulSoup(public.text,'html.parser')
    assert soup.find('meta',attrs={'name':'robots'})['content']=='index,nofollow,noarchive,noimageindex,nosnippet'
    assert '/bengaluru-office/' in client.get('/sitemap.xml').text
    changed = put_page(client,draft['id'],auth,{'seo':{'noindex':True,'nosnippet':False}})
    assert changed.status_code == 200
    assert changed.json()['seo']['noarchive'] is True
    # Changes to draft never mutate already published HTML.
    assert client.get('/site/bengaluru-office/').text == public.text
    publish(client,auth,draft)
    assert '/bengaluru-office/' not in client.get('/sitemap.xml').text


@pytest.mark.parametrize('field',['noindex','nofollow','noarchive','noimageindex','nosnippet'])
def test_robots_directives_reject_non_boolean_values(client,field):
    auth=login(client)
    template=approve(client,auth,imported(client,auth))
    draft=page(client,auth,template)
    response=put_page(client,draft['id'],auth,{'seo':{field:'false'}})
    assert response.status_code==422
