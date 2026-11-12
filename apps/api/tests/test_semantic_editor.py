"""Regression for semantic fields, static lead magnets and office layouts."""
from bs4 import BeautifulSoup
from sqlalchemy import select
from app.official_templates import (
    OFFICIAL_PAGES, fetch_official, make_template, refine_existing,
    legacy_official_key, official_key,
)
from app.template_engine import extract, render
from app.models import Page, Template
from app.db import SessionLocal
from app import main
from tests.test_persona_qa import client, login, FakeStore, put_page


def solution():
    item=next(item for item in OFFICIAL_PAGES if item.code=='one-person')
    return item, make_template(item,fetch_official(item))


def test_actual_page_sections_and_precise_field_semantics():
    _item,(src,sections,fields)=solution()
    soup=BeautifulSoup(src,'html.parser')
    style=soup.find('style',attrs={'data-we-approved-design':'v2'})
    assert style and '.sol-grid' in style.text and len(style.text)>100000
    assert not soup.select('link[href*="/assets/css/one-person."]')
    assert soup.select_one('#consultation .lm-ticket')
    assert soup.select_one('#why-us #enquiry')
    names={s['id']:s['name'] for s in sections}
    locked={s['id'] for s in sections if s['name'] in ('Office Consultation','Why Us')}
    assert len(locked)==2
    assert all(f['mode']=='static' for f in fields if f['section_id'] in locked)
    for field in fields:
        if field['kind']=='link':
            assert field['default'], 'empty CTA destinations must never be created'
    customise=next(s for s in sections if 'Customisation' in s['name'])
    interactive=soup.select('#customise button[data-size],#customise button[data-pref]')
    assert len(interactive)>=8
    for button in interactive:
        assert button.get('data-we-link-field') is None
        key=button.get('data-we-field')
        assert key
        assert next(f for f in fields if f['key']==key)['mode']=='static'
    faqs=next(s for s in sections if 'FAQs' in s['name'])
    faq_group=next(g for g in faqs['repeaters'] if g['kind']=='faqs')
    assert len(faq_group['items'])==5
    faq_keys={key for item in faq_group['items'] for key in item['field_keys']}
    faq_fields=[f for f in fields if f['key'] in faq_keys and f['mode']=='page']
    assert sum(f['tag']=='button' for f in faq_fields)==5
    assert all(f['kind']!='link' for f in faq_fields)
    assert len([f for f in faq_fields if f['tag']=='div'])>=5


def test_office_options_have_original_regular_generic_and_highlight_variants():
    _item,(src,sections,fields)=solution()
    sec=next(s for s in sections if 'Options' in s['name'])
    groups=[g for g in sec['repeaters'] if g['kind']=='options']
    assert len(groups)==1,groups
    group=groups[0]
    assert len(group['items'])==4
    assert group['max_additions']==0
    original=render(src,fields,{}, {})
    regular=BeautifulSoup(original,'html.parser')
    assert regular.select_one('.sol-grid > li.sol-item') is not None
    ids=[item['id'] for item in group['items']]
    values={
        '__variant__'+group['id']+'__'+ids[0]:'generic',
        '__variant__'+group['id']+'__'+ids[1]:'highlight',
        '__variant__'+group['id']+'__'+ids[2]:'regular'
    }
    modified=BeautifulSoup(render(src,fields,values,{}),'html.parser')
    generic=modified.find(attrs={'data-we-repeat-item':ids[0]})
    highlighted=modified.find(attrs={'data-we-repeat-item':ids[1]})
    unchanged=modified.find(attrs={'data-we-repeat-item':ids[2]})
    assert 'we-variant-generic' in generic.get('class',[])
    assert 'grid-column:span 2!important' in generic.get('style','')
    assert 'we-variant-highlight' in highlighted.get('class',[])
    assert 'outline:3px solid #ed2024' in highlighted.select_one('.sol-card').get('style','')
    assert 'we-variant-regular' in unchanged.get('class',[])
    assert modified.find('style',attrs={'data-we-variant-css':'true'})


