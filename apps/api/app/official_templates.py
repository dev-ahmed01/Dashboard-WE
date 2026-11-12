"""Idempotent, approved templates derived from the three existing public pages.

The upstream URLs are fixed and trusted. This module never accepts arbitrary
fetch destinations, never overwrites users' templates/pages, and seeds DRAFTS
rather than publishing to the public site.
"""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin
import re
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
        # Bundled page links to approved PDFs/icons are browser assets too.
        # Without this, the editor preview incorrectly loads /assets/ from
        # admin.workspacebyemlen.co.uk instead of the public website.
        if tag.name in ('a', 'link'):
            value = tag.get('href')
            if isinstance(value, str) and value.startswith('/assets/'):
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
    """Import the approved, versioned HTML *bundled inside the API image*.

    The production API network is internal-only and deliberately has no
    internet egress. Never fetch live site pages during login or bootstrap.
    These snapshots are copied from the public WE repo's built HTML, so they
    include real content, section markup and hashed stylesheet references.
    The browser loads normal public assets via HTTPS while the API stays private.
    """
    names = {
        'managed': 'managed.html',
        'one-person': 'one-person.html',
        'property': 'property.html',
    }
    filename = names.get(item.code)
    if filename is None:
        raise ValueError('Unknown official template')
    path = Path(__file__).with_name('official_pages') / filename
    try:
        source = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise RuntimeError(f'Missing bundled approved template: {item.code}') from exc
    if '<html' not in source.lower() or '<section' not in source.lower():
        raise ValueError(f'Invalid bundled approved template: {item.code}')
    return prepare_html(source)


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
#property-cms-solutions .property-cms-card-photo{display:block;width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:15px;margin:0 0 15px;background:#f8ebe0}
#property-cms-solutions .property-cms-card h3{font:800 22px/1.2 'Bricolage Grotesque',Arial,sans-serif}
#property-cms-solutions .property-cms-card p{margin:12px 0;font:400 14px/1.65 Poppins,Arial,sans-serif;color:#514b47}
#property-cms-solutions .property-cms-card small{display:block;color:#ed2024;margin:10px 0;font:700 13px Poppins,Arial,sans-serif}
#property-cms-solutions .property-cms-card a{display:inline-block;background:#ed2024;color:#fff;border-radius:99px;padding:11px 16px;text-decoration:none;font:700 13px Poppins,Arial,sans-serif}
#photos .property-cms-gallery{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}
#photos .property-cms-gallery figure{margin:0;position:relative;min-height:160px;border-radius:22px;overflow:hidden;background:#fff2e9}
#photos .property-cms-gallery figure:first-child{grid-column:span 2;grid-row:span 2}
#photos .property-cms-gallery img{display:block;width:100%;height:100%;min-height:160px;object-fit:cover}
#photos .property-cms-gallery figcaption{position:absolute;left:10px;bottom:10px;background:rgba(255,255,255,.86);border-radius:18px;padding:6px 10px;font:600 12px Poppins,Arial,sans-serif}
#testimonials .property-cms-reviews{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;width:min(1290px,calc(100% - 40px));margin:24px auto}
#testimonials .property-cms-review{margin:0;background:linear-gradient(140deg,#fff,#fff7f3);border:1px solid #f0e8e2;border-radius:23px;padding:24px;box-shadow:0 9px 25px rgba(66,37,27,.055)}
#testimonials .property-cms-review blockquote{margin:13px 0 22px;font:500 16px/1.52 Poppins,Arial,sans-serif;color:#292320}
#testimonials .property-cms-review strong{display:block;font:700 14px Poppins,Arial,sans-serif;color:#161616}
#testimonials .property-cms-review small{display:block;color:#716866;font:400 12px Poppins,Arial,sans-serif}
#locations .property-cms-map-link{display:inline-flex;margin:13px 0;padding:10px 16px;border-radius:999px;background:#ed2024;color:#fff;text-decoration:none;font:700 13px Poppins,Arial,sans-serif}

