"""Safe, structure-first HTML importer and configurable template renderer.

Structure, page text, heading levels, links and icons are detected separately.
Nothing becomes variable without an administrator mapping decision.
"""
import re
from bs4 import BeautifulSoup, NavigableString, Tag

SECTION_NAMES = {
    'hero': 'Hero', 'highlights': 'Highlights', 'offices': 'Office Types',
    'solutions': 'Solutions', 'benefits': 'Benefits', 'value': 'Benefits',
    'setup': 'Customisation', 'customise': 'Customisation', 'customize': 'Customisation',
    'journey': 'Three Simple Steps', 'steps': 'Three Simple Steps',
    'places': 'Locations', 'locations': 'Locations', 'contact': 'Enquiry',
    'enquiry': 'Enquiry', 'reviews': 'Reviews', 'faqs': 'FAQs', 'faq': 'FAQs',
    'pricing': 'Pricing', 'why': 'Why Us', 'finder': 'Guided Discovery',
    'features': 'Features', 'gallery': 'Gallery', 'about': 'About',
    'process': 'Process', 'cta': 'Call to Action', 'banner': 'Banner',
}
HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
TEXT_TAGS = HEADINGS | {'p', 'li', 'button', 'a', 'label', 'span', 'summary'}
SKIP_CONTAINERS = {'script', 'style', 'noscript', 'nav', 'head'}
SAFE_URL = re.compile(r'^(?:https?://|/(?!/)|#|data:image/(?:png|jpeg|webp|gif);base64,)', re.I)
SAFE_LINK = re.compile(r'^(?:https?://|/(?!/)|#|mailto:|tel:)', re.I)
SAFE_CLASS = re.compile(r'^[a-zA-Z0-9 _-]{1,240}$')
# Built-in, reviewed inline icons require no external image hosting.
# Geometry is fixed by the application and never loaded from user markup.
ICON_PATHS = {
    'arrow-up-right': ['M7 17 17 7', 'M7 7h10v10'],
    'arrow-right': ['M5 12h14', 'm12 5 7 7-7 7'],
    'phone': ['M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.96.35 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.35 1.85.58 2.81.7A2 2 0 0 1 22 16.92z'],
    'map-pin': ['M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 0 1 16 0Z', 'M12 10h.01'],
    'check': ['M20 6 9 17l-5-5'],
    'calendar': ['M8 2v4', 'M16 2v4', 'M3 10h18', 'M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z'],
    'chevron-right': ['m9 18 6-6-6-6'],
    'layers': ['m12 2 8 5-8 5-8-5 8-5z', 'm4 12 8 5 8-5', 'm4 17 8 5 8-5'],
}
ICON_PREFIX='icon:'

def is_safe_icon_value(value: str) -> bool:
    return not value or bool(SAFE_URL.match(value)) or (
        value.startswith(ICON_PREFIX) and value[len(ICON_PREFIX):] in ICON_PATHS
    )



BUTTON_LOCATION = re.compile(
    r"""(?:window\.)?location(?:\.href)?\s*=\s*["']([^"']+)["']""",
    re.I,
)
SECTION_HINT = re.compile(r'(?:^|[-_\s])section(?:$|[-_\s])', re.I)


def is_safe_link(value: str) -> bool:
    return bool(SAFE_LINK.match(value) and not any(c in value for c in ('\n', '\r', '\x00')))


