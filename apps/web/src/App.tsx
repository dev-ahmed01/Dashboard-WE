import {useEffect, useRef, useState} from 'react'
import {ArrowUpRight, Check, ChevronRight, CircleHelp, Copy, FileCode2, LayoutTemplate, LockKeyhole, EyeOff, LogOut, Plus, Search, ShieldCheck, UploadCloud, X, Eye, Save, AlertTriangle, MoreHorizontal, Trash2, Undo2, Redo2, Type, Image, Square, Link2, Layers, MousePointer2, Move, RotateCw, ArrowUp, ArrowDown, Grid3X3} from 'lucide-react'
import SeoSettings from './SeoSettings'
import AddPageWorkspace from './AddPageWorkspace'

type Mode='static'|'global'|'page'
type Field={key:string;section_id:string;label:string;kind:string;attr:string;default:string;mode:Mode;global_key:string|null;tag?:string;heading_tag?:string|null;marker?:string}
type DesignStyle={
  span?:number;height?:number;locked?:boolean;order?:number;widthPx?:number;heightPx?:number;
  x?:number;y?:number;rotate?:number;opacity?:number;zIndex?:number;
  radius?:number;padding?:number;fontPx?:number;fontWeight?:number;letterSpacing?:number;
  lineHeight?:number;color?:string;background?:string;fontFamily?:string;textAlign?:string;hidden?:boolean
}
type CanvasElement={
  id:string;type:'text'|'image'|'shape'|'button';sectionId:string;
  text?:string;url?:string;x:number;y:number;width:number;height:number;
  fontSize:number;fontFamily:string;fontWeight:number;color:string;background:string;
  opacity:number;rotate:number;radius:number;textAlign:string;zIndex:number;
  locked?:boolean;hidden?:boolean
}
type VisualDesign={
  groups?:Record<string,{columns?:number;gap?:number}>,
  items?:Record<string,DesignStyle>,fields?:Record<string,DesignStyle>,
  page?:{background?:string},elements?:CanvasElement[]
}
type RepeaterItem={id:string;title:string;field_keys:string[];variant?:string}
type Repeater={id:string;section_id:string;kind:string;name:string;items:RepeaterItem[];parent_item_id?:string|null;count:number;max_additions:number}
type Section={id:string;name:string;order:number;repeaters?:Repeater[]}
type Template={id:number;name:string;category:string;approved:boolean;version:number;sections:Section[];fields:Field[]}
type SEO={seo_title:string;description:string;noindex:boolean;nofollow:boolean;noarchive?:boolean;noimageindex?:boolean;nosnippet?:boolean;canonical_override:string;og_title?:string;og_description?:string}
type Page={id:number;template_id:number;template_name?:string;template_category?:string;title:string;slug:string;values:Record<string,string>;seo:SEO;status:'draft'|'published';published_version:number;edit_version:number;updated_at:string;has_unpublished_changes:boolean;archived:boolean}
type Nav='Category'|'Solution'|'Property'|'Templates'|'Saved Drafts'|'Published'|'Archived'|'Shared Content'|'SEO'|'Team Access'|'Media Library'
type Tab='All Pages'|'Add Page'|'Upload Template'
type ModuleNav='Category'|'Solution'|'Property'
const MODULE_INFO:Record<ModuleNav,{category:string;subtitle:string;source:string;sections:string[]}>={
  Category:{category:'Solution Category',
    subtitle:'Manage the approved Managed Offices category design and its pages.',
    source:'Managed Offices in South Bangalore',
    sections:['Hero','Office Types','Other Solutions','Guided Discovery','Benefits','Why Us','FAQs']},
  Solution:{category:'Solution',
    subtitle:'Build solution pages from the One Person Office design, with editable options, benefits and FAQs.',
    source:'One Person Office',
    sections:['1A · Hero: image, heading, description, highlights, offer tag','1B · Values: heading and description',
      '3 · Options: up to four cards, image, name, description, CTA','4 · Customisation',
      '6 · Benefits: heading, description, bullets, image','7 · How to Get Started',
      '8 · Locations','9 · FAQs: questions and answers']},
  Property:{category:'Property',
    subtitle:'Create property pages with galleries, amenity cards, solutions and a locked Testimonials section.',
    source:'Workspace Property',
    sections:['1A · Hero: heading, subheading, right description','2 · Photos: featured and gallery (4 minimum)',
      '4 · Amenities','5 · Solutions: Private Office / Coworking / Meeting Rooms / Additional',
      '6 · Location & Landmarks: map','7 · Testimonials: read-only','9 · FAQs: questions and answers']}
}
const MODULE_NAV:ModuleNav[]=['Category','Solution','Property']
const isModuleNav=(nav:Nav):nav is ModuleNav=>MODULE_NAV.includes(nav as ModuleNav)
const moduleOfCategory=(category:string):ModuleNav=>{
  if(category==='Property')return 'Property'
  if(category==='Solution'||category==='Sub-solution')return 'Solution'
  return 'Category'
}


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


type EditorBlock={id:string;kind:'text'|'cta'|'card'|'image';title:string;fields:Field[];fixedDestination?:string}
const isCtaText=(f:Field)=>f.attr==='text'&&(f.tag==='a'||f.tag==='button')
const excerpt=(v:string,n=60)=>v.replace(/\s+/g,' ').trim().slice(0,n)+(v.replace(/\s+/g,' ').trim().length>n?'…':'')

const SIMPLE_ICONS=[
  {value:'icon:arrow-up-right',label:'Arrow up-right ↗'},
  {value:'icon:arrow-right',label:'Arrow right →'},
  {value:'icon:phone',label:'Phone'},
  {value:'icon:map-pin',label:'Location pin'},
  {value:'icon:check',label:'Check mark'},
  {value:'icon:calendar',label:'Calendar'},
  {value:'icon:chevron-right',label:'Chevron'},
  {value:'icon:layers',label:'Layers'},
]
function isTestableHref(url:string){
  const trimmed=url.trim()
  return /^(https?:\/\/[^ \r\n\t]+|mailto:[^ \r\n\t]+|tel:[+0-9() -]+)$/i.test(trimmed)
}
function isSafePreviewHref(url:string){
  return isTestableHref(url)||url.startsWith('#')||(url.startsWith('/')&&!url.startsWith('//'))
}


/** Order the editor as the real HTML is ordered: headline, calls-to-action,
 * then repeated highlight cards, descriptions and images. Static content is
 * used only to identify a block. It never produces an editable input. */
function variableRepeaterGroups(section:Section,fields:Field[]):Repeater[]{
  const variable=new Set(fields.filter(f=>f.mode==='page').map(f=>f.key))
  return (section.repeaters||[]).filter(group=>
    group.items.some(item=>item.field_keys.some(key=>variable.has(key))))
}
function sourceOrderedEditor(section:Section,all:Field[]){
  const repeaters=variableRepeaterGroups(section,all)
  const repeated=new Set(repeaters.flatMap(group=>group.items.flatMap(item=>item.field_keys)))
  const blocks=pageEditorBlocks(all.filter(f=>!repeated.has(f.key)))
  const sourceIndex=new Map(all.map((f,i)=>[f.key,i]))
  const items=[
    ...blocks.map(block=>({id:block.id,kind:'block' as const,block,group:null as Repeater|null,
      order:sourceIndex.get(block.fields[0].key)??9999})),
    ...repeaters.filter(g=>!g.parent_item_id).map(group=>({id:group.id,kind:'group' as const,
      block:null as EditorBlock|null,group,order:Math.min(...group.items.flatMap(it=>it.field_keys.map(f=>sourceIndex.get(f)??9999)))}))
  ].sort((a,b)=>a.order-b.order)
  return {items,repeaters}
}
function pageEditorBlocks(source:Field[]):EditorBlock[]{
  const blocks:EditorBlock[]=[]
  let card:EditorBlock|null=null
  let lastCTA:EditorBlock|null=null
  for(const f of source){
    const editable=f.mode==='page'
    const isCardTitle=/^Card title:/i.test(f.label)
    if(isCardTitle){
      card={id:f.key,kind:'card',title:excerpt(f.default,65)||'Highlight card',fields:[]}
      blocks.push(card);lastCTA=null
      if(editable)card.fields.push(f)
      continue
    }
    if(isCtaText(f)){
      card=null
      lastCTA={id:f.key,kind:'cta',title:excerpt(f.default,60)||'Button',fields:[]}
      blocks.push(lastCTA)
      if(editable)lastCTA.fields.push(f)
      continue
    }
    if(f.kind==='link'){
      // Importer emits a button's text immediately before its destination.
      // Even if the text is static, pair its editable link with the named CTA.
      if(!lastCTA||lastCTA.fields.some(x=>x.kind==='link')){
        lastCTA={id:f.key,kind:'cta',title:excerpt(f.label.replace(/^.*?:\s*/,''),60)||'Button',fields:[]}
        blocks.push(lastCTA)
      }
      card=null
      if(editable)lastCTA.fields.push(f)
      else lastCTA.fixedDestination=f.default||'No destination specified'
      continue
    }
    if(f.kind==='icon'){
      // SVGs are usually decorative. Do not produce five anonymous URL
      // inputs; attach configurable icons to their actual card or CTA instead.
      if(editable){
        if(card)card.fields.push(f)
        else if(lastCTA)lastCTA.fields.push(f)
      }
      continue
    }
    lastCTA=null
    if(f.kind==='image'){
      if(card){if(editable)card.fields.push(f)}
      else if(editable)blocks.push({id:f.key,kind:'image',title:excerpt(f.label.replace(/^Image:\s*/,''),65)||'Image',fields:[f]})
      continue
    }
    if(card && f.tag && /^h[1-6]$/.test(f.tag))card=null
    if(card){
      if(editable)card.fields.push(f)
      continue
    }
    if(editable){
      const title=/^Card title:/i.test(f.label)?excerpt(f.default,60)
        :f.tag==='h1'?'Main headline':f.tag&&/^h[2-6]$/.test(f.tag)?'Section heading'
        :excerpt(f.default,64)||'Text'
      blocks.push({id:f.key,kind:'text',title,fields:[f]})
    }
  }
  return blocks.filter(b=>b.fields.length>0)
}
function fieldDisplayName(f:Field,kind:EditorBlock['kind'],_position:number):string{
  if(f.kind==='link')return 'Button destination'
  if(f.kind==='icon')return f.attr==='class'?'Icon class (advanced)':'Replacement icon image URL'
  if(f.kind==='image')return kind==='card'?'Card image':'Image'
  if(isCtaText(f))return 'Button text'
  if(/^Card title:/i.test(f.label))return 'Card heading'
  if(kind==='card'&&f.tag==='p')return 'Card description'
  if(f.tag==='h1')return 'Main headline'
  if(f.tag&&/^h[2-6]$/.test(f.tag))return 'Section heading ('+f.tag.toUpperCase()+')'
  if(f.tag==='li')return 'Bullet point — '+excerpt(f.default,48)
  if(f.tag==='p')return 'Description'
  return f.kind==='textarea'?'Description':f.label.replace(/^(?:Text|Paragraph|H[1-6] heading):\s*/i,'').slice(0,70)||'Text'
}
function repeaterFieldName(group:Repeater,field:Field,number:number):string{
  if(field.kind==='image')return (group.kind==='solutions'||group.kind==='options')?'Background image':group.kind==='benefits'?'Benefit image':'Card image'
  if(field.kind==='icon')return 'Icon (optional)'
  if(field.kind==='link')return 'CTA destination'
  if(group.kind==='benefit_bullets')return 'Bullet point '+number
  if(group.kind==='faqs')return field.tag==='summary'||field.tag==='button'?'Question':'Answer'
  if(group.kind==='options')return field.tag==='h3'?'Option name':field.tag==='p'?'Option description':field.tag==='a'?'CTA text':fieldDisplayName(field,'card',number)
  if(group.kind==='solutions')return field.tag==='h3'?'Solution name':field.tag==='p'?'Description':fieldDisplayName(field,'card',number)
  if(group.kind==='other_solutions')return 'Solution name'
  if(group.kind==='benefits')return field.tag?.startsWith('h')?'Benefit heading':'Benefit description'
  if(group.kind==='highlights')return field.label.startsWith('Card title:')?'Card heading':'Card description'
  return fieldDisplayName(field,'card',number)
}
function hintForField(field:Field):string{
  if(field.kind==='link'){
    if(field.default.startsWith('tel:'))return 'Phone link: tel:+91…'
    if(field.default.startsWith('#'))return 'Section link: #enquiry'
    return 'Enter a page path (/contact/), section (#enquiry), phone (tel:+91…), or full https:// URL.'
  }
  if(field.kind==='image')return 'Use the URL of your uploaded image.'
  if(field.kind==='icon')return field.attr==='class'?'Keep the original value unless you know the CSS icon class used by this template.':'Leave blank to keep the original icon. To replace it, enter a PNG, JPEG or WebP image URL.'
  return ''
}

