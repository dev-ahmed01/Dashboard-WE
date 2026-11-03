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
TEXT_TAGS = HEADINGS | {'p', 'li', 'button', 'a', 'label', 'span'}
SKIP_CONTAINERS = {'script', 'style', 'noscript', 'nav', 'head'}
SAFE_URL = re.compile(r'^(?:https?://|/(?!/)|#|data:image/(?:png|jpeg|webp|gif);base64,)', re.I)
SAFE_LINK = re.compile(r'^(?:https?://|/(?!/)|#|mailto:|tel:)', re.I)
SAFE_CLASS = re.compile(r'^[a-zA-Z0-9 _-]{1,240}$')
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
    reserved_fields = {str(tag.get(attr)) for tag in soup.find_all(True)
                       for attr in ('data-we-field', 'data-we-link-field')
                       if tag.get(attr)}

    for i, node in enumerate(nodes[:60]):
        annotated = str(node.get('data-we-section') or '').strip()
        sec_key = annotated if re.fullmatch(r'[a-z][a-z0-9_-]{1,70}', annotated) and annotated not in used_sections else f'section_{i+1}'
        while sec_key in used_sections:
            sec_key += '_copy'
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
    return str(soup), sections, fields


def render(source: str, fields: list, values: dict, global_values: dict, section_id: str | None = None):
    soup = sanitize(source)
    for field in fields:
        marker = field.get('marker') or 'data-we-field'
        target = soup.find(attrs={marker: field['key']})
        if not target:
            continue
        mode = field.get('mode', 'static')
        value = (values.get(field['key'], field['default']) if mode == 'page' else
                 global_values.get(field.get('global_key'), field['default']) if mode == 'global' else field['default'])
        value = str(value or '')
        attr = field['attr']
        if attr == 'text':
            requested_heading = field.get('heading_tag')
            if requested_heading in HEADINGS and target.name in HEADINGS:
                target.name = requested_heading
            # Preserve original nested spans, coloured words and inline SVGs if unchanged.
            if value != str(field.get('default', '')):
                texts = [x for x in target.descendants if isinstance(x, NavigableString)
                         and x.strip() and x.parent.name not in ('svg', 'style', 'script')]
                if texts:
                    texts[0].replace_with(value)
                    for extra in texts[1:]:
                        extra.replace_with('')
                else:
                    target.append(value)
        elif attr in ('href', 'data-we-link'):
            if value and not is_safe_link(value):
                continue
            if attr == 'data-we-link':
                if value:
                    if target.name == 'button':
                        target.name = 'a'
                        target.attrs.pop('type', None)
                        target.attrs.pop('disabled', None)
                    target['href'] = value
                    target['rel'] = 'noopener noreferrer'
                elif target.name == 'a':
                    target.attrs.pop('href', None)
            elif value:
                target['href'] = value
            else:
                target.attrs.pop('href', None)
        elif attr == 'icon_src':
            if value and SAFE_URL.match(value):
                replacement = soup.new_tag('img', src=value)
                replacement['alt'] = target.get('aria-label') or 'Icon'
                for retained in ('class', 'style', 'width', 'height'):
                    if target.get(retained):
                        replacement[retained] = target[retained]
                target.replace_with(replacement)
        elif attr == 'class':
            if SAFE_CLASS.fullmatch(value):
                target['class'] = value.split()
        elif attr == 'src':
            if SAFE_URL.match(value):
                target[attr] = value
    if section_id:
        for section in list(soup.find_all(attrs={'data-we-section': True})):
            if section.get('data-we-section') != section_id:
                section.decompose()
    return str(soup)