def sanitize(source: str) -> BeautifulSoup:
    if not source.strip() or len(source.encode()) > 8 * 1024 * 1024:
        raise ValueError('Upload an HTML file under 8 MB')
    soup = BeautifulSoup(source, 'html.parser')
    if not soup.html:
        soup = BeautifulSoup('<!doctype html><html><head></head><body></body></html>', 'html.parser')
        fragment = BeautifulSoup(source, 'html.parser')
        for n in list(fragment.contents):
            soup.body.append(n)
    # Preserve a simple safe navigation target on CTA buttons before stripping script handlers.
    for btn in soup.find_all('button'):
        raw = str(btn.get('data-we-link') or btn.get('data-href') or btn.get('data-url') or '')
        if not raw and btn.get('onclick'):
            match = BUTTON_LOCATION.search(str(btn.get('onclick')))
            if match:
                raw = match.group(1)
        if raw and is_safe_link(raw):
            btn['data-we-link'] = raw
    for tag in list(soup.find_all(['script', 'iframe', 'frame', 'object', 'embed', 'base', 'meta'])):
        tag.decompose()
    for tag in soup.find_all(True):
        for key in list(tag.attrs):
            key_lower = key.lower()
            if key_lower.startswith('on') or key_lower in ('srcdoc', 'formaction'):
                del tag.attrs[key]
            elif key_lower in ('href', 'xlink:href', 'data-we-link', 'data-href', 'data-url', 'action'):
                value = str(tag.get(key, '')).strip()
                if value and not is_safe_link(value):
                    del tag.attrs[key]
            elif key_lower in ('src', 'poster'):
                value = str(tag.get(key, '')).strip()
                if value and not SAFE_URL.match(value):
                    del tag.attrs[key]
        if tag.name == 'a':
            tag['rel'] = 'noopener noreferrer'
    if soup.head:
        soup.head.append(soup.new_tag('meta', charset='utf-8'))
        viewport = soup.new_tag('meta')
        viewport.attrs = {'name': 'viewport', 'content': 'width=device-width,initial-scale=1'}
        soup.head.append(viewport)
    return soup


def label(node, i):
    explicit = (node.get('data-we-name') or '').strip()
    if explicit:
        return explicit[:120]
    annotated = str(node.get('data-we-section') or '').strip()
    if annotated and not re.fullmatch(r'section_[0-9]+', annotated):
        return annotated.replace('_', ' ').replace('-', ' ').title()[:120]
    text = ' '.join([str(node.get('id') or ''), *node.get('class', [])]).lower()
    for key, name in SECTION_NAMES.items():
        if key in text:
            return name
    heading = node.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    if heading:
        title = heading.get_text(' ', strip=True)
        if 3 <= len(title) <= 75:
            return title
    return 'Hero' if i == 0 else f'Section {i+1}'


def get_sections(root):
    """Combine annotated and semantic sections; do not discard unannotated siblings.

    Older imports stored data-we-section on only the sections previously found.
    A re-scan must include an unannotated seventh section, while avoiding card
    elements or a surrounding full-page wrapper as duplicate sections.
    """
    candidate_nodes = []
    for node in root.find_all(True):
        if node.find_parent(['nav', 'form', 'footer']) and node.name != 'footer':
            continue
        is_annotated = bool(node.get('data-we-section'))
        heading = node.find(list(HEADINGS))
        text_length = len(node.get_text(' ', strip=True))
        marker = str(node.get('id') or '') + ' ' + ' '.join(node.get('class', []))
        marker = marker.lower()
        named_section = bool(SECTION_HINT.search(marker) or
                             any(re.search(r'(?<![a-z])' + re.escape(key) + r'(?![a-z])', marker)
                                 for key in SECTION_NAMES))
        if is_annotated or node.name == 'section':
            candidate_nodes.append(node)
        elif node.name == 'header' and heading and text_length >= 18 and node.find('h1'):
            candidate_nodes.append(node)
        elif node.name in ('div', 'article', 'footer') and (
            (named_section and (heading or text_length >= 30)) or
            (node.parent == root and heading and text_length >= 30)
        ):
            candidate_nodes.append(node)

    if not candidate_nodes:
        return [n for n in root.find_all(recursive=False)
                if n.name in ('div', 'article', 'header') and
                (n.get('id') or n.get('class'))]

    candidates = set(candidate_nodes)
    selected = []
    for node in candidate_nodes:
        # A generic wrapper surrounding several real sections is not one section.
        children = [child for child in node.descendants
                    if isinstance(child, Tag) and child in candidates]
        if (node.name in ('div', 'article') and not node.get('data-we-section') and
                len(children) >= 2):
            continue
        if any(parent in selected for parent in node.parents):
            continue
        selected.append(node)
    return selected


