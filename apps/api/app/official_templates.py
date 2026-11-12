"""Idempotent, approved templates derived from the three existing public pages.

The upstream URLs are fixed and trusted. This module never accepts arbitrary
fetch destinations, never overwrites users' templates/pages, and seeds DRAFTS
rather than publishing to the public site.
"""
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
import re

import httpx
from bs4 import BeautifulSoup

from .template_engine import extract
from .repeaters import overlay_metadata

PUBLIC_SITE = 'https://workspacebyemlen.co.uk'
MAX_SOURCE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class OfficialPage:
    code: str
    title: str
    category: str
    path: str
    page_title: str
    page_slug: str


OFFICIAL_PAGES = (
    OfficialPage('managed', 'Managed Offices — Approved 2026', 'Solution Category',
                 '/managed-office/south-bangalore/', 'Managed Offices', 'managed-offices-base'),
    OfficialPage('one-person', 'One Person Office — Approved 2026', 'Solution',
                 '/managed-office/one-person-office/', 'One Person Office', 'one-person-office-base'),
    OfficialPage('property', 'Workspace Property — Approved 2026', 'Property',
                 '/workspaces/', 'Workspace Property Reference', 'workspace-property-base'),
)

SOLUTION_SECTIONS = (
    ('1A · Hero', ('hero',)),
    ('1B · Values', ('values', 'value', 'highlight')),
    ('3 · Options', ('options', 'office options', 'office type')),
    ('4 · Customisation', ('customisation', 'customization', 'customise', 'customize')),
    ('6 · Benefits', ('benefits', 'benefit')),
    ('7 · How to Get Started', ('how to get started', 'steps', 'journey', 'process')),
    ('8 · Locations', ('locations', 'location')),
    ('9 · FAQs', ('faqs', 'faq', 'questions')),
)
PROPERTY_SECTIONS = (
    ('1A · Hero', ('hero',)),
    ('2 · Photos', ('gallery', 'photos', 'images')),
    ('4 · Amenities', ('amenities', 'facility', 'facilities')),
    ('5 · Solutions', ('solutions', 'solution', 'offices')),
    ('6 · Location & Landmarks', ('landmarks', 'locations', 'location', 'map')),
    ('7 · Testimonials', ('testimonials', 'testimonial', 'reviews', 'review')),
    ('9 · FAQs', ('faqs', 'faq', 'questions')),
)
CATEGORY_SECTIONS = (
    ('1 · Hero', ('hero',)),
    ('2 · Office Types', ('offices', 'office types')),
    ('3 · Other Solutions', ('other solutions', 'more solutions')),
    ('4 · Guided Discovery', ('discovery', 'questions', 'finder')),
    ('5 · Benefits', ('benefits',)),
    ('6 · Why Us', ('why us',)),
    ('7 · FAQs', ('faqs', 'faq')),
)


def official_key(code: str) -> str:
    return f'templates/official-workspace-{code}-2026.html'


def prepare_html(html: str) -> str:
    """Resolve *asset* references to the known public host for admin previews.

    Page/CTA hyperlinks remain whatever they were in the approved template.
    An admin iframe's origin must not accidentally rewrite static assets to the
    admin host. Never change data URIs, external sources, or anchor links.
    """
    if len(html.encode('utf-8')) > MAX_SOURCE_BYTES:
        raise ValueError('The official HTML exceeds the 8 MB importer limit')
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.html:
        raise ValueError('The official source is not a complete HTML document')
    for tag in soup.find_all(True):
        for attribute in ('src', 'poster'):
            value = tag.get(attribute)
            if isinstance(value, str) and value.startswith('/assets/'):
                tag[attribute] = urljoin(PUBLIC_SITE, value)
        if tag.name == 'link' and 'stylesheet' in tag.get('rel', []):
            value = tag.get('href')
            if isinstance(value, str) and value.startswith('/'):
                tag['href'] = urljoin(PUBLIC_SITE, value)
        if tag.get('srcset'):
            parts = []
            for part in str(tag['srcset']).split(','):
                part = part.strip()
                if part.startswith('/assets/'):
                    words = part.split(maxsplit=1)
                    part = urljoin(PUBLIC_SITE, words[0]) + (' ' + words[1] if len(words)>1 else '')
                parts.append(part)
            tag['srcset'] = ', '.join(parts)
        style = tag.get('style')
        if isinstance(style, str):
            tag['style'] = re.sub(
                r'url\(\s*([\'"]?)(/assets/[^)\'"]+)\1\s*\)',
                lambda m: 'url("' + urljoin(PUBLIC_SITE, m.group(2)) + '")', style
            )
    return str(soup)