export default function App(){
  const [user,setUser]=useState<{email:string;role:string}|null>(null)
  const [loginIdentifier,setLoginIdentifier]=useState('')
  const [loginPassword,setLoginPassword]=useState('')
  const [showLoginPassword,setShowLoginPassword]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [message,setMessage]=useState('')
  const [nav,setNav]=useState<Nav>('Category')
  const [tab,setTab]=useState<Tab>('All Pages')
  const officialBootstrapStarted=useRef(false)
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
  const [activeEditorSection,setActiveEditorSection]=useState<string|null>(null)
  const [propertySolutionsTab,setPropertySolutionsTab]=useState('Private Office')
  useEffect(()=>{
    if(!activeEditorSection)return
    const id=activeEditorSection
    const frame=window.requestAnimationFrame(()=>{
      document.getElementById('edit-section-'+id)?.scrollIntoView({behavior:'smooth',block:'start'})
    })
    return()=>window.cancelAnimationFrame(frame)
  },[activeEditorSection])

  const [customIconPickers,setCustomIconPickers]=useState<string[]>([])
  const [linkFeedback,setLinkFeedback]=useState('')
    const [focusedPreviewField,setFocusedPreviewField]=useState('')
  const [sectionPreviewHtml,setSectionPreviewHtml]=useState('')
  const [sectionPreviewLoading,setSectionPreviewLoading]=useState(false)
  const [sectionPreviewError,setSectionPreviewError]=useState('')
  const [previewRefresh,setPreviewRefresh]=useState(0)
  const [newName,setNewName]=useState('')
  const [lastAddedRepeater,setLastAddedRepeater]=useState('')
  const [selectedTemplate,setSelectedTemplate]=useState<number|null>(null)
  const [uploaded,setUploaded]=useState<Template|null>(null)
  const [uploadName,setUploadName]=useState('')
  const [,setUploadCategory]=useState('Solution Category')
  const [templateFile,setTemplateFile]=useState<File|null>(null)
  const [mappingId,setMappingId]=useState<number|null>(null)
  const [openMappingSection,setOpenMappingSection]=useState<string|null>(null)
  const [sectionModeBackups,setSectionModeBackups]=useState<Record<string,Record<string,{mode:Mode;global_key:string|null}>>>({})
  const [preview,setPreview]=useState<string|null>(null)
  const [canvasMode,setCanvasMode]=useState(false)
  const [canvasSelection,setCanvasSelection]=useState<{fieldKey:string;linkKey:string;groupId:string;itemId:string;elementId?:string}|null>(null)
  const [canvasGroupId,setCanvasGroupId]=useState('')
  const [canvasFontBaseline,setCanvasFontBaseline]=useState(20)
  const [canvasZoom,setCanvasZoom]=useState(100)
  const [canvasDevice,setCanvasDevice]=useState<'desktop'|'tablet'|'mobile'>('desktop')
  const [canvasGrid,setCanvasGrid]=useState(false)
  const [canvasLayersOpen,setCanvasLayersOpen]=useState(false)
  const [canvasInspectTarget,setCanvasInspectTarget]=useState<'card'|'text'>('card')
  const [canvasUndoCounter,setCanvasUndoCounter]=useState(0)
  const canvasUndoRef=useRef<Record<string,string>[]>([])
  const canvasRedoRef=useRef<Record<string,string>[]>([])
  const canvasLastHistoryRef=useRef<{key:string;time:number}>({key:'',time:0})

  const [previewSection,setPreviewSection]=useState('')
  const previewFrameRef=useRef<HTMLIFrameElement|null>(null)
  const previewScrollRef=useRef(0)
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
  const [pageSearch,setPageSearch]=useState('')
  const [selectedPageIds,setSelectedPageIds]=useState<number[]>([])
  const [selectedTemplatePreview,setSelectedTemplatePreview]=useState('')
  const [templateDragActive,setTemplateDragActive]=useState(false)
  const [deletingTemplate,setDeletingTemplate]=useState<Template|'all'|null>(null)
  const [deleteError,setDeleteError]=useState('')
  const draftState=(p:Page)=>JSON.stringify({title:p.title,slug:p.slug,values:p.values,seo:p.seo})
  const dirty=!!editor&&!!savedPage&&draftState(editor.page)!==draftState(savedPage)
  const previewPayload=editor?json({edit_version:editor.page.edit_version,title:editor.page.title,slug:editor.page.slug,values:editor.page.values,seo:editor.page.seo}):''
  const allRepeaters=editor?editor.template.sections.flatMap(sec=>sec.repeaters||[]):[]
  const selectedCanvasGroup=allRepeaters.find(g=>g.id===(canvasSelection?.groupId||canvasGroupId))
  const selectedCanvasItem=selectedCanvasGroup?.items.find(item=>item.id===canvasSelection?.itemId)
  const extraSelection=selectedCanvasGroup&&canvasSelection?.fieldKey?.startsWith(selectedCanvasGroup.id+'_added_')?
    canvasSelection.fieldKey.slice((selectedCanvasGroup.id+'_added_').length).match(/^(\d+)_(.+)$/):null
  const extraIndex=extraSelection?Number(extraSelection[1])-1:-1
  const selectedCanvasField=editor?.template.fields.find(field=>field.key===(extraSelection?extraSelection[2]:canvasSelection?.fieldKey))
  const selectedCanvasLink=editor?.template.fields.find(field=>field.key===canvasSelection?.linkKey)
  const visualDesign:VisualDesign=(()=>{try{return JSON.parse(editor?.page.values.__design__||'{}') as VisualDesign}catch{return {}}})()
  const selectedCanvasElement=visualDesign.elements?.find(el=>el.id===canvasSelection?.elementId)
  const hasFixedLinkOrIcon=!!editor?.template.fields.some(f=>f.mode==='static'&&(f.kind==='link'||f.kind==='icon'))
  // Keep ALL mapped sections visible, including intentionally locked
  // Property Testimonials, so section order always matches the source page.
  const editableSections=editor?editor.template.sections:[]
  const activeSectionId=editor?(activeEditorSection===null?editableSections[0]?.id:(editableSections.some(sec=>sec.id===activeEditorSection)?activeEditorSection:'')):''
  function mayLeave(){return !dirty||window.confirm('You have unsaved page changes. Leave and discard these changes?')}
  useEffect(()=>{if(!dirty)return;const guard=(e:BeforeUnloadEvent)=>{e.preventDefault();e.returnValue=''};window.addEventListener('beforeunload',guard);return()=>window.removeEventListener('beforeunload',guard)},[dirty])
  // Visual preview is a sandboxed copy of the *same draft*, not a second data
  // store. User changes update the draft and refresh the preview without saving.
  useEffect(()=>{
    if(!canvasMode||preview===null||!editor)return
    let cancelled=false
    const timer=window.setTimeout(()=>{
      const qs=previewSection?'?section_id='+encodeURIComponent(previewSection):''
      html('/api/pages/'+editor.page.id+'/preview'+qs,JSON.parse(previewPayload))
        .then(result=>{
          if(cancelled)return
          previewScrollRef.current=previewFrameRef.current?.contentWindow?.scrollY||0
          setPreview(result)
        }).catch(e=>{if(!cancelled)showError(e)})
    },380)
    return()=>{cancelled=true;window.clearTimeout(timer)}
  },[previewPayload,canvasMode,previewSection,previewRefresh])

  useEffect(()=>{
    if(!editor||!previewPayload||!activeSectionId){
      setSectionPreviewHtml('');setSectionPreviewLoading(false);setSectionPreviewError('');return
    }
    let cancelled=false
    setSectionPreviewLoading(true)
    const timer=window.setTimeout(()=>{
      html('/api/pages/'+editor.page.id+'/preview?section_id='+encodeURIComponent(activeSectionId),JSON.parse(previewPayload))
        .then(content=>{
          if(cancelled)return
          const key=/^[a-z0-9_-]+$/i.test(focusedPreviewField)?focusedPreviewField:''
          const css=key?'<style>[data-we-field="'+key+'"],[data-we-link-field="'+key+'"]{outline:3px solid #ed2024!important;outline-offset:3px!important;background:rgba(255,185,0,.22)!important;scroll-margin-top:90px!important}</style>':''
          setSectionPreviewHtml(css?content.replace('</head>',css+'</head>'):content)
          setSectionPreviewError('')
        })
        .catch(e=>{if(!cancelled)setSectionPreviewError(e instanceof Error?e.message:String(e))})
        .finally(()=>{if(!cancelled)setSectionPreviewLoading(false)})
    },320)
    return()=>{cancelled=true;window.clearTimeout(timer)}
  },[editor?.page.id,activeSectionId,previewPayload,previewRefresh,focusedPreviewField])
  useEffect(()=>{
    let active=true
    if(!selectedTemplate){setSelectedTemplatePreview('');return}
    html('/api/templates/'+selectedTemplate+'/preview')
      .then(content=>{if(active)setSelectedTemplatePreview(content)})
      .catch(()=>{if(active)setSelectedTemplatePreview('')})
    return()=>{active=false}
  },[selectedTemplate])
  useEffect(()=>{setOpenMappingSection(null);setSectionModeBackups({})},[mappingId])
  useEffect(()=>{if(!mappingId)return;let active=true;const query=focusField?'?focus_field='+encodeURIComponent(focusField):'';html(`/api/templates/${mappingId}/preview${query}`).then(r=>{if(active)setMapPreview(r)}).catch(e=>{if(active)showError(e)});return()=>{active=false}},[mappingId,focusField])

  async function refresh(){
    const [t,p]=await Promise.all([api<Template[]>('/api/templates'),api<Page[]>('/api/pages')])
    setTemplates(t);setPages(p)
    if(uploaded){const next=t.find(x=>x.id===uploaded.id);if(next)setUploaded(next)}
  }
  useEffect(()=>{if(!accessToken)return;api<{email:string;role:string}>('/api/auth/me').then(u=>{setUser(u);refresh().catch(showError)}).catch(()=>{accessToken='';sessionStorage.removeItem('emlen_access_token')})},[])
  useEffect(()=>{
    if(user?.role!=='admin'||officialBootstrapStarted.current)return
    officialBootstrapStarted.current=true
    preloadOfficialTemplates()
  },[user?.role])
  async function preloadOfficialTemplates(){
    // Silent, automatic, idempotent setup on the administrator's first login.
    // All three templates are bundled inside the private API image; no upload,
    // public-site fetch, or manual "preload" action is required.
    try {
      const result=await api<{templates_created:number;pages_created:number;existing:number;unavailable:string[]}>(
        '/api/official/bootstrap',{method:'POST'})
      await refresh()
      if(result.unavailable.length) {
        setError('Approved page templates are unavailable. Contact the dashboard administrator.')
      } else {
        setError('')
      }
    }catch(err){
      showError(err)
    }
  }
  useEffect(()=>{if(!user)return;setMessage('');if(nav==='Shared Content'){api<Record<string,string>>('/api/shared').then(setShared).catch(showError);api<typeof sharedUsage>('/api/shared/usage').then(setSharedUsage).catch(showError)};if(nav==='SEO')api<typeof redirects>('/api/redirects').then(setRedirects).catch(showError);if(nav==='Team Access'&&user.role==='admin')api<typeof team>('/api/users').then(setTeam).catch(showError);if(nav==='Media Library')api<typeof media>('/api/media').then(setMedia).catch(showError);if(nav==='SEO')api<typeof seoStatus>('/api/seo/status').then(setSeoStatus).catch(showError);if(nav==='Archived')api<Page[]>('/api/pages?include_archived=true').then(ps=>setArchivedPages(ps.filter(p=>p.archived))).catch(showError)},[nav,user])
  function showError(e:unknown){setError(e instanceof Error?e.message:String(e));setMessage('')}
  async function action(fn:()=>Promise<void>){setBusy(true);setError('');setMessage('');try{await fn()}catch(e){showError(e)}finally{setBusy(false)}}
  function notify(msg:string){setMessage(msg);setError('')}
  function logout(){if(!mayLeave())return;accessToken='';sessionStorage.removeItem('emlen_access_token');setUser(null);setEditor(null);setSavedPage(null);setPublicationInfo(null);setSelectedTemplate(null);setUploaded(null);setMappingId(null);setNewName('');setNav('Category');setTab('All Pages');officialBootstrapStarted.current=false}
  async function login(){await action(async()=>{
    const result=await api<{access_token:string;user:{email:string;role:string}}>('/api/auth/login',{method:'POST',body:json({identifier:loginIdentifier,password:loginPassword})})
    accessToken=result.access_token;sessionStorage.setItem('emlen_access_token',accessToken);setUser(result.user);await refresh()
  })}
  async function openPage(p:Page){if(!mayLeave())return;await action(async()=>{const data=await api<{page:Page;template:Template}>(`/api/pages/${p.id}`);setEditor(data);setSavedPage(structuredClone(data.page));api<typeof publicationInfo>(`/api/pages/${p.id}/publication-status`).then(setPublicationInfo).catch(showError);setActiveEditorSection(null);setFocusedPreviewField('');setCanvasMode(false);setCanvasSelection(null);setCanvasGroupId('')})}
  async function createPage(){await action(async()=>{
    if(!newName.trim()||!selectedTemplate)throw new Error('Enter a page name and select a template')
    const p=await api<Page>('/api/pages',{method:'POST',body:json({name:newName.trim(),template_id:selectedTemplate})})
    await refresh();setNewName('');await openPage(p)
  })}
  async function uploadTemplate(){await action(async()=>{
    if(!templateFile)throw new Error('Choose an HTML template first')
    const form=new FormData();form.append('file',templateFile)
    const params=new URLSearchParams({name:uploadName||templateFile.name.replace(/\.html$/i,''),category:MODULE_INFO[activeModule].category})
    const t=await api<Template>(`/api/templates/import?${params}`,{method:'POST',body:form});setUploaded(t);setMappingId(t.id);await refresh();notify(`${t.sections.length} structural sections detected. Fields are static until you approve their mapping.`)
  })}
  async function saveMapping(t:Template){await action(async()=>{
    const updated=await api<Template>(`/api/templates/${t.id}/mapping`,{method:'PUT',body:json({
      fields:t.fields.map(f=>({
        key:f.key,label:f.label,mode:f.mode,global_key:f.mode==='global'?f.global_key:null,
        ...(f.tag&&/^h[1-6]$/.test(f.tag)?{heading_tag:f.heading_tag||f.tag}:{}),
        ...(['link','icon'].includes(f.kind)?{default:f.default}:{})
      })),
      sections:t.sections,approved:t.approved
    })})
    setTemplates(prev=>prev.map(x=>x.id===t.id?updated:x));setUploaded(u=>u?.id===t.id?updated:u)
    notify('Template mapping saved. Static sections stay locked; page-variable fields will be editable.')
  })}
  function openDeleteDialog(target:Template|'all'){
    setDeletingTemplate(target);setDeleteError('')
  }
  function closeDeleteDialog(){if(busy)return;setDeletingTemplate(null);setDeleteError('')}
  async function confirmTemplateDeletion(){
    if(!deletingTemplate||busy)return
    const target=deletingTemplate
    setBusy(true);setDeleteError('');setError('')
    try{
      const endpoint=target==='all'?'/api/templates?category='+encodeURIComponent(MODULE_INFO[activeModule].category):'/api/templates/'+target.id
      const result=await api<{removed:number;retained_for_pages:number;storage_cleanup_failed:number}>(endpoint,{
        method:'DELETE',body:json({confirm:true})
      })
      if(target==='all'||mappingId===target.id){setMappingId(null);setUploaded(null);setOpenMappingSection(null);setSectionModeBackups({})}
      if(target==='all'||selectedTemplate===target.id)setSelectedTemplate(null)
      await refresh()
      setDeletingTemplate(null)
      notify(result.removed+' template'+(result.removed===1?'':'s')+' removed from your library. Existing pages are preserved.'+
        (result.storage_cleanup_failed?' '+result.storage_cleanup_failed+' unused storage object(s) could not be removed.':''))
    }catch(e){
      setDeleteError(e instanceof Error?e.message:String(e))
    }finally{setBusy(false)}
  }
  async function redetectTemplate(t:Template){
    if(!window.confirm('Re-detect sections from the saved HTML? Unsaved mapping changes will be discarded. Review and approve the detected fields again afterwards.'))return
    await action(async()=>{
      const updated=await api<Template>(`/api/templates/${t.id}/redetect`,{method:'POST'})
      setTemplates(items=>items.map(item=>item.id===t.id?updated:item))
      setUploaded(updated);setMappingId(updated.id);setFocusField('')
      setOpenMappingSection(null);setSectionModeBackups({})
      notify(`${updated.sections.length} sections and ${updated.fields.length} fields detected. Review the mapping and approve the template.`)
    })
  }
  function toggleSectionStatic(templateId:number,sectionId:string,locked:boolean){
    const backupKey=templateId+':'+sectionId
    if(locked){
      const template=templates.find(t=>t.id===templateId)
      if(template){
        const previous=Object.fromEntries(template.fields
          .filter(f=>f.section_id===sectionId)
          .map(f=>[f.key,{mode:f.mode,global_key:f.global_key}]))
        setSectionModeBackups(prev=>({...prev,[backupKey]:previous}))
      }
    }
    const previousModes=sectionModeBackups[backupKey]
    setTemplates(items=>items.map(t=>t.id!==templateId?t:{
      ...t,
      fields:t.fields.map(f=>f.section_id!==sectionId?f:locked
        ?{...f,mode:'static' as Mode,global_key:null}
        :{...f,mode:previousModes?.[f.key]?.mode||'page',global_key:previousModes?.[f.key]?.global_key||null})
    }))
  }
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
    setPreviewSection(section||'')
    const qs=section?`?section_id=${encodeURIComponent(section)}`:''
    const p=editor.page
    setPreview(await html(`/api/pages/${p.id}/preview${qs}`,{edit_version:p.edit_version,title:p.title,slug:p.slug,values:p.values,seo:p.seo}))
  })}
  function navigate(name:Nav){
    if(!mayLeave())return
    setEditor(null);setSavedPage(null);setNav(name);setSelectedTemplate(null);setSelectedPageIds([])
    setMappingId(null);setUploaded(null);setTemplateFile(null);setPageSearch('')
    if(isModuleNav(name)){setTab('All Pages');setUploadCategory(MODULE_INFO[name].category)}
  }
  function closeEditor(){navigate(moduleOfCategory(editor?.template.category||'Solution Category'))}
  function modifyMapField(id:number,key:string,patch:Partial<Field>){setTemplates(prev=>prev.map(t=>t.id===id?{...t,fields:t.fields.map(f=>f.key===key?{...f,...patch}:f)}:t))}
  async function rotatePassword(){await action(async()=>{
    await api('/api/auth/change-password',{method:'POST',body:json({old_password:oldPassword,new_password:newPassword})})
    setOldPassword('');setNewPassword('');setShowPassword(false);notify('Password changed. Sign in again with your new password.')
    accessToken='';sessionStorage.removeItem('emlen_access_token');setUser(null);setEditor(null);setSavedPage(null)
  })}
  const changeSEO=(patch:Partial<SEO>)=>setEditor(cur=>cur?{...cur,page:{...cur.page,seo:{...cur.page.seo,...patch}}}:cur)
  function changeCanvasValues(next:Record<string,string>,key='change'){
    if(!editor||JSON.stringify(next)===JSON.stringify(editor.page.values))return
    if(canvasMode){
      const now=Date.now()
      const last=canvasLastHistoryRef.current
      if(last.key!==key||now-last.time>650){
        canvasUndoRef.current=[...canvasUndoRef.current.slice(-69),structuredClone(editor.page.values)]
      }
      canvasRedoRef.current=[]
      canvasLastHistoryRef.current={key,time:now}
      setCanvasUndoCounter(n=>n+1)
    }
    setEditor(cur=>cur?{...cur,page:{...cur.page,values:next}}:cur)
  }
  function changeField(key:string,val:string){
    if(!editor)return
    changeCanvasValues({...editor.page.values,[key]:val},'field-'+key)
  }
  function undoCanvas(){
    const previous=canvasUndoRef.current.pop()
    if(!editor||!previous)return
    canvasRedoRef.current.push(structuredClone(editor.page.values))
    canvasLastHistoryRef.current={key:'',time:0}
    setEditor(cur=>cur?{...cur,page:{...cur.page,values:previous}}:cur)
    setCanvasUndoCounter(n=>n+1)
  }
  function redoCanvas(){
    const next=canvasRedoRef.current.pop()
    if(!editor||!next)return
    canvasUndoRef.current.push(structuredClone(editor.page.values))
    canvasLastHistoryRef.current={key:'',time:0}
    setEditor(cur=>cur?{...cur,page:{...cur.page,values:next}}:cur)
    setCanvasUndoCounter(n=>n+1)
  }
  function commitDesign(next:VisualDesign,key='style'){
    if(!editor)return
    changeCanvasValues({...editor.page.values,__design__:JSON.stringify(next)},key)
  }
  function designPatch(category:'groups'|'items'|'fields',key:string,patch:DesignStyle|Record<string,number|boolean>){
    commitDesign({...visualDesign,[category]:{...(visualDesign[category]||{}),
      [key]:{...(visualDesign[category]?.[key]||{}),...patch}}},category+'-'+key)
  }
  function designRemove(category:'items'|'fields',key:string){
    const options={...(visualDesign[category]||{})}
    delete options[key]
    commitDesign({...visualDesign,[category]:options},'reset-'+key)
  }
  function overlayPatch(id:string,patch:Partial<CanvasElement>){
    if(!id)return
    const elements=(visualDesign.elements||[]).map(el=>el.id===id?{...el,...patch}:el)
    commitDesign({...visualDesign,elements},'overlay-'+id)
  }
  function overlayAdd(type:CanvasElement['type']){
    if(!editor||((visualDesign.elements||[]).length>=50))return
    const frame=previewFrameRef.current
    const doc=frame?.contentDocument
    const selection=doc?.elementFromPoint(120,Math.min(220,(frame?.clientHeight||400)-30))
      ?.closest('[data-we-section]')
    const sectionId=selection?.getAttribute('data-we-section')||
      selectedCanvasGroup?.section_id||editor.template.sections[0]?.id
    if(!sectionId)return
    const id='ov_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,7)
    const entry:CanvasElement={
      id,type,sectionId,x:32,y:100,width:type==='shape'?180:type==='image'?230:260,
      height:type==='image'?160:type==='shape'?120:type==='button'?55:90,
      text:type==='text'?'Double-click to edit text':type==='button'?'New button':type==='image'?'Uploaded image':'',
      url:type==='button'?'#enquiry':type==='image'?'https://placehold.co/500x300/png':'',
      fontSize:type==='text'?28:18,fontFamily:'Poppins',fontWeight:600,
      color:'#161616',background:type==='button'?'#ED2024':type==='shape'?'#FFB900':'#FFFFFF',
      opacity:100,rotate:0,radius:12,textAlign:'center',zIndex:10,
    }
    commitDesign({...visualDesign,elements:[...(visualDesign.elements||[]),entry]},'add-'+id)
    setCanvasSelection({fieldKey:'',linkKey:'',groupId:'',itemId:'',elementId:id})
    setCanvasGroupId('')
    setCanvasLayersOpen(true)
  }
  function overlayDuplicate(){
    if(!selectedCanvasElement||(visualDesign.elements||[]).length>=50)return
    const copy={...selectedCanvasElement,id:'ov_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,7),
      x:Math.min(2350,selectedCanvasElement.x+24),y:Math.min(11950,selectedCanvasElement.y+24),locked:false}
    commitDesign({...visualDesign,elements:[...(visualDesign.elements||[]),copy]},'duplicate-'+copy.id)
    setCanvasSelection({fieldKey:'',linkKey:'',groupId:'',itemId:'',elementId:copy.id})
  }
  function overlayRemove(){
    if(!selectedCanvasElement||selectedCanvasElement.locked)return
    commitDesign({...visualDesign,elements:(visualDesign.elements||[]).filter(el=>el.id!==selectedCanvasElement.id)},'remove-'+selectedCanvasElement.id)
    setCanvasSelection(null)
  }
  function duplicateSelectedCard(){
    if(!selectedCanvasGroup||!canvasSelection?.itemId)return
    const entries=repeatEntries(selectedCanvasGroup)
    if(entries.length >= Math.min(selectedCanvasGroup.max_additions||12,12))return
    const item=selectedCanvasItem
    const index=Number(canvasSelection.itemId.split('_added_')[1])-1
    const clone:Record<string,string>={}
    if(!item && index>=0 && entries[index]){
      Object.assign(clone,entries[index])
    }else if(item){
      const target=selectedCanvasGroup.items[selectedCanvasGroup.items.length-1]
      const source=item.field_keys.map(k=>editor?.template.fields.find(f=>f.key===k)).filter((f):f is Field=>!!f&&f.mode==='page')
      const dest=target.field_keys.map(k=>editor?.template.fields.find(f=>f.key===k)).filter((f):f is Field=>!!f&&f.mode==='page')
      source.forEach((f,i)=>{
        const out=dest[i]
        if(!out)return
        const value=editor?.page.values[f.key]??f.default
        if(f.kind!=='image'&&f.kind!=='icon'&&value.length<2500)clone[out.key]=value
        else if((f.kind==='image'||f.kind==='icon')&&!value.startsWith('data:')&&value.length<2500)clone[out.key]=value
      })
      if(selectedCanvasGroup.kind==='solutions')
        clone.__variant=editor?.page.values['__variant__'+selectedCanvasGroup.id+'__'+item.id]||item.variant||'regular'
    }
    putRepeatEntries(selectedCanvasGroup,[...entries,clone])
    const id=selectedCanvasGroup.id+'_added_'+(entries.length+1)
    setCanvasSelection({fieldKey:'',linkKey:'',groupId:selectedCanvasGroup.id,itemId:id})
  }
  function isFieldLocked(key:string){
    if(visualDesign.fields?.[key]?.locked)return true
    return allRepeaters.some(group=>group.items.some(item=>
      item.field_keys.includes(key)&&!!visualDesign.items?.[item.id]?.locked))
  }
  function unsetField(key:string){
    setEditor(current=>{
      if(!current)return current
      const vals={...current.page.values};delete vals[key]
      return {...current,page:{...current.page,values:vals}}
    })
  }
  function attachPreviewLinks(frame:HTMLIFrameElement){
    // Source HTML is sandboxed without scripting. Listen from the parent so
    // links open safely in another tab instead of replacing the preview.
    const doc=frame.contentDocument
    if(!doc)return
    doc.addEventListener('click',event=>{
      if(canvasMode)return // visual editor uses click-to-select instead
      const node=event.target as Element
      const link=node.closest?.('a[href]')
      if(!link)return
      const href=(link.getAttribute('href')||'').trim()
      if(href.startsWith('#')){
        event.preventDefault()
        const id=href.slice(1)
        const target=id?doc.getElementById(id):null
        if(target){target.scrollIntoView({behavior:'smooth',block:'start'});setLinkFeedback('Jumped to '+href)}
        else setLinkFeedback('This button links to '+href+'. Use the full-page preview to locate that section.')
        return
      }
      event.preventDefault()
      if(!isSafePreviewHref(href)){setLinkFeedback('This destination is not a permitted link.');return}
      if(isTestableHref(href)){
        // Call directly from the user click, preserving the browser gesture.
        window.open(href,'_blank','noopener,noreferrer')
        setLinkFeedback('Opened '+href+' in a separate tab. The CMS preview stays here.')
      }else{
        window.open(href,'_blank','noopener,noreferrer')
        setLinkFeedback('Opened the local route in a separate tab.')
      }
    },true)
  }
  async function uploadPicture(file:File|null,onReady:(url:string)=>void){
    if(!file)return
    if(!['image/jpeg','image/png','image/webp'].includes(file.type)){
      showError('Choose a JPG, PNG or WebP image.');return
    }
    await action(async()=>{
      const data=new FormData()
      data.append('file',file)
      data.append('alt_text',file.name.replace(/\.[^.]+$/,'').replace(/[-_]+/g,' '))
      const result=await api<{id:number;url:string}>('/api/media',{method:'POST',body:data})
      onReady(result.url)
      notify('Image uploaded. The preview now uses your image. Save draft to keep it.')
    })
  }
  function iconChoiceControl(pickerId:string,value:string,onValue:(v:string)=>void){
    const custom=customIconPickers.includes(pickerId)||/^(https?:\/\/|\/(?!\/))/i.test(value)
    const selected=custom?'custom':value.startsWith('icon:')?value:'original'
    return <div className="editor-simple-icon-choice">
      <label>Choose icon
        <select aria-label={'Choose icon '+pickerId} value={selected} onChange={event=>{
          const v=event.target.value
          if(v==='custom'){setCustomIconPickers(prev=>prev.includes(pickerId)?prev:[...prev,pickerId]);return}
          setCustomIconPickers(prev=>prev.filter(id=>id!==pickerId))
          onValue(v==='original'?'':v)
        }}>
          <option value="original">Keep original icon</option>
          {SIMPLE_ICONS.map(icon=><option key={icon.value} value={icon.value}>{icon.label}</option>)}
          <option value="custom">Use my own icon image URL</option>
        </select>
      </label>
      {custom&&<><label>Icon image address
        <input type="url" aria-label={'Icon image URL '+pickerId} placeholder="https://example.com/icon.png"
          value={/^(https?:\/\/|\/(?!\/))/i.test(value)?value:''}
          onChange={event=>onValue(event.target.value)}/>
        <small>Use a direct PNG, JPG or WebP image URL—not a webpage or video link.</small>
      </label>
      <label>Or upload an icon from your computer
        <input type="file" accept="image/png,image/jpeg,image/webp" aria-label={'Upload icon '+pickerId}
          onChange={e=>uploadPicture(e.target.files?.[0]||null,onValue)}/>
      </label></>}
      <small className="editor-ordered-help">Your original arrow or symbol stays in place until you choose a replacement.</small>
    </div>
  }
  function canvasLoaded(frame:HTMLIFrameElement){
    attachPreviewLinks(frame)
    if(!canvasMode)return
    const doc=frame.contentDocument
    const win=frame.contentWindow
    if(!doc||!win)return
    const style=doc.createElement('style')
    style.textContent=[
      '[data-we-field],[data-we-link-field],[data-we-repeat-item],[data-we-design-element]{cursor:move!important;}',
      '[data-we-field]:hover,[data-we-repeat-item]:hover,[data-we-design-element]:hover{outline:2px dashed #ed2024!important;outline-offset:3px!important;}',
      '[data-we-canvas-selected]{outline:3px solid #ed2024!important;outline-offset:3px!important;box-shadow:0 0 0 5px rgba(237,32,36,.13)!important;}',
      '[data-we-resize-handle]{position:absolute;display:block;width:16px;height:16px;border-radius:5px;border:2px solid #fff;background:#ed2024;z-index:999999;cursor:nwse-resize;padding:0;box-shadow:0 2px 10px #16161655;}',
      '[data-we-design-element]:focus{outline:3px solid #ed2024!important}',
      canvasGrid?'body{background-image:linear-gradient(#cccccc32 1px,transparent 1px),linear-gradient(90deg,#cccccc32 1px,transparent 1px)!important;background-size:24px 24px!important;}':''
    ].join('\n')
    ;(doc.head||doc.body).appendChild(style)
    let handle:HTMLButtonElement|null=null
    let currentNode:HTMLElement|null=null
    function drawHandle(node:HTMLElement|null){
      handle?.remove()
      handle=null
      currentNode=node
      if(!node||!doc?.body)return
      const rect=node.getBoundingClientRect()
      if(rect.width<5||rect.height<5)return
      handle=doc.createElement('button')
      handle.type='button'
      handle.setAttribute('data-we-resize-handle','true')
      handle.setAttribute('aria-label','Drag to resize selected element')
      handle.style.left=(rect.right+(win?.scrollX||0)-9)+'px'
      handle.style.top=(rect.bottom+(win?.scrollY||0)-9)+'px'
      doc.body.appendChild(handle)
    }
    function selectedTarget(){
      if(canvasSelection?.elementId)return doc?.querySelector('[data-we-design-element="'+canvasSelection.elementId+'"]') as HTMLElement|null
      if(canvasSelection?.fieldKey)return doc?.querySelector('[data-we-field="'+canvasSelection.fieldKey+'"]') as HTMLElement|null
      if(canvasSelection?.itemId)return doc?.querySelector('[data-we-repeat-item="'+canvasSelection.itemId+'"]') as HTMLElement|null
      return null
    }
    const restore=selectedTarget()
    if(restore){restore.setAttribute('data-we-canvas-selected','true');drawHandle(restore)}
    doc.addEventListener('click',event=>{
      const target=event.target as Element
      if(target.closest?.('[data-we-resize-handle]')){event.preventDefault();event.stopPropagation();return}
      const clickable=target.closest?.('[data-we-design-element],[data-we-field],[data-we-link-field],[data-we-repeat-item],[data-we-repeat-group]')
      if(!clickable)return
      event.preventDefault();event.stopPropagation()
      const overlay=clickable.closest('[data-we-design-element]')
      const item=clickable.closest('[data-we-repeat-item]')
      const group=clickable.closest('[data-we-repeat-group]')
      const field=clickable.closest('[data-we-field],[data-we-link-field]')
      const fieldKey=field?.getAttribute('data-we-field')||''
      const linkKey=field?.getAttribute('data-we-link-field')||''
      const itemId=item?.getAttribute('data-we-repeat-item')||''
      const groupId=group?.getAttribute('data-we-repeat-group')||''
      const elementId=overlay?.getAttribute('data-we-design-element')||''
      const raw=field?win.getComputedStyle(field).fontSize:''
      if(raw)setCanvasFontBaseline(Math.max(8,Math.min(120,Math.round(parseFloat(raw)||20))))
      setCanvasGroupId(groupId)
      setCanvasSelection({fieldKey:elementId?'':fieldKey,linkKey:elementId?'':linkKey,
        groupId:elementId?'':groupId,itemId:elementId?'':itemId,elementId})
      setCanvasInspectTarget('card')
      doc.querySelectorAll('[data-we-canvas-selected]').forEach(el=>el.removeAttribute('data-we-canvas-selected'))
      const chosen=(overlay||field||item||group) as HTMLElement
      chosen?.setAttribute('data-we-canvas-selected','true')
      drawHandle(chosen||null)
    },true)
    type DragSession={
      node:HTMLElement;kind:'overlay'|'item'|'field';id:string;
      startX:number;startY:number;baseX:number;baseY:number;
      baseW:number;baseH:number;resize:boolean;moved:boolean
    }
    let drag:DragSession|null=null
    const clamp=(n:number,a:number,b:number)=>Math.max(a,Math.min(b,Math.round(n)))
    doc.addEventListener('pointerdown',event=>{
      if(event.button!==0)return
      const target=event.target as HTMLElement
      const resize=!!target.closest?.('[data-we-resize-handle]')
      const picked=resize?currentNode:target.closest?.('[data-we-design-element],[data-we-field],[data-we-repeat-item]') as HTMLElement|null
      if(!picked)return
      const overlay=picked.closest('[data-we-design-element]')
      const item=picked.closest('[data-we-repeat-item]')
      const field=picked.closest('[data-we-field]')
      const kind=overlay?'overlay':field?'field':'item'
      const id=(overlay?.getAttribute('data-we-design-element')||
        field?.getAttribute('data-we-field')||item?.getAttribute('data-we-repeat-item')||'')
      const el=visualDesign.elements?.find(x=>x.id===id)
      if(kind==='overlay'&&(!el||el.locked))return
      const settings=kind==='item'?visualDesign.items?.[id]:visualDesign.fields?.[id]
      if(kind!=='overlay'&&(settings?.locked||(
        kind==='field'&&!editor?.template.fields.some(f=>f.key===id&&f.mode==='page')&&
        !id.includes('_added_'))))return
      const rect=picked.getBoundingClientRect()
      drag={
        node:picked,kind,id,startX:event.clientX,startY:event.clientY,
        baseX:kind==='overlay'?(el?.x||0):(settings?.x||0),
        baseY:kind==='overlay'?(el?.y||0):(settings?.y||0),
        baseW:kind==='overlay'?(el?.width||rect.width):(settings?.widthPx||Math.round(rect.width)),
        baseH:kind==='overlay'?(el?.height||rect.height):(settings?.heightPx||Math.round(rect.height)),
        resize,moved:false,
      }
      if(resize){event.preventDefault();event.stopPropagation()}
    },true)
    doc.addEventListener('pointermove',event=>{
      if(!drag)return
      const dx=event.clientX-drag.startX,dy=event.clientY-drag.startY
      if(!drag.moved&&Math.hypot(dx,dy)<4)return
      drag.moved=true
      event.preventDefault()
      if(drag.resize){
        drag.node.style.width=clamp(drag.baseW+dx,30,1800)+'px'
        drag.node.style.height=clamp(drag.baseH+dy,20,1000)+'px'
      }else if(drag.kind==='overlay'){
        drag.node.style.left=clamp(drag.baseX+dx,0,2400)+'px'
        drag.node.style.top=clamp(drag.baseY+dy,0,12000)+'px'
      }else{
        drag.node.style.translate=clamp(drag.baseX+dx,-600,600)+'px '+clamp(drag.baseY+dy,-600,600)+'px'
      }
      drawHandle(drag.node)
    },true)
    doc.addEventListener('pointerup',event=>{
      const session=drag
      drag=null
      if(!session?.moved)return
      event.preventDefault();event.stopPropagation()
      const dx=event.clientX-session.startX,dy=event.clientY-session.startY
      if(session.resize){
        const width=clamp(session.baseW+dx,30,1800)
        const height=clamp(session.baseH+dy,20,1000)
        if(session.kind==='overlay'){
          overlayPatch(session.id,{width,height})
        }else if(session.kind==='item'){
          designPatch('items',session.id,{widthPx:width,heightPx:height})
        }else{
          designPatch('fields',session.id,{widthPx:width,heightPx:height})
        }
      }else{
        const x=session.baseX+dx,y=session.baseY+dy
        if(session.kind==='overlay'){
          overlayPatch(session.id,{x:clamp(x,0,2400),y:clamp(y,0,12000)})
        }else{
          designPatch(session.kind==='item'?'items':'fields',session.id,{
            x:clamp(x,-600,600),y:clamp(y,-600,600)
          })
        }
      }
    },true)
    doc.addEventListener('pointercancel',()=>{drag=null},true)
    doc.addEventListener('dblclick',event=>{
      const node=(event.target as Element).closest?.('[data-we-design-element]') as HTMLElement|null
      if(!node)return
      const id=node.getAttribute('data-we-design-element')||''
      const entry=visualDesign.elements?.find(el=>el.id===id)
      if(entry&&!entry.locked&&(entry.type==='text'||entry.type==='button')){
        event.preventDefault();event.stopPropagation()
        const value=window.prompt('Edit text',entry.text||'')
        if(value!==null)overlayPatch(id,{text:value.slice(0,1000)})
      }
    },true)
    if(previewScrollRef.current)win.scrollTo(0,previewScrollRef.current)
  }
  useEffect(()=>{
    if(!canvasMode)return
    const handler=(event:KeyboardEvent)=>{
      const target=event.target as HTMLElement
      if(target.closest('input,textarea,select,[contenteditable="true"]'))return
      const meta=event.ctrlKey||event.metaKey
      if(meta&&event.key.toLowerCase()==='z'){
        event.preventDefault();if(event.shiftKey)redoCanvas();else undoCanvas();return
      }
      if(meta&&event.key.toLowerCase()==='y'){event.preventDefault();redoCanvas();return}
      if(meta&&event.key.toLowerCase()==='d'){
        if(selectedCanvasElement||canvasSelection?.itemId){
          event.preventDefault();if(selectedCanvasElement)overlayDuplicate();else duplicateSelectedCard()
        }
        return
      }
      if((event.key==='Delete'||event.key==='Backspace')&&selectedCanvasElement&&!selectedCanvasElement.locked){
        event.preventDefault();overlayRemove();return
      }
      const arrows:{[key:string]:[number,number]}={
        ArrowUp:[0,-1],ArrowDown:[0,1],ArrowLeft:[-1,0],ArrowRight:[1,0],
      }
      const direction=arrows[event.key]
      if(!direction)return
      const delta=event.shiftKey?10:1
      if(selectedCanvasElement&&!selectedCanvasElement.locked){
        event.preventDefault()
        overlayPatch(selectedCanvasElement.id,{
          x:Math.max(0,Math.min(2400,selectedCanvasElement.x+direction[0]*delta)),
          y:Math.max(0,Math.min(12000,selectedCanvasElement.y+direction[1]*delta))
        })
      }else if(canvasSelection?.itemId||selectedCanvasField?.mode==='page'){
        const group=canvasSelection?.itemId?'items':'fields'
        const id=canvasSelection?.itemId||selectedCanvasField?.key||''
        const opts=group==='items'?visualDesign.items?.[id]:visualDesign.fields?.[id]
        if(!opts?.locked){
          event.preventDefault()
          designPatch(group,id,{
            x:Math.max(-600,Math.min(600,(opts?.x||0)+direction[0]*delta)),
            y:Math.max(-600,Math.min(600,(opts?.y||0)+direction[1]*delta))
          })
        }
      }
    }
    window.addEventListener('keydown',handler)
    const frameDocument=previewFrameRef.current?.contentDocument
    frameDocument?.addEventListener('keydown',handler)
    return()=>{
      window.removeEventListener('keydown',handler)
      frameDocument?.removeEventListener('keydown',handler)
    }
  },[canvasMode,editor,canvasSelection,visualDesign,preview])
  async function enableLinksAndIconsOnThisPage(){
    if(!editor||user?.role!=='admin')return
    if(dirty){showError('Save this draft first, then enable editing for its links and icons.');return}
    if(!window.confirm('Make fixed CTA links and icons editable on THIS page only? The approved template and published website will not change.'))return
    await action(async()=>{
      const latest=await api<{page:Page;template:Template;enabled_count:number}>(
        '/api/pages/'+editor.page.id+'/enable-link-icon-editing',
        {method:'POST',body:json({edit_version:editor.page.edit_version})})
      setEditor({page:latest.page,template:latest.template})
      setSavedPage(structuredClone(latest.page))
      await refresh()
      notify(latest.enabled_count+' button links and icons are now editable on this page.')
    })
  }
  async function enableRepeatersOnThisPage(){
    if(!editor)return
    if(dirty){showError('Save the current draft before refreshing repeater fields.');return}
    await action(async()=>{
      const updated=await api<{page:Page;template:Template;repeaters:number;new_fields:number}>(
        '/api/pages/'+editor.page.id+'/upgrade-repeaters',
        {method:'POST',body:json({edit_version:editor.page.edit_version})})
      setEditor({page:updated.page,template:updated.template})
      setSavedPage(structuredClone(updated.page))
      setActiveEditorSection(null)
      await refresh()
      notify('Repeaters refreshed for this page: '+updated.repeaters+' groups and '+updated.new_fields+' newly detected fields.')
    })
  }
  function editorFieldControl(field:Field,position:number,kind:EditorBlock['kind'],customLabel?:string){
    const title=customLabel||fieldDisplayName(field,kind,position)
    const rawValue=editor?.page.values[field.key]??field.default
    const value=(isCtaText(field)||field.tag==='summary')?rawValue.replace(/\s*[↗↖↘↙→➜➔›+]\s*$/,'').trim():rawValue
    return <div key={field.key} className={'editor-ordered-field '+(field.kind==='link'?'editor-destination-field':'')}>
      <span className="editor-ordered-label">{title}</span>
      {field.kind==='image'&&field.default.startsWith('data:')&&<div className="editor-current-image"><img src={value.startsWith('data:')?value:field.default} alt="Current template image"/><small>Original image</small></div>}
      {field.kind==='icon'&&field.attr==='icon_src'
        ?iconChoiceControl(field.key,value,v=>changeField(field.key,v))
        :field.kind==='textarea'
          ?<textarea aria-label={title} rows={3} disabled={isFieldLocked(field.key)} value={value} onFocus={()=>setFocusedPreviewField(field.key)} onChange={e=>changeField(field.key,e.target.value)}/>
          :<input aria-label={title} value={field.kind==='image'&&value.startsWith('data:')?'':value} disabled={isFieldLocked(field.key)}
            onFocus={()=>setFocusedPreviewField(field.key)} onChange={e=>field.kind==='image'&&!e.target.value?unsetField(field.key):changeField(field.key,e.target.value)} type="text"
            placeholder={field.kind==='image'?'Paste replacement image URL (optional)':field.kind==='link'?'e.g. #enquiry, /contact/, tel:+91...':undefined}/>}
      {field.kind==='image'&&<div className="editor-easy-image-upload">
        <label>Or upload a replacement photo (JPG, PNG or WebP)
          <input type="file" accept="image/png,image/jpeg,image/webp" aria-label={'Upload photo for '+title}
            onChange={e=>uploadPicture(e.target.files?.[0]||null,url=>changeField(field.key,url))}/>
        </label>
      </div>}
      {field.kind==='link'&&<div className="editor-link-check">
        {isTestableHref(value)?<a href={value.trim()} target="_blank" rel="noopener noreferrer"><ArrowUpRight size={14}/> Test this link</a>:
         value.startsWith('#')?<small>Goes to the {value} section on this page. Click the button in the full-page preview to check it.</small>:
         value.startsWith('/')&&!value.startsWith('//')?<small>This is a website page path. Test it after the page is published.</small>:
         <small>Enter a full website URL, a section anchor (#enquiry), a phone number starting with tel:, or an email starting with mailto:.</small>}
      </div>}
      {field.kind!=='icon'&&field.kind!=='link'&&(field.kind==='image'&&value.startsWith('data:')?<small className="editor-ordered-help">Leave blank to keep the original photo; paste a URL to replace it.</small>:hintForField(field)&&<small className="editor-ordered-help">{hintForField(field)}</small>)}
      {isFieldLocked(field.key)&&<small className="editor-ordered-help"><LockKeyhole size={12}/> Locked in visual editor</small>}
    </div>
  }
  function repeatEntries(group:Repeater):Record<string,string>[]{
    const raw=editor?.page.values['__repeat__'+group.id]||'[]'
    try{const items=JSON.parse(raw);return Array.isArray(items)?items:[]}catch{return []}
  }
  function putRepeatEntries(group:Repeater,entries:Record<string,string>[]){
    changeField('__repeat__'+group.id,JSON.stringify(entries))
  }
  function addRepeatEntry(group:Repeater){
    const previous=repeatEntries(group)
    if(previous.length >= Math.min(group.max_additions??12,12))return
    // New rows inherit the original card's layout and content from HTML.
    // Do not serialize original images (often large embedded base64 data),
    // which could exceed the page API's size cap before any field is edited.
    const entry:Record<string,string>={}
    if(group.kind==='solutions'||group.kind==='options')entry.__variant='regular'
    const newKey=group.id+'-added-'+previous.length
    setLastAddedRepeater(newKey)
    putRepeatEntries(group,[...previous,entry])
    window.requestAnimationFrame(()=>document.getElementById('repeater-'+newKey)?.scrollIntoView({behavior:'smooth',block:'nearest'}))
  }
  function updateRepeatEntry(group:Repeater,index:number,key:string,value:string){
    const items=repeatEntries(group).map((item,i)=>{
      if(i!==index)return item
      const next={...item}
      if(!value&&(editor?.template.fields.find(f=>f.key===key)?.kind==='image'||
                  editor?.template.fields.find(f=>f.key===key)?.kind==='icon')){
        delete next[key] // empty image/icon means preserve the original asset
      }else next[key]=value
      return next
    })
    putRepeatEntries(group,items)
  }
  function deleteRepeatEntry(group:Repeater,index:number){
    putRepeatEntries(group,repeatEntries(group).filter((_,i)=>i!==index))
  }
  function selectOptionLayout(group:Repeater,variant:'regular'|'generic'|'highlight',
                              itemId?:string,addedIndex?:number){
    if(!editor)return
    const next={...editor.page.values}
    const extras=repeatEntries(group).map(x=>({...x}))
    if(addedIndex!==undefined&&extras[addedIndex]){
      extras[addedIndex].__variant=variant
    }else if(itemId){
      next['__variant__'+group.id+'__'+itemId]=variant
    }
    if(variant==='highlight'){
      // Exactly one highlighted card per office-option group.
      group.items.forEach(x=>{
        if(x.id!==itemId)next['__variant__'+group.id+'__'+x.id]='regular'
      })
      extras.forEach((x,i)=>{
        if(i!==addedIndex && x.__variant==='highlight')extras[i].__variant='regular'
      })
    }
    if(extras.length)next['__repeat__'+group.id]=JSON.stringify(extras)
    changeCanvasValues(next,'option-layout-'+group.id)
  }
  function existingItemFields(item:RepeaterItem,section:Section){
    const nested=variableRepeaterGroups(section,editor?.template.fields||[])
      .filter(x=>x.parent_item_id===item.id)
    const nestedKeys=new Set(nested.flatMap(g=>g.items.flatMap(it=>it.field_keys)))
    return item.field_keys.map(key=>editor?.template.fields.find(f=>f.key===key))
      .filter((field):field is Field=>!!field&&field.mode==='page'&&!nestedKeys.has(field.key))
  }
  function renderRepeaterGroup(group:Repeater,section:Section,nested=false){
    const additions=repeatEntries(group)
    const suffix=group.kind==='benefit_bullets'?'bullet point':group.kind==='faqs'?'FAQ':(group.kind==='solutions'||group.kind==='options')?'option':group.kind==='other_solutions'?'solution link':group.kind==='benefits'?'benefit':'card'
    const title=group.kind==='highlights'?'Highlights cards':group.kind==='benefits'?'Benefits':group.kind==='faqs'?'Frequently asked questions':group.kind==='benefit_bullets'?'Bullet points':group.name
    const original=group.items.length
    const maxAdditions=Math.min(group.max_additions??12,12)
    return <div className={'editor-repeat-group '+(nested?'nested':'')} key={group.id}>
      <div className="editor-repeat-heading">
        <div><strong>{title}</strong><small>{original} in template · {additions.length} added</small></div>
        <span className="editor-repeat-count">{original+additions.length} items</span>
      </div>
      <div className="editor-repeat-items">
        {group.items.map((item,index)=>{
          const available=existingItemFields(item,section)
          const subGroups=(section.repeaters||[]).filter(g=>g.parent_item_id===item.id&&variableRepeaterGroups(section,editor?.template.fields||[]).includes(g))
          return <details className="editor-repeat-item" key={item.id}>
            <summary><span className="editor-repeat-item-num">{String(index+1).padStart(2,'0')}</span><span>{item.title||suffix+' '+(index+1)}</span><ChevronRight size={15}/></summary>
            <div className="editor-repeat-fields">
              {(group.kind==='solutions'||group.kind==='options')&&<div className="editor-repeat-variant">
                <span>Solution card layout</span>
                <div className="editor-solution-tabs" role="tablist" aria-label={'Style for '+item.title}>
                  {(['regular','generic','highlight'] as const).map(v=><button key={v} type="button" role="tab" aria-selected={(editor?.page.values['__variant__'+group.id+'__'+item.id]||item.variant||'regular')===v} onClick={()=>selectOptionLayout(group,v,item.id)}>{v[0].toUpperCase()+v.slice(1)}</button>)}
                </div>
                <small>Regular keeps the original size; Generic makes this card wider; Highlight accents one card.</small>
              </div>}
              {available.map((field,i)=>editorFieldControl(field,i+1,group.kind==='benefits'?'card':'text',repeaterFieldName(group,field,i+1)))}
              {subGroups.map(n=>renderRepeaterGroup(n,section,true))}
              {available.length===0&&subGroups.length===0&&<small>This template item is fixed.</small>}
            </div>
          </details>
        })}
        {additions.map((item,index)=>{
          const sample=group.items[group.items.length-1]
          const fields=sample.field_keys.map(k=>editor?.template.fields.find(f=>f.key===k))
            .filter((field):field is Field=>!!field&&field.mode==='page')
          return <details className="editor-repeat-item added" key={'extra-'+index}
            id={'repeater-'+group.id+'-added-'+index}
            ref={node=>{if(node&&lastAddedRepeater===group.id+'-added-'+index&&!node.dataset.initialized){node.open=true;node.dataset.initialized='yes'}}}>
            <summary><span className="editor-repeat-item-num">{String(original+index+1).padStart(2,'0')}</span><span>New {suffix} {index+1}</span><ChevronRight size={15}/></summary>
            <div className="editor-repeat-fields">
              {(group.kind==='solutions'||group.kind==='options')&&<div className="editor-repeat-variant">
                <span>Solution card layout</span>
                <div className="editor-solution-tabs" role="tablist" aria-label={'Style for new '+suffix+' '+(index+1)}>
                  {(['regular','generic','highlight'] as const).map(v=><button key={v} type="button" role="tab" aria-selected={(item.__variant||'regular')===v} onClick={()=>selectOptionLayout(group,v,undefined,index)}>{v[0].toUpperCase()+v.slice(1)}</button>)}
                </div>
                <small>Regular keeps the original size; Generic makes this card wider; Highlight accents one card.</small>
              </div>}
              {fields.map((field,i)=>{
                const title=repeaterFieldName(group,field,i+1)
                const value=item[field.key]??(field.kind==='image'||field.kind==='icon'?'':field.default)
                return <div className="editor-ordered-field" key={field.key}><label className="editor-ordered-label">{title}</label>
                  {field.kind==='icon'&&field.attr==='icon_src'?iconChoiceControl(group.id+'-'+index+'-'+field.key,value,v=>updateRepeatEntry(group,index,field.key,v)):
                    (field.kind==='textarea'||value.length>110)
                      ?<textarea rows={3} value={value} onChange={e=>updateRepeatEntry(group,index,field.key,e.target.value)} aria-label={title}/>
                      :<input value={value} onChange={e=>updateRepeatEntry(group,index,field.key,e.target.value)} aria-label={title}/>}
                  {field.kind==='image'&&<div className="editor-easy-image-upload"><label>Or upload a photo
                    <input type="file" accept="image/png,image/jpeg,image/webp"
                      aria-label={'Upload image for '+suffix+' '+(index+1)}
                      onChange={e=>uploadPicture(e.target.files?.[0]||null,url=>updateRepeatEntry(group,index,field.key,url))}/>
                  </label></div>}
                  {field.kind==='link'&&<div className="editor-link-check">{isTestableHref(value)
                    ?<a href={value.trim()} target="_blank" rel="noopener noreferrer"><ArrowUpRight size={14}/> Test this link</a>
                    :<small>Use a URL, #anchor, tel: or mailto: destination.</small>}</div>}
                  {(field.kind==='image'||field.kind==='icon'&&field.attr!=='icon_src')&&<small className="editor-ordered-help">Leave blank to reuse the original {suffix} image or icon.</small>}
                  {field.kind!=='image'&&field.kind!=='icon'&&field.kind!=='link'&&hintForField(field)&&<small className="editor-ordered-help">{hintForField(field)}</small>}
                </div>
              })}
              <div className="editor-repeat-actions">
                <button type="button" className="outline compact" disabled={index===0}
                  onClick={()=>{const next=[...additions];[next[index-1],next[index]]=[next[index],next[index-1]];putRepeatEntries(group,next)}}>Move up</button>
                <button type="button" className="outline compact" disabled={index===additions.length-1}
                  onClick={()=>{const next=[...additions];[next[index+1],next[index]]=[next[index],next[index+1]];putRepeatEntries(group,next)}}>Move down</button>
                <button type="button" className="editor-repeat-remove" onClick={()=>deleteRepeatEntry(group,index)}><Trash2 size={14}/> Remove {suffix}</button>
              </div>
            </div>
          </details>
        })}
      </div>
      <button type="button" className="editor-repeat-add" disabled={additions.length>=maxAdditions} onClick={()=>addRepeatEntry(group)}><Plus size={16}/> {additions.length>=maxAdditions?'Maximum added':'Add another '+suffix}</button>
    </div>
  }
  function editorBlockControl(block:EditorBlock,index:number){
    const regular=block.fields.filter(f=>f.kind!=='icon')
    const icons=block.fields.filter(f=>f.kind==='icon')
    const kindLabel=block.kind==='card'?'Highlight card':block.kind==='cta'?'Button / CTA':block.kind==='image'?'Image':'Page content'
    return <div className={'editor-ordered-block editor-block-'+block.kind} key={block.id}>
      <div className="editor-ordered-block-header">
        <span className="editor-ordered-step">{String(index+1).padStart(2,'0')}</span>
        <div><small>{kindLabel}</small><strong>{block.title}</strong></div>
      </div>
      {regular.length>0&&<div className="editor-ordered-block-fields">{regular.map((field,i)=>editorFieldControl(field,i+1,block.kind))}</div>}
      {block.kind==='cta'&&block.fixedDestination!==undefined&&<div className="editor-fixed-destination"><small>Button destination · Fixed by template</small><code>{block.fixedDestination}</code>{user?.role==='admin'&&<button type="button" className="outline compact" disabled={busy||dirty} onClick={enableLinksAndIconsOnThisPage}><LockKeyhole size={13}/> Make this page's links editable</button>}</div>}
      {icons.length>0&&<details className="editor-context-icon">
        <summary>Change {block.kind==='card'?'this card’s icon':block.kind==='cta'?'this button’s icon':'icon'} (optional) <ChevronRight size={15}/></summary>
        <p>The original icon stays in place unless you choose a replacement image.</p>
        <div className="editor-ordered-block-fields">{icons.map((field,i)=>editorFieldControl(field,i+1,block.kind))}</div>
      </details>}
    </div>
  }
  function canvasStyleControls(category:'items'|'fields',id:string){
    const options=category==='items'?visualDesign.items?.[id]||{}:visualDesign.fields?.[id]||{}
    const patch=(next:DesignStyle)=>designPatch(category,id,next)
    const numberInput=(title:string,key:keyof DesignStyle,min:number,max:number,fallback:number,unit='px')=>
      <label key={key} className="designer-number-field">{title}
        <div className="designer-unit-input">
          <input type="number" aria-label={title} min={min} max={max} value={Number(options[key]??fallback)}
            onChange={e=>patch({[key]:Math.max(min,Math.min(max,Math.round(Number(e.target.value)||0)))})}/>
          <span>{unit}</span>
        </div>
      </label>
    return <div className="designer-property-stack">
      <div className="designer-property-section">
        <h3><Move size={15}/> Position & size</h3>
        {category==='items'&&<label>Card grid width
          <select aria-label="Selected card width" value={options.span??1}
            onChange={e=>patch({span:Number(e.target.value)})}>
            <option value={1}>Regular (1 column)</option>
            <option value={2}>Wide (2 columns)</option>
            <option value={3}>Extra wide (3 columns)</option>
            <option value={4}>Full width (4 columns)</option>
          </select>
        </label>}
        <div className="designer-property-grid">
          {numberInput('Move horizontally','x',-600,600,0)}
          {numberInput('Move vertically','y',-600,600,0)}
          {numberInput('Width','widthPx',30,1800,category==='items'?300:300)}
          {numberInput('Height','heightPx',20,1000,category==='items'?300:80)}
          {numberInput('Rotate','rotate',-180,180,0,'°')}
          {numberInput('Corner radius','radius',0,120,0)}
        </div>
      </div>
      <div className="designer-property-section">
        <h3><Type size={15}/> Appearance</h3>
        <div className="designer-property-grid">
          <label>Text color<input aria-label="Text color" type="color" value={options.color||'#161616'} onChange={e=>patch({color:e.target.value})}/></label>
          <label>Fill color<input aria-label="Fill color" type="color" value={options.background||'#FFFFFF'} onChange={e=>patch({background:e.target.value})}/></label>
        </div>
        <label>Typeface
          <select aria-label="Typeface" value={options.fontFamily||'Poppins'} onChange={e=>patch({fontFamily:e.target.value})}>
            {['Poppins','Bricolage Grotesque','Arial','Georgia','Verdana'].map(f=><option key={f}>{f}</option>)}
          </select>
        </label>
        <label>Text alignment
          <select aria-label="Text alignment" value={options.textAlign||'left'} onChange={e=>patch({textAlign:e.target.value})}>
            {['left','center','right','justify'].map(a=><option key={a} value={a}>{a[0].toUpperCase()+a.slice(1)}</option>)}
          </select>
        </label>
        <div className="designer-property-grid">
          {numberInput('Font size','fontPx',8,120,canvasFontBaseline)}
          {numberInput('Font weight','fontWeight',400,800,600,'')}
          {numberInput('Letter spacing','letterSpacing',-5,20,0)}
          {numberInput('Line height','lineHeight',80,250,130,'%')}
          {numberInput('Padding','padding',0,80,0)}
        </div>
        <label>Opacity: {options.opacity??100}%
          <input type="range" aria-label="Element opacity" min="0" max="100" value={options.opacity??100}
            onChange={e=>patch({opacity:Number(e.target.value)})}/>
        </label>
      </div>
      <div className="designer-property-section">
        <h3><Layers size={15}/> Layer & visibility</h3>
        <div className="designer-property-grid">
          {numberInput('Layer order','zIndex',0,50,0,'')}
          {category==='items'&&numberInput('Card order','order',0,80,0,'')}
        </div>
        <label className="visual-lock-row"><input type="checkbox" checked={!!options.locked}
          aria-label="Lock selected element" onChange={e=>patch({locked:e.target.checked})}/>
          <LockKeyhole size={14}/> Lock element</label>
        <label className="visual-lock-row"><input type="checkbox" checked={!!options.hidden}
          aria-label="Hide selected element" onChange={e=>patch({hidden:e.target.checked})}/>
          <EyeOff size={14}/> Hide from page</label>
        <button type="button" className="designer-neutral-action" onClick={()=>designRemove(category,id)}>
          <RotateCw size={15}/> Reset styling
        </button>
      </div>
    </div>
  }
  function canvasOverlayControls(el:CanvasElement){
    const set=(p:Partial<CanvasElement>)=>overlayPatch(el.id,p)
    const num=(title:string,key:'x'|'y'|'width'|'height'|'rotate'|'radius'|'fontSize'|'opacity'|'zIndex',
      min:number,max:number,unit='px')=>
      <label className="designer-number-field">{title}
        <div className="designer-unit-input"><input type="number" aria-label={'Overlay '+title}
          min={min} max={max} value={el[key]}
          onChange={e=>set({[key]:Math.max(min,Math.min(max,Math.round(Number(e.target.value)||0)))})}/>
          <span>{unit}</span></div>
      </label>
    return <div className="designer-property-stack">
      <div className="designer-property-section">
        <h3>{el.type==='text'?'Text':el.type==='image'?'Image':el.type==='button'?'Button':'Shape'} properties</h3>
        {(el.type==='text'||el.type==='button')&&<label>Text
          <textarea aria-label="Overlay text" value={el.text||''} rows={3}
            disabled={!!el.locked} maxLength={1000} onChange={e=>set({text:e.target.value})}/>
        </label>}
        {(el.type==='image'||el.type==='button')&&<label>{el.type==='image'?'Image URL':'Button link'}
          <input aria-label={el.type==='image'?'Overlay image URL':'Overlay button URL'}
            disabled={!!el.locked} value={el.url||''} onChange={e=>set({url:e.target.value})}/>
        </label>}
        {el.type==='image'&&<label>Upload a photo
          <input aria-label="Upload overlay image" type="file" accept="image/png,image/jpeg,image/webp"
            disabled={!!el.locked} onChange={e=>uploadPicture(e.target.files?.[0]||null,url=>set({url}))}/>
        </label>}
        <label>Move to section
          <select aria-label="Overlay section" disabled={!!el.locked} value={el.sectionId}
            onChange={e=>set({sectionId:e.target.value})}>
            {editor?.template.sections.map(sec=><option key={sec.id} value={sec.id}>{sec.name}</option>)}
          </select>
        </label>
      </div>
      <div className="designer-property-section">
        <h3><Move size={15}/> Position & dimensions</h3>
        <div className="designer-property-grid">
          {num('Horizontal position','x',0,2400)}
          {num('Vertical position','y',0,12000)}
          {num('Width','width',30,1800)}
          {num('Height','height',20,1000)}
          {num('Rotation','rotate',-180,180,'°')}
          {num('Corners','radius',0,120)}
        </div>
        <small>Drag on the page to move; use the red corner handle to resize. Arrow keys move precisely, Shift + arrows move 10px.</small>
      </div>
      <div className="designer-property-section">
        <h3><Type size={15}/> Style</h3>
        <div className="designer-property-grid">
          <label>Text color<input type="color" aria-label="Overlay text color" value={el.color}
            disabled={!!el.locked} onChange={e=>set({color:e.target.value})}/></label>
          <label>Fill color<input type="color" aria-label="Overlay fill color" value={el.background}
            disabled={!!el.locked} onChange={e=>set({background:e.target.value})}/></label>
          {num('Text size','fontSize',8,120)}
          {num('Opacity','opacity',0,100,'%')}
        </div>
        <label>Typeface
          <select aria-label="Overlay font" value={el.fontFamily} disabled={!!el.locked}
            onChange={e=>set({fontFamily:e.target.value})}>
            {['Poppins','Bricolage Grotesque','Arial','Georgia','Verdana'].map(name=><option key={name}>{name}</option>)}
          </select>
        </label>
        <label>Weight
          <select aria-label="Overlay font weight" value={el.fontWeight} disabled={!!el.locked}
            onChange={e=>set({fontWeight:Number(e.target.value)})}>
            {[400,500,600,700,800].map(n=><option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label>Alignment
          <select aria-label="Overlay text alignment" value={el.textAlign} disabled={!!el.locked}
            onChange={e=>set({textAlign:e.target.value})}>
            {['left','center','right','justify'].map(a=><option key={a} value={a}>{a}</option>)}
          </select>
        </label>
      </div>
      <div className="designer-property-section">
        <h3><Layers size={15}/> Layer actions</h3>
        <div className="designer-property-grid">
          <button type="button" className="designer-neutral-action" disabled={!!el.locked||el.zIndex>=50}
            onClick={()=>set({zIndex:Math.min(50,el.zIndex+1)})}><ArrowUp size={14}/> Forward</button>
          <button type="button" className="designer-neutral-action" disabled={!!el.locked||el.zIndex<=0}
            onClick={()=>set({zIndex:Math.max(0,el.zIndex-1)})}><ArrowDown size={14}/> Backward</button>
        </div>
        <label className="visual-lock-row"><input type="checkbox" aria-label="Lock overlay" checked={!!el.locked}
          onChange={e=>set({locked:e.target.checked})}/><LockKeyhole size={14}/> Lock element</label>
        <label className="visual-lock-row"><input type="checkbox" aria-label="Hide overlay" checked={!!el.hidden}
          onChange={e=>set({hidden:e.target.checked})}/><EyeOff size={14}/> Hide element</label>
        <div className="designer-property-grid">
          <button type="button" className="designer-neutral-action" onClick={overlayDuplicate}
            disabled={(visualDesign.elements||[]).length>=50}><Copy size={15}/> Duplicate</button>
          <button type="button" className="designer-neutral-action danger" disabled={!!el.locked}
            onClick={overlayRemove}><Trash2 size={15}/> Delete</button>
        </div>
      </div>
    </div>
  }

  const mapping=templates.find(t=>t.id===mappingId)||uploaded
  const activeModule=isModuleNav(nav)?nav:'Category'
  const moduleTemplates=templates.filter(t=>moduleOfCategory(t.category)===activeModule)
  const modulePages=pages.filter(p=>moduleOfCategory(
    templates.find(t=>t.id===p.template_id)?.category||p.template_category||'Solution Category'
  )===activeModule)
  const visiblePages=pages.filter(p=>(nav==='Saved Drafts'?(p.status==='draft'||p.has_unpublished_changes):nav==='Published'?p.status==='published':filter==='All'?true:filter==='Draft'?(p.status==='draft'||p.has_unpublished_changes):p.status==='published'))
  const categoryPages=visiblePages.filter(p=>{
    if(!modulePages.some(modulePage=>modulePage.id===p.id))return false
    const search=pageSearch.trim().toLowerCase()
    return !search||[p.title,p.slug,templates.find(t=>t.id===p.template_id)?.name||''].some(value=>value.toLowerCase().includes(search))
  })
  const approvedTemplates=moduleTemplates.filter(t=>t.approved)
    .sort((a,b)=>Number(b.name.includes('Approved 2026'))-Number(a.name.includes('Approved 2026')))
  const selectedApprovedTemplate=approvedTemplates.find(t=>t.id===selectedTemplate)
  const allVisibleSelected=categoryPages.length>0&&categoryPages.every(p=>selectedPageIds.includes(p.id))
  const selectedHasPublished=modulePages.some(p=>selectedPageIds.includes(p.id)&&!!p.published_version)
  function chooseTemplateFile(file:File|null){
    if(file&&(!file.name.toLowerCase().endsWith('.html')||file.size>8*1024*1024)){
      setTemplateFile(null);showError('Choose an HTML file (.html) up to 8 MB.');return
    }
    setTemplateFile(file);setError('')
    if(file)setUploadName(file.name.replace(/\.html$/i,''))
  }
  async function archiveDraft(p:Page){
    if(p.published_version)return
    if(!window.confirm('Archive '+p.title+'? You can restore it later.'))return
    await action(async()=>{
      await api('/api/pages/'+p.id+'/archive',{method:'POST'})
      setSelectedPageIds(ids=>ids.filter(id=>id!==p.id))
      await refresh();notify('Draft archived')
    })
  }
  async function archiveSelectedDrafts(){
    const drafts=pages.filter(p=>selectedPageIds.includes(p.id)&&!p.published_version)
    if(!drafts.length||selectedHasPublished)return
    if(!window.confirm('Archive '+drafts.length+' selected drafts?'))return
    await action(async()=>{
      for(const p of drafts)await api('/api/pages/'+p.id+'/archive',{method:'POST'})
      setSelectedPageIds([])
      await refresh();notify('Selected drafts archived')
    })
  }

  if (!user) return (
    <div className="login-bg">
      <div className="login-card">
        <div className="login-brand">
          <div className="logo dark"><span className="logo-dot"/>workspace<span className="by-emlen">BY EMLEN</span></div>
        </div>

        <div className="login-intro">
          <div className="login-icon" aria-hidden="true"><LockKeyhole size={24}/></div>
          <h1>Welcome back.</h1>
          <p>Sign in to manage your website pages, templates and SEO.</p>
        </div>

        <form className="login-form" onSubmit={e=>{e.preventDefault();login()}}>
          <div className="login-field">
            <label htmlFor="login-identifier">Username or email</label>
            <input
              id="login-identifier"
              type="text"
              name="username"
              placeholder="Enter username or email"
              autoComplete="username"
              value={loginIdentifier}
              onChange={e=>setLoginIdentifier(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="login-field">
            <label htmlFor="login-password">Password</label>
            <div className="login-password-wrap">
              <input
                id="login-password"
                type={showLoginPassword?'text':'password'}
                name="password"
                placeholder="Your password"
                autoComplete="current-password"
                value={loginPassword}
                onChange={e=>setLoginPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="login-password-toggle"
                aria-label={showLoginPassword?'Hide password':'Show password'}
                aria-pressed={showLoginPassword}
                onClick={()=>setShowLoginPassword(value=>!value)}
              >{showLoginPassword?<EyeOff size={18}/>:<Eye size={18}/>}</button>
            </div>
          </div>
          <button className="primary fill login-submit" type="submit" disabled={busy}>
            {busy?'Signing in…':'Sign in'}{!busy&&<ArrowUpRight size={18}/>}
          </button>
        </form>
        {error&&<div className="alert error login-error" role="alert">{error}</div>}
      </div>
    </div>
  )

  return <div className="shell category-shell"><aside className="sidebar category-sidebar"><div className="brand"><span className="brand-mark"/> <div><strong>workspace</strong><small>BY EMLEN</small></div></div><div className="navigation">
    {MODULE_NAV.map((module,index)=><button key={module} className={'nav-item '+(nav===module?'active':'')} type="button"
      onClick={()=>navigate(module)} aria-current={nav===module?'page':undefined}>
      {index===0?<LayoutTemplate size={19}/>:index===1?<Layers size={19}/>:<Grid3X3 size={19}/>}
      {module}<ChevronRight className="right-chevron" size={16}/></button>)}
  </div><button className="logout" onClick={logout}><LogOut size={17}/> Sign out</button></aside>
  <main className="main"><div className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14}/> <span>{editor?'Page Editor':nav}</span></div><div className="topbar-right"><button className="password-link" onClick={()=>setShowPassword(true)}>Change password</button><span className="role">{user.role}</span><div className="avatar">{user.email[0].toUpperCase()}</div></div></div>
  <div className="content">{error&&<div className="alert error"><CircleHelp size={16}/>{error}<button onClick={()=>setError('')}><X size={16}/></button></div>}{message&&<div className="alert success"><Check size={16}/>{message}<button onClick={()=>setMessage('')}><X size={16}/></button></div>}

  {editor?<><div className="page-top we-editor-header">
    <div className="we-editor-heading">
      <button className="backlink" onClick={closeEditor}>← All Pages</button>
      <h1>{editor.page.title}</h1>
      <p>Edit the page content and SEO settings. Your published version stays unchanged until you publish.</p>
      <div className="editor-signals">
        {dirty&&<span className="unsaved-pill"><AlertTriangle size={14}/> Unsaved changes</span>}
        {editor.page.has_unpublished_changes&&<span className="draft-pill">Published · Unpublished changes</span>}
        {!dirty&&!editor.page.has_unpublished_changes&&<span className="saved-pill"><Check size={14}/> Saved</span>}
      </div>
      <div className="we-editor-jump-links" role="navigation" aria-label="Editor sections">
        <button type="button" onClick={()=>document.getElementById('section-editing')?.scrollIntoView({behavior:'smooth',block:'start'})}>Content <ChevronRight size={13}/></button>
        <button type="button" onClick={()=>document.getElementById('seo-settings')?.scrollIntoView({behavior:'smooth',block:'start'})}>SEO <ChevronRight size={13}/></button>
      </div>
    </div>
    <div className="we-editor-actions">
      <div className="we-editor-secondary-actions">
        <button className="outline" onClick={()=>fullPreview()} disabled={busy}>Full-page preview <ArrowUpRight size={16}/></button>
        <button className="outline" onClick={enableRepeatersOnThisPage} disabled={busy||dirty}><Plus size={15}/> Enable / refresh repeaters</button>
        {hasFixedLinkOrIcon&&user.role==='admin'&&<button className="outline" onClick={enableLinksAndIconsOnThisPage} disabled={busy||dirty}><LockKeyhole size={15}/> Enable links & icons</button>}
      </div>
      <div className="we-editor-main-actions">
        <button className="outline" onClick={savePage} disabled={busy||!dirty}><Save size={15}/> Save draft</button>
        {user.role==='admin'&&<button className="primary" onClick={publishPage} disabled={busy}>Publish locally <ArrowUpRight size={16}/></button>}
      </div>
    </div>
  </div>
  <div className="editor-layout editor-flow">
    <section className="edit-panel editor-section-panel" id="section-editing" aria-labelledby="editing-heading">
      <div className="panel-heading">
        <div><div className="small-label">01 / CONTENT</div><h2 id="editing-heading">Section Editing</h2><p>Edit each part in the same order it appears on the page. Choose a field to highlight it in the preview.</p></div>
        <span className="editor-field-total">{editableSections.length} editable sections</span>
      </div>
      <div className="editor-content-workspace"><div className="editor-section-rows">
         {editableSections.map(section=>{
           const ordered=sourceOrderedEditor(section,editor.template.fields.filter(f=>f.section_id===section.id))
           const propertySolutions=editor.template.category==='Property'&&/solutions/i.test(section.name)
           const tabNames=['Private Office','Coworking','Meeting Rooms','Additional']
           const sectionItems=propertySolutions?ordered.items.filter(part=>
             part.kind!=='group'||!part.group||!tabNames.includes(part.group.name)||part.group.name===propertySolutionsTab
           ):ordered.items
           const sectionOpen=section.id===activeSectionId
           return <div className="editor-section-block" key={section.id} id={'edit-section-'+section.id}>
             <button className="editor-section-toggle" type="button" aria-expanded={sectionOpen} onClick={()=>{setActiveEditorSection(sectionOpen?'':section.id);setFocusedPreviewField('')}}>
               <span className="editor-section-no">{String(section.order).padStart(2,'0')}</span>
               <span className="editor-section-name"><strong>{section.name}</strong><small>{ordered.items.length?ordered.items.length+' content '+(ordered.items.length===1?'group':'groups'):'Read-only / Static'} · Original page order</small></span>
               <ChevronRight size={17} className={'section-chevron '+(sectionOpen?'expanded':'')}/>
             </button>
             {sectionOpen&&<div className="editor-page-ordered-list">
               {propertySolutions&&<div className="property-solutions-switch" role="tablist" aria-label="Property workspace solution types">
                 {tabNames.map(type=><button key={type} type="button" role="tab"
                   aria-selected={propertySolutionsTab===type}
                   className={propertySolutionsTab===type?'selected':''}
                   onClick={()=>setPropertySolutionsTab(type)}>{type}</button>)}
               </div>}
               {ordered.items.length===0&&<div className="editor-locked-section"><LockKeyhole size={17}/>
                   {editor.template.category==='Property'&&/testimonials|reviews/i.test(section.name)
                     ?'Testimonials are read-only to protect approved reviews.'
                     :'This section is Static. Its original design stays in the preview.'}</div>}
               {sectionItems.map((part,i)=>part.kind==='group'&&part.group
                 ?renderRepeaterGroup(part.group,section)
                 :part.block?editorBlockControl(part.block,i):null)}
             </div>}
           </div>
         })}
         {editableSections.length===0&&<div className="editor-no-variable"><LockKeyhole size={20}/><strong>No editable sections</strong><p>Everything in this template is set to Static. Choose a template with Variable fields to edit page content.</p></div>}
       </div>
       <aside className="editor-side-preview" aria-label="Live section preview">
        <div className="editor-side-preview-head">
          <div><strong>Section preview</strong><small>{editor.template.sections.find(x=>x.id===activeSectionId)?.name||'Choose a section'}</small></div>
          <div className="editor-side-preview-actions"><button type="button" className="outline compact" onClick={()=>setPreviewRefresh(n=>n+1)}>Refresh</button>{activeSectionId&&<button type="button" className="outline compact" onClick={()=>fullPreview(activeSectionId)}>Expand <ArrowUpRight size={14}/></button>}</div>
        </div>
        <div className="editor-side-preview-tip">Your changes appear here as you type. Select a field to highlight it.</div>
        <div className="editor-side-preview-window">
          {activeSectionId&&sectionPreviewHtml
            ?<iframe title="Selected section preview" sandbox="allow-same-origin" srcDoc={sectionPreviewHtml} onLoad={e=>attachPreviewLinks(e.currentTarget)}/>
            :<div className="editor-side-preview-empty">{sectionPreviewLoading?'Loading section…':activeSectionId?'Preparing section…':'Choose a section on the left.'}</div>}
          {sectionPreviewLoading&&sectionPreviewHtml&&<span className="editor-preview-refreshing">Updating…</span>}
        </div>
        {sectionPreviewError&&<p className="editor-side-preview-error" role="alert">{sectionPreviewError}</p>}
        {!!linkFeedback&&<small className="editor-side-preview-feedback" role="status">{linkFeedback}</small>}
        <small className="editor-side-preview-foot">Preview only · Not published</small>
      </aside>
      </div>
    </section>

    <SeoSettings page={editor.page} fields={editor.template.fields} shared={shared} published={publicationInfo?.published} onChange={changeSEO}/>

    </div></>:
  <>
  {isModuleNav(nav)&&<div className="category-page">
    <div className="category-heading">
      <h1>{nav}</h1>
    </div>
    <div className={'tabs category-tabs '+(user.role==='admin'?'':'category-tabs-two')} role="tablist" aria-label={nav+' views'}>
      {(['All Pages','Add Page',...(user.role==='admin'?['Upload Template' as const]:[])] as Tab[]).map(name=>
        <button key={name} type="button" role="tab" aria-selected={tab===name} className={tab===name?'active':''} onClick={()=>setTab(name)}>{name}</button>
      )}
    </div>

    {tab==='All Pages'&&<div className="category-all-pages" role="tabpanel">
      <div className="category-toolbar">
        <div className="category-search"><Search size={19}/><input value={pageSearch} onChange={e=>setPageSearch(e.target.value)} placeholder="Search pages..." aria-label="Search pages"/></div>
        <div className="category-filters" role="group" aria-label="Page status filter">
          {(['All','Published','Draft'] as const).map(name=>
            <button type="button" key={name} className={filter===name?'active':''} aria-pressed={filter===name} onClick={()=>{setFilter(name);setSelectedPageIds([])}}>
              {name} <span>{name==='All'?modulePages.length:name==='Published'?modulePages.filter(p=>p.status==='published').length:modulePages.filter(p=>p.status==='draft'||p.has_unpublished_changes).length}</span>
            </button>
          )}
        </div>
      </div>
      {selectedPageIds.length>0&&<div className="category-selection-bar">
        <strong>{selectedPageIds.length} selected</strong>
        <button type="button" onClick={()=>setSelectedPageIds([])}>Clear selection</button>
        {user.role==='admin'&&<button type="button" disabled={busy||selectedHasPublished} title={selectedHasPublished?'Published pages cannot be archived':''} onClick={archiveSelectedDrafts}>Archive selected drafts</button>}
      </div>}
      <div className="category-pages-table">
        <div className="category-table-head">
          <input type="checkbox" aria-label="Select all visible pages" checked={allVisibleSelected} onChange={e=>{
            const ids=categoryPages.map(p=>p.id)
            setSelectedPageIds(selected=>e.target.checked?[...new Set([...selected,...ids])]:selected.filter(id=>!ids.includes(id)))
          }} disabled={!categoryPages.length}/>
          <span>Page Name</span><span>Template</span><span>Status</span><span>Updated</span><span className="category-action-title">Action</span>
        </div>
        {categoryPages.map(p=><div className="category-table-row" key={p.id}>
          <input type="checkbox" aria-label={'Select '+p.title} checked={selectedPageIds.includes(p.id)} onChange={e=>setSelectedPageIds(ids=>e.target.checked?[...ids,p.id]:ids.filter(id=>id!==p.id))}/>
          <div className="category-page-name"><strong>{p.title}</strong><span>{'/'+p.slug+'/'}</span></div>
          <div className="category-template-name">{templates.find(t=>t.id===p.template_id)?.name||p.template_name||'Previously removed template'}</div>
          <div><span className={'category-status '+(p.status==='published'?'category-published':'category-draft')}>{p.status==='published'?'Published':'Draft'}</span>{p.has_unpublished_changes&&<small className="category-draft-indicator">Unpublished changes</small>}</div>
          <time dateTime={p.updated_at}>{new Date(p.updated_at).toLocaleString('en-IN',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})}</time>
          <details className="category-actions"><summary aria-label={'Actions for '+p.title}><MoreHorizontal size={20}/></summary><div className="category-action-menu">
            <button type="button" onClick={()=>openPage(p)}>Edit page</button>
            {user.role==='admin'&&!p.published_version&&<button type="button" onClick={()=>archiveDraft(p)}>Archive draft</button>}
          </div></details>
        </div>)}
        {!categoryPages.length&&<div className="category-empty">
          <strong>{pageSearch||filter!=='All'?'No matching pages':'No pages yet'}</strong>
          {pageSearch||filter!=='All'
            ?<button type="button" className="outline" onClick={()=>{setPageSearch('');setFilter('All')}}>Clear filters</button>
            :<button type="button" className="primary" onClick={()=>setTab(user.role==='admin'?'Upload Template':'Add Page')}>{user.role==='admin'?'Upload a template':'Add a page'} <ArrowUpRight size={16}/></button>}
        </div>}
      </div>
    </div>}

    {tab==='Add Page'&&<AddPageWorkspace name={newName} selectedId={selectedTemplate}
      templates={approvedTemplates} selected={selectedApprovedTemplate||null} previewHtml={selectedTemplatePreview}
      busy={busy} isAdmin={user.role==='admin'} onNameChange={setNewName}
      onSelect={setSelectedTemplate} onSubmit={createPage}
      onCancel={()=>{setNewName('');setSelectedTemplate(null);setTab('All Pages')}}
      onUpload={()=>setTab('Upload Template')}/>}

    {tab==='Upload Template'&&user.role==='admin'&&<div className="category-upload-screen" role="tabpanel">
      <div className={'category-upload-dropzone '+(templateDragActive?'drag-active':'')} onDragOver={e=>{e.preventDefault();setTemplateDragActive(true)}} onDragLeave={e=>{e.preventDefault();setTemplateDragActive(false)}} onDrop={e=>{e.preventDefault();setTemplateDragActive(false);chooseTemplateFile(e.dataTransfer.files?.[0]||null)}}>
        <UploadCloud size={29}/>
        <strong>{templateFile?templateFile.name:'Upload an HTML template'}</strong>
        <span>Drag and drop an HTML file here, or</span>
        <label className="category-upload-browse">Browse files<input type="file" accept=".html,text/html" onChange={e=>chooseTemplateFile(e.target.files?.[0]||null)}/></label>
        <small>HTML (.html) · Maximum 8 MB</small>
      </div>
      <div className="category-upload-fields">
        <label>Template name<input value={uploadName} onChange={e=>setUploadName(e.target.value)} placeholder="e.g. Managed Office Category"/></label>
        <label>Category<select value={MODULE_INFO[activeModule].category} disabled><option>{MODULE_INFO[activeModule].category}</option></select></label>
        <button type="button" className="primary" onClick={uploadTemplate} disabled={!templateFile||busy}>Detect and map sections <ArrowUpRight size={17}/></button>
      </div>
      <div className="category-mapping-layout mapping-area">
        <section className="category-mapping-card category-mapping-fullwidth">
          <div className="category-panel-header category-fullwidth-header">
            <div><h2>Section Mapping</h2><p>{mapping?(mapping.sections.length+' detected sections · '+mapping.fields.length+' field candidates'):'Upload an HTML template to inspect all sections.'}</p></div>
            {mapping&&<button type="button" className="outline compact" disabled={busy} onClick={()=>redetectTemplate(mapping)}>Re-detect sections</button>}
          </div>
          {mapping?<div className="category-expanded-sections">
            {mapping.sections.map((sec,i)=>{
              const fields=mapping.fields.filter(f=>f.section_id===sec.id)
              const isReadOnly=mapping.category==='Property'&&/testimonials|reviews/i.test(sec.name)
              const isStatic=fields.every(f=>f.mode==='static')
              const isOpen=(openMappingSection===null?mapping.sections[0]?.id:openMappingSection)===sec.id
              const variableCount=fields.filter(f=>f.mode==='page').length
              const sharedCount=fields.filter(f=>f.mode==='global').length
              return <section key={sec.id} className={'category-section-card '+(isOpen?'is-open':'')+(isStatic?' is-static':'')}>
                <div className="category-section-card-header">
                  <span className="category-section-number">{String(i+1).padStart(2,'0')}</span>
                  <div className="category-section-summary">
                    <h3>{sec.name}</h3>
                    <small>{fields.length} fields <span aria-hidden="true">·</span> {isStatic?'Static, locked':variableCount+' variable'+(sharedCount?' · '+sharedCount+' shared':'')}</small>
                  </div>
                  <label className="category-static-toggle">
                    <span>Static</span>
                    <input type="checkbox" role="switch" aria-label={'Keep '+sec.name+' static'} checked={isStatic||isReadOnly} disabled={!fields.length||isReadOnly} onChange={e=>toggleSectionStatic(mapping.id,sec.id,e.target.checked)}/>
                    <span className="category-static-track" aria-hidden="true"/>
                  </label>
                  <button type="button" className="category-section-expand" aria-expanded={isOpen} aria-controls={'section-map-'+sec.id} onClick={()=>setOpenMappingSection(isOpen?'':sec.id)}>
                    {isOpen?'Show less':'View more'}<ChevronRight size={16} aria-hidden="true"/>
                  </button>
                </div>
                {isOpen&&<div id={'section-map-'+sec.id} className="category-section-card-content">
                  <div className="category-map-table">
                    <div className="category-map-table-head"><span>Detected field</span><span>Current content / link</span><span>Heading level</span><span>Behavior</span></div>
                    {fields.map(f=><div key={f.key} className="category-map-row map-field">
                      <div className="category-map-cell category-field-summary">
                        <strong title={f.label}>{f.label}</strong>
                        <small className="category-field-type">{f.kind==='link'?'Button / link destination':f.kind==='icon'?'Icon':f.kind==='image'?'Image':f.tag&&/^h[1-6]$/.test(f.tag)?'Heading':f.kind==='textarea'?'Long text':'Text'}</small>
                      </div>
                      <div className="category-map-cell">
                        {(f.kind==='link'||f.kind==='icon')&&!isStatic
                          ?<label className="category-map-control-label">{f.kind==='link'?'Destination URL':f.attr==='icon_src'?'Replacement icon URL':'Icon classes'}
                            <input aria-label={'Current value: '+f.key} value={f.default} onChange={e=>modifyMapField(mapping.id,f.key,{default:e.target.value})} placeholder={f.kind==='link'?'e.g. /contact/ or https://...':f.attr==='icon_src'?'Keep empty for original SVG':'e.g. fa fa-check'}/>
                          </label>
                          :<div className="category-detected-value" title={f.default}>{f.default||'Not set'}</div>}
                        {f.kind==='icon'&&f.attr==='icon_src'&&!isStatic&&<small className="category-field-help">Leave empty to keep the original SVG.</small>}
                      </div>
                      <div className="category-map-cell category-heading-cell">
                        {f.tag&&/^h[1-6]$/.test(f.tag)
                          ?<label className="category-map-control-label">Level
                            <select aria-label={'Heading level: '+f.key} value={f.heading_tag||f.tag} disabled={isStatic} onChange={e=>modifyMapField(mapping.id,f.key,{heading_tag:e.target.value})}>
                              {['h1','h2','h3','h4','h5','h6'].map(level=><option value={level} key={level}>{level.toUpperCase()}</option>)}
                            </select>
                          </label>
                          :<span className="category-not-heading">—</span>}
                      </div>
                      <div className="category-map-cell">
                        {isStatic?<span className="category-static-field-badge"><LockKeyhole size={13}/>Static</span>
                        :<label className="category-map-control-label">Behavior
                          <select aria-label={'Behavior: '+f.key} value={f.mode} onChange={e=>modifyMapField(mapping.id,f.key,{mode:e.target.value as Mode})}>
                            <option value="static">Static</option><option value="page">Variable</option><option value="global">Shared</option>
                          </select>
                        </label>}
                        {!isStatic&&f.mode==='global'&&<label className="category-shared-key">Shared key<input value={f.global_key||''} placeholder="e.g. phone_number" onChange={e=>modifyMapField(mapping.id,f.key,{global_key:e.target.value})}/></label>}
                      </div>
                    </div>)}
                    {!fields.length&&<p className="category-no-fields">No detected fields in this section.</p>}
                  </div>
                  {(isStatic||isReadOnly)&&<div className="category-locked-note"><LockKeyhole size={14}/>{isReadOnly?'Testimonials are permanently read-only.': 'This section is locked. Turn off Static to adjust links, heading levels or field behavior.'}</div>}
                </div>}
              </section>
            })}
          </div>:<div className="category-upload-placeholder"><LayoutTemplate size={23}/><p>Upload or select an HTML template to detect all sections and editable fields.</p></div>}
        </section>
        <section className="category-mapping-card category-preview-card category-preview-below">
          <div className="category-panel-header"><div><h2>Visual Preview</h2><p>Full template preview · scripts disabled</p></div></div>
          {mapping?<div className="category-browser-frame"><div className="category-browser-bar"><span/><span/><span/><div>{mapping.name}</div></div><iframe title="Mapped template preview" sandbox="" srcDoc={mapPreview}/></div>
          :<div className="category-upload-placeholder category-preview-placeholder"><Eye size={25}/><p>The complete uploaded design will appear here after detection.</p></div>}
        </section>
      </div>
      {mapping&&<div className="category-map-actions">
        <label className="approve"><input type="checkbox" checked={mapping.approved} onChange={e=>setTemplates(items=>items.map(t=>t.id===mapping.id?{...t,approved:e.target.checked}:t))}/> Approve template</label>
        <button className="primary" type="button" disabled={busy} onClick={()=>saveMapping(mapping)}>Save template configuration <ArrowUpRight size={17}/></button>
      </div>}
      <div className="category-uploaded-list">
        <div className="category-uploaded-heading">
          <h2>Uploaded Templates <span>({moduleTemplates.length})</span></h2>
          {moduleTemplates.length>0&&<button type="button" className="outline category-delete-templates" disabled={busy} onClick={()=>openDeleteDialog('all')}><Trash2 size={15}/> Delete all templates</button>}
        </div>
        <div className="category-uploaded-table">
          {moduleTemplates.map(t=><div className={'category-uploaded-row '+(mappingId===t.id?'selected':'')} key={t.id}>
            <div className="category-uploaded-file"><FileCode2 size={20}/><div><strong>{t.name}</strong><small>{t.category} · {t.sections.length} sections</small></div></div>
            <span className={'category-status '+(t.approved?'category-approved':'category-draft')}>{t.approved?'Approved':'Needs mapping'}</span>
            <div className="category-template-row-actions"><button type="button" className="outline" onClick={()=>{setMappingId(t.id);setFocusField('');setUploaded(t)}}>Configure <ArrowUpRight size={15}/></button><button type="button" className="category-template-delete-one" onClick={()=>openDeleteDialog(t)} disabled={busy} aria-label={'Delete template '+t.name} title={'Delete '+t.name}><Trash2 size={15}/> Delete</button></div>
          </div>)}
          {!moduleTemplates.length&&<div className="category-empty category-empty-templates"><strong>No templates uploaded yet</strong></div>}
        </div>
      </div>
    </div>}
  </div>}

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
  {deletingTemplate!==null&&<div className="dialog-backdrop template-delete-backdrop">
    <form className="dialog-card template-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="template-delete-title" onSubmit={e=>{e.preventDefault();confirmTemplateDeletion()}}>
      <div className="template-delete-icon"><Trash2 size={23}/></div>
      <h2 id="template-delete-title">{deletingTemplate==='all'?'Delete all templates?':'Delete this template?'}</h2>
      <p>{deletingTemplate==='all'?'Remove all templates from the active library?':'Remove "'+deletingTemplate.name+'" from the active library?'}</p>
      <p className="template-delete-warning">Are you sure? This removes the template from your active library. Pages already created from it, including published pages, keep their original content and can still be edited.</p>
      {deleteError&&<div className="template-delete-error" role="alert">{deleteError}</div>}
      <div className="button-group"><button type="button" className="outline" onClick={closeDeleteDialog} disabled={busy}>Cancel</button>
        <button type="submit" className="primary template-confirm-delete" disabled={busy}><Trash2 size={15}/> {busy?'Removing…':deletingTemplate==='all'?'Remove all templates':'Remove template'}</button>
      </div>
    </form>
  </div>}
  {showPassword&&<div className="dialog-backdrop"><form className="dialog-card" onSubmit={e=>{e.preventDefault();rotatePassword()}}><h2>Change your password</h2><p>All existing sessions will be signed out after the change.</p><label>Current password<input type="password" value={oldPassword} required onChange={e=>setOldPassword(e.target.value)}/></label><label>New password (minimum 12 characters)<input type="password" value={newPassword} minLength={12} required onChange={e=>setNewPassword(e.target.value)}/></label><div className="button-group"><button type="button" className="outline" onClick={()=>setShowPassword(false)}>Cancel</button><button className="primary" disabled={busy}>Change password</button></div></form></div>}
  {preview!==null&&<div className={'preview-modal '+(canvasMode?'canvas-active':'')}>
    {!!linkFeedback&&<div className="preview-link-feedback" role="status">{linkFeedback}<button type="button" aria-label="Dismiss link message" onClick={()=>setLinkFeedback('')}><X size={14}/></button></div>}
    <div className="preview-head">
      <div><strong>{canvasMode?'Visual Page Editor':'Full-page preview'}</strong><span>Draft only · Changes require Save draft · Live WordPress unaffected</span></div>
      <div className="visual-head-actions">
        {canvasMode&&<>
          <button type="button" title="Undo (Ctrl + Z)" aria-label="Undo design change" disabled={canvasUndoRef.current.length===0}
            onClick={undoCanvas}><Undo2 size={17}/><span className="designer-desktop-label">Undo</span></button>
          <button type="button" title="Redo (Ctrl + Y)" aria-label="Redo design change" disabled={canvasRedoRef.current.length===0}
            onClick={redoCanvas}><Redo2 size={17}/><span className="designer-desktop-label">Redo</span></button>
          <button type="button" aria-pressed={canvasGrid} aria-label="Toggle alignment grid" title="Alignment grid"
            onClick={()=>{setCanvasGrid(v=>!v);setPreviewRefresh(n=>n+1)}}><Grid3X3 size={16}/></button>
          <select aria-label="Preview device" className="designer-device-switch" value={canvasDevice} onChange={e=>setCanvasDevice(e.target.value as typeof canvasDevice)}>
            <option value="desktop">Desktop</option><option value="tablet">Tablet</option><option value="mobile">Mobile</option>
          </select>
          <select aria-label="Canvas zoom" className="designer-zoom-switch" value={canvasZoom} onChange={e=>setCanvasZoom(Number(e.target.value))}>
            {[50,75,90,100,125,150].map(v=><option key={v} value={v}>{v}%</option>)}
          </select>
        </>}
        <button type="button" className={canvasMode?'visual-mode-on':'visual-mode-off'} onClick={()=>{
          setCanvasMode(mode=>!mode);setCanvasSelection(null);setCanvasGroupId('');previewScrollRef.current=0
        }}><Eye size={16}/>{canvasMode?'Exit editor':'Edit design'}</button>
        {canvasMode&&<button type="button" className="visual-save" disabled={!dirty||busy} onClick={savePage}><Save size={15}/> Save draft</button>}
        <button type="button" onClick={()=>{setPreview(null);setCanvasMode(false);setCanvasSelection(null)}} aria-label="Close preview"><X size={23}/></button>
      </div>
    </div>
    <div className={'visual-main '+(canvasMode?'designer-workspace':'')}>
      {canvasMode&&<nav className="designer-toolrail" aria-label="Add elements">
        <button type="button" title="Select and drag elements" aria-label="Select tool" className="tool-active"
          onClick={()=>setCanvasSelection(null)}><MousePointer2 size={19}/><span>Select</span></button>
        <button type="button" title="Add text" aria-label="Add text" onClick={()=>overlayAdd('text')}>
          <Type size={20}/><span>Text</span></button>
        <button type="button" title="Add image" aria-label="Add image" onClick={()=>overlayAdd('image')}>
          <Image size={19}/><span>Image</span></button>
        <button type="button" title="Add rectangle or shape" aria-label="Add shape" onClick={()=>overlayAdd('shape')}>
          <Square size={19}/><span>Shape</span></button>
        <button type="button" title="Add button or link" aria-label="Add button" onClick={()=>overlayAdd('button')}>
          <Link2 size={19}/><span>Button</span></button>
        <button type="button" title="Show layers" aria-label="Show layers" aria-pressed={canvasLayersOpen}
          onClick={()=>setCanvasLayersOpen(v=>!v)}><Layers size={19}/><span>Layers</span></button>
      </nav>}
      <iframe key={canvasMode?'visual-editable':'readonly-preview'} ref={previewFrameRef} title="Website preview" sandbox="allow-same-origin"
        style={canvasMode?{width:canvasDevice==='desktop'?'100%':canvasDevice==='tablet'?'768px':'390px',maxWidth:'100%',zoom:canvasZoom/100,
          flex:canvasDevice==='desktop'?'1 1 auto':'none'}:undefined}
        srcDoc={preview} onLoad={e=>canvasLoaded(e.currentTarget)}/>
      {canvasMode&&<aside className="visual-inspector" aria-label="Visual editing inspector">
        <h2>Design controls</h2>
        <p>Click any editable element. Drag to move, drag the red corner to resize, or use the controls below. Changes stay in your draft.</p>
        <div className="designer-info-bar" title={'Draft design revision '+canvasUndoCounter}>
          <span>Editor ready</span><small>Ctrl+Z undo · Ctrl+D duplicate · Delete remove</small>
        </div>
        <div className="visual-inspector-group">
          <h3>Page settings</h3>
          <label>Page background
            <input aria-label="Page background color" type="color"
              value={visualDesign.page?.background||'#FFFFFF'}
              onChange={e=>commitDesign({...visualDesign,page:{...visualDesign.page,background:e.target.value}},'page-background')}/>
          </label>
          <small>Brand presets</small>
          <div className="designer-swatches">
            {['#ED2024','#161616','#FFB900','#FFFFFF','#FFF4F2'].map(color=>
              <button key={color} type="button" title={'Set page background '+color} aria-label={'Choose '+color+' background'}
                style={{background:color}} onClick={()=>commitDesign({...visualDesign,page:{...visualDesign.page,background:color}},'page-background')}/>)}
          </div>
        </div>
        {canvasLayersOpen&&<div className="visual-inspector-group designer-layers">
          <h3><Layers size={15}/> Layers</h3>
          {(visualDesign.elements||[]).length===0&&<small>No added elements yet. Use Text, Image, Shape or Button on the left.</small>}
          <details className="designer-existing-layers">
            <summary>Page cards & text</summary>
            <div className="designer-existing-layer-list">
              {allRepeaters.filter(g=>!g.parent_item_id).flatMap(group=>
                group.items.map(item=><button type="button" key={item.id}
                  className={canvasSelection?.itemId===item.id?'layer-selected':''}
                  onClick={()=>{setCanvasSelection({fieldKey:'',linkKey:'',groupId:group.id,itemId:item.id});setCanvasGroupId(group.id)}}>
                  <Layers size={13}/><span>{item.title||group.name}</span>
                  {visualDesign.items?.[item.id]?.locked&&<LockKeyhole size={12}/>}
                  {visualDesign.items?.[item.id]?.hidden&&<EyeOff size={12}/>}
                </button>))}
              {editor?.template.fields.filter(f=>f.mode==='page'&&(f.tag==='h1'||f.tag==='h2'||f.tag==='h3')).map(f=>
                <button type="button" key={f.key} className={canvasSelection?.fieldKey===f.key?'layer-selected':''}
                  onClick={()=>setCanvasSelection({fieldKey:f.key,linkKey:'',itemId:'',groupId:''})}>
                  <Type size={13}/><span>{f.label.slice(0,50)}</span>
                  {visualDesign.fields?.[f.key]?.hidden&&<EyeOff size={12}/>}
                </button>)}
            </div>
          </details>
          {(visualDesign.elements||[]).slice().sort((a,b)=>b.zIndex-a.zIndex).map(el=>
            <button type="button" key={el.id} className={el.id===canvasSelection?.elementId?'layer-selected':''}
              aria-label={'Select '+el.type+' layer '+el.id}
              onClick={()=>{setCanvasSelection({fieldKey:'',linkKey:'',groupId:'',itemId:'',elementId:el.id});setCanvasGroupId('')}}>
              {el.type==='text'?<Type size={15}/>:el.type==='image'?<Image size={15}/>:el.type==='button'?<Link2 size={15}/>:<Square size={15}/>}
              <span>{el.text?.slice(0,28)||el.type}</span>
              {el.locked&&<LockKeyhole size={12}/>}
              {el.hidden&&<EyeOff size={12}/>}
            </button>)}
        </div>}
        <div className="visual-inspector-group">
          <label>Repeatable section
            <select aria-label="Choose repeatable section" value={selectedCanvasGroup?.id||''} onChange={e=>{
              const gid=e.target.value;setCanvasGroupId(gid);setCanvasSelection({fieldKey:'',linkKey:'',itemId:'',groupId:gid})
            }}>
              <option value="">Select section</option>
              {allRepeaters.filter(g=>!g.parent_item_id).map(g=><option key={g.id} value={g.id}>{g.name} · {g.count} existing</option>)}
            </select>
          </label>
        </div>
        {selectedCanvasGroup&&<div className="visual-inspector-group">
          <h3>{selectedCanvasGroup.name}</h3>

          <label>Space between cards: {visualDesign.groups?.[selectedCanvasGroup.id]?.gap??16}px
            <input type="range" min="0" max="48" step="2" aria-label="Card spacing"
              value={visualDesign.groups?.[selectedCanvasGroup.id]?.gap??16}
              onChange={e=>designPatch('groups',selectedCanvasGroup.id,{gap:Number(e.target.value)})}/>
          </label>
          <button type="button" className="visual-add" disabled={repeatEntries(selectedCanvasGroup).length>=selectedCanvasGroup.max_additions}
            onClick={()=>addRepeatEntry(selectedCanvasGroup)}><Plus size={15}/> Add another {selectedCanvasGroup.kind==='faqs'?'FAQ':selectedCanvasGroup.kind==='solutions'?'solution':'card'}</button>
        </div>}
        {selectedCanvasElement&&canvasOverlayControls(selectedCanvasElement)}
        {canvasSelection?.itemId&&selectedCanvasField&&<div className="designer-inspect-switch">
          <button type="button" aria-pressed={canvasInspectTarget==='card'} onClick={()=>setCanvasInspectTarget('card')}>Card design</button>
          <button type="button" aria-pressed={canvasInspectTarget==='text'} onClick={()=>setCanvasInspectTarget('text')}>Selected text</button>
        </div>}
        {canvasSelection?.itemId&&selectedCanvasGroup&&canvasInspectTarget!=='text'&&<div className="visual-inspector-group">
          <h3>{selectedCanvasItem?.title||'Added card'}</h3>
          {selectedCanvasGroup.kind==='solutions'&&<div className="visual-variant-buttons">
            <span>Card layout</span>
            {(['regular','highlight','generic'] as const).map(variant=><button type="button" key={variant}
              aria-pressed={(selectedCanvasItem?editor?.page.values['__variant__'+selectedCanvasGroup.id+'__'+selectedCanvasItem.id]
                ||selectedCanvasItem.variant:repeatEntries(selectedCanvasGroup)[Number(canvasSelection.itemId.split('_added_')[1])-1]?.__variant||'regular')===variant}
              onClick={()=>{
                if(selectedCanvasItem)changeField('__variant__'+selectedCanvasGroup.id+'__'+selectedCanvasItem.id,variant)
                else{const index=Number(canvasSelection.itemId.split('_added_')[1])-1
                  if(index>=0)updateRepeatEntry(selectedCanvasGroup,index,'__variant',variant)}
              }}>{variant[0].toUpperCase()+variant.slice(1)}</button>)}
          </div>}
          <button type="button" className="designer-neutral-action" onClick={duplicateSelectedCard}><Copy size={14}/> Duplicate card</button>
          {canvasSelection?.itemId&&canvasStyleControls('items',canvasSelection.itemId)}
        </div>}
        {selectedCanvasField&&(!canvasSelection?.itemId||canvasInspectTarget==='text')&&<div className="visual-inspector-group">
          <h3>{fieldDisplayName(selectedCanvasField,'text',1)}</h3>
          {selectedCanvasField.mode==='page'&&!isFieldLocked(canvasSelection?.fieldKey||selectedCanvasField.key)
            ?<label>{selectedCanvasField.kind==='image'?'Replacement image URL':'Text'}
              {selectedCanvasField.kind==='image'&&<img className="visual-inspector-image" alt="Selected page image"
                src={extraIndex>=0&&selectedCanvasGroup
                  ?repeatEntries(selectedCanvasGroup)[extraIndex]?.[selectedCanvasField.key]||selectedCanvasField.default
                  :editor?.page.values[selectedCanvasField.key]||selectedCanvasField.default}/>}
              {selectedCanvasField.kind==='image'
                ?<><input aria-label="Selected image URL" placeholder="Paste an image URL; blank keeps original"
                  value={extraIndex>=0&&selectedCanvasGroup
                    ?repeatEntries(selectedCanvasGroup)[extraIndex]?.[selectedCanvasField.key]||''
                    :(editor?.page.values[selectedCanvasField.key]||'').startsWith('data:')?'':editor?.page.values[selectedCanvasField.key]||''}
                  onChange={e=>{
                    if(extraIndex>=0&&selectedCanvasGroup)updateRepeatEntry(selectedCanvasGroup,extraIndex,selectedCanvasField.key,e.target.value)
                    else if(!e.target.value)unsetField(selectedCanvasField.key)
                    else changeField(selectedCanvasField.key,e.target.value)
                  }}/>
                  <div className="editor-easy-image-upload"><label>Or upload a replacement photo
                    <input type="file" accept="image/png,image/jpeg,image/webp"
                      aria-label="Upload selected image"
                      onChange={e=>uploadPicture(e.target.files?.[0]||null,url=>{
                        if(extraIndex>=0&&selectedCanvasGroup)updateRepeatEntry(selectedCanvasGroup,extraIndex,selectedCanvasField.key,url)
                        else changeField(selectedCanvasField.key,url)
                      })}/>
                  </label></div></>
                :selectedCanvasField.kind==='icon'&&selectedCanvasField.attr==='icon_src'
                ?iconChoiceControl('visual-'+selectedCanvasField.key,
                  extraIndex>=0&&selectedCanvasGroup
                    ?repeatEntries(selectedCanvasGroup)[extraIndex]?.[selectedCanvasField.key]??selectedCanvasField.default
                    :editor?.page.values[selectedCanvasField.key]??selectedCanvasField.default,
                  v=>{
                    if(extraIndex>=0&&selectedCanvasGroup)updateRepeatEntry(selectedCanvasGroup,extraIndex,selectedCanvasField.key,v)
                    else changeField(selectedCanvasField.key,v)
                  })
                :<textarea aria-label="Selected element content" rows={3}
                  value={extraIndex>=0&&selectedCanvasGroup
                    ?repeatEntries(selectedCanvasGroup)[extraIndex]?.[selectedCanvasField.key]??selectedCanvasField.default
                    :editor?.page.values[selectedCanvasField.key]??selectedCanvasField.default}
                  onChange={e=>{
                    if(extraIndex>=0&&selectedCanvasGroup)updateRepeatEntry(selectedCanvasGroup,extraIndex,selectedCanvasField.key,e.target.value)
                    else changeField(selectedCanvasField.key,e.target.value)
                  }}/>}
            </label>
            :<p>{isFieldLocked(canvasSelection?.fieldKey||selectedCanvasField.key)?'This element is locked. Unlock it to edit.':'This text is Static in the approved template.'}</p>}
          {selectedCanvasLink?.mode==='page'&&<label>Button destination
            <input aria-label="Selected CTA destination" value={editor?.page.values[selectedCanvasLink.key]??selectedCanvasLink.default}
              onChange={e=>changeField(selectedCanvasLink.key,e.target.value)}/>
            {isTestableHref(editor?.page.values[selectedCanvasLink.key]??selectedCanvasLink.default)
              ?<a className="editor-inspector-test-link" href={editor?.page.values[selectedCanvasLink.key]??selectedCanvasLink.default} target="_blank" rel="noopener noreferrer"><ArrowUpRight size={14}/> Test this link</a>
              :<small>For a section on this page, enter an anchor such as #enquiry.</small>}
          </label>}
          {selectedCanvasField.mode==='page'&&canvasStyleControls('fields',canvasSelection?.fieldKey||selectedCanvasField.key)}
        </div>}
        {!selectedCanvasGroup&&!selectedCanvasField&&!selectedCanvasElement&&<div className="visual-inspector-empty">Select an element on the page, or add text, an image, a shape or a button from the left toolbar.</div>}
        <small className="visual-inspector-note">Page-specific changes · Desktop widths adapt to tablet and mobile · Preview is not published</small>
      </aside>}
    </div>
  </div>}
  </div>
}
