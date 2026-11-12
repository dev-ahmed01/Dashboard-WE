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
            # A Solution page has at most FOUR office-option cards total.
            # Keep this cap in metadata for both the editor and API validator.
            if 'options' in str(meta.get('name','')).lower() and kind in ('cards','solutions'):
                kind='options';title='Office options'
                max_additions=max(0,4-len(items))
            else:
                max_additions=MAX_ADDITIONS
            meta['repeaters'].append({'id':group_id,'section_id':sid,'kind':kind,'name':title,
                                      'items':items,'parent_item_id':parent_id,
                                      'count':len(items),'max_additions':max_additions})
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



VISUAL_FONTS={
    'Poppins', 'Bricolage Grotesque', 'Arial', 'Georgia', 'Verdana',
}
VISUAL_ALIGN={'left','center','right','justify'}
VISUAL_COLOR=re.compile(r'^#[0-9a-fA-F]{6}$')
VISUAL_OVERLAY_ID=re.compile(r'^ov_[a-zA-Z0-9_-]{4,35}$')

def _style_pair(prop,value):
    return f'{prop}:{value}!important'

def _append_visual_style(node, opts, *, field=False):
    styles=[]
    for prop,key,lo,hi,unit in (
        ('font-size','fontPx',8,120,'px'), ('width','widthPx',30,1800,'px'),
        ('height','heightPx',20,1000,'px'), ('padding','padding',0,80,'px'),
        ('border-radius','radius',0,120,'px'), ('letter-spacing','letterSpacing',-5,20,'px'),
        ('line-height','lineHeight',80,250,'%'),
    ):
        val=opts.get(key)
        if type(val) is int and lo<=val<=hi:
            styles.append(_style_pair(prop,str(val)+unit))
    if 'height' in opts and type(opts['height']) is int and 150<=opts['height']<=600:
        styles.append(_style_pair('height',str(opts['height'])+'px'))
    x=opts.get('x',0);y=opts.get('y',0)
    if type(x) is int and type(y) is int and (x or y) and -600<=x<=600 and -600<=y<=600:
        styles.append(_style_pair('translate',f'{x}px {y}px'))
    rotation=opts.get('rotate')
    if type(rotation) is int and -180<=rotation<=180:
        styles.append(_style_pair('rotate',f'{rotation}deg'))
    opacity=opts.get('opacity')
    if type(opacity) is int and 0<=opacity<=100:
        styles.append(_style_pair('opacity',str(opacity/100)))
    zindex=opts.get('zIndex')
    if type(zindex) is int and 0<=zindex<=50:
        styles.append(_style_pair('z-index',str(zindex)))
        styles.append(_style_pair('position','relative'))
    for prop,key in (('color','color'),('background-color','background')):
        val=opts.get(key)
        if isinstance(val,str) and VISUAL_COLOR.fullmatch(val):
            styles.append(_style_pair(prop,val))
    if opts.get('fontFamily') in VISUAL_FONTS:
        styles.append(_style_pair('font-family',f'"{opts["fontFamily"]}",sans-serif'))
    if opts.get('textAlign') in VISUAL_ALIGN:
        styles.append(_style_pair('text-align',opts['textAlign']))
    weight=opts.get('fontWeight')
    if type(weight) is int and weight in (400,500,600,700,800):
        styles.append(_style_pair('font-weight',str(weight)))
    order=opts.get('order')
    if not field and type(order) is int and 0<=order<=80:
        styles.append(_style_pair('order',str(order)))
    if opts.get('hidden') is True:
        styles.append(_style_pair('display','none'))
    if styles:
        node['style']=str(node.get('style',''))+';'+';'.join(styles)+';'


def _render_overlay(soup, entry):
    """Create an editable, script-free overlay anchored within a page section."""
    section=soup.find(attrs={'data-we-section':entry['sectionId']})
    if section is None:
        return
    if not section.get('style') or 'position:' not in section.get('style',''):
        section['style']=str(section.get('style',''))+';position:relative;'
    kind=entry['type']
    if kind=='image':
        node=soup.new_tag('img')
        node['src']=entry.get('url','')
        node['alt']=entry.get('text','')[:120] or 'Page image'
        node['loading']='lazy'
    elif kind=='button':
        node=soup.new_tag('a')
        node['href']=entry.get('url','#')
        node['rel']='noopener noreferrer'
        node.string=entry.get('text','Button')
    else:
        node=soup.new_tag('div')
        if kind=='text':
            node.string=entry.get('text','Text')
    node['data-we-design-element']=entry['id']
    node['data-we-design-type']=kind
    x,y=entry.get('x',32),entry.get('y',80)
    width,height=entry.get('width',240),entry.get('height',70)
    color=entry.get('color','#161616')
    background=entry.get('background','#FFFFFF')
    size=entry.get('fontSize',24)
    z=entry.get('zIndex',10)
    radius=entry.get('radius',12)
    opacity=entry.get('opacity',100)
    rotation=entry.get('rotate',0)
    weight=entry.get('fontWeight',600)
    font=entry.get('fontFamily','Poppins')
    align=entry.get('textAlign','left')
    # Values were all validated before they enter page.values.
    properties=[
      f'position:absolute!important',f'left:{x}px!important',f'top:{y}px!important',
      f'width:{width}px!important',f'height:{height}px!important',
      'box-sizing:border-box!important','max-width:95%!important',
      f'z-index:{z}!important',f'opacity:{opacity/100}!important',
      f'rotate:{rotation}deg!important',f'border-radius:{radius}px!important',
      f'background-color:{background}!important',f'color:{color}!important',
      f'font-size:{size}px!important',f'font-weight:{weight}!important',
      f'font-family:"{font}",sans-serif!important',f'text-align:{align}!important',
      'overflow:hidden!important',
    ]
    if kind=='image':
        properties+=['object-fit:cover!important','display:block!important']
    else:
        properties+=['display:flex!important','align-items:center!important',
                     'justify-content:center!important','padding:8px!important',
                     'text-decoration:none!important']
        if kind=='text':properties+=['white-space:pre-wrap!important']
    if entry.get('hidden'):
        properties.append('display:none!important')
    node['style']=';'.join(properties)+';'
    section.append(node)


