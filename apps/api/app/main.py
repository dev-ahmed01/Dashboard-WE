"""Workspace by Emlen API. Publishing is local only; the public WordPress site is not changed."""
from contextlib import asynccontextmanager
from functools import lru_cache
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePath, Path
from urllib.parse import urlsplit
from uuid import uuid4
from xml.sax.saxutils import escape as xml_escape
import json
import re

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Depends, File, Form, UploadFile, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update, or_, text
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db, SessionLocal
from .models import User, Template, Page, Publication, SharedContent, Redirect, Media, AuditLog, utcnow
from .security import admin, current_user, issue_token, verify_password, seed_admin
from .storage import ObjectStore
from .template_engine import extract, render, SAFE_URL, SAFE_CLASS, is_safe_link, is_safe_icon_value, HEADINGS
from .repeaters import overlay_metadata, PREFIX as REPEAT_PREFIX, VARIANT_PREFIX, MAX_ADDITIONS, VARIANTS, DESIGN_KEY, validate_design
from .seo import metadata_html, safe_slug
from .official_templates import OFFICIAL_PAGES, official_key, fetch_official, make_template, read_only_section


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.app_environment == 'production' and (
        len(s.jwt_secret) < 32
        or not s.database_url.startswith('postgresql+psycopg://')
        or any('CHANGE_ME' in value for value in (
            s.jwt_secret, s.database_url, s.admin_password, s.s3_secret_key,
        ))
    ):
        raise RuntimeError('Production requires configured secrets and PostgreSQL')
    with SessionLocal() as db:
        seed_admin(db)
    ObjectStore().ensure_bucket()
    yield

