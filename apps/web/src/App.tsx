import {useEffect, useState} from 'react'
import {ArrowUpRight, Check, ChevronRight, CircleHelp, Copy, FileCode2, FilePenLine, Globe2, LayoutTemplate, LockKeyhole, LogOut, Plus, Search, Settings2, ShieldCheck, UploadCloud, X, Eye, Save, AlertTriangle} from 'lucide-react'

type Mode='static'|'global'|'page'
type Field={key:string;section_id:string;label:string;kind:string;attr:string;default:string;mode:Mode;global_key:string|null}
type Section={id:string;name:string;order:number}
type Template={id:number;name:string;category:string;approved:boolean;version:number;sections:Section[];fields:Field[]}
type SEO={seo_title:string;description:string;noindex:boolean;nofollow:boolean;canonical_override:string;og_title?:string;og_description?:string}
type Page={id:number;template_id:number;title:string;slug:string;values:Record<string,string>;seo:SEO;status:'draft'|'published';published_version:number;edit_version:number;updated_at:string;has_unpublished_changes:boolean;archived:boolean}
type Nav='Category'|'Templates'|'Saved Drafts'|'Published'|'Archived'|'Shared Content'|'SEO'|'Team Access'|'Media Library'
type Tab='All Pages'|'Add Page'|'Upload Template'

let accessToken=sessionStorage.getItem('emlen_access_token')||''
async function api<T>(path:string, options:RequestInit={}):Promise<T>{
  const headers:Record<string,string>={...(options.headers as Record<string,string>||{})}
  if(accessToken)headers.Authorization=`Bearer ${accessToken}`
  if(options.body && !(options.body instanceof FormData))headers['Content-Type']='application/json'
  const res=await fetch(path,{...options,headers})
  if(!res.ok){let message=`Request failed (${res.status})`;try{const j=await res.json();message=typeof j.detail==='string'?j.detail:JSON.stringify(j.detail)}catch{}throw new Error(message)}
  return res.json()
}
async function html(path:string,payload?:unknown):Promise<string>{
  const res=await fetch(path,{method:payload?'POST':'GET',headers:{Authorization:`Bearer ${accessToken}`,...(payload?{'Content-Type':'application/json'}:{})},body:payload?json(payload):undefined})
  if(!res.ok){let msg=`Preview failed (${res.status})`;try{const detail=await res.json();if(detail.detail)msg=typeof detail.detail==='string'?detail.detail:JSON.stringify(detail.detail)}catch{}throw new Error(msg)}
  return res.text()
}
const json=(o:unknown)=>JSON.stringify(o)
const label=(k:string)=>k.replaceAll('_',' ')

