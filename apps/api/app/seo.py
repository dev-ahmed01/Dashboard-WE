from html import escape
from urllib.parse import urljoin
import json
from bs4 import BeautifulSoup


def safe_slug(slug: str) -> str:
    slug = slug.strip().strip('/')
    import re
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*',slug):
        raise ValueError('Use lowercase URL parts separated by hyphens')
    return slug


def metadata_html(html: str, title: str, slug: str, seo: dict, origin: str):
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.head:
        soup.html.insert(0, soup.new_tag('head'))
    for n in soup.head.find_all(['title','meta','link'],recursive=False):
        if n.name=='title' or (n.name=='meta' and n.get('name') in ('description','robots')) or (n.name=='link' and n.get('rel')==['canonical']):n.decompose()
    title_text = seo.get('seo_title') or title
    description = seo.get('description') or ''
    canonical = seo.get('canonical_override') or f'{origin.rstrip("/")}/{slug.strip("/")}/'
    if not canonical.startswith('https://'):
        raise ValueError('Canonical URL must be HTTPS')
    tag = soup.new_tag('title'); tag.string = title_text; soup.head.append(tag)
    desc = soup.new_tag('meta'); desc.attrs = {'name':'description','content':description}; soup.head.append(desc)
    directives = [
        'noindex' if seo.get('noindex', True) else 'index',
        'nofollow' if seo.get('nofollow', False) else 'follow',
    ]
    for setting in ('noarchive', 'noimageindex', 'nosnippet'):
        if seo.get(setting, False):
            directives.append(setting)
    robots = soup.new_tag('meta')
    robots.attrs = {'name': 'robots', 'content': ','.join(directives)}
    soup.head.append(robots)
    link = soup.new_tag('link');link.attrs={'rel':'canonical','href':canonical};soup.head.append(link)
    for key, content in [('og:title',seo.get('og_title') or title_text),('og:description',seo.get('og_description') or description),('og:url',canonical)]:
        meta = soup.new_tag('meta');meta.attrs={'property':key,'content':content};soup.head.append(meta)
    schema = {'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':[
        {'@type':'ListItem','position':1,'name':'Home','item':origin.rstrip('/')+'/'},
        {'@type':'ListItem','position':2,'name':title,'item':canonical},
    ]}
    script=soup.new_tag('script',type='application/ld+json');script.string=json.dumps(schema).replace('<','\\u003c');soup.head.append(script)
    return str(soup)
