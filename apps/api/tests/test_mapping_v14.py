"""Regression coverage for full-width seven-section CMS extraction and field mapping."""
from bs4 import BeautifulSoup
from sqlalchemy import select

from tests.test_persona_qa import client, login, imported, approve, FakeStore
from app.db import SessionLocal
from app.models import Template
from app.template_engine import extract, render


SEVEN_HTML = """<!doctype html><html><head><title>Workspace</title></head><body>
<main>
 <header class="hero-section">
  <h1>Flexible <span>Private Offices</span></h1>
  <a class="red-button" href="/contact/">Request a callback</a>
  <button onclick="window.location.href='/call/'"><svg width="18" height="18" viewBox="0 0 20 20"><path d="M2 2 L8 8"/></svg><span>Call now</span></button>
  <i class="fa fa-arrow-right"></i>
 </header>
 <section id="offices"><h2>Office Types</h2><p>One-person offices available</p></section>
 <section id="features"><h3>Benefits</h3><p>Choose what works</p></section>
 <section id="journey"><h4>Simple setup</h4><p>Three steps to move in</p></section>
 <section id="locations"><h5>Our Locations</h5><p>Find a location near you</p></section>
 <section id="reviews"><h6>Trusted Teams</h6><p>Business owners recommend us</p></section>
 <div id="faq"><h2>Frequently Asked Questions</h2><p>We are here to help you.</p></div>
</main></body></html>"""


def test_seven_sections_and_all_field_types():
    source, sections, fields = extract(SEVEN_HTML)
    assert len(sections) == 7, [s['name'] for s in sections]
    assert [s['order'] for s in sections] == list(range(1, 8))
    assert len({f['key'] for f in fields}) == len(fields)
    for heading in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        assert any(f['tag'] == heading and f['heading_tag'] == heading for f in fields)
    assert any(f['kind'] == 'link' and f['attr'] == 'href' and f['default'] == '/contact/' for f in fields)
    assert any(f['kind'] == 'link' and f['attr'] == 'data-we-link' and f['default'] == '/call/' for f in fields)
    assert any(f['kind'] == 'icon' and f['attr'] == 'icon_src' for f in fields)
    assert any(f['kind'] == 'icon' and f['attr'] == 'class' for f in fields)
    assert 'onclick=' not in source

    annotated = BeautifulSoup(source, 'html.parser')
    # Mimic a V12 HTML file which annotated six sections but missed the seventh.
    last = annotated.find(id='faq')
    assert last.get('data-we-section') is not None
    del last['data-we-section']
    _, rediscovered, refields = extract(str(annotated))
    assert len(rediscovered) == 7
    assert len({f['key'] for f in refields}) == len(refields)


def test_render_heading_button_links_icons_and_static_safety():
    source, sections, fields = extract(SEVEN_HTML)
    h1 = next(f for f in fields if f['tag'] == 'h1' and f['attr'] == 'text')
    h1['heading_tag'] = 'h3'
    button_url = next(f for f in fields if f['attr'] == 'data-we-link')
    button_url['mode'] = 'page'
    icon = next(f for f in fields if f['attr'] == 'icon_src')
    icon['mode'] = 'page'
    icon_class = next(f for f in fields if f['kind'] == 'icon' and f['attr'] == 'class')
    icon_class['default'] = 'fa fa-check'
    rendered = BeautifulSoup(render(source, fields, {
        button_url['key']: '/book/',
        icon['key']: 'https://example.com/icon.png',
    }, {}), 'html.parser')
    assert rendered.h3 and 'Private Offices' in rendered.h3.get_text(' ', strip=True)
    assert not rendered.h1
    call = rendered.find('a', href='/book/')
    assert call and call['href'] == '/book/'
    assert call.find('img') and call.find('img')['src'] == 'https://example.com/icon.png'
    assert 'fa-check' in rendered.i['class']
    assert 'onclick' not in str(rendered)


