"""Three native CMS modules and their idempotent official template bootstrap."""
from app import main
from app.official_templates import (
    OFFICIAL_PAGES, make_template, prepare_html, official_key, read_only_section, fetch_official,
)
from tests.test_persona_qa import client, login, FakeStore
from app.db import SessionLocal
from app.models import Template, Page
from sqlalchemy import select

HTML="""<!doctype html><html><head>
<link rel="stylesheet" href="/assets/css/page.css"></head><body>
<main>
<section id="hero"><h1>Workspace for growing companies</h1>
 <p>Private, furnished office</p><img src="/assets/img/office.jpg" alt="Featured office"></section>
<section id="options"><h2>Options</h2><div class="options-grid">
 <article class="option-card"><h3>One person</h3><p>Private office</p><a href="#enquiry">Get quote</a></article>
 <article class="option-card"><h3>Small team</h3><p>Team-ready</p><a href="#enquiry">Get quote</a></article>
 <article class="option-card"><h3>Large team</h3><p>Room to grow</p><a href="#enquiry">Get quote</a></article>
 </div></section>
<section id="reviews"><h2>Testimonials</h2><p>Trusted review text</p></section>
<section id="faq"><h2>FAQs</h2><div class="faq-list">
<details><summary>What is included?</summary><p>Wi-Fi</p></details>
<details><summary>Are rooms available?</summary><p>Yes</p></details>
</div></section>
</main></body></html>"""



def test_all_approved_pages_are_bundled_offline_and_editable():
    """No internet is needed to prepare Category, Solution or Property."""
    expected={
        'managed': ('#benefits', 'Managed Offices'),
        'one-person': ('#how-it-works', 'One Person Office'),
        'property': ('#testimonials', 'Workspace Property'),
    }
    for item in OFFICIAL_PAGES:
        html=fetch_official(item)
        assert len(html)>15000
        assert '<section' in html
        assert 'https://workspacebyemlen.co.uk/assets/css/' in html
        assert 'src="/assets/' not in html and 'href="/assets/' not in html
        source,sections,fields=make_template(item,html)
        assert len(sections)>=6
        assert len(fields)>=15
        assert item.category in ('Solution Category','Solution','Property')
        assert expected[item.code][0][1:] in source
        assert source and all('id' in sec for sec in sections)
        assert any(field['mode']=='page' for field in fields)
        if item.code=='property':
            assert 'Saritha Kumari' in source
            assert 'Saandeep K Das' in source
            assert 'https://workspacebyemlen.co.uk/assets/img/jayanagar-workspace-' in source
            assert 'What workspace options are available?' in source
            assert any(sec['name']=='5 · Solutions' for sec in sections)
        names={sec['name'] for sec in sections}
        if item.code=='one-person':
            assert {'1A · Hero','1B · Values','3 · Options','4 · Customisation',
                    '6 · Benefits','7 · How to Get Started','8 · Locations',
                    '9 · FAQs'}.issubset(names)
        if item.code=='property':
            assert {'1A · Hero','2 · Photos','4 · Amenities','5 · Solutions',
                    '6 · Location & Landmarks','7 · Testimonials','9 · FAQs'}.issubset(names)
        if item.code=='managed':
            assert {'1 · Hero','2 · Office Types','5 · Benefits',
                    '6 · Why Us','7 · FAQs'}.issubset(names)


def test_asset_refs_are_safe_and_absolute():
    source=prepare_html(HTML)
    assert 'https://workspacebyemlen.co.uk/assets/css/page.css' in source
    assert 'https://workspacebyemlen.co.uk/assets/img/office.jpg' in source
    assert 'href="#enquiry"' in source


def test_solution_metadata_has_four_card_limit_and_editable_fields():
    item=next(x for x in OFFICIAL_PAGES if x.code=='one-person')
    _source,sections,fields=make_template(item,prepare_html(HTML))
    assert sections[0]['name']=='1A · Hero'
    opt=next(s for s in sections if 'Options' in s['name'])
    groups=opt['repeaters']
    assert any(group['kind']=='options' and group['max_additions']==1 for group in groups)
    assert any(f['mode']=='page' and f['kind']=='image' for f in fields)
    assert any(f['mode']=='page' and f['kind']=='link' for f in fields)