def fetch_official(item: OfficialPage) -> str:
    url = PUBLIC_SITE + item.path
    # Fixed host and redirect disabled prevent unexpected SSRF targets.
    with httpx.Client(timeout=httpx.Timeout(18.0), follow_redirects=False,
                      headers={'User-Agent': 'WorkspaceEmlenAdminTemplateSync/1.0'}) as client:
        with client.stream('GET', url) as response:
            response.raise_for_status()
            if urlsplit(str(response.url)).hostname != 'workspacebyemlen.co.uk':
                raise ValueError('Unexpected template source')
            if 'text/html' not in response.headers.get('content-type', ''):
                raise ValueError('Official source was not HTML')
            chunks=[];size=0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_SOURCE_BYTES:
                    raise ValueError('Official HTML exceeds the importer limit')
                chunks.append(chunk)
    return prepare_html(b''.join(chunks).decode('utf-8'))


def _rename_sections(category: str, sections: list[dict]) -> list[dict]:
    presets = (SOLUTION_SECTIONS if category == 'Solution' else
               PROPERTY_SECTIONS if category == 'Property' else CATEGORY_SECTIONS)
    already=set();result=[]
    for index, original in enumerate(sections):
        section=dict(original)
        name=str(section['name']).lower().strip()
        # Default numbered names provide no meaningful hint, but first is
        # the hero in all three approved designs.
        candidates=[(title,markers) for title,markers in presets
                    if any(mark in name for mark in markers)]
        if index == 0 and not candidates:
            candidates=[presets[0]]
        for title, _markers in candidates:
            if title not in already:
                section['name'] = title
                already.add(title)
                break
        result.append(section)
    return result


def _auto_fields(category: str, sections: list[dict], fields: list[dict]) -> list[dict]:
    names={s['id']:s['name'].lower() for s in sections}
    output=[]
    counters={}
    for item in fields:
        field=dict(item)
        sec=names.get(field['section_id'], '')
        read_only = category == 'Property' and (
            'testimonial' in sec or 'review' in sec
        )
        # Do not make icons and layout-only SVGs free-form editors.
        field['mode'] = ('page' if not read_only and
                         field['kind'] in ('text','textarea','image','link') else 'static')
        field['global_key']=None
        if field['mode']=='page':
            key=(field['section_id'],field.get('kind'),field.get('tag'))
            counters[key]=counters.get(key,0)+1
            no=counters[key]
            if field['kind']=='image':
                name='Featured image' if 'photo' in sec and no==1 else 'Image' if no==1 else f'Image {no}'
            elif field['kind']=='link':
                name='CTA link' if no==1 else f'CTA link {no}'
            elif field.get('tag')=='h1':
                name='Heading'
            elif field.get('tag') in ('h2','h3','h4','h5','h6'):
                name='Heading' if no==1 else f'Card / subheading {no}'
            elif field.get('tag')=='summary' and 'faq' in sec:
                name=f'Question {no}'
            elif field.get('tag')=='li':
                name=f'Highlight / bullet point {no}'
            elif field.get('tag')=='p':
                name='Description' if no==1 else f'Description {no}'
            else:
                name=str(field.get('label') or 'Text')[:95]
            field['label'] = name
        output.append(field)
    return output