def apply_design(soup,fields,values):
    """Apply validated per-page visual styles and editable overlays."""
    design=read_design(values)
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
        if isinstance(span,int) and 1<=span<=4:
            node['style']=str(node.get('style',''))+f';grid-column:span {span}!important;'
            stylesheet.append(f'@media(max-width:900px){{[data-we-repeat-item="{item_id}"]{{grid-column:auto!important;}}}}')
        _append_visual_style(node,options)
        if options.get('x') or options.get('y'):
            stylesheet.append(f'@media(max-width:580px){{[data-we-repeat-item="{item_id}"]{{translate:none!important;}}}}')
    for key,options in field_styles.items():
        if not isinstance(options,dict):continue
        node=soup.find(attrs={'data-we-field':key})
        if not node:continue
        _append_visual_style(node,options,field=True)
        if options.get('x') or options.get('y'):
            stylesheet.append(f'@media(max-width:580px){{[data-we-field="{key}"]{{translate:none!important;}}}}')
    page_opts=design.get('page') or {}
    if page_opts.get('background') and soup.body:
        soup.body['style']=str(soup.body.get('style',''))+f';background-color:{page_opts["background"]}!important;'
    for entry in design.get('elements',[]):
        if isinstance(entry,dict):
            _render_overlay(soup,entry)
    # Highlights expand automatically when the admin adds a fifth or sixth
    # card. No manual "Cards per row" selector is necessary.
    for wrapper in soup.select('.cards[data-we-repeat-group]'):
        original_and_new=[
          el for el in wrapper.find_all(recursive=False)
          if isinstance(el,Tag) and el.get('data-we-repeat-item')
        ]
        count=len(original_and_new)
        if count>4:
            columns=min(count,6)
            gid=wrapper.get('data-we-repeat-group')
            selector=f'[data-we-repeat-group="{gid}"]'
            stylesheet.append(f'{selector}{{display:grid!important;grid-template-columns:repeat({columns},minmax(0,1fr))!important;}}')
            stylesheet.append(f'@media(max-width:900px){{{selector}{{grid-template-columns:repeat(2,minmax(0,1fr))!important;}}}}')
            stylesheet.append(f'@media(max-width:580px){{{selector}{{grid-template-columns:1fr!important;}}}}')
    if soup.find(attrs={'data-we-variant':True}):
        stylesheet.append('@media(max-width:900px){[data-we-variant]{grid-column:auto!important;}}')
    if stylesheet:
        style=soup.new_tag('style')
        style['id']='we-editor-safe-layout'
        style.string='\n'.join(stylesheet)
        (soup.head or soup.body).append(style)


def _validate_visual_options(opts,category):
    if not isinstance(opts,dict):
        raise ValueError('Invalid visual style options')
    allowed=({'columns':(1,6),'gap':(0,48)} if category=='groups' else {
        'span':(1,4),'height':(150,600),'locked':None,'order':(0,80),
        'widthPx':(30,1800),'heightPx':(20,1000),'x':(-600,600),'y':(-600,600),
        'rotate':(-180,180),'opacity':(0,100),'zIndex':(0,50),
        'radius':(0,120),'padding':(0,80),'fontPx':(8,120),
        'fontWeight':(400,800),'letterSpacing':(-5,20),'lineHeight':(80,250),
        'color':'color','background':'color','fontFamily':'font','textAlign':'align',
        'hidden':None,
    })
    if category=='fields':
        allowed.pop('span',None);allowed.pop('height',None);allowed.pop('order',None)
    if set(opts)-set(allowed):
        raise ValueError('Unexpected visual style option')
    for key,value in opts.items():
        rule=allowed[key]
        if rule is None:
            if type(value) is not bool:raise ValueError('Lock/visibility must be true or false')
        elif rule=='color':
            if not isinstance(value,str) or not VISUAL_COLOR.fullmatch(value):
                raise ValueError('Visual colors must use hex values')
        elif rule=='font':
            if value not in VISUAL_FONTS:raise ValueError('Unsupported font family')
        elif rule=='align':
            if value not in VISUAL_ALIGN:raise ValueError('Unsupported text alignment')
        elif key=='fontWeight':
            if type(value) is not int or value not in (400,500,600,700,800):
                raise ValueError('Unsupported font weight')
        elif type(value) is not int or not rule[0]<=value<=rule[1]:
            raise ValueError('Visual size is outside the allowed range')


