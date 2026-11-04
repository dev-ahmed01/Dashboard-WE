"""V20: true source-structure repeaters and icon-preserving CTA text edits."""
import json
from bs4 import BeautifulSoup
from tests.test_persona_qa import client, login, imported, approve, page, put_page
from app.template_engine import extract, render


PAGE_HTML = """<!doctype html><html><body><main>
<section id="hero"><h1>Workspaces for your team</h1>
 <div class="cards">
  <article class="card"><div class="card-title">Prime locations</div><p>Near your team</p><svg viewBox="0 0 20 20"><path d="M0 0L10 10"/></svg></article>
  <article class="card"><div class="card-title">Flexible pricing</div><p>Choose your plan</p><svg viewBox="0 0 20 20"><path d="M0 0L10 10"/></svg></article>
  <article class="card"><div class="card-title">Fully furnished</div><p>Move in today</p><svg viewBox="0 0 20 20"><path d="M0 0L10 10"/></svg></article>
 </div>
 <a class="btn" href="#enquiry"><span>Request a callback</span><span class="pill-arr" aria-hidden="true">↗</span></a>
 <a class="btn" href="tel:+919814953954">Call now ↗</a>
</section>
<section id="solutions"><h2>Office Solutions</h2><div class="office-grid">
 <a class="office-tile" href="#enquiry"><img src="/a.jpg"/><span><strong>One-Person Office</strong><span aria-hidden="true" class="office-arrow">↗</span></span></a>
 <a class="office-tile office-special" href="#enquiry"><img src="/b.jpg"/><span><strong>Team Office</strong><span aria-hidden="true" class="office-arrow">↗</span></span></a>
 <a class="office-tile" href="#enquiry"><img src="/c.jpg"/><span><strong>Enterprise Office</strong><span aria-hidden="true" class="office-arrow">↗</span></span></a>
 </div></section>
<section id="other"><h2>Other Solutions</h2><div class="other-pill-grid">
 <a class="other-pill" href="#enquiry"><span>Dedicated desk</span><span class="pill-arr" aria-hidden="true">↗</span></a>
 <a class="other-pill" href="#enquiry"><span>Day office</span><span class="pill-arr" aria-hidden="true">↗</span></a>
 <a class="other-pill" href="#enquiry"><span>Meeting rooms</span><span class="pill-arr" aria-hidden="true">↗</span></a>
 </div></section>
<section id="benefits"><h2>Benefits</h2><p>Flexible workspaces</p><div class="benefit-list">
 <article class="benefit-row"><h3>Cost predictable</h3><p>Know your cost</p><ul><li>Included utilities</li><li>Support included</li><li>Fully furnished</li></ul><img src="/benefit1.jpg"/></article>
 <article class="benefit-row"><h3>Flexible terms</h3><p>Scale with ease</p><ul><li>Team grows</li><li>No delays</li><li>Simple setup</li></ul><img src="/benefit2.jpg"/></article>
 <article class="benefit-row"><h3>Client ready</h3><p>Meet with clients</p><ul><li>Meeting rooms</li><li>Reception</li><li>Fast internet</li></ul><img src="/benefit3.jpg"/></article>
 </div></section>
<section id="faq"><h2>Before you decide</h2><div class="faq-list">
 <details class="faq-item"><summary>What is a managed office?<span class="faq-toggle" aria-hidden="true">+</span></summary><div class="faq-answer">A managed office is ready to use.</div></details>
 <details class="faq-item"><summary>What plans can I choose?<span class="faq-toggle" aria-hidden="true">+</span></summary><div class="faq-answer">Choose from flexible options.</div></details>
 <details class="faq-item"><summary>How do I enquire?<span class="faq-toggle" aria-hidden="true">+</span></summary><div class="faq-answer">Contact our team.</div></details>
 </div></section>
</main></body></html>"""


def test_section_repeater_metadata_matches_real_html_structure():
    source, sections, fields = extract(PAGE_HTML)
    counts = {g['kind']:g['count'] for sec in sections for g in sec.get('repeaters', [])
              if g['kind']!='benefit_bullets'}
    assert counts['highlights']==3
    assert counts['solutions']==3
    assert counts['other_solutions']==3
    assert counts['benefits']==3
    assert counts['faqs']==3
    bullet_groups=[g for sec in sections for g in sec.get('repeaters',[])
                   if g['kind']=='benefit_bullets']
    assert len(bullet_groups)==3
    assert all(g['count']==3 and g['parent_item_id'] for g in bullet_groups)
    assert any(f['tag']=='summary' and f['default'].startswith('What is') for f in fields)
    annotated=BeautifulSoup(source,'html.parser')
    assert len(annotated.select('[data-we-repeat-group]'))>=8