# The public workspace page fills some sections in JavaScript. CMS previews
# deliberately sandbox scripts, so render editable HTML equivalents instead
# of importing empty gallery/FAQ/card containers.
PROPERTY_CSS = """
#property-cms-solutions{padding:60px 0;background:#fffaf6;color:#161616}
#property-cms-solutions .property-cms-inner{width:min(1290px,calc(100% - 40px));margin:auto}
#property-cms-solutions .property-cms-head h2{font:800 clamp(32px,3.7vw,50px)/1.12 'Bricolage Grotesque',Arial,sans-serif;letter-spacing:-.045em}
#property-cms-solutions .property-cms-head p{margin:12px 0 22px;color:#615856;font:400 16px/1.6 Poppins,Arial,sans-serif}
#property-cms-solutions .property-cms-input{position:absolute;opacity:0;pointer-events:none}
#property-cms-solutions .property-cms-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0 25px}
#property-cms-solutions .property-cms-tabs label{padding:15px 8px;text-align:center;border-radius:999px;background:#fff;border:1px solid #e7ded7;font:700 14px Poppins,Arial,sans-serif;cursor:pointer}
#property-cms-solutions .property-cms-panel{display:none}
#property-cms-tab-private:checked~.property-cms-tabs label[for=property-cms-tab-private],
#property-cms-tab-coworking:checked~.property-cms-tabs label[for=property-cms-tab-coworking],
#property-cms-tab-meeting:checked~.property-cms-tabs label[for=property-cms-tab-meeting],
#property-cms-tab-additional:checked~.property-cms-tabs label[for=property-cms-tab-additional]{background:#ed2024;color:#fff;border-color:#ed2024}
#property-cms-tab-private:checked~.property-cms-panels #property-cms-private,
#property-cms-tab-coworking:checked~.property-cms-panels #property-cms-coworking,
#property-cms-tab-meeting:checked~.property-cms-panels #property-cms-meeting,
#property-cms-tab-additional:checked~.property-cms-panels #property-cms-additional{display:block}
#property-cms-solutions .property-tab-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:15px}
#property-cms-solutions .property-cms-card{padding:22px;border-radius:24px;background:linear-gradient(145deg,#fff,#fff8f2);border:1px solid #eee7e4;box-shadow:0 12px 24px rgba(64,38,29,.06)}
#property-cms-solutions .property-cms-card h3{font:800 22px/1.2 'Bricolage Grotesque',Arial,sans-serif}
#property-cms-solutions .property-cms-card p{margin:12px 0;font:400 14px/1.65 Poppins,Arial,sans-serif;color:#514b47}
#property-cms-solutions .property-cms-card small{display:block;color:#ed2024;margin:10px 0;font:700 13px Poppins,Arial,sans-serif}
#property-cms-solutions .property-cms-card a{display:inline-block;background:#ed2024;color:#fff;border-radius:99px;padding:11px 16px;text-decoration:none;font:700 13px Poppins,Arial,sans-serif}
#photos .property-cms-gallery{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}
#photos .property-cms-gallery figure{margin:0;position:relative;min-height:160px;border-radius:22px;overflow:hidden;background:#fff2e9}
#photos .property-cms-gallery figure:first-child{grid-column:span 2;grid-row:span 2}
#photos .property-cms-gallery img{display:block;width:100%;height:100%;min-height:160px;object-fit:cover}
#photos .property-cms-gallery figcaption{position:absolute;left:10px;bottom:10px;background:rgba(255,255,255,.86);border-radius:18px;padding:6px 10px;font:600 12px Poppins,Arial,sans-serif}
@media(max-width:900px){#property-cms-solutions .property-tab-cards{grid-template-columns:repeat(2,minmax(0,1fr))}#photos .property-cms-gallery{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:580px){#property-cms-solutions .property-cms-tabs{grid-template-columns:repeat(2,minmax(0,1fr))}#property-cms-solutions .property-tab-cards{grid-template-columns:1fr}}
"""

PROPERTY_CARD_TABS = (
    ('private', 'Private Office', ('One Person Office','Small Team Office','Large Team Office','Full Floor Office')),
    ('coworking', 'Coworking', ('Coworking Option 1','Coworking Option 2')),
    ('meeting', 'Meeting Rooms', ('Meeting Room Option 1','Meeting Room Option 2')),
    ('additional', 'Additional', ('Additional Solution 1','Additional Solution 2')),
)