def test_property_testimonials_cannot_be_edited():
    item=next(x for x in OFFICIAL_PAGES if x.code=='property')
    _source,sections,fields=make_template(item,prepare_html(HTML))
    review=next(s for s in sections if 'Testimonials' in s['name'])
    assert read_only_section(item.category,review['name'])
    assert all(f['mode']=='static' for f in fields if f['section_id']==review['id'])



def test_property_source_hydrates_script_only_sections():
    item=next(x for x in OFFICIAL_PAGES if x.code=='property')
    source=HTML.replace(
        '<section id="options">',
        '<section id="photos"><h2>Photos</h2><div id="weGalGrid"></div></section><section id="options">'
    ).replace(
        '<section id="faq"><h2>FAQs</h2><div class="faq-list">',
        '<section id="faqs"><h2>FAQs</h2><div class="faq-list">'
    )
    source=source.replace(
        '<details><summary>What is included?</summary><p>Wi-Fi</p></details>',
        ''
    ).replace(
        '<details><summary>Are rooms available?</summary><p>Yes</p></details>',
        ''
    )
    html,sections,fields=make_template(item,prepare_html(source))
    assert html.count('class="property-cms-card"')==13
    assert html.count('class="property-cms-panel"')==4
    assert html.count('<figure')>=4
    assert 'What workspace options are available?' in html
    sol=next(s for s in sections if s['name']=='5 · Solutions')
    groups=sol.get('repeaters',[])
    assert {'Private Office','Coworking','Meeting Rooms','Additional'}.issubset(
        {g['name'] for g in groups}
    )
    assert any(f['mode']=='page' for f in fields if f['section_id']==sol['id'])


def test_idempotent_bootstrap_preserves_other_templates(client,monkeypatch):
    auth=login(client)
    monkeypatch.setattr(main,'fetch_official',lambda item:prepare_html(HTML))
    original=client.post('/api/templates/import?name=Existing',headers=auth,
        files={'file':('original.html',HTML.encode(),'text/html')})
    assert original.status_code==201
    first=client.post('/api/official/bootstrap',headers=auth)
    assert first.status_code==200,first.text
    assert first.json()['templates_created']==3
    assert first.json()['pages_created']==3
    assert first.json()['unavailable']==[]
    second=client.post('/api/official/bootstrap',headers=auth)
    assert second.status_code==200
    assert second.json()['existing']==3
    assert second.json()['pages_created']==0
    listed=client.get('/api/templates',headers=auth).json()
    assert len(listed)==4
    assert any(x['name']=='Existing' for x in listed)
    assert {x['category'] for x in listed}=={'Solution Category','Solution','Property'}
    pages=client.get('/api/pages',headers=auth).json()
    assert len(pages)==3 and all(x['status']=='draft' for x in pages)
    assert all(x['seo']['noindex'] and x['seo']['nofollow'] for x in pages)
    assert {x['template_category'] for x in pages}=={'Solution Category','Solution','Property'}
    with SessionLocal() as db:
        t=db.scalar(select(Template).where(Template.object_key==official_key('property')))
        assert t is not None and t.approved
        property_page=db.scalar(select(Page).where(Page.template_id==t.id))
        assert property_page is not None
        fields=t.fields
        review=next(x for x in t.sections if 'Testimonials' in x['name'])
        assert all(x['mode']=='static' for x in fields if x['section_id']==review['id'])
        # A malicious mapping request cannot unlock the approved testimonials.
        payload=[{'key':f['key'],'label':f['label'],'mode':'page'} for f in fields]
        tid=t.id
    response=client.put(f'/api/templates/{tid}/mapping',headers=auth,
        json={'fields':payload,'approved':True})
    assert response.status_code==200,response.text
    mapped=response.json()
    assert all(f['mode']=='static' for f in mapped['fields']
               if f['section_id']==review['id'])
    # A module-scoped "delete all" never deletes the other two modules.
    removed=client.request('DELETE','/api/templates?category=Property',headers=auth,
        json={'confirm':True})
    assert removed.status_code==200
    remaining=client.get('/api/templates',headers=auth).json()
    assert any(t['category']=='Solution' for t in remaining)
    assert any(t['category']=='Solution Category' for t in remaining)