@media(max-width:900px){#property-cms-solutions .property-tab-cards{grid-template-columns:repeat(2,minmax(0,1fr))}#photos .property-cms-gallery{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:900px){#testimonials .property-cms-reviews{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:580px){#property-cms-solutions .property-cms-tabs{grid-template-columns:repeat(2,minmax(0,1fr))}#property-cms-solutions .property-tab-cards{grid-template-columns:1fr}}
@media(max-width:580px){#testimonials .property-cms-reviews{grid-template-columns:1fr}}
"""

PROPERTY_CARD_TABS = (
    ('private', 'Private Office', (
        ('One Person Office','A quiet, private workspace to focus on what matters.','Private workspace',
         'one-person-office-dfb5956b.webp'),
        ('Small Team Office','A comfortable team base without the setup overhead.','Team-ready',
         'jp-nagar-workspace-7a871d3c.webp'),
        ('Large Team Office','More space to collaborate, plan and keep growing.','Room to grow',
         'bannerghatta-road-workspace-e85c27e2.webp'),
        ('Full Floor Office','A dedicated workspace for larger teams and operations.','Dedicated floor',
         'workstations-2d09a12b.jpg'),
    )),
    ('coworking', 'Coworking', (
        ('Dedicated Desk','Keep a familiar desk in a shared professional environment.','Regular workspace',
         'community-work-17db361c.jpg'),
        ('Coworking Access Plans','Flexible access for hybrid work and changing schedules.','Flexible access',
         'workstations-2d09a12b.jpg'),
        ('Day Pass','Get a professional place to work whenever you need one.','Day access',
         'jayanagar-workspace-8305969a.jpg'),
    )),
    ('meeting', 'Meeting Rooms', (
        ('Meeting Rooms','A dedicated setting for team and client conversations.','Professional setting',
         'meeting-space-dee1cf8a.jpg'),
        ('Training Rooms','A comfortable space for workshops and group sessions.','Group sessions',
         'private-meeting-room-ca25c712.webp'),
    )),
    ('additional', 'Additional', (
        ('Virtual Office','Build a professional business presence with a lighter footprint.','Business presence',
         'welcome-area-712a74c1.webp'),
        ('Day Office','Use a private workspace for the day when you need extra focus.','Private space',
         'one-person-office-dfb5956b.webp'),
        ('Event Space','A flexible environment for hosting professional gatherings.','Events',
         'community-work-17db361c.jpg'),
        ('Enterprise & GCC','Discuss tailored workspace needs for larger organisations.','Custom plans',
         'workstations-2d09a12b.jpg'),
    )),
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
            # Real, approved Workspace by Emlen public-site photography.
            # The compiled website keeps gallery data in external JavaScript,
            # which is intentionally disabled in CMS previews. These stable,
            # existing assets preserve a usable, fully populated gallery.
            sources = [
                PUBLIC_SITE+'/assets/img/jayanagar-workspace-8305969a.jpg',
                PUBLIC_SITE+'/assets/img/jp-nagar-workspace-7a871d3c.webp',
                PUBLIC_SITE+'/assets/img/bannerghatta-road-workspace-e85c27e2.webp',
                PUBLIC_SITE+'/assets/img/arekere-workspace-f3cbd409.webp',
                PUBLIC_SITE+'/assets/img/welcome-area-712a74c1.webp',
            ]
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
            for name,description,highlight,photo in items:
                card=soup.new_tag('article');card['class']='property-cms-card'
                image=soup.new_tag('img',alt=f'Illustrative workspace for {name}')
                image['class']='property-cms-card-photo'
                image['src']=PUBLIC_SITE+'/assets/img/'+photo
                heading=soup.new_tag('h3');heading.string=name
                desc=soup.new_tag('p');desc.string=description
                badge=soup.new_tag('small');badge.string=highlight
                price=soup.new_tag('small');price.string='Pricing on request · Speak to our team'
                link=soup.new_tag('a',href='#enquiry');link.string='Get a quote'
                card.extend([image,heading,desc,badge,price,link])
                cards.append(card)
            panel.append(cards);panels.append(panel)
        inner.append(panels);section.append(inner)
        amenities=soup.find(id='amenities')
        if amenities:amenities.insert_after(section)
        else:(soup.find('main') or soup.body).append(section)

    # Original four approved reviews from WE property's reference source.
    # Keep the source text fixed and never offer editable testimonial fields.
    testimonials=soup.find(id='testimonials')
    if testimonials and not testimonials.select_one('.property-cms-reviews'):
        approved_reviews=(
            ('Genuine support',
             'Their professionalism and attention to detail make a noticeable difference in the overall experience.',
             'Saritha Kumari','Henry Harvin Education'),
            ('Thoughtful spaces',
             'The space is modern, clean, and well-equipped.',
             'Jnanesh K','Workspace visitor'),
            ('Great location',
             'The best you can ask for in the heart of Jayanagar, near main road, yet very quiet.',
             'Saandeep K Das','Upman Placements Pvt Ltd'),
            ('Everyday comfort',
             'Excellent workplace in Jayanagar 3rd block.',
             'K Anand Anand','Workspace visitor'),
        )
        reviews=soup.new_tag('div')
        reviews['class']='property-cms-reviews'
        for tag,quote,name,role in approved_reviews:
            card=soup.new_tag('article');card['class']='property-cms-review'
            tag_el=soup.new_tag('small');tag_el.string=tag
            quote_el=soup.new_tag('blockquote');quote_el.string=quote
            author=soup.new_tag('strong');author.string=name
            desc=soup.new_tag('small');desc.string=role
            card.extend([tag_el,quote_el,author,desc]);reviews.append(card)
        testimonials.append(reviews)
    # An editable map destination remains available even though security
    # sandboxing removes embedded third-party map iframes from previews.
    locations=soup.find(id='locations')
    if locations:
        # The location stage was otherwise empty without the public JS.
        stage=locations.find(id='weLcPhotos')
        if stage is not None and not stage.find('img'):
            photo=soup.new_tag('img',alt='Workspace by Emlen — Jayanagar office')
            photo['src']=PUBLIC_SITE+'/assets/img/jayanagar-workspace-8305969a.jpg'
            photo['style']='width:100%;height:100%;object-fit:cover;display:block;border-radius:20px'
            stage.append(photo)
        detail=locations.find(id='weLcCard')
        if detail is not None and not detail.get_text(' ',strip=True):
            title=soup.new_tag('h3');title.string='Jayanagar workspace'
            copy=soup.new_tag('p');copy.string='Jayanagar 3rd Block, Bengaluru'
            detail.extend([title,copy])
    if locations and not locations.select_one('.property-cms-map-link'):
        map_link=soup.new_tag('a',href='https://www.google.com/maps/search/?api=1&query=Workspace+by+Emlen+Jayanagar')
        map_link['class']='property-cms-map-link'
        map_link.string='View workspace on Google Maps'
        map_frame=locations.select_one('.we-lc__mapframe') or locations
        map_frame.append(map_link)
    # Populate JS-rendered FAQ only if the source contains no actual cards.
    faqs=soup.find(id='faqs') or soup.find(id='faq')
    if faqs:
        wrapper=faqs.select_one('.faq-list')
        if wrapper is not None and not wrapper.find('details'):
            # Approved public-site FAQ copy, not generic placeholder text.
            content=(
                ('What workspace options are available?',
                 'Explore private offices, coworking, meeting rooms and flexible workspace options. The best choice depends on your team size, preferred location and working style.'),
                ('Can I choose a short-term plan?',
                 'There are flexible options for different needs. Our team can confirm available terms and minimum commitments for your chosen workspace.'),
                ('Are the offices fully furnished?',
                 'Our managed office options are designed to be move-in ready. Exact furniture, facilities and inclusions depend on the office and plan you select.'),
                ('Which locations can I choose from?',
                 'Our current featured neighbourhoods are Jayanagar, JP Nagar, Bannerghatta Road and Arekere. Ask our team about exact addresses and current availability.'),
                ('How quickly can I move in?',
                 'It depends on the office you choose, availability and any requested changes. The team can confirm the expected move-in date after understanding your needs.'),
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
