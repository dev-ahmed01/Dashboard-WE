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
    if 'office-tile' in classes:
        # Override positional template classes such as tile-3 (span 2).
        # Explicit styles are constrained to presets and leave mobile layout
        # responsive via a separate media rule in apply_design.
        span=2 if variant=='highlight' else 1
        height=345 if variant=='highlight' else 265 if variant=='generic' else 300
        node['style']=node.get('style','')+f';grid-column:span {span}!important;height:{height}px!important;'
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


DESIGN_KEY='__design__'


def read_design(values):
    try:
        item=json.loads(values.get(DESIGN_KEY,'{}'))
        return item if isinstance(item,dict) else {}
    except (ValueError,TypeError):
        return {}


def apply_design(soup,fields,values):
    """Apply a narrow, sanitized layout schema without inserting user CSS."""
    design=read_design(values)
    if not design:return
    from bs4 import BeautifulSoup
    groups=design.get('groups') or {}
    items=design.get('items') or {}
    field_styles=design.get('fields') or {}
    stylesheet=[]
    for group_id,settings in groups.items():
        if not isinstance(settings,dict):continue
        wrapper=soup.find(attrs={'data-we-repeat-group':group_id})
        if not wrapper:continue
        cols=settings.get('columns')
        gap=settings.get('gap')
        if isinstance(cols,int) and 1<=cols<=6 and wrapper.name in ('div','ul','ol'):
            selector=f'[data-we-repeat-group="{group_id}"]'
            stylesheet.append(f'{selector}{{display:grid!important;grid-template-columns:repeat({cols},minmax(0,1fr))!important;}}')
            stylesheet.append(f'@media(max-width:900px){{{selector}{{grid-template-columns:repeat({min(cols,2)},minmax(0,1fr))!important;}}}}')
            stylesheet.append(f'@media(max-width:580px){{{selector}{{grid-template-columns:1fr!important;}}}}')
        if isinstance(gap,int) and 0<=gap<=48:
            wrapper['style']=(wrapper.get('style','')+f';gap:{gap}px!important;')
    for item_id,options in items.items():
        if not isinstance(options,dict):continue
        node=soup.find(attrs={'data-we-repeat-item':item_id})
        if not node:continue
        span=options.get('span')
        height=options.get('height')
        styles=[]
        if isinstance(span,int) and 1<=span<=4:
            styles.append(f'grid-column:span {span}!important')
            stylesheet.append(f'@media(max-width:900px){{[data-we-repeat-item="{item_id}"]{{grid-column:auto!important;}}}}')
        if isinstance(height,int) and 150<=height<=600:
            styles.append(f'height:{height}px!important')
        if styles:node['style']=(node.get('style','')+';'+';'.join(styles)+';')
    for key,options in field_styles.items():
        if not isinstance(options,dict):continue
        node=soup.find(attrs={'data-we-field':key})
        if not node:continue
        size=options.get('fontPx')
        if isinstance(size,int) and 10<=size<=100:
            node['style']=(node.get('style','')+f';font-size:{size}px!important;')
    # Layout variants remain one column on narrow viewports regardless of
    # legacy tile-number class rules in the uploaded design.
    if soup.find(attrs={'data-we-variant':True}):
        stylesheet.append('@media(max-width:900px){[data-we-variant]{grid-column:auto!important;}}')
    if stylesheet:
        style=soup.new_tag('style')
        style['id']='we-editor-safe-layout'
        style.string='\n'.join(stylesheet)
        (soup.head or soup.body).append(style)


def validate_design(raw,sections,fields):
    if not isinstance(raw,str) or len(raw)>16000:
        raise ValueError('Layout settings must be under 16 KB')
    try: data=json.loads(raw)
    except (TypeError,ValueError):
        raise ValueError('Invalid visual layout settings')
    if not isinstance(data,dict) or set(data)-{'groups','items','fields'}:
        raise ValueError('Unexpected visual layout controls')
    groups={g['id']:g for s in sections for g in s.get('repeaters',[])}
    permitted_fields={f['key'] for f in fields if f.get('mode')=='page'}
    item_ids={item['id'] for group in groups.values() for item in group['items']}
    item_ids.update(f"{gid}_added_{i}" for gid in groups for i in range(1,MAX_ADDITIONS+1))
    for category,allowed in (('groups',set(groups)),('items',item_ids),('fields',permitted_fields)):
        entries=data.get(category,{})
        if not isinstance(entries,dict) or len(entries)>240 or set(entries)-allowed:
            raise ValueError('Visual layout references a locked or unknown element')
        for opts in entries.values():
            if not isinstance(opts,dict):raise ValueError('Invalid visual layout options')
            allowed_opts=({'columns':(1,6),'gap':(0,48)} if category=='groups'
                          else {'span':(1,4),'height':(150,600),'locked':None} if category=='items'
                          else {'fontPx':(10,100),'locked':None})
            if set(opts)-set(allowed_opts):raise ValueError('Invalid visual style option')
            for key,value in opts.items():
                limits=allowed_opts[key]
                if limits is None:
                    if not isinstance(value,bool):raise ValueError('Lock state must be true or false')
                elif type(value) is not int or not limits[0]<=value<=limits[1]:
                    raise ValueError('Visual size is outside the allowed range')