def test_category_office_card_layout_presets_are_consistent():
    html='''<!doctype html><html><head></head><body><main>
    <section id="office-types"><h2>Offices</h2><div class="office-grid">
    <a class="office-tile" href="#enquiry"><h3>One Person</h3><p>Private</p></a>
    <a class="office-tile" href="#enquiry"><h3>Small Team</h3><p>Collaborate</p></a>
    <a class="office-tile" href="#enquiry"><h3>Large Team</h3><p>Grow</p></a>
    </div></section></main></body></html>'''
    source,sections,fields=extract(html)
    group=next(g for sec in sections for g in sec.get('repeaters',[])
               if g['kind']=='solutions')
    i,j=group['items'][:2]
    values={
       '__variant__'+group['id']+'__'+i['id']:'generic',
       '__variant__'+group['id']+'__'+j['id']:'highlight',
    }
    markup=BeautifulSoup(render(source,fields,values,{}),'html.parser')
    generic=markup.find(attrs={'data-we-repeat-item':i['id']})
    highlight=markup.find(attrs={'data-we-repeat-item':j['id']})
    assert 'grid-column:span 2!important' in generic.get('style','')
    assert 'height:365px!important' in generic.get('style','')
    assert 'outline:3px solid #ed2024' in highlight.get('style','')
    assert 'grid-column:span 1!important' in highlight.get('style','')


def test_existing_annotations_and_saved_keys_survive_repair():
    item,(source,sections,fields)=solution()
    old_soup=BeautifulSoup(source,'html.parser')
    old_soup.find('style',attrs={'data-we-approved-design':'v2'}).decompose()
    faq=old_soup.select_one('.faq-item .faq-toggle')
    faq['data-we-link-field']='legacy_FAQ_empty_link'
    old_fields=[dict(f) for f in fields]+[{
        'key':'legacy_FAQ_empty_link','section_id':next(s['id'] for s in sections if 'FAQs' in s['name']),
        'label':'Button link:','kind':'link','attr':'data-we-link','default':'',
        'mode':'page','global_key':None,'tag':'button','marker':'data-we-link-field'
    }]
    revised,new_sections,new_fields=refine_existing(item,str(old_soup),sections,old_fields)
    assert {f['key'] for f in new_fields}=={f['key'] for f in old_fields}
    assert any(f['key']=='legacy_FAQ_empty_link' and f['mode']=='static' for f in new_fields)
    assert BeautifulSoup(revised,'html.parser').find('style',attrs={'data-we-approved-design':'v2'})
    assert any(g['kind']=='options' for s in new_sections for g in s.get('repeaters',[]))


def test_legacy_page_upgrade_preserves_user_edits_and_is_idempotent(client):
    auth=login(client)
    first=client.post('/api/official/bootstrap',headers=auth)
    assert first.status_code==200,first.text
    assert first.json()['templates_created']==3
    with SessionLocal() as db:
        template=db.scalar(select(Template).where(Template.object_key==official_key('one-person')))
        assert template
        key=official_key('one-person')
        old=legacy_official_key('one-person')
        FakeStore.files[old]=FakeStore.files[key]
        demo=Page(template_id=template.id,title='Demo_1',slug='demo-one-person',
                  template_snapshot={**main.template_json(template),'object_key':old},
                  values={},seo={'noindex':True,'nofollow':True},status='draft')
        db.add(demo);db.flush()
        f=next(f for f in template.fields if f['mode']=='page' and f['kind']=='text')
        fixed_section=next(sec for sec in template.sections if sec['name']=='Office Consultation')
        formerly_editable=next(x for x in template.fields if x['section_id']==fixed_section['id'] and x['kind']=='text')
        demo.values={f['key']:'My independently edited heading',
                     formerly_editable['key']:'Legacy consultation draft value'}
        template.object_key=old
        template.version+=1
        db.commit()
        target=demo.id
        before_rev=demo.edit_version
    repaired=client.post('/api/official/bootstrap',headers=auth)
    assert repaired.status_code==200,repaired.text
    assert repaired.json()['repaired']==1
    assert repaired.json()['drafts_repaired']>=1
    saved=client.get(f'/api/pages/{target}',headers=auth)
    assert saved.status_code==200
    page=saved.json()['page']
    assert page['values'][f['key']]=='My independently edited heading'
    assert page['values'][formerly_editable['key']]=='Legacy consultation draft value'
    assert page['edit_version']>before_rev
    allowed=put_page(client,target,auth,{'values':page['values']})
    assert allowed.status_code==200,allowed.text
    hostile=dict(page['values'])
    hostile[formerly_editable['key']]='Unexpected edit to locked consultation'
    rejected=put_page(client,target,auth,{'values':hostile})
    assert rejected.status_code==422
    result=client.post('/api/official/bootstrap',headers=auth)
    assert result.json()['existing']==3 and result.json()['repaired']==0
    assert len(client.get('/api/templates',headers=auth).json())==3
