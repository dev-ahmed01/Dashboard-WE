"""Safe, structure-first HTML importer. Nothing becomes variable without an admin mapping decision."""
import re
from html import escape
from bs4 import BeautifulSoup

SECTION_NAMES = {
    'hero': 'Hero', 'highlights': 'Highlights', 'offices': 'Office Types',
    'solutions': 'Solutions', 'benefits': 'Benefits', 'value': 'Benefits',
    'setup': 'Customisation', 'customise': 'Customisation', 'customize': 'Customisation',
    'journey': 'Three Simple Steps', 'steps': 'Three Simple Steps',
    'places': 'Locations', 'locations': 'Locations', 'contact': 'Enquiry',
    'enquiry': 'Enquiry', 'reviews': 'Reviews', 'faqs': 'FAQs', 'faq': 'FAQs',
    'pricing': 'Pricing', 'why': 'Why Us', 'finder': 'Guided Discovery',
}
TEXT_TAGS = {'h1', 'h2', 'h3', 'h4', 'p', 'li', 'button', 'a', 'label', 'span'}
SKIP_CONTAINERS = {'script', 'style', 'noscript', 'svg', 'nav', 'footer', 'form', 'head'}
SAFE_URL = re.compile(r'^(?:https?://|/|#|data:image/(?:png|jpeg|webp|gif);base64,)', re.I)


def sanitize(source: str) -> BeautifulSoup:
    if not source.strip() or len(source.encode()) > 8 * 1024 * 1024:
        raise ValueError('Upload an HTML file under 8 MB')
    soup = BeautifulSoup(source, 'html.parser')
    if not soup.html:
        soup = BeautifulSoup('<!doctype html><html><head></head><body></body></html>', 'html.parser')
        fragment = BeautifulSoup(source, 'html.parser')
        for n in list(fragment.contents): soup.body.append(n)
    for tag in list(soup.find_all(['script', 'iframe', 'frame', 'object', 'embed', 'base', 'meta'])):
        tag.decompose()
    for tag in soup.find_all(True):
        for key in list(tag.attrs):
            if key.lower().startswith('on') or key in ('srcdoc', 'formaction'):
                del tag.attrs[key]
            elif key.lower() in ('href', 'src', 'action', 'poster'):
                value = tag.get(key, '')
                if value and not SAFE_URL.match(str(value)):
                    del tag.attrs[key]
        if tag.name == 'a':
            tag['rel'] = 'noopener noreferrer'
    if soup.head:
        charset = soup.new_tag('meta',charset='utf-8'); soup.head.append(charset)
        viewport = soup.new_tag('meta'); viewport.attrs={'name':'viewport','content':'width=device-width,initial-scale=1'}; soup.head.append(viewport)
    return soup


def label(node, i):
    text = ' '.join([str(node.get('id') or ''), *node.get('class', [])]).lower()
    for key, name in SECTION_NAMES.items():
        if key in text:
            return name
    return 'Hero' if i == 0 else f'Section {i+1}'


def extract(source: str):
    soup = sanitize(source)
    body = soup.body
    root = body.find('main') or body
    nodes = [n for n in root.find_all('section') if not n.find_parent('section')]
    if not nodes:
        nodes = [n for n in root.find_all(recursive=False) if n.name in ('div', 'article', 'header') and (n.get('id') or n.get('class'))]
    if not nodes:
        raise ValueError('No structural sections found. Wrap your design sections in <section> elements.')
    sections, fields = [], []
    for i, node in enumerate(nodes[:40]):
        sec_key = f'section_{i+1}'
        node['data-we-section'] = sec_key
        sections.append({'id': sec_key, 'name': label(node, i), 'order': i+1})
        n = 0
        for tag in node.find_all(True):
            if n >= 48: break
            if tag.find_parent(list(SKIP_CONTAINERS)) or tag.name in SKIP_CONTAINERS: continue
            if tag.name == 'img':
                attr = 'src'; value = str(tag.get(attr, ''))
                if not value: continue
                field_type = 'image'
            elif tag.name in TEXT_TAGS:
                if tag.name == 'span' and tag.find_parent(['h1','h2','h3','h4','p','a','button','li']):continue
                if tag.find(TEXT_TAGS): continue
                value = tag.get_text(' ', strip=True)
                if not 2 <= len(value) <= 700:continue
                attr = 'text'; field_type = 'textarea' if len(value)>110 else 'text'
            else:continue
            n += 1
            key = f'{sec_key}_field_{n}'
            tag['data-we-field'] = key
            fields.append({'key': key, 'section_id': sec_key,
                           'label': ('Image' if field_type=='image' else tag.name.upper())+f' {n}',
                           'kind': field_type, 'attr': attr, 'default': value,
                           'mode': 'static', 'global_key': None})
    return str(soup), sections, fields


def render(source: str, fields: list, values: dict, global_values: dict, section_id: str|None=None):
    soup = BeautifulSoup(source, 'html.parser')
    # The importer already strips active code; rendering repeats sanitation for defence in depth.
    soup = sanitize(str(soup))
    for f in fields:
        target = soup.find(attrs={'data-we-field': f['key']})
        if not target:continue
        mode = f.get('mode', 'static')
        value = (values.get(f['key'], f['default']) if mode == 'page' else
                 global_values.get(f.get('global_key'), f['default']) if mode == 'global' else f['default'])
        if f['attr'] == 'text':
            target.clear()
            target.append(str(value))
        else:
            target[f['attr']] = str(value)
    if section_id:
        for sec in list(soup.find_all(attrs={'data-we-section':True})):
            if sec.get('data-we-section') != section_id: sec.decompose()
    return str(soup)
