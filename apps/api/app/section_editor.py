"""Immutable section composition for CMS templates."""
from copy import deepcopy
import re
from uuid import uuid4
from bs4 import BeautifulSoup
from .template_engine import sanitize

def edit_sections(html, sections, fields, operation, section_id, source=None):
    soup = BeautifulSoup(html, 'html.parser')
    sections = deepcopy(sections)
    fields = deepcopy(fields)
    if operation == 'delete':
        if len(sections) <= 1:
            raise ValueError('Keep at least one section in the template')
        node = soup.find(attrs={'data-we-section': section_id})
        if not node or not any(s['id'] == section_id for s in sections):
            raise ValueError('Section not found')
        node.decompose()
        for style in soup.find_all('style', attrs={'data-we-imported-section': section_id}):
            style.decompose()
        sections = [s for s in sections if s['id'] != section_id]
        fields = [f for f in fields if f['section_id'] != section_id]
    elif operation == 'import':
        if len(sections) >= 60:
            raise ValueError('A template supports up to 60 sections')
        source_html, source_sections, source_fields = source
        donor = BeautifulSoup(source_html, 'html.parser')
        meta = next((s for s in source_sections if s['id'] == section_id), None)
        node = donor.find(attrs={'data-we-section': section_id})
        if not meta or not node:
            raise ValueError('Source section not found')
        new_id = 'import_' + uuid4().hex[:16]
        clone = deepcopy(node)
        tags = [clone, *clone.find_all(True)]
        key_map = {}
        for attr, prefix in [('data-we-field','field'), ('data-we-link-field','link'),
                             ('data-we-repeat-group','group'), ('data-we-repeat-item','item')]:
            for tag in tags:
                if tag.get(attr):
                    old = str(tag[attr])
                    key_map.setdefault(old, new_id + '_' + prefix + '_' + str(len(key_map)+1))
                    tag[attr] = key_map[old]
        clone['data-we-section'] = new_id
        # Avoid duplicate DOM IDs and preserve local anchor/ARIA references.
        id_map = {str(tag['id']): new_id+'_'+str(tag['id']) for tag in tags if tag.get('id')}
        for tag in tags:
            if tag.get('id'):
                tag['id'] = id_map[str(tag['id'])]
            for attr in ('href','xlink:href','data-we-link','data-href','data-url'):
                v = str(tag.get(attr,''))
                if v.startswith('#') and v[1:] in id_map:
                    tag[attr] = '#'+id_map[v[1:]]
            for attr in ('for','aria-controls','aria-labelledby','aria-describedby','headers'):
                if tag.get(attr):
                    tag[attr] = ' '.join(id_map.get(v,v) for v in str(tag[attr]).split())
        imported = deepcopy(meta)
        imported['id'] = new_id
        for group in imported.get('repeaters', []):
            group['id'] = key_map[group['id']]
            group['section_id'] = new_id
            if group.get('parent_item_id'):
                group['parent_item_id'] = key_map[group['parent_item_id']]
            for item in group['items']:
                item['id'] = key_map[item['id']]
                item['field_keys'] = [key_map[k] for k in item['field_keys']]
        for f in source_fields:
            if f['section_id'] != section_id:
                continue
            copy = deepcopy(f)
            copy['key'] = key_map[f['key']]
            copy['section_id'] = new_id
            if copy.get('kind') == 'link':
                v = str(copy.get('default',''))
                if v.startswith('#') and v[1:] in id_map:
                    copy['default'] = '#'+id_map[v[1:]]
            fields.append(copy)
        # Keep donor CSS within the imported section rather than changing the
        # destination's global styles. Official designs carry embedded CSS.
        for original in donor.find_all('style'):
            owner = original.get('data-we-imported-section')
            if owner and owner != section_id:
                continue
            rules = original.get_text()
            if not rules.strip():
                continue
            rules = rules.replace('[data-we-section="'+section_id+'"]','[data-we-section="'+new_id+'"]')
            for old, new in id_map.items():
                rules = re.sub(r'#'+re.escape(old)+r'(?![\w-])', '#'+new, rules)
            style = soup.new_tag('style')
            style['data-we-imported-section'] = new_id
            style.string = '@scope ([data-we-section="'+new_id+'"]) {\n'+rules+'\n}'
            (soup.head or soup.html).append(style)
        anchor = soup.find(attrs={'data-we-section': sections[-1]['id']}) if sections else None
        if anchor:
            anchor.insert_after(clone)
        else:
            (soup.body.find('main') or soup.body).append(clone)
        sections.append(imported)
    else:
        raise ValueError('Unknown section operation')
    for i, sec in enumerate(sections, 1):
        sec['order'] = i
    return str(sanitize(str(soup))), sections, fields