def hydrate_property(html: str) -> str:
    """Make the approved Property source editable without executing its scripts.

    Keep the original page and its styling. Add CMS-only cards where the public
    page relies on dynamic scripts; never fabricate commercial pricing/reviews.
    """
    soup=BeautifulSoup(html,'html.parser')
    if not soup.head or not soup.body:
        return html
    style=soup.new_tag('style')
    style['id']='property-cms-static-sections'
    style.string=PROPERTY_CSS
    soup.head.append(style)
    photos=soup.find(id='photos')
    if photos and not photos.select_one('.property-cms-gallery'):
        # Pick authentic embedded photo assets from the public page's scripts,
        # but do not interpret or execute JavaScript.
        sources=[]
        for match in re.finditer(
            r'(?:(?:data:image/(?:webp|jpeg|png);base64,[A-Za-z0-9+/=]{90,})|(?:/assets/img/[a-zA-Z0-9_.-]+))',
            html
        ):
            url=match.group(0)
            if url not in sources:
                sources.append(url)
            if len(sources)>=5:break
        if not sources:
            # Four explicit, editable photo slots. Blank until the editor uploads
            # genuine property photography; never substitute an unrelated logo.
            sources=['data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4//8/AwAI/AL+XUm6SAAAAABJRU5ErkJggg==']
        if sources:
            wrapper=soup.new_tag('div')
            wrapper['class']='property-cms-gallery'
            wrapper['data-we-name']='Featured image and gallery'
            for idx in range(max(4,min(5,len(sources)))):
                fig=soup.new_tag('figure')
                img=soup.new_tag('img')
                img['src']=sources[idx%len(sources)]
                img['alt']='Featured workspace' if idx==0 else f'Workspace gallery image {idx}'
                fig.append(img)
                label=soup.new_tag('figcaption')
                label.string='Featured image' if idx==0 else f'Gallery photo {idx}'
                fig.append(label);wrapper.append(fig)
            gallery=photos.find(id='weGalGrid') or photos
            gallery.append(wrapper)
    if not soup.find(id='property-cms-solutions'):
        section=soup.new_tag('section',id='property-cms-solutions')
        section['data-we-name']='5 · Solutions'
        inner=soup.new_tag('div');inner['class']='property-cms-inner'
        head=soup.new_tag('div');head['class']='property-cms-head'
        h2=soup.new_tag('h2');h2.string='Solutions for every workday'
        p=soup.new_tag('p');p.string='Choose the format that fits your business. Ask our team for a current quote.'
        head.append(h2);head.append(p);inner.append(head)
        for idx,(code,title,items) in enumerate(PROPERTY_CARD_TABS):
            input_el=soup.new_tag('input',attrs={'type':'radio','name':'property-cms-tab','id':'property-cms-tab-'+code})
            input_el['class']='property-cms-input'
            if idx==0:input_el['checked']='checked'
            inner.append(input_el)
        tabs=soup.new_tag('div');tabs['class']='property-cms-tabs';tabs['role']='tablist'
        for code,title,_ in PROPERTY_CARD_TABS:
            tab=soup.new_tag('label');tab['for']='property-cms-tab-'+code
            tab.string=title
            tabs.append(tab)
        inner.append(tabs)
        panels=soup.new_tag('div');panels['class']='property-cms-panels'
        for code,title,items in PROPERTY_CARD_TABS:
            panel=soup.new_tag('div',id='property-cms-'+code);panel['class']='property-cms-panel'
            cards=soup.new_tag('div');cards['class']='property-tab-cards'
            cards['data-we-repeat-name']=title
            for name in items:
                card=soup.new_tag('article');card['class']='property-cms-card'
                heading=soup.new_tag('h3');heading.string=name
                desc=soup.new_tag('p');desc.string='Tell us your requirements to explore suitable workspace options.'
                price=soup.new_tag('small');price.string='Pricing on request · Speak to our team'
                link=soup.new_tag('a',href='#enquiry');link.string='Get a quote'
                card.append(heading);card.append(desc);card.append(price);card.append(link)
                cards.append(card)
            panel.append(cards);panels.append(panel)
        inner.append(panels);section.append(inner)
        amenities=soup.find(id='amenities')
        if amenities:amenities.insert_after(section)
        else:(soup.find('main') or soup.body).append(section)
    # Populate JS-rendered FAQ only if the source contains no actual cards.
    faqs=soup.find(id='faqs') or soup.find(id='faq')
    if faqs:
        wrapper=faqs.select_one('.faq-list')
        if wrapper is not None and not wrapper.find('details'):
            content=(
                ('Can I visit before choosing?', 'Contact our team to arrange a workspace visit.'),
                ('What amenities are included?', 'Facilities may vary by office and plan; please confirm when enquiring.'),
                ('Are private offices available?', 'Ask about private office formats for your team.'),
                ('Can I book a meeting room?', 'Our team can explain the available meeting room options.'),
                ('How do I get a quote?', 'Submit your workspace requirements using the enquiry form.'),
            )
            for question,answer in content:
                detail=soup.new_tag('details')
                summary=soup.new_tag('summary');summary.string=question
                paragraph=soup.new_tag('p');paragraph.string=answer
                detail.append(summary);detail.append(paragraph);wrapper.append(detail)
    return str(soup)

def make_template(item: OfficialPage, html: str):
    """Return sanitized HTML, named sections and automatically editable fields."""
    if item.category == 'Property':
        html = hydrate_property(html)
    source, sections, fields = extract(html)
    sections = _rename_sections(item.category, sections)
    fields = _auto_fields(item.category, sections, fields)
    source, sections = overlay_metadata(source, sections, fields)
    # Solution option cards stop at FOUR total, not four extra copies.
    for section in sections:
        if item.category == 'Solution' and 'options' in section['name'].lower():
            for group in section.get('repeaters', []):
                if group['kind'] in ('cards','solutions','options'):
                    group['kind']='options'
                    group['name']='Office options'
                    group['max_additions']=max(0,4-len(group['items']))
    return source, sections, fields


def read_only_section(category: str, name: str) -> bool:
    return category == 'Property' and any(token in name.lower() for token in (
        'testimonial', 'review'
    ))