def extract(source: str):
    soup = sanitize(source)
    main = soup.body.find('main')
    root = main or soup.body
    nodes = get_sections(root)
    if main:
        # Some exported designs put their visual hero <header> before <main>;
        # legacy extraction looked inside main only and silently omitted it.
        before_main = []
        for node in soup.body.descendants:
            if node is main:
                break
            if not isinstance(node, Tag) or node.name not in ('header', 'section', 'div'):
                continue
            if node.find('main') or node.find_parent(['nav', 'footer']):
                continue
            heading = node.find('h1')
            if heading and heading.get_text(' ', strip=True) and len(node.get_text(' ', strip=True)) >= 25:
                before_main.append(node)
        if before_main:
            # Choose the first meaningful outer container, not a nested hero card.
            hero = next((n for n in before_main if n.name in ('header', 'section')), before_main[0])
            nodes = [hero] + nodes
    if not nodes:
        raise ValueError('No structural sections found. Wrap your design sections in <section> elements.')
    sections, fields = [], []
    used_sections, used_fields = set(), set()
    # Reserve previously annotated keys before producing any new ones on re-scan.
    # A newly discovered hero appearing before six old sections must not steal
    # "section_1" and shift every old section's identity and mapping.
    reserved_sections = {str(node.get('data-we-section')) for node in soup.find_all(True)
                         if node.get('data-we-section')}
    reserved_fields = {str(tag.get(attr)) for tag in soup.find_all(True)
                       for attr in ('data-we-field', 'data-we-link-field')
                       if tag.get(attr)}

    for i, node in enumerate(nodes[:60]):
        annotated = str(node.get('data-we-section') or '').strip()
        if re.fullmatch(r'[a-z][a-z0-9_-]{1,70}', annotated) and annotated not in used_sections:
            sec_key = annotated
        else:
            number = i + 1
            while f'section_{number}' in used_sections or f'section_{number}' in reserved_sections:
                number += 1
            sec_key = f'section_{number}'
        used_sections.add(sec_key)
        node['data-we-section'] = sec_key
        sections.append({'id': sec_key, 'name': label(node, i), 'order': i+1})
        count = 0

        def add_field(tag, kind, attr, default, prefix, marker='data-we-field'):
            nonlocal count
            if count >= 160:
                return
            count += 1
            previous = str(tag.get(marker) or '').strip()
            if re.fullmatch(r'[a-z][a-z0-9_-]{1,100}', previous) and previous not in used_fields:
                key = previous
            else:
                key = f'{sec_key}_field_{count}'
                while key in used_fields or key in reserved_fields:
                    key += '_copy'
            used_fields.add(key)
            tag[marker] = key
            snippet = str(tag.get('alt') or 'Image') if kind == 'image' else str(default)
            if kind == 'icon':
                snippet = 'Inline SVG' if attr == 'icon_src' else 'Icon class'
            if kind == 'link':
                snippet = tag.get_text(' ', strip=True)[:55] or str(default)
            snippet = ' '.join(snippet.split())
            field_label = str(tag.get('data-we-label') or '').strip() if marker == 'data-we-field' else ''
            if not field_label:
                field_label = f'{prefix}: {snippet[:65]}' + ('…' if len(snippet)>65 else '')
            fields.append({
                'key': key, 'section_id': sec_key, 'label': field_label[:120],
                'kind': kind, 'attr': attr, 'default': str(default), 'mode': 'static',
                'global_key': None, 'tag': tag.name, 'heading_tag': tag.name if tag.name in HEADINGS else None,
                'marker': marker,
            })

        for tag in node.find_all(True):
            if count >= 160:
                break
            if tag.name in SKIP_CONTAINERS or tag.find_parent(list(SKIP_CONTAINERS)):
                continue
            if tag.name == 'img':
                url = str(tag.get('src', ''))
                if url:
                    add_field(tag, 'image', 'src', url, 'Image')
            elif tag.name == 'svg':
                # Original SVG remains in place until an icon URL is supplied.
                add_field(tag, 'icon', 'icon_src', '', 'SVG icon')
            elif tag.name == 'i' and tag.get('class'):
                add_field(tag, 'icon', 'class', ' '.join(tag.get('class')), 'Icon class')
            elif tag.name in ('div', 'strong', 'b'):
                # Real designs often style their highlight-card titles as
                # <div class="card-title"> rather than h2/h3. Detect only leaf
                # text nodes; never map layout wrappers containing other fields.
                if tag.find(list(TEXT_TAGS | {'div', 'strong', 'b'})):
                    continue
                if tag.find_parent(list(HEADINGS | {'p', 'li', 'label', 'a', 'button'})):
                    continue
                value=' '.join(part.strip() for part in tag.contents
                               if isinstance(part, NavigableString) and part.strip())
                if 2 <= len(value) <= 1000:
                    classes=' '.join(tag.get('class', []))
                    prefix='Card title' if re.search(r'(?:^|[-_\\s])(card|tile|feature)[-_\\s]*title', classes, re.I) else 'Text'
                    add_field(tag, 'textarea' if len(value)>110 else 'text','text',value,prefix)
            elif tag.name in TEXT_TAGS:
                # Parent headings/paragraphs/buttons own their text even when styled
                # spans or inline icons occur inside. Never double-count nested spans.
                if tag.name == 'span' and tag.find_parent(list(TEXT_TAGS)):
                    continue
                if tag.name in {'p', 'label', 'li'} and tag.find_parent(['a', 'button']):
                    continue
                value = tag.get_text(' ', strip=True)
                if tag.name in ('a', 'button'):
                    if 2 <= len(value) <= 1000:
                        add_field(tag, 'textarea' if len(value) > 110 else 'text', 'text', value,
                                  'Button text' if tag.name == 'button' or 'btn' in tag.get('class', []) else 'Link text')
                    url = str(tag.get('href', '') if tag.name == 'a' else tag.get('data-we-link', ''))
                    # Button-shaped controls are NOT automatically links:
                    # FAQ accordions, office-size options, tabs and step dots
                    # must retain their interaction semantics and must never
                    # become an editable "Button destination" input.
                    if url and url not in ('#', '#!') and is_safe_link(url):
                        add_field(tag, 'link', 'href' if tag.name == 'a' else 'data-we-link', url,
                                  'Button link' if tag.name == 'button' else 'Link destination',
                                  marker='data-we-link-field')
                elif 2 <= len(value) <= 1000:
                    if tag.find_parent(list(HEADINGS | {'p', 'li', 'label'})):
                        continue
                    prefix = {
                        'h1':'H1 heading','h2':'H2 heading','h3':'H3 heading',
                        'h4':'H4 heading','h5':'H5 heading','h6':'H6 heading',
                        'p':'Paragraph','li':'List item','span':'Text','label':'Label'
                    }.get(tag.name, 'Text')
                    add_field(tag, 'textarea' if len(value) > 110 else 'text', 'text', value, prefix)
    from .repeaters import overlay_metadata
    annotated_html, enriched_sections = overlay_metadata(str(soup), sections, fields)
    return annotated_html, enriched_sections, fields


