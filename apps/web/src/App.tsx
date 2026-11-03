import {useEffect, useState} from 'react'
import {ArrowUpRight, Check, ChevronRight, CircleHelp, Copy, FileCode2, FilePenLine, Globe2, LayoutTemplate, LockKeyhole, LogOut, Plus, Search, Settings2, ShieldCheck, UploadCloud, X} from 'lucide-react'

type Mode='static'|'global'|'page'
type Field={key:string;section_id:string;label:string;kind:string;attr:string;default:string;mode:Mode;global_key:string|null}
type Section={id:string;name:string;order:number}
type Template={id:number;name:string;category:string;approved:boolean;version:number;sections:Section[];fields:Field[]}
type SEO={seo_title:string;description:string;noindex:boolean;nofollow:boolean;canonical_override:string;og_title?:string;og_description?:string}
type Page={id:number;template_id:number;title:string;slug:string;values:Record<string,string>;seo:SEO;status:'draft'|'published';published_version:number;updated_at:string}
type Nav='Category'|'Templates'|'Saved Drafts'|'Published'|'Shared Content'|'SEO'|'Media Library'
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
async function html(path:string):Promise<string>{
  const res=await fetch(path,{headers:{Authorization:`Bearer ${accessToken}`}})
  if(!res.ok)throw new Error(`Preview failed (${res.status})`)
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
  const [selectedSection,setSelectedSection]=useState('')
  const [editSEO,setEditSEO]=useState(false)
  const [newName,setNewName]=useState('')
  const [selectedTemplate,setSelectedTemplate]=useState<number|null>(null)
  const [uploaded,setUploaded]=useState<Template|null>(null)
  const [uploadName,setUploadName]=useState('')
  const [uploadCategory,setUploadCategory]=useState('Solution Category')
  const [templateFile,setTemplateFile]=useState<File|null>(null)
  const [mappingId,setMappingId]=useState<number|null>(null)
  const [preview,setPreview]=useState<string|null>(null)
  const [shared,setShared]=useState<Record<string,string>>({})
  const [newSharedKey,setNewSharedKey]=useState('')
  const [redirects,setRedirects]=useState<{id:number;from_path:string;to_path:string}[]>([])
  const [redirectFrom,setRedirectFrom]=useState('')
  const [redirectTo,setRedirectTo]=useState('')
  const [media,setMedia]=useState<{id:number;filename:string;alt_text:string;url:string}[]>([])
  const [filter,setFilter]=useState<'All'|'Published'|'Draft'>('All')

  async function refresh(){
    const [t,p]=await Promise.all([api<Template[]>('/api/templates'),api<Page[]>('/api/pages')])
    setTemplates(t);setPages(p)
    if(uploaded){const next=t.find(x=>x.id===uploaded.id);if(next)setUploaded(next)}
  }
  useEffect(()=>{if(!accessToken)return;api<{email:string;role:string}>('/api/auth/me').then(u=>{setUser(u);refresh().catch(showError)}).catch(()=>{accessToken='';sessionStorage.removeItem('emlen_access_token')})},[])
  useEffect(()=>{if(!user)return;setMessage('');if(nav==='Shared Content')api<Record<string,string>>('/api/shared').then(setShared).catch(showError);if(nav==='SEO')api<typeof redirects>('/api/redirects').then(setRedirects).catch(showError);if(nav==='Media Library')api<typeof media>('/api/media').then(setMedia).catch(showError)},[nav,user])
  function showError(e:unknown){setError(e instanceof Error?e.message:String(e));setMessage('')}
  async function action(fn:()=>Promise<void>){setBusy(true);setError('');setMessage('');try{await fn()}catch(e){showError(e)}finally{setBusy(false)}}
  function notify(msg:string){setMessage(msg);setError('')}
  function logout(){accessToken='';sessionStorage.removeItem('emlen_access_token');setUser(null);setEditor(null);setNav('Category')}
  async function login(){await action(async()=>{
    const result=await api<{access_token:string;user:{email:string;role:string}}>('/api/auth/login',{method:'POST',body:json({email:loginEmail,password:loginPassword})})
    accessToken=result.access_token;sessionStorage.setItem('emlen_access_token',accessToken);setUser(result.user);await refresh()
  })}
  async function openPage(p:Page){await action(async()=>{const data=await api<{page:Page;template:Template}>(`/api/pages/${p.id}`);setEditor(data);setSelectedSection(data.template.sections[0]?.id||'');setEditSEO(false)})}
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
    const result=await api<Page>(`/api/pages/${p.id}`,{method:'PUT',body:json({title:p.title,slug:p.slug,values:p.values,seo:p.seo})})
    setEditor(prev=>prev?{...prev,page:result}:prev);await refresh();notify('Draft changes saved')
  })}
  async function publishPage(){if(!editor)return;await action(async()=>{
    const p=editor.page
    await api(`/api/pages/${p.id}`,{method:'PUT',body:json({title:p.title,slug:p.slug,values:p.values,seo:p.seo})})
    await api(`/api/pages/${p.id}/publish`,{method:'POST'})
    const latest=await api<{page:Page;template:Template}>(`/api/pages/${p.id}`)
    setEditor(latest);await refresh();notify('Published to the local preview endpoint. The live WordPress website is unchanged.')
  })}
  async function fullPreview(section?:string){if(!editor)return;await action(async()=>{const qs=section?`?section_id=${encodeURIComponent(section)}`:'';setPreview(await html(`/api/pages/${editor.page.id}/preview${qs}`))})}
  const changePage=(patch:Partial<Page>)=>setEditor(cur=>cur?{...cur,page:{...cur.page,...patch}}:cur)
  const changeSEO=(patch:Partial<SEO>)=>setEditor(cur=>cur?{...cur,page:{...cur.page,seo:{...cur.page.seo,...patch}}}:cur)
  const changeField=(key:string,val:string)=>setEditor(cur=>cur?{...cur,page:{...cur.page,values:{...cur.page.values,[key]:val}}}:cur)
  const mapping=templates.find(t=>t.id===mappingId)||uploaded
  const visiblePages=pages.filter(p=>(nav==='Saved Drafts'?p.status==='draft':nav==='Published'?p.status==='published':filter==='All'?true:p.status.toLowerCase()===filter.toLowerCase()))

  if(!user)return <div className="login-bg"><div className="login-card"><div className="logo dark"><span className="logo-dot"/>workspace<span className="by-emlen">BY EMLEN</span></div><div className="login-icon"><LockKeyhole size={28}/></div><h1>Welcome back.</h1><p>Sign in to manage pages, templates and SEO.</p><form onSubmit={e=>{e.preventDefault();login()}}><label>Admin email</label><input type="email" placeholder="admin@workspacebyemlen.co.in" value={loginEmail} onChange={e=>setLoginEmail(e.target.value)} required/><label>Password</label><input type="password" placeholder="Your password" value={loginPassword} onChange={e=>setLoginPassword(e.target.value)} required/><button className="primary fill" disabled={busy}>Sign in <ArrowUpRight size={18}/></button></form>{error&&<div className="alert error">{error}</div>}<small>Secure sign-in · Access configured during deployment</small></div></div>

  return <div className="shell"><aside className="sidebar"><div className="brand"><span className="brand-mark"/> <div><strong>workspace</strong><small>BY EMLEN</small></div></div><div className="side-label">WORKSPACE</div><div className="navigation">
    {([['Category',LayoutTemplate],['Templates',FileCode2],['Saved Drafts',FilePenLine],['Published',Globe2],['Shared Content',Copy],['SEO',Search],['Media Library',Settings2]] as const).map(([name,Icon])=><button key={name} className={`nav-item ${nav===name?'active':''}`} onClick={()=>{setEditor(null);setNav(name);if(name==='Category')setTab('All Pages')}}><Icon size={18}/>{name}<ChevronRight className="right-chevron" size={15}/></button>)}
  </div><button className="logout" onClick={logout}><LogOut size={17}/> Sign out</button></aside>
  <main className="main"><div className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14}/> <span>{editor?'Page Editor':nav}</span></div><div className="topbar-right"><span className="role">{user.role}</span><div className="avatar">{user.email[0].toUpperCase()}</div></div></div>
  <div className="content">{error&&<div className="alert error"><CircleHelp size={16}/>{error}<button onClick={()=>setError('')}><X size={16}/></button></div>}{message&&<div className="alert success"><Check size={16}/>{message}<button onClick={()=>setMessage('')}><X size={16}/></button></div>}

  {editor?<><div className="page-top"><div><button className="backlink" onClick={()=>{setEditor(null);setNav('Category');setTab('All Pages')}}>← All Pages</button><h1>{editor.page.title}</h1><p>Edit content only where the approved template permits changes.</p></div><div className="button-group"><button className="outline" onClick={()=>fullPreview()} disabled={busy}>Full-page preview <ArrowUpRight size={16}/></button><button className="outline" onClick={savePage} disabled={busy}>Save draft</button><button className="primary" onClick={publishPage} disabled={busy||user.role!=='admin'}>Publish <ArrowUpRight size={16}/></button></div></div>
  <div className="editor-layout"><div className="section-list"><strong>PAGE SECTIONS</strong><button className={`section-nav ${editSEO?'active':''}`} onClick={()=>setEditSEO(true)}>SEO Settings</button>{editor.template.sections.map((s,i)=><button key={s.id} className={`section-nav ${!editSEO&&selectedSection===s.id?'active':''}`} onClick={()=>{setSelectedSection(s.id);setEditSEO(false)}}><span className="index">{String(i+1).padStart(2,'0')}</span>{s.name}</button>)}</div>
  <div className="edit-panel">{editSEO?<><div className="panel-heading"><div><div className="small-label">SEARCH APPEARANCE</div><h2>SEO Settings</h2></div></div><div className="form-stack"><label>SEO title<input value={editor.page.seo.seo_title||''} onChange={e=>changeSEO({seo_title:e.target.value})} placeholder="Your unique search title"/></label><label>Meta description<textarea rows={3} value={editor.page.seo.description||''} onChange={e=>changeSEO({description:e.target.value})} placeholder="Brief, useful page description"/></label><label>URL slug<input value={editor.page.slug} onChange={e=>changePage({slug:e.target.value})}/></label><div className="two-col"><div className="switch-block"><strong>Search indexing</strong><div className="segment"><button className={!editor.page.seo.noindex?'selected':''} onClick={()=>changeSEO({noindex:false})}>Index</button><button className={editor.page.seo.noindex?'selected':''} onClick={()=>changeSEO({noindex:true})}>Noindex</button></div></div><div className="switch-block"><strong>Link following</strong><div className="segment"><button className={!editor.page.seo.nofollow?'selected':''} onClick={()=>changeSEO({nofollow:false})}>Follow</button><button className={editor.page.seo.nofollow?'selected':''} onClick={()=>changeSEO({nofollow:true})}>Nofollow</button></div></div></div><label>Canonical override (optional)<input value={editor.page.seo.canonical_override||''} onChange={e=>changeSEO({canonical_override:e.target.value})} placeholder="Automatic self-canonical"/></label><div className="search-preview"><span>Search result preview</span><small>workspacebyemlen.co.in › {editor.page.slug}</small><h3>{editor.page.seo.seo_title||editor.page.title}</h3><p>{editor.page.seo.description||'Add a meta description to preview the search snippet.'}</p></div></div></>:<><div className="panel-heading"><div><div className="small-label">SECTION EDITOR</div><h2>{editor.template.sections.find(x=>x.id===selectedSection)?.name}</h2></div><button className="outline compact" onClick={()=>fullPreview(selectedSection)} disabled={busy}>Preview section <ArrowUpRight size={15}/></button></div>
  {editor.template.fields.filter(f=>f.section_id===selectedSection&&f.mode==='page').length===0?<div className="locked-section"><ShieldCheck size={28}/><h3>This section is reusable and locked.</h3><p>There are no page-variable fields here. An administrator can change the template field mapping in Templates.</p></div>:<div className="form-stack">{editor.template.fields.filter(f=>f.section_id===selectedSection&&f.mode==='page').map(f=><label key={f.key}>{f.label}{f.kind==='textarea'?<textarea rows={4} value={editor.page.values[f.key]??f.default} onChange={e=>changeField(f.key,e.target.value)}/>:<input value={editor.page.values[f.key]??f.default} onChange={e=>changeField(f.key,e.target.value)} type="text"/>}{f.kind==='image'&&<small>Image URL. Upload media in the Media Library to get a reusable URL.</small>}</label>)}</div>}</>}
  </div></div></>:
  <>
  {nav==='Category'&&<><div className="page-top"><div><div className="small-label">CONTENT MANAGEMENT</div><h1>Category</h1><p>Manage reusable website pages from approved templates.</p></div></div><div className="tabs">{(['All Pages','Add Page','Upload Template'] as Tab[]).map(x=><button key={x} className={tab===x?'active':''} onClick={()=>setTab(x)}>{x}</button>)}</div>
  {tab==='All Pages'&&<><div className="toolbar"><h2>All Pages <span className="count">{pages.length}</span></h2><div className="filter-row">{(['All','Published','Draft'] as const).map(x=><button className={filter===x?'active':''} onClick={()=>setFilter(x)} key={x}>{x}</button>)}</div></div><div className="list-table"><div className="list-header"><span>No.</span><span>Page name</span><span>Template</span><span>Status</span><span>Action</span></div>{visiblePages.map((p,i)=><div className="list-row" key={p.id}><span className="number">{String(i+1).padStart(2,'0')}</span><strong>{p.title}</strong><span>{templates.find(t=>t.id===p.template_id)?.name||'Template unavailable'}</span><span><span className={`status ${p.status}`}>{p.status}</span></span><button className="row-action" onClick={()=>openPage(p)}>Edit <ArrowUpRight size={16}/></button></div>)}{!visiblePages.length&&<div className="empty">No pages found. Create your first page from an uploaded template.</div>}</div></>}
  {tab==='Add Page'&&<div className="add-page"><h2>Add Page</h2><p>Enter the page name, then select an approved template.</p><label className="add-name">Page name<input placeholder="e.g. One Person Office" value={newName} onChange={e=>setNewName(e.target.value)}/></label><h3>Choose template</h3><div className="template-rows">{templates.filter(t=>t.approved).map((t,i)=><button key={t.id} className={`template-row ${selectedTemplate===t.id?'selected':''}`} onClick={()=>setSelectedTemplate(t.id)}><span className="index">{String(i+1).padStart(2,'0')}</span><strong>{t.name}</strong><small>{t.category}</small><span className="select-circle">{selectedTemplate===t.id&&<Check size={14}/>}</span></button>)}{templates.filter(t=>t.approved).length===0&&<div className="empty">No approved templates available. Upload a template, configure its fields and approve it first.</div>}</div><button className="primary continue" onClick={createPage} disabled={busy||!selectedTemplate||!newName.trim()}>Continue to editor <ArrowUpRight size={17}/></button></div>}
  {tab==='Upload Template'&&<div className="upload-screen"><h2>Upload Template</h2><p>Upload an approved HTML design. Sections are detected by structure, not headings.</p><div className="upload-box"><UploadCloud size={34}/><strong>Choose your HTML template</strong><span>Only .html files · Maximum 8 MB</span><label className="file-button">Choose HTML file<input type="file" accept=".html,text/html" onChange={e=>setTemplateFile(e.target.files?.[0]||null)}/></label><small>{templateFile?.name||'No file selected'}</small></div><div className="upload-fields"><label>Template name<input value={uploadName} onChange={e=>setUploadName(e.target.value)} placeholder="e.g. Managed Office Category"/></label><label>Category<select value={uploadCategory} onChange={e=>setUploadCategory(e.target.value)}>{['Solution Category','Sub-solution','Country','City','Property'].map(x=><option key={x}>{x}</option>)}</select></label></div><button className="primary centered" onClick={uploadTemplate} disabled={!templateFile||busy}>Detect and map sections <ArrowUpRight size={17}/></button>{uploaded&&<div className="upload-result"><h3>{uploaded.name}</h3><p>{uploaded.sections.length} sections · {uploaded.fields.length} detected fields. Everything is static until configured.</p><button className="outline" onClick={()=>{setNav('Templates');setMappingId(uploaded.id)}}>Configure editability <ArrowUpRight size={16}/></button></div>}</div>}
  </>}

  {nav==='Templates'&&<><div className="page-top"><div><div className="small-label">TEMPLATE LIBRARY</div><h1>Templates</h1><p>Choose which fields stay static, become shared, or vary by page.</p></div></div><div className="template-rows">{templates.map((t,i)=><button key={t.id} className={`template-row ${mapping?.id===t.id?'selected':''}`} onClick={()=>setMappingId(t.id)}><span className="index">{String(i+1).padStart(2,'0')}</span><strong>{t.name}</strong><small>{t.category}</small><span className={`status ${t.approved?'published':'draft'}`}>{t.approved?'Approved':'Needs mapping'}</span><ArrowUpRight size={18}/></button>)}{!templates.length&&<div className="empty">No templates yet. Upload your first approved HTML design.</div>}</div>{mapping&&<div className="mapping-area"><div className="panel-heading"><div><div className="small-label">TEMPLATE CONFIGURATION</div><h2>{mapping.name}</h2><p>Detected content is locked by default. Set only the necessary fields to Page variable.</p></div><label className="approve"><input type="checkbox" checked={mapping.approved} onChange={e=>setTemplates(ts=>ts.map(t=>t.id===mapping.id?{...t,approved:e.target.checked}:t))}/> Approve template</label></div>{mapping.sections.map(s=><div className="map-section" key={s.id}><h3>{String(s.order).padStart(2,'0')} · {s.name}</h3>{mapping.fields.filter(f=>f.section_id===s.id).map(f=><div className="map-field" key={f.key}><div><strong>{f.label}</strong><small title={f.default}>{f.default.slice(0,105)}{f.default.length>105?'…':''}</small></div><select value={f.mode} onChange={e=>setTemplates(prev=>prev.map(t=>t.id===mapping.id?{...t,fields:t.fields.map(x=>x.key===f.key?{...x,mode:e.target.value as Mode}:x)}:t))}><option value="static">Static</option><option value="page">Page variable</option><option value="global">Shared global</option></select>{f.mode==='global'&&<input placeholder="Shared field key" value={f.global_key||''} onChange={e=>setTemplates(prev=>prev.map(t=>t.id===mapping.id?{...t,fields:t.fields.map(x=>x.key===f.key?{...x,global_key:e.target.value}:x)}:t))}/>}</div>)}</div>)}<button className="primary" disabled={busy} onClick={()=>saveMapping(mapping)}>Save template configuration <ArrowUpRight size={17}/></button></div>}</>}

  {(nav==='Saved Drafts'||nav==='Published')&&<><div className="page-top"><div><div className="small-label">PAGE LIBRARY</div><h1>{nav}</h1><p>{nav==='Published'?'Published snapshots are immutable until a new version is explicitly published.':'Saved pages can be edited without affecting the published website.'}</p></div></div><div className="list-table"><div className="list-header"><span>No.</span><span>Page name</span><span>URL</span><span>Status</span><span>Action</span></div>{visiblePages.map((p,i)=><div className="list-row" key={p.id}><span className="number">{String(i+1).padStart(2,'0')}</span><strong>{p.title}</strong><span>/{p.slug}/</span><span className={`status ${p.status}`}>{p.status}</span><button className="row-action" onClick={()=>openPage(p)}>Edit <ArrowUpRight size={16}/></button></div>)}{!visiblePages.length&&<div className="empty">No pages here yet.</div>}</div></>}

  {nav==='Shared Content'&&<><div className="page-top"><div><div className="small-label">SITE-WIDE CONTENT</div><h1>Shared Content</h1><p>Change once and reuse in every template field marked Shared global.</p></div></div><div className="shared-list">{Object.entries(shared).map(([key,val])=><label key={key}>{label(key)}<input value={val} onChange={e=>setShared(s=>({...s,[key]:e.target.value}))}/></label>)}<label>New shared key<input value={newSharedKey} placeholder="e.g. callback_phone" onChange={e=>setNewSharedKey(e.target.value)}/></label><button className="outline" onClick={()=>{if(newSharedKey.trim())setShared(s=>({...s,[newSharedKey.trim()]:''}));setNewSharedKey('')}}><Plus size={16}/> Add field</button><button className="primary" disabled={busy||user.role!=='admin'} onClick={()=>action(async()=>{setShared(await api('/api/shared',{method:'PUT',body:json({items:shared})}));notify('Shared fields saved')})}>Save shared content</button></div></>}

  {nav==='SEO'&&<><div className="page-top"><div><div className="small-label">SEARCH MANAGEMENT</div><h1>SEO & Redirects</h1><p>Metadata and robots options are edited per page. Redirects are managed here.</p></div></div><div className="stat-grid"><div className="stat"><span>Indexable published pages</span><strong>{pages.filter(p=>p.status==='published'&&!p.seo.noindex).length}</strong></div><div className="stat"><span>Published noindex pages</span><strong>{pages.filter(p=>p.status==='published'&&p.seo.noindex).length}</strong></div><div className="stat"><span>301 Redirects</span><strong>{redirects.length}</strong></div></div><div className="link-row"><a href="/sitemap.xml" target="_blank" rel="noreferrer">View XML sitemap <ArrowUpRight size={16}/></a><a href="/robots.txt" target="_blank" rel="noreferrer">View robots.txt <ArrowUpRight size={16}/></a></div><div className="redirect-panel"><h2>301 Redirects</h2>{redirects.map(r=><div className="redirect-item" key={r.id}><code>/{r.from_path}/</code><ChevronRight size={16}/><code>/{r.to_path}/</code></div>)}<div className="redirect-form"><input placeholder="Old path (without /)" value={redirectFrom} onChange={e=>setRedirectFrom(e.target.value)}/><input placeholder="New path (without /)" value={redirectTo} onChange={e=>setRedirectTo(e.target.value)}/><button className="primary" disabled={busy||user.role!=='admin'} onClick={()=>action(async()=>{await api('/api/redirects',{method:'POST',body:json({from_path:redirectFrom,to_path:redirectTo})});setRedirects(await api('/api/redirects'));setRedirectFrom('');setRedirectTo('');notify('301 redirect saved')})}>Add redirect</button></div></div></>}

  {nav==='Media Library'&&<><div className="page-top"><div><div className="small-label">IMAGE STORAGE</div><h1>Media Library</h1><p>Images are stored outside the application container with their alternative text.</p></div></div><form className="media-upload" onSubmit={e=>{e.preventDefault();const form=new FormData(e.currentTarget);action(async()=>{await api('/api/media',{method:'POST',body:form});setMedia(await api('/api/media'));notify('Image uploaded')})}}><input type="file" name="file" accept="image/jpeg,image/png,image/webp" required/><input type="text" name="alt_text" placeholder="Alt text: what does this image convey?"/><button className="primary" disabled={busy}>Upload image</button></form><div className="media-grid">{media.map(m=><div className="media-card" key={m.id}><img src={m.url} alt={m.alt_text||''}/><strong>{m.filename}</strong><small>{m.alt_text||'Decorative / no alt text set'}</small><button className="outline compact" onClick={()=>{navigator.clipboard.writeText(location.origin+m.url);notify('Image URL copied')}}>Copy URL <Copy size={14}/></button></div>)}</div></>}
  </>}
  </div></main>
  {preview!==null&&<div className="preview-modal"><div className="preview-head"><div><strong>Full-page preview</strong><span>Sandboxed · Draft · Not indexed</span></div><button onClick={()=>setPreview(null)} aria-label="Close preview"><X size={23}/></button></div><iframe title="Website preview" sandbox="" srcDoc={preview}/></div>}
  </div>
}