export default function App(){
  const [user,setUser]=useState<{email:string;role:string}|null>(null)
  const [loginEmail,setLoginEmail]=useState('')
  const [loginPassword,setLoginPassword]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [message,setMessage]=useState('')
  const [nav,setNav]=useState<Nav>('Category')
  const [tab,setTab]=useState<Tab>('All Pages')
  const [templates,setTemplates]=useState<Template[]>([])
  const [pages,setPages]=useState<Page[]>([])
  const [editor,setEditor]=useState<{page:Page;template:Template}|null>(null)
  const [savedPage,setSavedPage]=useState<Page|null>(null)
  const [focusField,setFocusField]=useState('')
  const [mapPreview,setMapPreview]=useState('')
  const [seoStatus,setSeoStatus]=useState<{published:number;indexable:number;noindex:number}|null>(null)
  const [showPassword,setShowPassword]=useState(false)
  const [oldPassword,setOldPassword]=useState('')
  const [newPassword,setNewPassword]=useState('')
  const [archivedPages,setArchivedPages]=useState<Page[]>([])
  const [collapsedSections,setCollapsedSections]=useState<string[]>([])
  const [inlinePreview,setInlinePreview]=useState('')
  const [inlinePreviewError,setInlinePreviewError]=useState('')
  const [inlinePreviewLoading,setInlinePreviewLoading]=useState(false)
  const [previewRefresh,setPreviewRefresh]=useState(0)
  const [newName,setNewName]=useState('')
  const [selectedTemplate,setSelectedTemplate]=useState<number|null>(null)
  const [uploaded,setUploaded]=useState<Template|null>(null)
  const [uploadName,setUploadName]=useState('')
  const [uploadCategory,setUploadCategory]=useState('Solution Category')
  const [templateFile,setTemplateFile]=useState<File|null>(null)
  const [mappingId,setMappingId]=useState<number|null>(null)
  const [preview,setPreview]=useState<string|null>(null)
  const [shared,setShared]=useState<Record<string,string>>({})
  const [sharedUsage,setSharedUsage]=useState<{key:string;pages:number;published_pages:number}[]>([])
  const [publicationInfo,setPublicationInfo]=useState<{published:{slug:string;seo:SEO;version:number}|null}|null>(null)
  const [newSharedKey,setNewSharedKey]=useState('')
  const [redirects,setRedirects]=useState<{id:number;from_path:string;to_path:string}[]>([])
  const [redirectFrom,setRedirectFrom]=useState('')
  const [redirectTo,setRedirectTo]=useState('')
  const [team,setTeam]=useState<{id:number;email:string;role:string;active:boolean}[]>([])
  const [teamEmail,setTeamEmail]=useState('')
  const [teamPassword,setTeamPassword]=useState('')
  const [teamRole,setTeamRole]=useState<'admin'|'editor'>('editor')
  const [media,setMedia]=useState<{id:number;filename:string;alt_text:string;url:string}[]>([])
  const [filter,setFilter]=useState<'All'|'Published'|'Draft'>('All')
  const draftState=(p:Page)=>JSON.stringify({title:p.title,slug:p.slug,values:p.values,seo:p.seo})
  const dirty=!!editor&&!!savedPage&&draftState(editor.page)!==draftState(savedPage)
  const previewPayload=editor?json({edit_version:editor.page.edit_version,title:editor.page.title,slug:editor.page.slug,values:editor.page.values,seo:editor.page.seo}):''
  function mayLeave(){return !dirty||window.confirm('You have unsaved page changes. Leave and discard these changes?')}
  useEffect(()=>{if(!dirty)return;const guard=(e:BeforeUnloadEvent)=>{e.preventDefault();e.returnValue=''};window.addEventListener('beforeunload',guard);return()=>window.removeEventListener('beforeunload',guard)},[dirty])
  useEffect(()=>{
    if(!editor||!previewPayload){setInlinePreview('');setInlinePreviewError('');setInlinePreviewLoading(false);return}
    let cancelled=false
    setInlinePreviewLoading(true)
    const timer=window.setTimeout(()=>{
      html(`/api/pages/${editor.page.id}/preview`,JSON.parse(previewPayload))
        .then(content=>{if(!cancelled){setInlinePreview(content);setInlinePreviewError('')}})
        .catch(e=>{if(!cancelled)setInlinePreviewError(e instanceof Error?e.message:String(e))})
        .finally(()=>{if(!cancelled)setInlinePreviewLoading(false)})
    },450)
    return()=>{cancelled=true;window.clearTimeout(timer)}
  },[editor?.page.id,previewPayload,previewRefresh])
  useEffect(()=>{if(!mappingId)return;let active=true;const query=focusField?'?focus_field='+encodeURIComponent(focusField):'';html(`/api/templates/${mappingId}/preview${query}`).then(r=>{if(active)setMapPreview(r)}).catch(e=>{if(active)showError(e)});return()=>{active=false}},[mappingId,focusField])

  async function refresh(){
    const [t,p]=await Promise.all([api<Template[]>('/api/templates'),api<Page[]>('/api/pages')])
    setTemplates(t);setPages(p)
    if(uploaded){const next=t.find(x=>x.id===uploaded.id);if(next)setUploaded(next)}
  }
  useEffect(()=>{if(!accessToken)return;api<{email:string;role:string}>('/api/auth/me').then(u=>{setUser(u);refresh().catch(showError)}).catch(()=>{accessToken='';sessionStorage.removeItem('emlen_access_token')})},[])
  useEffect(()=>{if(!user)return;setMessage('');if(nav==='Shared Content'){api<Record<string,string>>('/api/shared').then(setShared).catch(showError);api<typeof sharedUsage>('/api/shared/usage').then(setSharedUsage).catch(showError)};if(nav==='SEO')api<typeof redirects>('/api/redirects').then(setRedirects).catch(showError);if(nav==='Team Access'&&user.role==='admin')api<typeof team>('/api/users').then(setTeam).catch(showError);if(nav==='Media Library')api<typeof media>('/api/media').then(setMedia).catch(showError);if(nav==='SEO')api<typeof seoStatus>('/api/seo/status').then(setSeoStatus).catch(showError);if(nav==='Archived')api<Page[]>('/api/pages?include_archived=true').then(ps=>setArchivedPages(ps.filter(p=>p.archived))).catch(showError)},[nav,user])
  function showError(e:unknown){setError(e instanceof Error?e.message:String(e));setMessage('')}
  async function action(fn:()=>Promise<void>){setBusy(true);setError('');setMessage('');try{await fn()}catch(e){showError(e)}finally{setBusy(false)}}
  function notify(msg:string){setMessage(msg);setError('')}
  function logout(){if(!mayLeave())return;accessToken='';sessionStorage.removeItem('emlen_access_token');setUser(null);setEditor(null);setNav('Category')}
  async function login(){await action(async()=>{
    const result=await api<{access_token:string;user:{email:string;role:string}}>('/api/auth/login',{method:'POST',body:json({email:loginEmail,password:loginPassword})})
    accessToken=result.access_token;sessionStorage.setItem('emlen_access_token',accessToken);setUser(result.user);await refresh()
  })}
  async function openPage(p:Page){if(!mayLeave())return;await action(async()=>{const data=await api<{page:Page;template:Template}>(`/api/pages/${p.id}`);setEditor(data);setSavedPage(structuredClone(data.page));api<typeof publicationInfo>(`/api/pages/${p.id}/publication-status`).then(setPublicationInfo).catch(showError);setCollapsedSections([])})}
  async function createPage(){await action(async()=>{
    if(!newName.trim()||!selectedTemplate)throw new Error('Enter a page name and select a template')
    const p=await api<Page>('/api/pages',{method:'POST',body:json({name:newName.trim(),template_id:selectedTemplate})})
    await refresh();setNewName('');await openPage(p)
  })}
  async function uploadTemplate(){await action(async()=>{
    if(!templateFile)throw new Error('Choose an HTML template first')
    const form=new FormData();form.append('file',templateFile)
    const params=new URLSearchParams({name:uploadName||templateFile.name.replace(/\.html$/i,''),category:uploadCategory})
    const t=await api<Template>(`/api/templates/import?${params}`,{method:'POST',body:form});setUploaded(t);setMappingId(t.id);await refresh();notify(`${t.sections.length} structural sections detected. Fields are static until you approve their mapping.`)
  })}
  async function saveMapping(t:Template){await action(async()=>{
    const updated=await api<Template>(`/api/templates/${t.id}/mapping`,{method:'PUT',body:json({fields:t.fields.map(f=>({key:f.key,label:f.label,mode:f.mode,global_key:f.mode==='global'?f.global_key:null})),sections:t.sections,approved:t.approved})})
    setTemplates(prev=>prev.map(x=>x.id===t.id?updated:x));setUploaded(u=>u?.id===t.id?updated:u);notify('Template mapping saved. Only page-variable fields will appear in page editing.')
  })}
  async function savePage(){if(!editor)return;await action(async()=>{
    const p=editor.page
    const result=await api<Page>(`/api/pages/${p.id}`,{method:'PUT',body:json({title:p.title,slug:p.slug,values:p.values,seo:p.seo,edit_version:p.edit_version})})
    setEditor(prev=>prev?{...prev,page:result}:prev);setSavedPage(structuredClone(result));await refresh();notify('Draft changes saved')
  })}
  async function publishPage(){if(!editor)return;
    const p=editor.page
    if(!p.seo.seo_title?.trim()||!p.seo.description?.trim()){document.getElementById('seo-settings')?.scrollIntoView({behavior:'smooth',block:'start'});showError('Before publishing, add a page SEO title and meta description.');return}
    if(!window.confirm('Publish this version to the LOCAL CMS preview only? The WordPress website will NOT be updated.'))return
    await action(async()=>{
      if(dirty){const saved=await api<Page>(`/api/pages/${p.id}`,{method:'PUT',body:json({title:p.title,slug:p.slug,values:p.values,seo:p.seo,edit_version:p.edit_version})});setEditor(prev=>prev?{...prev,page:saved}:prev);setSavedPage(structuredClone(saved))}
      await api(`/api/pages/${p.id}/publish`,{method:'POST'})
      const latest=await api<{page:Page;template:Template}>(`/api/pages/${p.id}`)
      setEditor(latest);setSavedPage(structuredClone(latest.page));api<typeof publicationInfo>(`/api/pages/${p.id}/publication-status`).then(setPublicationInfo).catch(showError);await refresh();notify('Published to the local CMS only. The live WordPress website is unchanged.')
    })
  }
  async function fullPreview(section?:string){if(!editor)return;await action(async()=>{
    const qs=section?`?section_id=${encodeURIComponent(section)}`:''
    const p=editor.page
    setPreview(await html(`/api/pages/${p.id}/preview${qs}`,{edit_version:p.edit_version,title:p.title,slug:p.slug,values:p.values,seo:p.seo}))
  })}
  function navigate(name:Nav){if(!mayLeave())return;setEditor(null);setSavedPage(null);setNav(name);if(name==='Category')setTab('All Pages')}
  function closeEditor(){navigate('Category')}
  function modifyMapField(id:number,key:string,patch:Partial<Field>){setTemplates(prev=>prev.map(t=>t.id===id?{...t,fields:t.fields.map(f=>f.key===key?{...f,...patch}:f)}:t))}
  async function rotatePassword(){await action(async()=>{
    await api('/api/auth/change-password',{method:'POST',body:json({old_password:oldPassword,new_password:newPassword})})
    setOldPassword('');setNewPassword('');setShowPassword(false);notify('Password changed. Sign in again with your new password.')
    accessToken='';sessionStorage.removeItem('emlen_access_token');setUser(null);setEditor(null);setSavedPage(null)
  })}
  const changePage=(patch:Partial<Page>)=>setEditor(cur=>cur?{...cur,page:{...cur.page,...patch}}:cur)
  const changeSEO=(patch:Partial<SEO>)=>setEditor(cur=>cur?{...cur,page:{...cur.page,seo:{...cur.page.seo,...patch}}}:cur)
  const changeField=(key:string,val:string)=>setEditor(cur=>cur?{...cur,page:{...cur.page,values:{...cur.page.values,[key]:val}}}:cur)
  const mapping=templates.find(t=>t.id===mappingId)||uploaded
  const visiblePages=pages.filter(p=>(nav==='Saved Drafts'?(p.status==='draft'||p.has_unpublished_changes):nav==='Published'?p.status==='published':filter==='All'?true:filter==='Draft'?(p.status==='draft'||p.has_unpublished_changes):p.status==='published'))

  if(!user)return <div className="login-bg"><div className="login-card"><div className="logo dark"><span className="logo-dot"/>workspace<span className="by-emlen">BY EMLEN</span></div><div className="login-icon"><LockKeyhole size={28}/></div><h1>Welcome back.</h1><p>Sign in to manage pages, templates and SEO.</p><form onSubmit={e=>{e.preventDefault();login()}}><label>Admin email</label><input type="email" placeholder="admin@workspacebyemlen.co.in" value={loginEmail} onChange={e=>setLoginEmail(e.target.value)} required/><label>Password</label><input type="password" placeholder="Your password" value={loginPassword} onChange={e=>setLoginPassword(e.target.value)} required/><button className="primary fill" disabled={busy}>Sign in <ArrowUpRight size={18}/></button></form>{error&&<div className="alert error">{error}</div>}<small>Secure sign-in · Access configured during deployment</small></div></div>

  return <div className="shell"><aside className="sidebar"><div className="brand"><span className="brand-mark"/> <div><strong>workspace</strong><small>BY EMLEN</small></div></div><div className="side-label">WORKSPACE</div><div className="navigation">
    {([['Category',LayoutTemplate],['Templates',FileCode2],['Saved Drafts',FilePenLine],['Published',Globe2],['Archived',FilePenLine],['Shared Content',Copy],['SEO',Search],['Team Access',ShieldCheck],['Media Library',Settings2]] as const)
      .filter(([name])=>user.role==='admin'||!['Templates','Team Access','Archived'].includes(name))
      .map(([name,Icon])=><button key={name} className={`nav-item ${nav===name?'active':''}`} onClick={()=>navigate(name as Nav)}><Icon size={18}/>{name}<ChevronRight className="right-chevron" size={15}/></button>)}
  </div><button className="logout" onClick={logout}><LogOut size={17}/> Sign out</button></aside>
  <main className="main"><div className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14}/> <span>{editor?'Page Editor':nav}</span></div><div className="topbar-right"><button className="password-link" onClick={()=>setShowPassword(true)}>Change password</button><span className="role">{user.role}</span><div className="avatar">{user.email[0].toUpperCase()}</div></div></div>
  <div className="content">{error&&<div className="alert error"><CircleHelp size={16}/>{error}<button onClick={()=>setError('')}><X size={16}/></button></div>}{message&&<div className="alert success"><Check size={16}/>{message}<button onClick={()=>setMessage('')}><X size={16}/></button></div>}

  {editor?<><div className="page-top"><div><button className="backlink" onClick={closeEditor}>← All Pages</button><h1>{editor.page.title}</h1><p>Edit content only where the approved template permits changes.</p><div className="editor-signals">{dirty&&<span className="unsaved-pill"><AlertTriangle size={14}/> Unsaved changes</span>}{editor.page.has_unpublished_changes&&<span className="draft-pill">Published · Unpublished changes</span>}{!dirty&&!editor.page.has_unpublished_changes&&<span className="saved-pill"><Check size={14}/> Saved</span>}</div></div><div className="button-group"><button className="outline" onClick={()=>fullPreview()} disabled={busy}>Full-page preview <ArrowUpRight size={16}/></button><button className="outline" onClick={savePage} disabled={busy||!dirty}><Save size={15}/> Save draft</button>{user.role==='admin'&&<button className="primary" onClick={publishPage} disabled={busy}>Publish locally <ArrowUpRight size={16}/></button>}</div></div>
  <div className="editor-layout editor-flow">
    <section className="edit-panel editor-section-panel" id="section-editing" aria-labelledby="editing-heading">
      <div className="panel-heading">
        <div><div className="small-label">01 / CONTENT</div><h2 id="editing-heading">Section Editing</h2><p>Only fields approved as page-variable can be changed. The original HTML layout stays intact.</p></div>
        <span className="editor-field-total">{editor.template.fields.filter(f=>f.mode==='page').length} editable fields</span>
      </div>
      <div className="editor-section-rows">
        {editor.template.sections.map((section,i)=>{
          const fields=editor.template.fields.filter(f=>f.section_id===section.id&&f.mode==='page')
          const collapsed=collapsedSections.includes(section.id)
          return <div className="editor-section-block" key={section.id}>
            <button className="editor-section-toggle" type="button" aria-expanded={!collapsed} onClick={()=>setCollapsedSections(prev=>prev.includes(section.id)?prev.filter(id=>id!==section.id):[...prev,section.id])}>
              <span className="editor-section-no">{String(i+1).padStart(2,'0')}</span>
              <span className="editor-section-name"><strong>{section.name}</strong><small>{fields.length?`${fields.length} editable field${fields.length===1?'':'s'}`:'Fixed content · reused from template'}</small></span>
              {fields.length===0&&<LockKeyhole size={15} className="fixed-icon"/>}
              <ChevronRight size={17} className={`section-chevron ${collapsed?'':'expanded'}`}/>
            </button>
            {!collapsed&&fields.length>0&&<div className="editor-fields-grid">{fields.map(f=><label key={f.key} className={f.kind==='textarea'||f.kind==='image'?'wide-field':''}>{f.label}{f.kind==='textarea'?<textarea rows={4} value={editor.page.values[f.key]??f.default} onChange={e=>changeField(f.key,e.target.value)}/>:<input value={editor.page.values[f.key]??f.default} onChange={e=>changeField(f.key,e.target.value)} type="text"/>}{f.kind==='image'&&<small>Image URL · Upload the asset in Media Library first.</small>}</label>)}</div>}
          </div>
        })}
      </div>
    </section>

    <section className="edit-panel editor-seo-panel" id="seo-settings" aria-labelledby="seo-heading">
      <div className="panel-heading"><div><div className="small-label">02 / SEARCH</div><h2 id="seo-heading">SEO Settings</h2><p>Set the information search engines use for this page.</p></div></div>
      <div className="form-stack seo-form-stack">
        <div className="preflight"><strong>Publication checklist (local CMS)</strong><span className={editor.page.seo.seo_title?.trim()?'ok':'missing'}>{editor.page.seo.seo_title?.trim()?'✓':'!'} SEO title</span><span className={editor.page.seo.description?.trim()?'ok':'missing'}>{editor.page.seo.description?.trim()?'✓':'!'} Meta description</span><span className="note">Draft changes never affect published pages until you click Publish locally.</span></div>
        {publicationInfo?.published&&<div className="publication-diff"><strong>Currently published SEO · Version {publicationInfo.published.version}</strong><p>These are the values in the last local publication. Your draft fields below can differ until republishing.</p><dl><dt>Title</dt><dd>{publicationInfo.published.seo.seo_title||'Not set'}</dd><dt>Meta description</dt><dd>{publicationInfo.published.seo.description||'Not set'}</dd><dt>Robots</dt><dd>{publicationInfo.published.seo.noindex?'Noindex':'Index'} / {publicationInfo.published.seo.nofollow?'Nofollow':'Follow'}</dd><dt>URL</dt><dd>/{publicationInfo.published.slug}/</dd></dl></div>}
        <div className="seo-primary-fields"><label>SEO title<input value={editor.page.seo.seo_title||''} onChange={e=>changeSEO({seo_title:e.target.value})} placeholder="Your unique search title"/></label><label>URL slug<input value={editor.page.slug} onChange={e=>changePage({slug:e.target.value})}/></label><label className="wide-field">Meta description<textarea rows={3} value={editor.page.seo.description||''} onChange={e=>changeSEO({description:e.target.value})} placeholder="Brief, useful page description"/></label></div>
        <div className="two-col"><div className="switch-block"><strong>Search indexing</strong><div className="segment"><button className={!editor.page.seo.noindex?'selected':''} onClick={()=>changeSEO({noindex:false})}>Index</button><button className={editor.page.seo.noindex?'selected':''} onClick={()=>changeSEO({noindex:true})}>Noindex</button></div></div><div className="switch-block"><strong>Link following</strong><div className="segment"><button className={!editor.page.seo.nofollow?'selected':''} onClick={()=>changeSEO({nofollow:false})}>Follow</button><button className={editor.page.seo.nofollow?'selected':''} onClick={()=>changeSEO({nofollow:true})}>Nofollow</button></div></div></div>
        <label>Canonical override (optional)<input value={editor.page.seo.canonical_override||''} onChange={e=>changeSEO({canonical_override:e.target.value})} placeholder="Automatic self-canonical"/></label>
        <div className="search-preview"><span>Search result preview</span><small>workspacebyemlen.co.in › {editor.page.slug}</small><h3>{editor.page.seo.seo_title||editor.page.title}</h3><p>{editor.page.seo.description||'Add a meta description to preview the search snippet.'}</p></div>
      </div>
    </section>

    <section className="edit-panel editor-preview-panel" id="page-preview" aria-labelledby="preview-heading">
      <div className="panel-heading"><div><div className="small-label">03 / RESULT</div><h2 id="preview-heading">Page Preview</h2><p>See the full page below. Content and SEO edits appear here automatically without saving.</p></div><div className="button-group"><button className="outline compact" onClick={()=>setPreviewRefresh(n=>n+1)} disabled={inlinePreviewLoading}>Refresh preview</button><button className="outline compact" onClick={()=>fullPreview()} disabled={busy}>Expand preview <ArrowUpRight size={15}/></button></div></div>
      <div className="inline-preview-bar"><span aria-live="polite">{inlinePreviewLoading?'Updating preview…':inlinePreviewError?'Preview unavailable':'Preview is up to date'}</span><span>Desktop · Full page · Draft only</span></div>
      <div className="inline-preview-frame">{inlinePreview&&<iframe title="Inline page preview" sandbox="" srcDoc={inlinePreview}/>}{!inlinePreview&&<div className="inline-preview-empty">{inlinePreviewLoading?'Generating page preview…':inlinePreviewError||'Preparing preview…'}</div>}</div>
      {inlinePreviewError&&<div className="inline-preview-error" role="alert">{inlinePreviewError} <button className="quiet-action" onClick={()=>setPreviewRefresh(n=>n+1)}>Try again</button></div>}
      <div className="editor-preview-foot"><span>Preview changes are not published to WordPress.</span><div className="button-group"><button className="outline" onClick={savePage} disabled={busy||!dirty}><Save size={15}/> Save draft</button>{user.role==='admin'&&<button className="primary" onClick={publishPage} disabled={busy}>Publish locally <ArrowUpRight size={16}/></button>}</div></div>
    </section>
  </div></>:
  <>
  {nav==='Category'&&<><div className="page-top"><div><div className="small-label">CONTENT MANAGEMENT</div><h1>Category</h1><p>Manage reusable website pages from approved templates.</p></div></div><div className="tabs">{(['All Pages','Add Page',...(user.role==='admin'?['Upload Template' as const]:[])] as Tab[]).map(x=><button key={x} className={tab===x?'active':''} onClick={()=>setTab(x)}>{x}</button>)}</div>
  {tab==='All Pages'&&<><div className="toolbar"><h2>All Pages <span className="count">{pages.length}</span></h2><div className="filter-row">{(['All','Published','Draft'] as const).map(x=><button className={filter===x?'active':''} onClick={()=>setFilter(x)} key={x}>{x}</button>)}</div></div><div className="list-table"><div className="list-header"><span>No.</span><span>Page name</span><span>Template</span><span>Status</span><span>Action</span></div>{visiblePages.map((p,i)=><div className="list-row" key={p.id}><span className="number">{String(i+1).padStart(2,'0')}</span><strong>{p.title}</strong><span>{templates.find(t=>t.id===p.template_id)?.name||'Template unavailable'}</span><span><span className={`status ${p.status}`}>{p.has_unpublished_changes?'Published · Draft changes':p.status}</span></span><div className="row-actions"><button className="row-action" onClick={()=>openPage(p)}>Edit <ArrowUpRight size={16}/></button>{user.role==='admin'&&!p.published_version&&<button className="quiet-action" onClick={()=>action(async()=>{if(!window.confirm(`Archive ${p.title}? This hides it from the page list.`))return;await api(`/api/pages/${p.id}/archive`,{method:'POST'});await refresh();notify('Page archived')})}>Archive</button>}</div></div>)}{!visiblePages.length&&<div className="empty">No pages found. Create your first page from an uploaded template.</div>}</div></>}
  {tab==='Add Page'&&<div className="add-page"><h2>Add Page</h2><p>Enter the page name, then select an approved template.</p><label className="add-name">Page name<input placeholder="e.g. One Person Office" value={newName} onChange={e=>setNewName(e.target.value)}/></label><h3>Choose template</h3><div className="template-rows">{templates.filter(t=>t.approved).map((t,i)=><button key={t.id} className={`template-row ${selectedTemplate===t.id?'selected':''}`} onClick={()=>setSelectedTemplate(t.id)}><span className="index">{String(i+1).padStart(2,'0')}</span><strong>{t.name}</strong><small>{t.category}</small><span className="select-circle">{selectedTemplate===t.id&&<Check size={14}/>}</span></button>)}{templates.filter(t=>t.approved).length===0&&<div className="empty">No approved templates available. Upload a template, configure its fields and approve it first.</div>}</div><button className="primary continue" onClick={createPage} disabled={busy||!selectedTemplate||!newName.trim()}>Continue to editor <ArrowUpRight size={17}/></button></div>}
  {tab==='Upload Template'&&user.role==='admin'&&<div className="upload-screen"><h2>Upload Template</h2><p>Upload an approved HTML design. Sections are detected by structure, not headings.</p><div className="upload-box"><UploadCloud size={34}/><strong>Choose your HTML template</strong><span>Only .html files · Maximum 8 MB</span><label className="file-button">Choose HTML file<input type="file" accept=".html,text/html" onChange={e=>setTemplateFile(e.target.files?.[0]||null)}/></label><small>{templateFile?.name||'No file selected'}</small></div><div className="upload-fields"><label>Template name<input value={uploadName} onChange={e=>setUploadName(e.target.value)} placeholder="e.g. Managed Office Category"/></label><label>Category<select value={uploadCategory} onChange={e=>setUploadCategory(e.target.value)}>{['Solution Category','Sub-solution','Country','City','Property'].map(x=><option key={x}>{x}</option>)}</select></label></div><button className="primary centered" onClick={uploadTemplate} disabled={!templateFile||busy}>Detect and map sections <ArrowUpRight size={17}/></button>{uploaded&&<div className="upload-result"><h3>{uploaded.name}</h3><p>{uploaded.sections.length} sections · {uploaded.fields.length} detected fields. Everything is static until configured.</p><button className="outline" onClick={()=>{setNav('Templates');setFocusField('');setMappingId(uploaded.id)}}>Configure editability <ArrowUpRight size={16}/></button></div>}</div>}
  </>}

  {nav==='Templates'&&<><div className="page-top"><div><div className="small-label">TEMPLATE LIBRARY</div><h1>Templates</h1><p>Choose which fields stay static, become shared, or vary by page.</p></div></div><div className="template-rows">{templates.map((t,i)=><button key={t.id} className={`template-row ${mapping?.id===t.id?'selected':''}`} onClick={()=>{setFocusField('');setMappingId(t.id)}}><span className="index">{String(i+1).padStart(2,'0')}</span><strong>{t.name}</strong><small>{t.category}</small><span className={`status ${t.approved?'published':'draft'}`}>{t.approved?'Approved':'Needs mapping'}</span><ArrowUpRight size={18}/></button>)}{!templates.length&&<div className="empty">No templates yet. Upload your first approved HTML design.</div>}</div>{mapping&&<div className="mapping-area">
    <div className="panel-heading"><div><div className="small-label">TEMPLATE CONFIGURATION</div><h2>{mapping.name}</h2><p>Fields are locked by default. Approve only the fields that should change between pages.</p></div><label className="approve"><input type="checkbox" checked={mapping.approved} onChange={e=>setTemplates(ts=>ts.map(t=>t.id===mapping.id?{...t,approved:e.target.checked}:t))}/> Approve template</label></div>
    <div className="mapping-steps"><span>1 · Upload HTML</span><span className="active">2 · Configure fields</span><span>3 · Approve &amp; save</span></div>
    <div className="mapping-layout"><div className="mapping-fields">
    {mapping.sections.map(sec=><details className="map-section" key={sec.id} open={sec.order===1}>
      <summary><strong>{String(sec.order).padStart(2,'0')} · {sec.name}</strong><small>{mapping.fields.filter(f=>f.section_id===sec.id&&f.mode==='page').length} variable / {mapping.fields.filter(f=>f.section_id===sec.id).length} detected</small></summary>
      <label className="section-name-label">Section name<input value={sec.name} onChange={e=>setTemplates(ts=>ts.map(t=>t.id===mapping.id?{...t,sections:t.sections.map(x=>x.id===sec.id?{...x,name:e.target.value}:x)}:t))}/></label>
      {mapping.fields.filter(f=>f.section_id===sec.id).map(f=><div className={`map-field ${focusField===f.key?'focused':''}`} key={f.key}>
        <div className="map-field-heading"><button className="field-focus" title="Highlight this content in the preview" onClick={()=>{setMappingId(mapping.id);setFocusField(f.key)}}><Eye size={15}/> Locate</button><span>{f.kind==='image'?'Image':f.attr==='text'?'Text':'Field'} · {f.key}</span></div>
        <label>Editable name<input value={f.label} onChange={e=>modifyMapField(mapping.id,f.key,{label:e.target.value})}/></label>
        <small title={f.default}>Current content: {f.default.length>140?f.default.slice(0,140)+'…':f.default}</small>
        <label>Field behavior<select value={f.mode} onChange={e=>modifyMapField(mapping.id,f.key,{mode:e.target.value as Mode})}><option value="static">Static · never changes</option><option value="page">Variable · per page</option><option value="global">Shared · all drafts</option></select></label>
        {f.mode==='global'&&<label>Global content key<input placeholder="e.g. business_phone" value={f.global_key||''} onChange={e=>modifyMapField(mapping.id,f.key,{global_key:e.target.value})}/></label>}
      </div>)}
    </details>)}
    </div><div className="mapping-visual"><div className="preview-label"><div><strong>Template Preview</strong><small>{focusField?'Highlighted selected content':'Select Locate next to a field'}</small></div><button className="quiet-action" onClick={()=>setFocusField('')}>Full page</button></div><iframe title="Mapped template preview" sandbox="" srcDoc={mapPreview}/><small>HTML scripts are disabled for safety; layout and content remain visible.</small></div></div>
    <div className="mapping-footer"><span>{mapping.fields.filter(f=>f.mode==='page').length} page-variable fields out of {mapping.fields.length} detected</span><button className="primary" disabled={busy} onClick={()=>saveMapping(mapping)}>Save template configuration <ArrowUpRight size={17}/></button></div>
  </div>}</>}


  {(nav==='Saved Drafts'||nav==='Published')&&<><div className="page-top"><div><div className="small-label">PAGE LIBRARY</div><h1>{nav}</h1><p>{nav==='Published'?'Published snapshots are immutable until a new version is explicitly published.':'Saved pages can be edited without affecting the published website.'}</p></div></div><div className="list-table"><div className="list-header"><span>No.</span><span>Page name</span><span>URL</span><span>Status</span><span>Action</span></div>{visiblePages.map((p,i)=><div className="list-row" key={p.id}><span className="number">{String(i+1).padStart(2,'0')}</span><strong>{p.title}</strong><span>/{p.slug}/</span><span className={`status ${p.status}`}>{p.has_unpublished_changes?'Published · Draft changes':p.status}</span><div className="row-actions"><button className="row-action" onClick={()=>openPage(p)}>Edit <ArrowUpRight size={16}/></button>{user.role==='admin'&&!p.published_version&&<button className="quiet-action" onClick={()=>action(async()=>{if(!window.confirm(`Archive ${p.title}? This hides it from the page list.`))return;await api(`/api/pages/${p.id}/archive`,{method:'POST'});await refresh();notify('Page archived')})}>Archive</button>}</div></div>)}{!visiblePages.length&&<div className="empty">No pages here yet.</div>}</div></>}

  {nav==='Archived'&&user.role==='admin'&&<><div className="page-top"><div><div className="small-label">PAGE LIBRARY</div><h1>Archived Drafts</h1><p>Restore an archived draft to make it editable again. Published pages must not be archived while live.</p></div></div><div className="list-table">{archivedPages.map(p=><div className="list-row" key={p.id}><span className="number">{p.id}</span><strong>{p.title}</strong><span>/{p.slug}/</span><span className="status draft">Archived</span><button className="row-action" onClick={()=>action(async()=>{await api(`/api/pages/${p.id}/restore`,{method:'POST'});setArchivedPages(ps=>ps.filter(x=>x.id!==p.id));await refresh();notify('Draft restored')})}>Restore</button></div>)}{!archivedPages.length&&<div className="empty">No archived drafts.</div>}</div></>}

  {nav==='Shared Content'&&<><div className="page-top"><div><div className="small-label">SITE-WIDE CONTENT</div><h1>Shared Content</h1><p>Shared values update draft previews only. Existing published pages will keep their previous snapshots until each page is republished.</p></div></div><div className="shared-list">{Object.entries(shared).map(([key,val])=><label key={key}>{label(key)}<input value={val} disabled={user.role!=='admin'} onChange={e=>setShared(s=>({...s,[key]:e.target.value}))}/><small>{sharedUsage.find(x=>x.key===key)?.pages||0} draft pages use this field · {sharedUsage.find(x=>x.key===key)?.published_pages||0} published page(s) require republishing to reflect changes.</small></label>)}<label>New shared key<input disabled={user.role!=='admin'} value={newSharedKey} placeholder="e.g. callback_phone" onChange={e=>setNewSharedKey(e.target.value)}/></label><button className="outline" disabled={user.role!=='admin'} onClick={()=>{if(newSharedKey.trim())setShared(s=>({...s,[newSharedKey.trim()]:''}));setNewSharedKey('')}}><Plus size={16}/> Add field</button><button className="primary" disabled={busy||user.role!=='admin'} onClick={()=>action(async()=>{setShared(await api('/api/shared',{method:'PUT',body:json({items:shared})}));notify('Shared fields saved')})}>Save shared content</button></div></>}

  {nav==='SEO'&&<><div className="page-top"><div><div className="small-label">SEARCH MANAGEMENT</div><h1>SEO & Redirects</h1><p>Metadata and robots options are edited per page. Redirects are managed here.</p></div></div><div className="stat-grid"><div className="stat"><span>Indexable published pages</span><strong>{seoStatus?.indexable??'—'}</strong></div><div className="stat"><span>Published noindex pages</span><strong>{seoStatus?.noindex??'—'}</strong></div><div className="stat"><span>301 Redirects</span><strong>{redirects.length}</strong></div></div><div className="link-row"><a href="/sitemap.xml" target="_blank" rel="noreferrer">View XML sitemap <ArrowUpRight size={16}/></a><a href="/robots.txt" target="_blank" rel="noreferrer">View robots.txt <ArrowUpRight size={16}/></a></div><div className="redirect-panel"><h2>301 Redirects</h2>{redirects.map(r=><div className="redirect-item" key={r.id}><code>/{r.from_path}/</code><ChevronRight size={16}/><code>/{r.to_path}/</code></div>)}<div className="redirect-form"><input placeholder="Old path (without /)" value={redirectFrom} onChange={e=>setRedirectFrom(e.target.value)}/><input placeholder="New path (without /)" value={redirectTo} onChange={e=>setRedirectTo(e.target.value)}/><button className="primary" disabled={busy||user.role!=='admin'} onClick={()=>action(async()=>{await api('/api/redirects',{method:'POST',body:json({from_path:redirectFrom,to_path:redirectTo})});setRedirects(await api('/api/redirects'));setRedirectFrom('');setRedirectTo('');notify('301 redirect saved')})}>Add redirect</button></div></div></>}

  {nav==='Team Access'&&<><div className="page-top"><div><div className="small-label">ACCOUNT PERMISSIONS</div><h1>Team Access</h1><p>Administrators can invite editors without sharing the main login.</p></div></div>{user.role==='admin'?<><div className="list-table"><div className="list-header"><span>No.</span><span>Email</span><span>Role</span><span>Status</span><span>Access</span></div>{team.map((member,i)=><div className="list-row" key={member.id}><span className="number">{String(i+1).padStart(2,'0')}</span><strong>{member.email}</strong><span>{member.role}</span><span className={`status ${member.active?'published':'draft'}`}>{member.active?'Active':'Disabled'}</span><div className="team-actions"><button className="quiet-action" disabled={busy||member.email===user.email} onClick={()=>action(async()=>{if(!window.confirm(`${member.active?'Disable':'Restore'} access for ${member.email}?`))return;await api(`/api/users/${member.id}/status`,{method:'PATCH',body:json({active:!member.active})});setTeam(await api('/api/users'));notify('Account status updated')})}>{member.active?'Disable':'Enable'}</button><button className="quiet-action" disabled={busy} onClick={()=>action(async()=>{const replacement=window.prompt(`Set a new temporary password (12+ chars) for ${member.email}`);if(!replacement)return;await api(`/api/users/${member.id}/reset-password`,{method:'POST',body:json({new_password:replacement})});notify('Password reset; user must sign in again')})}>Reset password</button></div></div>)}</div><form className="shared-list team-form" onSubmit={e=>{e.preventDefault();action(async()=>{await api('/api/users',{method:'POST',body:json({email:teamEmail,password:teamPassword,role:teamRole})});setTeam(await api('/api/users'));setTeamEmail('');setTeamPassword('');notify('Team account created. Share the initial password securely.')})}}><h2>Create team account</h2><label>Email<input type="email" value={teamEmail} onChange={e=>setTeamEmail(e.target.value)} required/></label><label>Initial password (at least 12 characters)<input type="password" value={teamPassword} onChange={e=>setTeamPassword(e.target.value)} required minLength={12}/></label><label>Role<select value={teamRole} onChange={e=>setTeamRole(e.target.value as 'admin'|'editor')}><option value="editor">Editor — drafts and content</option><option value="admin">Administrator — templates, users, publishing</option></select></label><button className="primary" disabled={busy}>Create account</button></form></>:<div className="locked-section"><ShieldCheck size={28}/><h3>Administrator access required.</h3></div>}</>}

  {nav==='Media Library'&&<><div className="page-top"><div><div className="small-label">IMAGE STORAGE</div><h1>Media Library</h1><p>Images are stored outside the application container with their alternative text.</p></div></div><form className="media-upload" onSubmit={e=>{e.preventDefault();const form=new FormData(e.currentTarget);action(async()=>{await api('/api/media',{method:'POST',body:form});setMedia(await api('/api/media'));notify('Image uploaded')})}}><input type="file" name="file" accept="image/jpeg,image/png,image/webp" required/><input type="text" name="alt_text" placeholder="Alt text: what does this image convey?"/><button className="primary" disabled={busy}>Upload image</button></form><div className="media-grid">{media.map(m=><div className="media-card" key={m.id}><img src={m.url} alt={m.alt_text||''}/><strong>{m.filename}</strong><small>{m.alt_text||'Decorative / no alt text set'}</small><button className="quiet-action" onClick={()=>action(async()=>{const value=window.prompt('Edit image alt text (leave blank for decorative images)',m.alt_text);if(value===null)return;await api(`/api/media/${m.id}`,{method:'PATCH',body:json({alt_text:value})});setMedia(await api('/api/media'));notify('Alt text updated')})}>Edit alt text</button><button className="outline compact" onClick={()=>{navigator.clipboard.writeText(location.origin+m.url);notify('Image URL copied')}}>Copy URL <Copy size={14}/></button></div>)}</div></>}
  </>}
  </div></main>
  {showPassword&&<div className="dialog-backdrop"><form className="dialog-card" onSubmit={e=>{e.preventDefault();rotatePassword()}}><h2>Change your password</h2><p>All existing sessions will be signed out after the change.</p><label>Current password<input type="password" value={oldPassword} required onChange={e=>setOldPassword(e.target.value)}/></label><label>New password (minimum 12 characters)<input type="password" value={newPassword} minLength={12} required onChange={e=>setNewPassword(e.target.value)}/></label><div className="button-group"><button type="button" className="outline" onClick={()=>setShowPassword(false)}>Cancel</button><button className="primary" disabled={busy}>Change password</button></div></form></div>}
  {preview!==null&&<div className="preview-modal"><div className="preview-head"><div><strong>Full-page preview</strong><span>Sandboxed · Draft · Not indexed</span></div><button onClick={()=>setPreview(null)} aria-label="Close preview"><X size={23}/></button></div><iframe title="Website preview" sandbox="" srcDoc={preview}/></div>}
  </div>
}