def test_clone_highlight_solution_benefit_bullet_and_faq_in_real_dom():
    source, sections, fields = extract(PAGE_HTML)
    for f in fields:
        f['mode']='page'
    groups={g['kind']:g for sec in sections for g in sec.get('repeaters', [])
            if g['kind']!='benefit_bullets'}
    bullets=next(g for sec in sections for g in sec.get('repeaters',[])
                 if g['kind']=='benefit_bullets')
    additions={}
    for kind,title in [
        ('highlights','New highlight title'),
        ('solutions','New managed solution'),
        ('other_solutions','New coworking option'),
        ('benefits','New client benefit'),
        ('faqs','Can I add more FAQs?'),
        ('benefit_bullets','A fourth bullet point')]:
        group=bullets if kind=='benefit_bullets' else groups[kind]
        keys=group['items'][-1]['field_keys']
        text_key=next((k for k in keys if
                       next(f for f in fields if f['key']==k)['attr']=='text'),None)
        assert text_key,kind
        values={text_key:title}
        if kind=='solutions':values['__variant']='highlight'
        additions['__repeat__'+group['id']]=json.dumps([values])
    source_html=render(source,fields,additions,{})
    soup=BeautifulSoup(source_html,'html.parser')
    assert len(soup.select('#hero .cards > article'))==4
    assert len(soup.select('#solutions .office-grid > a'))==4
    assert len(soup.select('#other .other-pill-grid > a'))==4
    assert len(soup.select('#benefits .benefit-list > article'))==4
    assert len(soup.select('#faq .faq-list > details'))==4
    assert len(soup.select('#benefits .benefit-list > article:nth-of-type(1) li'))==4
    assert soup.find(string=lambda x:x and 'New highlight title' in x)
    assert soup.find(string=lambda x:x and 'Can I add more FAQs?' in x)
    assert soup.select('#solutions .office-grid > a')[-1].get('data-we-variant')=='highlight'
    assert 'office-special' in soup.select('#solutions .office-grid > a')[-1].get('class',[])
    assert len([n.get('id') for n in soup.find_all(id=True)])==len(
        {n.get('id') for n in soup.find_all(id=True)})


def test_button_arrow_keeps_its_markup_when_label_is_edited():
    source,sections,fields=extract(PAGE_HTML)
    first=next(f for f in fields if f['kind']=='text' and
               f['tag']=='a' and f['default'].startswith('Request a callback'))
    second=next(f for f in fields if f['kind']=='text' and
                f['tag']=='a' and f['default'].startswith('Call now'))
    first['mode']='page';second['mode']='page'
    output=BeautifulSoup(render(source,fields,{
        first['key']:'Book a call',
        second['key']:'Phone our team',
    },{}),'html.parser')
    a,b=output.select('a.btn')
    assert 'Book a call' in a.get_text(' ',strip=True)
    assert a.select_one('span.pill-arr').get_text(strip=True)=='↗'
    assert 'Phone our team' in b.get_text(' ',strip=True)
    assert b.find('span',class_='we-preserved-cta-icon').get_text(strip=True)=='↗'
    assert b.get_text(' ',strip=True).count('↗')==1


def test_repeater_values_save_preview_and_unsafe_urls_are_rejected(client):
    auth=login(client)
    detected=imported(client,auth,PAGE_HTML.encode(),name='Repeatable Workspace')
    fields=[dict(f,mode='page',global_key=None) for f in detected['fields']]
    saved=client.put(f"/api/templates/{detected['id']}/mapping",headers=auth,
                     json={'fields':[{'key':f['key'],'label':f['label'],'mode':'page'}
                                     for f in fields],
                           'sections':detected['sections'],'approved':True})
    assert saved.status_code==200,saved.text
    created=page(client,auth,saved.json(),name='Editable Repeaters Page')
    loaded=client.get(f"/api/pages/{created['id']}",headers=auth).json()
    groups={g['kind']:g for sec in loaded['template']['sections']
            for g in sec.get('repeaters',[]) if g['kind']!='benefit_bullets'}
    faq=groups['faqs']
    key=next(k for k in faq['items'][-1]['field_keys']
             if next(f for f in fields if f['key']==k)['tag']=='summary')
    entry={'__repeat__'+faq['id']:json.dumps([{key:'Do you offer five plans?'}])}
    update=put_page(client,created['id'],auth,{'values':entry})
    assert update.status_code==200,update.text
    preview=client.get(f"/api/pages/{created['id']}/preview",headers=auth)
    assert preview.status_code==200 and 'Do you offer five plans?' in preview.text
    assert len(BeautifulSoup(preview.text,'html.parser').select('#faq details'))==4
    other=groups['other_solutions']
    link=next(k for k in other['items'][-1]['field_keys']
              if next(f for f in fields if f['key']==k)['kind']=='link')
    unsafe=put_page(client,created['id'],auth,{'values':{
        '__repeat__'+other['id']:json.dumps([{link:'javascript:alert(1)'}])}})
    assert unsafe.status_code==422
    static=client.put(f"/api/templates/{detected['id']}/mapping",headers=auth,
        json={'fields':[{'key':f['key'],'label':f['label'],'mode':'static'}
                        for f in fields],
              'sections':detected['sections'],'approved':True})
    assert static.status_code==200,static.text
    # The existing page keeps its earlier approved variable snapshot.
    assert client.get(f"/api/pages/{created['id']}/preview",headers=auth).status_code==200