def test_redetect_saved_six_to_seven_and_configure_controls(client):
    a = login(client)
    t = imported(client, a, SEVEN_HTML.encode(), name='Seven Section Template')
    assert len(t['sections']) == 7
    old_key = next(f['key'] for f in t['fields'] if f['tag'] == 'h1' and f['attr'] == 'text')
    with SessionLocal() as db:
        record = db.get(Template, t['id'])
        last_id = record.sections[-1]['id']
        record.sections = record.sections[:-1]
        record.fields = [f for f in record.fields if f['section_id'] != last_id]
        db.commit()
    r = client.post(f"/api/templates/{t['id']}/redetect", headers=a)
    assert r.status_code == 200, r.text
    t = r.json()
    assert len(t['sections']) == 7
    assert t['approved'] is False
    assert any(f['key'] == old_key for f in t['fields'])

    configured=[]
    h1 = next(f for f in t['fields'] if f['key'] == old_key)
    button_link = next(f for f in t['fields'] if f['attr'] == 'data-we-link')
    icon = next(f for f in t['fields'] if f['attr'] == 'icon_src')
    for field in t['fields']:
        item={'key':field['key'], 'label':field['label'],
              'mode':'page' if field['key'] in (button_link['key'], icon['key']) else 'static'}
        if field['key'] == h1['key']:
            item['heading_tag'] = 'h2'
        if field['key'] == button_link['key']:
            item['default'] = '/request-a-callback/'
        if field['key'] == icon['key']:
            item['default'] = 'https://example.com/default-icon.png'
        configured.append(item)
    mapped=client.put(f"/api/templates/{t['id']}/mapping",headers=a,
                      json={'fields':configured,'sections':t['sections'],'approved':True})
    assert mapped.status_code == 200, mapped.text

    bad=client.put(f"/api/templates/{t['id']}/mapping",headers=a,
                   json={'fields':[{
                       **item, 'default':'javascript:alert(1)'
                   } if item['key']==button_link['key'] else item for item in configured]})
    assert bad.status_code == 422

    page=client.post('/api/pages', headers=a, json={'name':'Seven section office','template_id':t['id']})
    assert page.status_code == 201, page.text
    pid=page.json()['id']
    current=client.get(f'/api/pages/{pid}',headers=a).json()['page']
    values={button_link['key']:'https://workspacebyemlen.co.in/enquire/',
            icon['key']:'https://example.com/changed.png'}
    saved=client.put(f'/api/pages/{pid}',headers=a,
                     json={'edit_version':current['edit_version'],'values':values})
    assert saved.status_code == 200,saved.text
    preview=client.get(f'/api/pages/{pid}/preview',headers=a)
    assert preview.status_code==200
    assert 'https://workspacebyemlen.co.in/enquire/' in preview.text
    assert 'https://example.com/changed.png' in preview.text
    assert any('Private Offices' in tag.get_text(' ', strip=True) for tag in BeautifulSoup(preview.text,'html.parser').find_all('h2'))

    current=client.get(f'/api/pages/{pid}',headers=a).json()['page']
    bad_url=client.put(f'/api/pages/{pid}',headers=a,
        json={'edit_version':current['edit_version'],'values':{button_link['key']:'javascript:alert(1)'}})
    assert bad_url.status_code==422
    bad_icon=client.put(f'/api/pages/{pid}',headers=a,
        json={'edit_version':current['edit_version'],'values':{icon['key']:'javascript:alert(1)'}})
    assert bad_icon.status_code==422


def test_export_with_hero_before_main_is_seven_sections():
    source = """<!doctype html><html><body>
      <header class="hero"><h1>Premium Flexible Private Offices</h1><p>Teams thrive here with a private office.</p></header>
      <main>
       <section id="office-types"><h2>Office Types</h2><p>Choose your office</p></section>
       <section id="features"><h2>Benefits</h2><p>More services</p></section>
       <section id="journey"><h2>Steps</h2><p>How it works</p></section>
       <section id="locations"><h2>Locations</h2><p>Local options</p></section>
       <section id="reviews"><h2>Reviews</h2><p>Trusted teams</p></section>
       <section id="faq"><h2>FAQs</h2><p>Questions and answers</p></section>
      </main></body></html>"""
    _,sections,fields=extract(source)
    assert len(sections)==7,[s['name'] for s in sections]
    assert sections[0]['name']=='Hero'
    assert any(f['tag']=='h1' and f['section_id']==sections[0]['id'] for f in fields)


def test_new_hero_does_not_steal_legacy_section_ids():
    old=''.join(
        f'<section data-we-section="section_{i}" id="{name}">'
        f'<h2 data-we-field="section_{i}_field_1">{name} heading</h2>'
        f'<p>{name} supporting description</p></section>'
        for i,name in enumerate(['offices','features','journey','locations','reviews','faq'],1)
    )
    html=('<!doctype html><html><body>'
          '<header class="hero"><h1>Premium Flexible Private Offices</h1><p>Our private offices are ready for you.</p></header>'
          '<main>'+old+'</main></body></html>')
    _,sections,fields=extract(html)
    assert len(sections)==7
    assert sections[0]['name']=='Hero'
    assert sections[0]['id'] not in {'section_1','section_2','section_3','section_4','section_5','section_6'}
    assert [s['id'] for s in sections[1:]] == [f'section_{i}' for i in range(1,7)]
    assert all(any(f['key']==f'section_{i}_field_1' and f['section_id']==f'section_{i}' for f in fields) for i in range(1,7))
