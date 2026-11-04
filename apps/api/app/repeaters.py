"""Repeatable section metadata and safe DOM cloning.

The HTML itself is the schema. Repeaters use recognizable sibling groups from
the approved template, so adding an item inherits its real CSS and structure.
New items live in Page.values as restricted JSON (no template mutation).
"""
from copy import deepcopy
import json
import re
from bs4 import Tag

GROUPS = (
    ('highlights', 'Highlights cards', '.cards', 'article'),
    ('solutions', 'Solutions cards', '.office-grid', 'a'),
    ('other_solutions', 'Other solutions', '.other-pill-grid', 'a'),
    ('benefits', 'Benefit cards', '.benefit-list', 'article'),
    ('faqs', 'FAQs', '.faq-list', 'details'),
    ('benefit_bullets', 'Benefit bullet points', '.benefit-row ul', 'li'),
)
MAX_ADDITIONS = 12
PREFIX = '__repeat__'
VARIANT_PREFIX = '__variant__'
VARIANTS = {'regular', 'highlight', 'generic'}


def _fields_inside(node: Tag, fields: dict) -> list[str]:
    found = []
    for tag in [node, *node.find_all(True)]:
        for attr in ('data-we-field', 'data-we-link-field'):
            key = tag.get(attr)
            if key and key in fields and key not in found:
                found.append(key)
    return found


def _name(item: Tag) -> str:
    for selector in ('h2', 'h3', '.card-title', '.office-glass strong',
                     'strong', 'summary', 'span', 'p', 'li'):
        found = item.select_one(selector)
        if found:
            value = found.get_text(' ', strip=True)
            if value:
                return re.sub(r'[↗→➜➔]+$', '', value).strip()[:72]
    return re.sub(r'[↗→➜➔]+$', '', item.get_text(' ', strip=True)).strip()[:72]


def _variant(item: Tag) -> str:
    tokens = item.get('class', [])
    if any('special' in v or 'highlight' in v for v in tokens):
        return 'highlight'
    if any('generic' in v for v in tokens):
        return 'generic'
    return 'regular'


def discover(soup, sections: list[dict], fields: list[dict]):
    """Annotate existing HTML and return repeaters attached to matching sections.

    Deterministic group and item IDs for already-stored HTML, no migration.
    Original template records and the number of existing items are untouched.
    """
    by_section = {s['id']: dict(s, repeaters=[]) for s in sections}
    all_fields = {f['key']: f for f in fields}
    for sec in soup.find_all(attrs={'data-we-section': True}):
        sid = sec.get('data-we-section')
        meta = by_section.get(sid)
        if not meta:
            continue
        parents = []
        for kind, title, wrapper_css, item_tag in GROUPS:
            for wrapper in sec.select(wrapper_css):
                children = [x for x in wrapper.find_all(recursive=False)
                            if x.name == item_tag]
                if len(children) >= 2:
                    parents.append((wrapper, children, kind, title))
        # Generic repeated content: three or more similar cards / list items
        # beneath a semantic list/grid, without producing wrappers for nav or forms.
        for wrapper in sec.find_all(['div', 'ul', 'ol']):
            if any(wrapper is x[0] for x in parents):
                continue
            if wrapper.find_parent(['nav', 'form', 'footer']):
                continue
            children = [x for x in wrapper.find_all(recursive=False) if isinstance(x, Tag)]
            if len(children) < 3 or len(children) > 25:
                continue
            if len({x.name for x in children}) != 1:
                continue
            if children[0].name not in ('article', 'li', 'details', 'a', 'div'):
                continue
            styles = [{v for v in x.get('class', []) if not re.search(r'\d+$', v)}
                      for x in children]
            shared = set.intersection(*styles) if styles else set()
            marker = ' '.join(wrapper.get('class', [])).lower()
            if not shared and not re.search(r'cards|grid|list|items|tiles|pills|repeat', marker):
                continue
            if not all(_fields_inside(item, all_fields) for item in children):
                continue
            kind = ('benefit_bullets' if children[0].name == 'li' else
                    'faqs' if children[0].name == 'details' else
                    'solutions' if 'solution' in marker or 'office' in marker else
                    'cards')
            title = {'benefit_bullets':'Bullet points','faqs':'FAQs',
                     'solutions':'Solution cards','cards':'Repeatable cards'}[kind]
            parents.append((wrapper, children, kind, title))
        for index, (wrapper, children, kind, title) in enumerate(parents[:18], 1):
            if not all(_fields_inside(item, all_fields) for item in children):
                continue
            existing = str(wrapper.get('data-we-repeat-group') or '')
            group_id = existing if re.fullmatch(r'[a-z][a-z0-9_-]{1,100}', existing) else f'{sid}_repeat_{index}'
            wrapper['data-we-repeat-group'] = group_id
            items = []
            for i, child in enumerate(children):
                original = str(child.get('data-we-repeat-item') or '')
                item_id = original if re.fullmatch(r'[a-z][a-z0-9_-]{1,110}', original) else f'{group_id}_item_{i+1}'
                child['data-we-repeat-item'] = item_id
                items.append({'id':item_id,'title':_name(child),'field_keys':_fields_inside(child, all_fields),
                              'variant':_variant(child)})
            parent_item = wrapper.find_parent(attrs={'data-we-repeat-item': True})
            parent_id = parent_item.get('data-we-repeat-item') if parent_item else None
            meta['repeaters'].append({'id':group_id,'section_id':sid,'kind':kind,'name':title,
                                      'items':items,'parent_item_id':parent_id,
                                      'count':len(items),'max_additions':MAX_ADDITIONS})
    return [by_section[s['id']] for s in sections]