ARROW_SUFFIX = re.compile(r'\s*([↗↖↘↙→➜➔›])\s*$')
ICON_CLASS_HINT = re.compile(r'(?:icon|arrow|arr|chevron|toggle|symbol|glyph)', re.I)


def _decorative_node(node: NavigableString, root: Tag) -> bool:
    """Protect CSS arrow/icon glyphs and aria-hidden spans during CTA edits."""
    parent=node.parent
    while parent is not None and parent is not root:
        if parent.name in ('svg', 'style', 'script') or str(parent.get('aria-hidden', '')).lower() == 'true':
            return True
        if ICON_CLASS_HINT.search(' '.join(parent.get('class', []))):
            return True
        parent=parent.parent
    return bool(re.fullmatch(r'\s*[↗↖↘↙→➜➔›+]\s*',str(node)))


def change_rendered_field(soup, target: Tag, field: dict, value: str):
    """Apply one value while preserving icons, arrows and legal URL schemes."""
    attr=field['attr']
    if attr=='text':
        requested_heading=field.get('heading_tag')
        if requested_heading in HEADINGS and target.name in HEADINGS:
            target.name=requested_heading
        if value==str(field.get('default','')):
            return
        if target.name in ('a','button','summary'):
            # Legacy snapshots may include an arrow as plain trailing text.
            # Move it into its own noneditable icon only when none exists yet.
            icon_match=ARROW_SUFFIX.search(str(field.get('default','')))
            descendants=[x for x in target.descendants if isinstance(x,NavigableString) and x.strip()]
            protected=[x for x in descendants if _decorative_node(x,target)]
            raw_main=[x for x in descendants if x not in protected]
            if icon_match and not protected:
                last=raw_main[-1] if raw_main else None
                if last is not None and ARROW_SUFFIX.search(str(last)):
                    current=str(last)
                    last.replace_with(ARROW_SUFFIX.sub('',current))
                    preserved=soup.new_tag('span')
                    preserved['aria-hidden']='true'
                    preserved['class']='we-preserved-cta-icon'
                    preserved.string=icon_match.group(1)
                    target.append(preserved)
            texts=[x for x in target.descendants if isinstance(x,NavigableString)
                   and x.strip() and not _decorative_node(x,target)]
            # If the user typed an arrow into the button label, keep just
            # the real text so it never duplicates the protected arrow.
            if any(_decorative_node(x,target) for x in target.descendants if isinstance(x,NavigableString)):
                value=ARROW_SUFFIX.sub('',value).strip()
        else:
            texts=[x for x in target.descendants if isinstance(x,NavigableString)
                   and x.strip() and x.parent.name not in ('svg','style','script')]
        if texts:
            texts[0].replace_with(value)
            for extra in texts[1:]:extra.replace_with('')
        else:
            target.insert(0,value)
    elif attr in ('href','data-we-link'):
        if value and not is_safe_link(value):return
        if attr=='data-we-link':
            if value:
                if target.name=='button':
                    target.name='a'
                    target.attrs.pop('type',None)
                    target.attrs.pop('disabled',None)
                target['href']=value
                target['rel']='noopener noreferrer'
            elif target.name=='a':
                target.attrs.pop('href',None)
        elif value:
            target['href']=value
        else:
            target.attrs.pop('href',None)
    elif attr=='icon_src':
        if not value:
            return  # Keep the exact source icon when no change is selected.
        if value.startswith(ICON_PREFIX) and value[len(ICON_PREFIX):] in ICON_PATHS:
            replacement=soup.new_tag('svg')
            replacement['viewBox']='0 0 24 24'
            replacement['fill']='none'
            replacement['stroke']='currentColor'
            replacement['stroke-width']='2'
            replacement['stroke-linecap']='round'
            replacement['stroke-linejoin']='round'
            replacement['aria-hidden']='true'
            for d in ICON_PATHS[value[len(ICON_PREFIX):]]:
                path=soup.new_tag('path')
                path['d']=d
                replacement.append(path)
        elif SAFE_URL.match(value):
            replacement=soup.new_tag('img',src=value)
            replacement['alt']=target.get('aria-label') or ''
            replacement['loading']='lazy'
        else:
            return
        for retained in ('class','width','height'):
            if target.get(retained):replacement[retained]=target[retained]
        original_style=str(target.get('style') or '')
        if replacement.name=='img':
            replacement['style']=original_style+';display:inline-block;width:1.4em;height:1.4em;object-fit:contain;vertical-align:middle;'
        elif original_style:
            replacement['style']=original_style
        replacement['data-we-field']=field['key']
        target.replace_with(replacement)
    elif attr=='class':
        if SAFE_CLASS.fullmatch(value):target['class']=value.split()
    elif attr=='src':
        if SAFE_URL.match(value):target['src']=value


def render(source: str, fields: list, values: dict, global_values: dict, section_id: str | None = None):
    soup=sanitize(source)
    for field in fields:
        marker=field.get('marker') or 'data-we-field'
        target=soup.find(attrs={marker:field['key']})
        if not target:continue
        mode=field.get('mode','static')
        value=(values.get(field['key'],field['default']) if mode=='page' else
               global_values.get(field.get('global_key'),field['default']) if mode=='global' else field['default'])
        change_rendered_field(soup,target,field,str(value or ''))
    from .repeaters import apply_extras, apply_design
    apply_extras(soup,fields,values,change_rendered_field)
    apply_design(soup,fields,values)
    if section_id:
        for section in list(soup.find_all(attrs={'data-we-section':True})):
            if section.get('data-we-section')!=section_id:
                section.decompose()
    return str(soup)
