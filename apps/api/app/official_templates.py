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


def make_template(item: OfficialPage, html: str):
    """Return sanitized HTML, named sections and automatically editable fields."""
    source, sections, fields = extract(html)
    sections = _rename_sections(item.category, sections)
    fields = _auto_fields(item.category, sections, fields)
    source, sections = overlay_metadata(source, sections, fields)
    return source, sections, fields


def read_only_section(category: str, name: str) -> bool:
    return category == 'Property' and any(token in name.lower() for token in (
        'testimonial', 'review'
    ))