app = FastAPI(title='Workspace by Emlen Page Manager API', version='10.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[get_settings().cors_origin], allow_methods=['GET','POST','PUT','PATCH','DELETE'], allow_headers=['Authorization','Content-Type'])


def audit(db, user, action, subject, details=None):
    db.add(AuditLog(actor_id=user.id,action=action,subject=subject,details=details or {}))


def fail(code, message):
    raise HTTPException(code, message)


def template_json(t: Template):
    return {'id':t.id,'name':t.name,'category':t.category,'approved':t.approved,'version':t.version,'sections':t.sections,'fields':t.fields,'created_at':t.created_at.isoformat()}


def page_json(p: Page):
    return {'id':p.id,'template_id':p.template_id,'template_name':(p.template_snapshot or {}).get('name',''),'template_category':(p.template_snapshot or {}).get('category','Solution Category'),'title':p.title,'slug':p.slug,'values':p.values,'seo':p.seo,'status':p.status,'published_version':p.published_version,'updated_at':p.updated_at.isoformat(),
            'edit_version':p.edit_version,'archived':p.archived,
            'has_unpublished_changes':bool(p.published_version and p.edit_version>p.published_edit_version)}


def globals_dict(db):
    return {x.key:x.value for x in db.scalars(select(SharedContent)).all()}


def get_page(db, id):
    p=db.get(Page,id)
    if not p:fail(404,'Page not found')
    return p


def get_template(db,id):
    t=db.get(Template,id)
    if not t:fail(404,'Template not found')
    return t


def latest_publication(db,page_id):
    return db.scalar(select(Publication).where(Publication.page_id==page_id).order_by(Publication.version.desc()).limit(1))


class Login(BaseModel):
    identifier: str | None = None
    email: str | None = None  # Backward-compatible with existing API clients
    password: str


@app.get('/api/health')
def health():
    """Liveness only: the process can respond, but backing stores may be unavailable."""
    return {'ok':True,'service':'Workspace by Emlen API'}


@lru_cache(maxsize=1)
def _migration_heads() -> set[str]:
    config = AlembicConfig(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    return set(ScriptDirectory.from_config(config).get_heads())


@app.get('/api/health/ready')
def readiness():
    """Fail closed if PostgreSQL schema or object storage is not ready for editors."""
    try:
        with SessionLocal() as db:
            db.execute(text('SELECT 1'))
            revisions = set(db.execute(text('SELECT version_num FROM alembic_version')).scalars())
            if not revisions or revisions != _migration_heads():
                raise ValueError('Schema revision mismatch')
        store = ObjectStore()
        store.client.head_bucket(Bucket=store.bucket)
    except Exception:
        # Never expose database/storage endpoints, credentials or exception details.
        raise HTTPException(status_code=503, detail='Service unavailable') from None
    return {'status':'ready'}


@app.post('/api/auth/login')
def login(payload:Login,db:Session=Depends(get_db)):
    identifier=(payload.identifier or payload.email or '').strip().lower()
    if not identifier: fail(422,'Enter your username or email')
    settings=get_settings()
    # Keep all existing accounts email-based. Only the configured administrator
    # can additionally sign in with an explicit, opt-in username alias.
    alias=settings.admin_username.strip().lower()
    using_admin_alias=bool(alias and identifier==alias)
    email=settings.admin_email.strip().lower() if using_admin_alias else identifier
    u=db.scalar(select(User).where(User.email==email,User.active==True))
    if not u or (using_admin_alias and u.role!='admin') or not verify_password(payload.password,u.password_hash):
        fail(401,'Invalid credentials')
    return {'access_token':issue_token(u),'user':{'email':u.email,'role':u.role}}


@app.get('/api/auth/me')
def me(user:User=Depends(current_user)):
    return {'email':user.email,'role':user.role}



class NewTeamUser(BaseModel):
    email: str = Field(min_length=5,max_length=255)
    password: str = Field(min_length=12,max_length=256)
    role: str = Field(pattern='^(admin|editor)$')


@app.get('/api/users')
def list_team(db:Session=Depends(get_db),_:User=Depends(admin)):
    return [{'id':u.id,'email':u.email,'role':u.role,'active':u.active} for u in db.scalars(select(User).order_by(User.id)).all()]


@app.post('/api/users', status_code=201)
def create_team_user(payload:NewTeamUser,db:Session=Depends(get_db),actor:User=Depends(admin)):
    from .security import hash_password
    email=payload.email.strip().lower()
    if '@' not in email or email.startswith('@') or email.endswith('@'): fail(422,'Enter a valid email address')
    if db.scalar(select(User.id).where(User.email==email)):fail(409,'Email already exists')
    user=User(email=email,password_hash=hash_password(payload.password),role=payload.role)
    db.add(user);db.flush()
    audit(db,actor,'user_create',str(user.id),{'role':user.role})
    db.commit()
    return {'id':user.id,'email':user.email,'role':user.role,'active':True}


class ChangePassword(BaseModel):
    old_password:str
    new_password:str = Field(min_length=12,max_length=256)


@app.post('/api/auth/change-password')
def change_password(payload:ChangePassword,db:Session=Depends(get_db),user:User=Depends(current_user)):
    from .security import hash_password,verify_password
    if not verify_password(payload.old_password,user.password_hash):fail(403,'Current password is incorrect')
    user.password_hash=hash_password(payload.new_password)
    user.auth_version += 1  # Invalidates every previously issued bearer token.
    audit(db,user,'password_changed',str(user.id))
    db.commit()
    return {'ok':True,'message':'Password changed. Please sign in again; previous sessions have expired.'}


class UserStatusUpdate(BaseModel):
    active:bool


@app.patch('/api/users/{user_id}/status')
def change_team_status(user_id:int,payload:UserStatusUpdate,db:Session=Depends(get_db),actor:User=Depends(admin)):
    target=db.get(User,user_id)
    if not target:fail(404,'User not found')
    if target.id==actor.id and not payload.active:fail(409,'You cannot deactivate your own account')
    if target.active!=payload.active:
        target.active=payload.active;target.auth_version+=1
    audit(db,actor,'user_status',str(target.id),{'active':target.active})
    db.commit()
    return {'id':target.id,'email':target.email,'active':target.active}


class AdminResetPassword(BaseModel):
    new_password:str=Field(min_length=12,max_length=256)


@app.post('/api/users/{user_id}/reset-password')
def admin_reset_password(user_id:int,payload:AdminResetPassword,db:Session=Depends(get_db),actor:User=Depends(admin)):
    from .security import hash_password
    target=db.get(User,user_id)
    if not target:fail(404,'User not found')
    target.password_hash=hash_password(payload.new_password)
    target.auth_version+=1
    audit(db,actor,'user_password_reset',str(user_id))
    db.commit()
    return {'ok':True,'message':'Password reset. Existing sessions revoked.'}


@app.get('/api/overview')
def overview(db:Session=Depends(get_db),_:User=Depends(current_user)):
    return {'templates':db.scalar(select(func.count()).select_from(Template)),
      'drafts':db.scalar(select(func.count()).select_from(Page).where(Page.status=='draft')),
      'published':db.scalar(select(func.count()).select_from(Page).where(Page.status=='published')),
      'pages':db.scalar(select(func.count()).select_from(Page))}


@app.get('/api/templates')
def templates(db:Session=Depends(get_db),_:User=Depends(current_user)):
    return [template_json(t) for t in db.scalars(select(Template).where(Template.is_deleted==False).order_by(Template.id.desc())).all()]


class DeleteTemplatesRequest(BaseModel):
    confirm: bool = False


def remove_templates(db:Session,user:User,selected:list[Template]):
    """Delete unused templates; hide templates still referenced by pages.

    A page's snapshot and its source HTML are immutable. Hiding the originating
    template from this library must not delete those records or object keys.
    """
    if not selected:
        return {'removed':0,'retained_for_pages':0,'storage_cleanup_failed':0}
    unused_keys=[]
    retained=0
    for t in selected:
        used=db.scalar(select(func.count()).select_from(Page).where(Page.template_id==t.id)) or 0
        if used:
            t.is_deleted=True
            retained+=1
        else:
            unused_keys.append(t.object_key)
            db.delete(t)
    audit(db,user,'template_library_remove','templates',{'ids':[t.id for t in selected],'retained_for_pages':retained})
    try:
        db.commit()
    except Exception:
        db.rollback()
        fail(409,'Could not remove templates. No changes were saved.')
    failed=0
    try:
        store=ObjectStore() if unused_keys else None
    except Exception:
        failed=len(set(unused_keys));store=None
    if store:
        for key in set(unused_keys):
            try:store.delete(key)
            except Exception:failed+=1
    return {'removed':len(selected),'retained_for_pages':retained,'storage_cleanup_failed':failed}


@app.delete('/api/templates')
def delete_all_templates(payload:DeleteTemplatesRequest,db:Session=Depends(get_db),user:User=Depends(admin)):
    if not payload.confirm:fail(422,'Please confirm template removal')
    selected=db.scalars(select(Template).where(Template.is_deleted==False).order_by(Template.id)).all()
    return remove_templates(db,user,selected)


@app.delete('/api/templates/{template_id}')
def delete_one_template(template_id:int,payload:DeleteTemplatesRequest,db:Session=Depends(get_db),user:User=Depends(admin)):
    if not payload.confirm:fail(422,'Please confirm template removal')
    t=get_template(db,template_id)
    if t.is_deleted:fail(404,'Template is already removed from the library')
    return remove_templates(db,user,[t])


@app.get('/api/official/catalog')
def official_catalog(_:User=Depends(current_user)):
    """The three source pages and their modules, without importing anything."""
    return [{'code':x.code,'name':x.title,'category':x.category,'source_url':'https://workspacebyemlen.co.uk'+x.path}
            for x in OFFICIAL_PAGES]


@app.post('/api/official/bootstrap')
def bootstrap_official(db:Session=Depends(get_db),user:User=Depends(admin)):
    """Idempotently import the approved public designs as editable draft templates.

    Existing Category templates, pages, publications and object-storage keys are
    never overwritten. Deleting or archiving a seed page is respected. Errors
    for one source are isolated from other sources.
    """
    store=ObjectStore()
    result={'templates_created':0,'pages_created':0,'existing':0,'unavailable':[]}
    for item in OFFICIAL_PAGES:
        key=official_key(item.code)
        existing=db.scalar(select(Template).where(Template.object_key==key).limit(1))
        if existing:
            result['existing']+=1
            continue
        try:
            source,sections,fields=make_template(item,fetch_official(item))
            # Preserve exactly the approved source in immutable object storage.
            store.put(key,source.encode('utf-8'),'text/html')
            t=Template(name=item.title,category=item.category,object_key=key,
                       fields=fields,sections=sections,version=1,approved=True)
            db.add(t);db.flush()
            slug=item.page_slug
            occupied=db.scalar(select(Page.id).where(Page.slug==slug))
            if occupied:
                slug=f'{slug}-{t.id}'
            p=Page(template_id=t.id,title=item.page_title,slug=slug,values={},
                   template_snapshot={**template_json(t),'object_key':key,
                                      'source_url':'https://workspacebyemlen.co.uk'+item.path},
                   seo={'seo_title':'','description':'','noindex':True,'nofollow':True,
                        'noarchive':False,'noimageindex':False,'nosnippet':False,
                        'canonical_override':''},status='draft')
            db.add(p);db.flush()
            audit(db,user,'official_template_seed',str(t.id),
                  {'module':item.category,'section_count':len(sections),'page_id':p.id})
            db.commit()
            result['templates_created']+=1
            result['pages_created']+=1
        except (ValueError,UnicodeError,RuntimeError,Exception):
            db.rollback()
            # Do not expose provider internals/credentials or change stored data.
            result['unavailable'].append(item.title)
    return result


@app.post('/api/templates/import',status_code=201)
async def import_template(file:UploadFile=File(...),name:str='',category:str='Solution Category',
   db:Session=Depends(get_db),user:User=Depends(admin)):
    if not file.filename or not file.filename.lower().endswith('.html'):fail(422,'Upload an .html file')
    raw=await file.read(get_settings().max_upload_bytes+1)
    try:
        source,sections,fields=extract(raw.decode('utf-8'))
    except (UnicodeError,ValueError) as exc:fail(422,str(exc))
    key=f'templates/{uuid4().hex}.html'
    ObjectStore().put(key,source.encode('utf-8'),'text/html')
    t=Template(name=(name.strip() or PurePath(file.filename).stem)[:200],category=category[:80],object_key=key,sections=sections,fields=fields)
    db.add(t);db.flush()
    audit(db,user,'template_import',str(t.id),{'sections':len(sections),'fields':len(fields)})
    db.commit();db.refresh(t)
    return template_json(t)


class FieldConfig(BaseModel):
    key:str
    mode:str=Field(pattern='^(static|page|global)$')
    label:str=Field(min_length=1,max_length=120)
    global_key:str|None=None
    heading_tag:str|None=None
    default:str|None=None


class TemplateMapping(BaseModel):
    fields:list[FieldConfig]
    sections:list[dict]|None=None
    approved:bool=False


@app.put('/api/templates/{template_id}/mapping')
def save_mapping(template_id:int,payload:TemplateMapping,db:Session=Depends(get_db),user:User=Depends(admin)):
    t=get_template(db,template_id)
    existing={f['key']:f for f in t.fields}
    if set(f.key for f in payload.fields)!=set(existing) or len(payload.fields)!=len(existing):
        fail(422,'Mapping must include each detected field exactly once')
    updated=[]
    section_names={s['id']:s['name'] for s in t.sections}
    for entry in payload.fields:
        f=dict(existing[entry.key]);f['mode']=entry.mode;f['label']=entry.label
        if read_only_section(t.category,section_names.get(f['section_id'],'')):
            # Property testimonials are deliberately non-editable, even for admins.
            f['mode']='static'
        if f['mode']=='global':
            if not entry.global_key or not re.fullmatch(r'[a-z][a-z0-9_]{1,100}',entry.global_key):
                fail(422,'Global fields need a valid shared-content key')
            f['global_key']=entry.global_key
        else:
            f['global_key']=None
        if entry.heading_tag is not None:
            if f.get('tag') not in HEADINGS or entry.heading_tag not in HEADINGS:
                fail(422,'Heading level must be H1 through H6 for a detected heading')
            f['heading_tag']=entry.heading_tag
        if entry.default is not None:
            if f.get('kind') not in ('link','icon'):
                fail(422,'Only link and icon defaults can be changed in template mapping')
            if len(entry.default)>1000:
                fail(422,'Default link or icon value is too long')
            if f.get('kind')=='link' and entry.default and not is_safe_link(entry.default):
                fail(422,'Unsafe link destination')
            if f.get('kind')=='icon' and f.get('attr')=='icon_src' and entry.default and not SAFE_URL.match(entry.default):
                fail(422,'Unsafe icon image URL')
            if f.get('kind')=='icon' and f.get('attr')=='class' and not SAFE_CLASS.fullmatch(entry.default):
                fail(422,'Icon class must contain only safe class characters')
            f['default']=entry.default
        updated.append(f)
    t.fields=updated
    if payload.sections is not None:
        if set(s.get('id') for s in payload.sections)!=set(x['id'] for x in t.sections):fail(422,'Section IDs cannot change')
        original_sections={sec['id']:sec for sec in t.sections}
        t.sections=[{'id':s['id'],'name':str(s.get('name') or 'Section')[:120],'order':i+1,
                     'repeaters':original_sections[s['id']].get('repeaters',[])}
                    for i,s in enumerate(payload.sections)]
    t.approved=payload.approved
    t.version+=1
    audit(db,user,'mapping_update',str(t.id),{'approved':t.approved})
    db.commit()
    return template_json(t)


@app.post('/api/templates/{template_id}/redetect')
def redetect_template(template_id:int,db:Session=Depends(get_db),user:User=Depends(admin)):
    """Re-extract saved HTML to include previously missed unmarked sections.

    Existing mapped fields retain their settings and new fields stay static.
    Re-approval is required. Existing page snapshots are not modified.
    """
    t=get_template(db,template_id)
    source=ObjectStore().get(t.object_key).decode('utf-8')
    fresh_source,sections,fields=extract(source)
    existing={f['key']:f for f in t.fields}
    old_sections={sec['id']:sec for sec in t.sections}
    for field in fields:
        old=existing.get(field['key'])
        if old and old.get('kind')==field.get('kind') and old.get('attr')==field.get('attr'):
            for key in ('label','mode','global_key'):
                if key in old:field[key]=old[key]
            if old.get('tag') in HEADINGS and old.get('heading_tag') in HEADINGS:
                field['heading_tag']=old['heading_tag']
            if field['kind'] in ('link','icon') and 'default' in old:
                field['default']=old['default']
    for sec in sections:
        if sec['id'] in old_sections:
            sec['name']=old_sections[sec['id']]['name']
    previous=len(t.sections)
    # Write a new immutable object so existing page/template snapshots keep
    # referencing their original HTML, even when an old template is re-scanned.
    new_key=f'templates/{uuid4().hex}.html'
    ObjectStore().put(new_key,fresh_source.encode('utf-8'),'text/html')
    t.object_key=new_key
    t.sections=sections;t.fields=fields;t.approved=False;t.version+=1
    audit(db,user,'template_redetect',str(t.id),{'before':previous,'after':len(sections),'fields':len(fields)})
    db.commit()
    return template_json(t)


@app.get('/api/templates/{template_id}/preview',response_class=HTMLResponse)
def template_preview(template_id:int,focus_field:str|None=None,db:Session=Depends(get_db),_:User=Depends(current_user)):
    t=get_template(db,template_id)
    src=ObjectStore().get(t.object_key).decode('utf-8')
    output=render(src,t.fields,{},globals_dict(db))
    if focus_field:
        if focus_field not in {f['key'] for f in t.fields}:fail(404,'Unknown field')
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(output,'html.parser')
        highlight=soup.find(attrs={'data-we-field':focus_field})
        if highlight:
            styles=soup.new_tag('style');styles.string='[data-we-qa-focus]{outline:4px solid #ed2024!important;outline-offset:3px!important;background:rgba(255,185,0,.2)!important;scroll-margin-top:140px!important}'
            soup.head.append(styles)
            highlight['data-we-qa-focus']='1'
            section=next((f['section_id'] for f in t.fields if f['key']==focus_field),None)
            if section:
                for other in list(soup.find_all(attrs={'data-we-section': True})):
                    if other.get('data-we-section')!=section:other.decompose()
            output=str(soup)
    return HTMLResponse(output,headers={'X-Robots-Tag':'noindex, nofollow','Content-Security-Policy':"sandbox; default-src 'none'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; font-src 'self' https:"})


class NewPage(BaseModel):
    name:str=Field(min_length=1,max_length=200)
    template_id:int


@app.post('/api/pages',status_code=201)
def create_page(payload:NewPage,db:Session=Depends(get_db),user:User=Depends(current_user)):
    t=get_template(db,payload.template_id)
    if t.is_deleted:fail(409,'This template was removed from the library. Choose an active template.')
    if not t.approved:fail(409,'Approve the template field mapping before creating pages')
    base=re.sub(r'[^a-z0-9]+','-',payload.name.lower()).strip('-') or 'page'
    slug=base;i=2
    while (db.scalar(select(Page.id).where(Page.slug==slug)) or db.scalar(select(Redirect.id).where(Redirect.from_path==slug))
           or db.scalar(select(Publication.id).where(Publication.slug==slug))):
        slug=f'{base}-{i}';i+=1
    p=Page(template_id=t.id,title=payload.name.strip(),slug=slug,values={},template_snapshot={**template_json(t),'object_key':t.object_key},
           seo={'seo_title':'','description':'','noindex':True,'nofollow':False,'noarchive':False,'noimageindex':False,'nosnippet':False,'canonical_override':''},status='draft')
    db.add(p);db.flush()
    audit(db,user,'page_create',str(p.id),{'template_id':t.id})
    db.commit();db.refresh(p)
    return page_json(p)


@app.get('/api/pages')
def list_pages(status:str|None=None,include_archived:bool=False,db:Session=Depends(get_db),_:User=Depends(current_user)):
    query=select(Page).order_by(Page.updated_at.desc())
    if not include_archived:query=query.where(Page.archived==False)
    if status in ('draft','published'):query=query.where(Page.status==status)
    return [page_json(p) for p in db.scalars(query).all()]


def page_template_with_repeaters(db:Session,p:Page):
    """Expose repeaters on old page snapshots without modifying stored pages."""
    stored=p.template_snapshot or template_json(get_template(db,p.template_id))
    # Recompute on every read: older saved pages contain empty/stale repeater
    # metadata even though their HTML has legitimate card and FAQ groups.
    source_key=stored.get('object_key') or get_template(db,p.template_id).object_key
    source=ObjectStore().get(source_key).decode('utf-8')
    _,sections=overlay_metadata(source,stored['sections'],stored['fields'])
    return {**stored,'sections':sections}


@app.post('/api/pages/{page_id}/enable-link-icon-editing')
def enable_link_and_icon_editing(page_id:int,payload:dict,db:Session=Depends(get_db),user:User=Depends(admin)):
    """Explicit page-only opt-in, protecting approved templates and publications."""
    p=get_page(db,page_id)
    if p.archived:fail(409,'Restore this page before changing editing permissions')
    if payload.get('edit_version')!=p.edit_version:
        fail(409,'Page has changed. Reload before enabling editing.')
    snapshot=p.template_snapshot or {**template_json(get_template(db,p.template_id)),
                                     'object_key':get_template(db,p.template_id).object_key}
    updated=[]
    count=0
    for field in snapshot['fields']:
        if field.get('mode')=='static' and field.get('kind') in ('link','icon'):
            updated.append({**field,'mode':'page'})
            count+=1
        else:updated.append(field)
    if count:
        p.template_snapshot={**snapshot,'fields':updated}
        p.edit_version+=1
        p.updated_at=utcnow()
        audit(db,user,'enable_page_links_icons',str(page_id),{'count':count})
        db.commit();db.refresh(p)
    return {'page':page_json(p),'template':page_template_with_repeaters(db,p),
            'enabled_count':count}


@app.get('/api/pages/{page_id}')
def read_page(page_id:int,db:Session=Depends(get_db),_:User=Depends(current_user)):
    p=get_page(db,page_id)
    return {'page':page_json(p),'template':page_template_with_repeaters(db,p)}


@app.post('/api/pages/{page_id}/upgrade-repeaters')
def upgrade_page_repeaters(page_id:int,payload:dict,db:Session=Depends(get_db),user:User=Depends(admin)):
    """Explicit opt-in upgrade for an existing page's old approved snapshot.

    Write new immutable source HTML: no other pages/templates or publications
    are changed. Preserve all old field mapping decisions and values, and
    expose omitted repeated items and FAQ answers as new page variables.
    """
    p=get_page(db,page_id)
    if p.archived:fail(409,'Restore the page before updating repeaters')
    if payload.get('edit_version')!=p.edit_version:
        fail(409,'Page has changed. Reload before upgrading repeaters.')
    original=p.template_snapshot or template_json(get_template(db,p.template_id))
    source=ObjectStore().get(original['object_key']).decode('utf-8')
    try:
        upgraded,sections,fresh=extract(source)
    except ValueError as e:fail(422,str(e))
    old={f['key']:f for f in original['fields']}
    old_sec={x['id']:x for x in original['sections']}
    for sec in sections:
        if sec['id'] in old_sec:sec['name']=old_sec[sec['id']]['name']
    repeated={key for sec in sections for group in sec.get('repeaters',[])
              for item in group['items'] for key in item['field_keys']}
    for field in fresh:
        previous=old.get(field['key'])
        if previous and previous.get('kind')==field.get('kind') and previous.get('attr')==field.get('attr'):
            for key in ('label','mode','global_key','heading_tag'):
                if key in previous:field[key]=previous[key]
            if field.get('kind') in ('link','icon') and 'default' in previous:
                field['default']=previous['default']
        elif field['key'] in repeated:
            field['mode']='page'
    # Existing locked/static choices remain locked. The upgrade enables only
    # fields that were not previously detected and are in repeatable groups.
    key=f'pages/{p.id}/repeater-upgrade-{uuid4().hex}.html'
    ObjectStore().put(key,upgraded.encode('utf-8'),'text/html')
    p.template_snapshot={**original,'object_key':key,'sections':sections,'fields':fresh,'approved':True}
    p.edit_version+=1;p.updated_at=utcnow()
    audit(db,user,'page_repeaters_upgrade',str(p.id),{'repeaters':sum(len(x.get('repeaters',[])) for x in sections),'new_fields':len(fresh)-len(old)})
    db.commit();db.refresh(p)
    return {'page':page_json(p),'template':page_template_with_repeaters(db,p),
            'new_fields':len([field for field in fresh if field['key'] not in old]),
            'repeaters':sum(len(x.get('repeaters',[])) for x in sections)}


@app.post('/api/pages/{page_id}/archive')
def archive_page(page_id:int,db:Session=Depends(get_db),user:User=Depends(admin)):
    p=get_page(db,page_id)
    if p.published_version:fail(409,'Published pages cannot be archived while live; an explicit unpublish workflow is required')
    p.archived=True
    audit(db,user,'page_archive',str(p.id))
    db.commit()
    return {'ok':True,'page_id':p.id}


@app.post('/api/pages/{page_id}/restore')
def restore_page(page_id:int,db:Session=Depends(get_db),user:User=Depends(admin)):
    p=get_page(db,page_id)
    p.archived=False
    audit(db,user,'page_restore',str(p.id))
    db.commit()
    return {'ok':True,'page_id':p.id}


class PageUpdate(BaseModel):
    edit_version:int = Field(ge=1, description="Current revision returned by the page API, required to prevent lost edits")
    title:str|None=None
    slug:str|None=None
    values:dict|None=None
    seo:dict|None=None


def validate_repeater_value(key,value,t):
    if not isinstance(value,str) or len(value)>24000:
        fail(422,'Repeater content must be text under 24,000 characters')
    groups={g['id']:g for sec in t['sections'] for g in sec.get('repeaters',[])}
    fields={f['key']:f for f in t['fields']}
    if key.startswith(VARIANT_PREFIX):
        for group in groups.values():
            if group['kind']!='solutions':continue
            if key in {VARIANT_PREFIX+group['id']+'__'+i['id'] for i in group['items']}:
                if value not in VARIANTS:fail(422,'Unknown solution card style')
                if not any(fields.get(fk,{}).get('mode')=='page'
                           for item in group['items'] for fk in item['field_keys']):
                    fail(422,'Static solution cards cannot be customised')
                return
        fail(422,'Unrecognized solution card style setting')
    if not key.startswith(REPEAT_PREFIX):fail(422,'Unknown repeater')
    group=groups.get(key[len(REPEAT_PREFIX):])
    if not group or not group['items']:fail(422,'Unknown repeater group')
    available={k:fields[k] for k in group['items'][-1]['field_keys']
               if k in fields and fields[k].get('mode')=='page'}
    if not available:fail(422,'This repeater is locked by its template mapping')
    try:
        entries=json.loads(value)
    except (TypeError,ValueError):
        fail(422,'Repeater entries must contain valid JSON')
    if not isinstance(entries,list) or len(entries)>MAX_ADDITIONS:
        fail(422,'Repeater supports up to 12 additional items')
    for entry in entries:
        if not isinstance(entry,dict):
            fail(422,'Every repeater item must be an object')
        if not set(entry).issubset(set(available)|({'__variant'} if group['kind']=='solutions' else set())):
            fail(422,'Repeater contains a static or unrecognized field')
        if '__variant' in entry and entry['__variant'] not in VARIANTS:
            fail(422,'Invalid solution card style')
        for fk,v in entry.items():
            if fk=='__variant':continue
            if not isinstance(v,str) or len(v)>3000:fail(422,'Repeater fields must be text under 3000 characters')
            f=available[fk]
            if f['kind']=='link' and v and not is_safe_link(v):fail(422,'Unsafe repeated link URL')
            if f['kind']=='image' and not SAFE_URL.match(v):fail(422,'Unsafe repeated image URL')
            if f['kind']=='icon':
                if f.get('attr')=='icon_src' and not is_safe_icon_value(v):
                    fail(422,'Unsafe repeated icon URL')
                if f.get('attr')=='class' and not SAFE_CLASS.fullmatch(v):
                    fail(422,'Unsafe repeated icon class')


def validated_page_changes(p: Page, payload: PageUpdate, db: Session) -> dict:
    """Validate and construct a proposed page without modifying the stored record."""
    t=page_template_with_repeaters(db,p)
    changes={}
    if payload.title is not None:changes['title']=payload.title.strip()[:200] or p.title
    if payload.slug is not None:
        try:slug=safe_slug(payload.slug)
        except ValueError as exc:fail(422,str(exc))
        if db.scalar(select(Page.id).where(Page.slug==slug,Page.id!=p.id)):
            fail(409,'URL already used by another page')
        if db.scalar(select(Redirect.id).where(Redirect.from_path==slug)):
            fail(409,'URL is reserved by an existing redirect')
        # A previous publication from a different page must also remain reserved.
        if db.scalar(select(Publication.id).where(Publication.slug==slug,Publication.page_id!=p.id)):
            fail(409,'URL is already associated with a published page')
        changes['slug']=slug
    if payload.values is not None:
        allowed={f['key']:f for f in t['fields'] if f['mode']=='page'}
        extra_keys={k for k in payload.values if k.startswith(REPEAT_PREFIX) or k.startswith(VARIANT_PREFIX) or k==DESIGN_KEY}
        if not (set(payload.values)-extra_keys).issubset(allowed):
            fail(422,'Attempted to change static or shared template fields')
        for key in extra_keys:
            if key==DESIGN_KEY:
                try: validate_design(payload.values[key],t['sections'],t['fields'])
                except ValueError as exc:fail(422,str(exc))
            else:validate_repeater_value(key,payload.values[key],t)
        newvals=dict(p.values or {})
        for key,value in payload.values.items():
            if key in extra_keys:
                newvals[key]=value
                continue
            if not isinstance(value,str) or len(value)>3000:fail(422,'Values must be text under 3000 characters')
            field=allowed[key]
            if field['kind']=='image' and not SAFE_URL.match(value):fail(422,'Image URL is not allowed')
            if field['kind']=='link' and value and not is_safe_link(value):fail(422,'Unsafe link destination')
            if field['kind']=='icon':
                if field.get('attr')=='icon_src' and not is_safe_icon_value(value):fail(422,'Icon URL is not allowed')
                if field.get('attr')=='class' and not SAFE_CLASS.fullmatch(value):fail(422,'Icon class is not allowed')
            newvals[key]=value
        changes['values']=newvals
    if payload.seo is not None:
        allowed={'seo_title','description','noindex','nofollow','noarchive','noimageindex','nosnippet','canonical_override','og_title','og_description'}
        if not set(payload.seo).issubset(allowed):fail(422,'Unexpected SEO field')
        seo=dict(p.seo or {})
        for k,v in payload.seo.items():
            if k in ('noindex','nofollow','noarchive','noimageindex','nosnippet') and not isinstance(v,bool):fail(422,'Robots settings must be booleans')
            if k not in ('noindex','nofollow','noarchive','noimageindex','nosnippet') and (not isinstance(v,str) or len(v)>500):fail(422,'SEO text is too long')
            seo[k]=v
        changes['seo']=seo
    return changes


@app.put('/api/pages/{page_id}')
def save_page(page_id:int,payload:PageUpdate,db:Session=Depends(get_db),user:User=Depends(current_user)):
    p=get_page(db,page_id)
    if p.archived:fail(409,'Restore this page before editing it')
    if p.edit_version!=payload.edit_version:fail(409,'This page changed since you opened it. Reload to see the latest version before saving.')
    changes=validated_page_changes(p,payload,db)
    # Atomic compare-and-set: simultaneous writers cannot overwrite stale revisions.
    result=db.execute(update(Page).where(Page.id==page_id,Page.edit_version==payload.edit_version)
        .values(**changes,edit_version=Page.edit_version+1,updated_at=utcnow()).execution_options(synchronize_session=False))
    if result.rowcount!=1:
        db.rollback();fail(409,'Another editor saved changes. Reload the page and compare before saving.')
    audit(db,user,'page_save',str(page_id))
    db.commit();db.expire_all()
    return page_json(get_page(db,page_id))

def compiled(db,p:Page,section_id=None):
    t=p.template_snapshot or {**template_json(get_template(db,p.template_id)),'object_key':get_template(db,p.template_id).object_key}
    source=ObjectStore().get(t['object_key']).decode('utf-8')
    output=render(source,t['fields'],p.values or {},globals_dict(db),section_id)
    # Media selection in page-variable image fields retains the actual media
    # record's alternative text. Published HTML stays immutable after snapshot.
    if '/api/media/' in output:
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(output,'html.parser')
        changed=False
        for img in soup.find_all('img',src=True):
            path=urlsplit(img.get('src','')).path
            m=re.fullmatch(r'/api/media/(\d+)/content',path)
            if not m:continue
            media=db.get(Media,int(m.group(1)))
            if media:
                img['alt']=media.alt_text
                changed=True
        if changed:output=str(soup)
    return output


@app.get('/api/pages/{page_id}/preview',response_class=HTMLResponse)
def page_preview(page_id:int,section_id:str|None=None,db:Session=Depends(get_db),_:User=Depends(current_user)):
    p=get_page(db,page_id)
    if section_id and section_id not in {x['id'] for x in (p.template_snapshot or template_json(get_template(db,p.template_id)))['sections']}:fail(404,'Unknown section')
    html=compiled(db,p,section_id)
    return HTMLResponse(html,headers={'X-Robots-Tag':'noindex, nofollow',
      'Content-Security-Policy':"sandbox; default-src 'none'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; font-src 'self' https:"})


@app.post('/api/pages/{page_id}/preview',response_class=HTMLResponse)
def preview_unsaved(page_id:int,payload:PageUpdate,section_id:str|None=None,
                  db:Session=Depends(get_db),_:User=Depends(current_user)):
    """Preview current editor state without a write or public-indexable response."""
    p=get_page(db,page_id)
    if p.edit_version!=payload.edit_version:fail(409,'This page has changed. Reload before previewing your edits.')
    changes=validated_page_changes(p,payload,db)
    t=p.template_snapshot or template_json(get_template(db,p.template_id))
    if section_id and section_id not in {x['id'] for x in t['sections']}:fail(404,'Unknown section')
    from types import SimpleNamespace
    draft=SimpleNamespace(template_id=p.template_id,template_snapshot=p.template_snapshot,
                          values=changes.get('values',p.values or {}))
    rendered=compiled(db,draft,section_id)
    if not section_id:
        try:
            rendered=metadata_html(rendered,changes.get('title',p.title),changes.get('slug',p.slug),changes.get('seo',p.seo or {}),get_settings().public_site_url)
        except ValueError as exc:fail(422,str(exc))
    return HTMLResponse(rendered,headers={'X-Robots-Tag':'noindex, nofollow',
      'Content-Security-Policy':"sandbox; default-src 'none'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; font-src 'self' https:"})


@app.post('/api/pages/{page_id}/publish')
def publish(page_id:int,db:Session=Depends(get_db),user:User=Depends(admin)):
    p=get_page(db,page_id)
    t=p.template_snapshot or template_json(get_template(db,p.template_id))
    if p.archived:fail(409,'Restore this page before publishing')
    if not t['approved']:fail(409,'Template mapping is not approved')
    if not p.seo.get('seo_title') or not p.seo.get('description'):fail(422,'SEO title and description are required')
    html=metadata_html(compiled(db,p),p.title,p.slug,p.seo,get_settings().public_site_url)
    old=latest_publication(db,page_id)
    if old and old.slug!=p.slug:
        existing=db.scalar(select(Redirect).where(Redirect.from_path==old.slug))
        if existing: existing.to_path=p.slug
        else:db.add(Redirect(from_path=old.slug,to_path=p.slug))
    ver=p.published_version+1
    db.add(Publication(page_id=p.id,version=ver,slug=p.slug,html=html,seo_snapshot=dict(p.seo or {})))
    p.status='published';p.published_version=ver;p.published_edit_version=p.edit_version;p.updated_at=utcnow()
    audit(db,user,'publish',str(p.id),{'version':ver,'slug':p.slug})
    db.commit()
    return {'version':ver,'url':f'/site/{p.slug}/','message':'Published to local preview server only. Live website unchanged.'}


@app.get('/api/seo/status')
def seo_status(db:Session=Depends(get_db),_:User=Depends(current_user)):
    published=0;indexable=0
    for p in db.scalars(select(Page).where(Page.status=='published',Page.archived==False)).all():
        pub=latest_publication(db,p.id)
        if not pub:continue
        published+=1
        if pub.seo_snapshot is not None:
            noindex=pub.seo_snapshot.get('noindex',True)
        else:
            from bs4 import BeautifulSoup
            m=BeautifulSoup(pub.html,'html.parser').find('meta',attrs={'name':'robots'})
            noindex=not m or 'noindex' in (m.get('content') or '').lower()
        if not noindex:indexable+=1
    return {'published':published,'indexable':indexable,'noindex':published-indexable}


@app.get('/api/pages/{page_id}/publication-status')
def publication_status(page_id:int,db:Session=Depends(get_db),_:User=Depends(current_user)):
    p=get_page(db,page_id)
    pub=latest_publication(db,page_id)
    return {'draft':{'slug':p.slug,'seo':p.seo,'edit_version':p.edit_version},
      'published':({'slug':pub.slug,'version':pub.version,'seo':pub.seo_snapshot or {}} if pub else None),
      'has_unpublished_changes':bool(pub and p.edit_version>p.published_edit_version)}


@app.get('/api/shared/usage')
def shared_usage(db:Session=Depends(get_db),_:User=Depends(current_user)):
    usage={}
    for p in db.scalars(select(Page).where(Page.archived==False)).all():
        used={f.get('global_key') for f in (p.template_snapshot or {}).get('fields',[])
              if f.get('mode')=='global' and f.get('global_key')}
        for key in used:
            entry=usage.setdefault(key,{'key':key,'pages':0,'published_pages':0})
            entry['pages']+=1
            entry['published_pages']+=int(p.status=='published')
    return list(usage.values())


@app.get('/api/shared')
def get_shared(db:Session=Depends(get_db),_:User=Depends(current_user)):
    return globals_dict(db)


class SharedUpdate(BaseModel):
    items:dict[str,str]


@app.put('/api/shared')
def update_shared(payload:SharedUpdate,db:Session=Depends(get_db),user:User=Depends(admin)):
    for key,value in payload.items.items():
        if not re.fullmatch(r'[a-z][a-z0-9_]{1,100}',key) or len(value)>3000:fail(422,'Invalid shared field')
        obj=db.get(SharedContent,key)
        if obj:obj.value=value;obj.updated_at=utcnow()
        else:db.add(SharedContent(key=key,value=value))
    audit(db,user,'shared_update','globals',{'keys':list(payload.items)})
    db.commit()
    return globals_dict(db)


@app.post('/api/media',status_code=201)
async def upload_media(file:UploadFile=File(...),alt_text:str=Form(''),db:Session=Depends(get_db),user:User=Depends(current_user)):
    permitted={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}
    if file.content_type not in permitted:fail(415,'Upload a JPG, PNG or WebP image')
    raw=await file.read(get_settings().max_upload_bytes+1)
    if len(raw)>get_settings().max_upload_bytes:fail(413,'Image too large')
    signatures={'image/jpeg':raw[:3]==b'\xff\xd8\xff','image/png':raw[:8]==b'\x89PNG\r\n\x1a\n','image/webp':raw[:4]==b'RIFF' and raw[8:12]==b'WEBP'}
    if not signatures[file.content_type]:fail(422,'Invalid image data')
    key=f'media/{uuid4().hex}{permitted[file.content_type]}'
    ObjectStore().put(key,raw,file.content_type)
    m=Media(object_key=key,filename=(file.filename or 'image')[:255],alt_text=alt_text[:300],content_type=file.content_type)
    db.add(m);db.flush();audit(db,user,'media_upload',str(m.id));db.commit();db.refresh(m)
    return {'id':m.id,'url':f'/api/media/{m.id}/content','alt_text':m.alt_text}


@app.get('/api/media')
def get_media(db:Session=Depends(get_db),_:User=Depends(current_user)):
    return [{'id':m.id,'filename':m.filename,'alt_text':m.alt_text,'url':f'/api/media/{m.id}/content'} for m in db.scalars(select(Media).order_by(Media.id.desc())).all()]


class MediaAltUpdate(BaseModel):
    alt_text:str=Field(max_length=300)


@app.patch('/api/media/{media_id}')
def update_media_alt(media_id:int,payload:MediaAltUpdate,db:Session=Depends(get_db),user:User=Depends(current_user)):
    m=db.get(Media,media_id)
    if not m:fail(404,'Image not found')
    m.alt_text=payload.alt_text.strip()
    audit(db,user,'media_alt_update',str(media_id))
    db.commit()
    return {'id':m.id,'alt_text':m.alt_text}


@app.get('/api/media/{media_id}/content')
def media_content(media_id:int,db:Session=Depends(get_db)):
    m=db.get(Media,media_id)
    if not m:fail(404,'Image not found')
    return Response(content=ObjectStore().get(m.object_key),media_type=m.content_type,headers={'Cache-Control':'public, max-age=3600','X-Content-Type-Options':'nosniff'})


@app.get('/api/redirects')
def redirects(db:Session=Depends(get_db),_:User=Depends(current_user)):
    return [{'id':x.id,'from_path':x.from_path,'to_path':x.to_path} for x in db.scalars(select(Redirect)).all()]


class RedirectInput(BaseModel):
    from_path:str
    to_path:str


@app.post('/api/redirects',status_code=201)
def add_redirect(payload:RedirectInput,db:Session=Depends(get_db),user:User=Depends(admin)):
    try:a,b=safe_slug(payload.from_path),safe_slug(payload.to_path)
    except ValueError as e:fail(422,str(e))
    if a==b:fail(422,'Cannot redirect to same URL')
    if db.scalar(select(Redirect).where(Redirect.from_path==a)):fail(409,'Redirect source already exists')
    if db.scalar(select(Publication.id).where(Publication.slug==a)):
        fail(409,'A published URL cannot be used as a redirect source')
    if db.scalar(select(Page.id).where(Page.slug==a)):
        fail(409,'An existing page URL cannot be used as a redirect source')
    graph={r.from_path:r.to_path for r in db.scalars(select(Redirect))}
    cur=b
    for _ in range(100):
        if cur==a:fail(422,'Redirect loop detected')
        if cur not in graph:break
        cur=graph[cur]
    db.add(Redirect(from_path=a,to_path=b));audit(db,user,'redirect_create',a)
    db.commit();return {'from_path':a,'to_path':b}


@app.get('/site/{slug:path}',response_class=HTMLResponse)
def published_site(slug:str,db:Session=Depends(get_db)):
    slug=slug.strip('/')
    r=db.scalar(select(Redirect).where(Redirect.from_path==slug))
    if r:return RedirectResponse(url='/site/'+r.to_path+'/',status_code=301)
    p=db.scalar(select(Page).where(Page.slug==slug))
    pub=latest_publication(db,p.id) if p else None
    if pub and pub.slug!=slug:pub=None
    if not pub:
        # Old published slug may still have a snapshot even while page draft slug is changed.
        pub=db.scalar(select(Publication).where(Publication.slug==slug).order_by(Publication.version.desc()).limit(1))
    if not pub:fail(404,'Published page not found')
    return HTMLResponse(pub.html,headers={'X-Content-Type-Options':'nosniff',
        'Content-Security-Policy':"default-src 'self' https: data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https:; img-src 'self' https: data:; object-src 'none'; base-uri 'none'"})


@app.get('/sitemap.xml')
def sitemap(db:Session=Depends(get_db)):
    origin=get_settings().public_site_url.rstrip('/')
    urls=[]
    for p in db.scalars(select(Page).where(Page.status=='published',Page.archived==False)).all():
        pub=latest_publication(db,p.id)
        if not pub:continue
        if pub.seo_snapshot is not None:
            if pub.seo_snapshot.get('noindex',True):continue
        else:
            # Backwards compatibility for publications made before SEO snapshots existed.
            from bs4 import BeautifulSoup
            meta=BeautifulSoup(pub.html,'html.parser').find('meta',attrs={'name':'robots'})
            if not meta or 'noindex' in (meta.get('content') or '').lower():continue
        if pub:
            urls.append(f'<url><loc>{xml_escape(origin+"/"+pub.slug+"/")}</loc><lastmod>{pub.published_at.date()}</lastmod></url>')
    return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(urls)+'</urlset>',media_type='application/xml')


@app.get('/robots.txt')
def robots():
    return PlainTextResponse('User-agent: *\nDisallow: /api/\nDisallow: /admin/\nSitemap: '+get_settings().public_site_url.rstrip('/')+'/sitemap.xml\n')