def _validate_overlay(entry,section_ids):
    if not isinstance(entry,dict):
        raise ValueError('Invalid custom design element')
    strings={'id','type','sectionId','text','url','fontFamily','color','background','textAlign'}
    nums={'x':(0,2400),'y':(0,12000),'width':(30,1800),'height':(20,1000),
          'fontSize':(8,120),'fontWeight':(400,800),'opacity':(0,100),
          'rotate':(-180,180),'zIndex':(0,50),'radius':(0,120)}
    if set(entry)-strings-set(nums)-{'locked','hidden'}:
        raise ValueError('Unexpected custom element setting')
    if not VISUAL_OVERLAY_ID.fullmatch(str(entry.get('id',''))):
        raise ValueError('Invalid custom element identifier')
    if entry.get('type') not in ('text','image','shape','button'):
        raise ValueError('Unsupported custom element')
    if entry.get('sectionId') not in section_ids:
        raise ValueError('Choose an existing page section')
    if not isinstance(entry.get('text',''),str) or len(entry.get('text',''))>1000:
        raise ValueError('Custom text is too long')
    kind=entry['type']
    url=entry.get('url','')
    if not isinstance(url,str) or len(url)>3000:
        raise ValueError('Invalid custom URL')
    if kind=='image':
        from .template_engine import SAFE_URL
        if not url or not SAFE_URL.match(url):raise ValueError('Choose a safe image URL')
    elif kind=='button':
        from .template_engine import is_safe_link
        if url and not is_safe_link(url):raise ValueError('Unsafe custom button link')
    elif url:
        raise ValueError('This element does not need a URL')
    for key in ('color','background'):
        if key in entry and (not isinstance(entry[key],str) or not VISUAL_COLOR.fullmatch(entry[key])):
            raise ValueError('Custom element color must be #RRGGBB')
    if entry.get('fontFamily','Poppins') not in VISUAL_FONTS or entry.get('textAlign','left') not in VISUAL_ALIGN:
        raise ValueError('Choose a supported font and alignment')
    for key,rule in nums.items():
        if key not in entry:continue
        val=entry[key]
        if type(val) is not int or not rule[0]<=val<=rule[1]:
            raise ValueError('Invalid custom element dimensions')
        if key=='fontWeight' and val not in (400,500,600,700,800):
            raise ValueError('Unsupported font weight')
    for key in ('locked','hidden'):
        if key in entry and type(entry[key]) is not bool:
            raise ValueError('Invalid lock/visibility control')


def validate_design(raw,sections,fields):
    if not isinstance(raw,str) or len(raw)>48000:
        raise ValueError('Layout settings must be under 48 KB')
    try:data=json.loads(raw)
    except (TypeError,ValueError):
        raise ValueError('Invalid visual layout settings')
    if not isinstance(data,dict) or set(data)-{'groups','items','fields','page','elements'}:
        raise ValueError('Unexpected visual layout controls')
    groups={g['id']:g for sec in sections for g in sec.get('repeaters',[])}
    permitted_fields={f['key'] for f in fields if f.get('mode')=='page'}
    for gid,g in groups.items():
        for i in range(1,MAX_ADDITIONS+1):
            for item in g['items'][-1:]:
                for key in item['field_keys']:
                    if key in permitted_fields:
                        permitted_fields.add(f'{gid}_added_{i}_{key}')
    item_ids={item['id'] for group in groups.values() for item in group['items']}
    item_ids.update(f'{gid}_added_{i}' for gid in groups for i in range(1,MAX_ADDITIONS+1))
    for category,allowed in (('groups',set(groups)),('items',item_ids),('fields',permitted_fields)):
        entries=data.get(category,{})
        if not isinstance(entries,dict) or len(entries)>240 or set(entries)-allowed:
            raise ValueError('Visual layout references a locked or unknown element')
        for opts in entries.values():
            _validate_visual_options(opts,category)
    page=data.get('page',{})
    if not isinstance(page,dict) or set(page)-{'background'}:
        raise ValueError('Unsupported page design option')
    if 'background' in page and (
        not isinstance(page['background'],str) or not VISUAL_COLOR.fullmatch(page['background'])
    ):raise ValueError('Invalid page background')
    elements=data.get('elements',[])
    if not isinstance(elements,list) or len(elements)>50:
        raise ValueError('A page can have up to 50 added design elements')
    ids=set()
    section_ids={sec['id'] for sec in sections}
    for elem in elements:
        _validate_overlay(elem,section_ids)
        if elem['id'] in ids:raise ValueError('Custom design element IDs must be unique')
        ids.add(elem['id'])