def overlay_metadata(source: str, sections: list[dict], fields: list[dict]):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(source, 'html.parser')
    annotated = discover(soup, sections, fields)
    return str(soup), annotated


def get_extras(values: dict, group_id: str):
    raw = values.get(PREFIX + group_id, '[]')
    try:
        extras = json.loads(raw)
        return extras if isinstance(extras, list) else []
    except (TypeError, ValueError):
        return []


def set_variant(node: Tag, variant: str):
    if variant not in VARIANTS:
        variant='regular'
    classes = [c for c in node.get('class', []) if c not in
               ('we-variant-highlight','we-variant-generic','we-variant-regular')]
    # Existing design's "office-special" is its highlighted variant.
    if variant == 'highlight' and 'office-tile' in classes and 'office-special' not in classes:
        classes.append('office-special')
    if variant != 'highlight' and 'office-special' in classes:
        classes.remove('office-special')
    classes.append('we-variant-'+variant)
    node['class'] = classes
    node['data-we-variant'] = variant


def apply_extras(soup, fields: list[dict], values: dict, change_field):
    """Append cloned groups after original fields have already been rendered."""
    if not any(k.startswith(PREFIX) or k.startswith(VARIANT_PREFIX) for k in values):
        return
    all_fields={f['key']:f for f in fields}
    sections=[{'id':s.get('data-we-section'),'name':'','order':i+1}
              for i,s in enumerate(soup.find_all(attrs={'data-we-section': True}))]
    groups=[g for section in discover(soup,sections,fields) for g in section['repeaters']]
    for group in groups:
        for item in group['items']:
            key=VARIANT_PREFIX+group['id']+'__'+item['id']
            if key in values and group['kind']=='solutions':
                node=soup.find(attrs={'data-we-repeat-item':item['id']})
                if node:set_variant(node,values[key])
    for group in groups:
        additions=get_extras(values,group['id'])
        if not additions or not group['items']:
            continue
        wrapper=soup.find(attrs={'data-we-repeat-group':group['id']})
        template=soup.find(attrs={'data-we-repeat-item':group['items'][-1]['id']})
        if not wrapper or not template:
            continue
        # Use a deep copy of the last original item, never clone a previous addition.
        sample=deepcopy(template)
        allowed=set(group['items'][-1]['field_keys'])
        for index, entry in enumerate(additions[:MAX_ADDITIONS],1):
            if not isinstance(entry,dict):
                continue
            clone=deepcopy(sample)
            clone['data-we-repeat-item']=group['id']+'_added_'+str(index)
            clone['data-we-repeat-created']='true'
            # HTML IDs in cloned nodes must not duplicate the original's IDs.
            for tag in [clone,*clone.find_all(True)]:
                if tag.has_attr('id'):
                    tag['id']=str(tag['id'])+'-repeat-'+str(index)
            for key,value in entry.items():
                if key not in allowed or not isinstance(value,str):
                    continue
                field=all_fields.get(key)
                if not field or field.get('mode')!='page':
                    continue
                marker=field.get('marker') or 'data-we-field'
                target=clone.find(attrs={marker:key})
                if target:
                    change_field(soup,target,field,value)
            if group['kind']=='solutions':
                set_variant(clone,entry.get('__variant','regular'))
            # Give focused copies unique IDs and never rewrite original fields.
            for tag in [clone,*clone.find_all(True)]:
                for marker in ('data-we-field','data-we-link-field'):
                    if tag.get(marker):
                        tag[marker]=group['id']+'_added_'+str(index)+'_'+tag[marker]
            wrapper.append(clone)
