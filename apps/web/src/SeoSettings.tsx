import {useState} from 'react'
import {Check, CircleHelp, Globe2, LayoutTemplate, MoreHorizontal, WandSparkles} from 'lucide-react'

type SEO={
  seo_title:string; description:string; noindex:boolean; nofollow:boolean;
  noarchive?:boolean; noimageindex?:boolean; nosnippet?:boolean;
  canonical_override:string; og_title?:string; og_description?:string
}
type Page={title:string;slug:string;seo:SEO;values:Record<string,string>}
type Field={key:string;kind:string;attr:string;mode:string;default:string;tag?:string;global_key?:string|null}
type Published={slug:string;version:number;seo:SEO}
type Props={
  page:Page;fields:Field[];shared:Record<string,string>;
  published?:Published|null;onChange:(patch:Partial<SEO>)=>void
}
function cleanText(value:string){
  return value.replace(/<[^>]*>/g,' ').replace(/&nbsp;/gi,' ')
    .replace(/&amp;/gi,'&').replace(/\s+/g,' ').trim()
}
function robotsLabel(seo:SEO){
  return [seo.noindex?'noindex':'index',seo.nofollow?'nofollow':'follow',
    ...(seo.noarchive?['noarchive']:[]),...(seo.noimageindex?['noimageindex']:[]),
    ...(seo.nosnippet?['nosnippet']:[])].join(', ')
}

export default function SeoSettings({page,fields,shared,published,onChange}:Props){
  const [previewKind,setPreviewKind]=useState<'search'|'social'>('search')
  const [previewSize,setPreviewSize]=useState<'desktop'|'mobile'>('desktop')
  const seo=page.seo||({} as SEO)
  const fieldText=(field:Field)=>{
    const edited=field.mode==='page'?page.values[field.key]
      :field.mode==='global'&&field.global_key?shared[field.global_key]:undefined
    return cleanText(typeof edited==='string'&&edited.trim()?edited:field.default||'')
  }
  const texts=fields.filter(f=>f.kind==='text'&&f.attr==='text')
  const primaryHeading=texts.find(f=>f.tag==='h1'&&fieldText(f))
    ||texts.find(f=>f.tag==='h2'&&fieldText(f))
  const heading=primaryHeading?fieldText(primaryHeading):page.title
  const paragraphs=texts.filter(f=>f.tag==='p').map(fieldText).filter(t=>t.length>=24)
  const sourceDescription=(paragraphs.find(s=>s.length>=55)||paragraphs[0]||'').slice(0,165)
  const fallbackTitle=heading.toLowerCase().includes('workspace by emlen')
    ?heading.slice(0,110):(heading+' | Workspace by Emlen').slice(0,110)
  const seoTitle=(seo.seo_title||'').trim()
  const seoDescription=(seo.description||'').trim()
  const displayTitle=seoTitle||fallbackTitle
  const displayDescription=seoDescription||sourceDescription
  const siteUrl='https://workspacebyemlen.co.in/'+page.slug.replace(/^\/+|\/+$/g,'')+'/'
  const socialTitle=(seo.og_title||'').trim()||displayTitle
  const socialDescription=(seo.og_description||'').trim()||displayDescription
  const canFill=(!seoTitle&&!!fallbackTitle)||(!seoDescription&&!!sourceDescription)

  const directives=[
    {key:'index',name:'Index',detail:'Allow this page in search results.',checked:!seo.noindex,exclusive:true,change:()=>onChange({noindex:false})},
    {key:'noindex',name:'No Index',detail:'Keep this page out of search results.',checked:!!seo.noindex,exclusive:true,change:()=>onChange({noindex:true})},
    {key:'nofollow',name:'Nofollow',detail:'Ask crawlers not to follow page links.',checked:!!seo.nofollow,exclusive:false,change:()=>onChange({nofollow:!seo.nofollow})},
    {key:'noarchive',name:'No Archive',detail:'Legacy directive (not used by Google).',checked:!!seo.noarchive,exclusive:false,change:()=>onChange({noarchive:!seo.noarchive})},
    {key:'noimageindex',name:'No Image Index',detail:'Exclude this page’s images from indexing.',checked:!!seo.noimageindex,exclusive:false,change:()=>onChange({noimageindex:!seo.noimageindex})},
    {key:'nosnippet',name:'No Snippet',detail:'Hide text snippets in search results.',checked:!!seo.nosnippet,exclusive:false,change:()=>onChange({nosnippet:!seo.nosnippet})}
  ]
  function fillFromPage(){
    const patch:Partial<SEO>={}
    if(!seoTitle&&fallbackTitle)patch.seo_title=fallbackTitle
    if(!seoDescription&&sourceDescription)patch.description=sourceDescription
    if(Object.keys(patch).length)onChange(patch)
  }

  return <section className="edit-panel editor-seo-panel we-seo-section" id="seo-settings" aria-labelledby="seo-heading">
    <div className="panel-heading we-seo-title-row">
      <div><div className="small-label">02 / SEARCH</div>
        <h2 id="seo-heading">SEO Settings</h2>
        <p>Manage search appearance and indexing for this page.</p>
      </div>
      {published&&<span className="we-published-chip"><Check size={13}/> Published version {published.version}</span>}
    </div>

    <div className="we-seo-workspace">
      <div className="we-seo-form-column">
        <div className="we-seo-card we-seo-metadata-card">
          <div className="we-seo-card-head">
            <div><span className="we-eyebrow">PAGE METADATA</span><h3>Search appearance</h3></div>
            <button type="button" className="outline compact seo-autofill" onClick={fillFromPage}
              disabled={!canFill} title="Fill only empty SEO fields from the current page">
              <WandSparkles size={14}/> Use page content
            </button>
          </div>
          <div className="we-seo-fields">
            <label>SEO title
              <input aria-label="SEO title" value={seo.seo_title||''} maxLength={500}
                onChange={e=>onChange({seo_title:e.target.value})}
                placeholder={fallbackTitle||'Enter search title'}/>
              <small>{(seo.seo_title||'').length} characters · Preview updates as you type</small>
            </label>
            <label>Meta description
              <textarea aria-label="Meta description" rows={3} value={seo.description||''} maxLength={500}
                onChange={e=>onChange({description:e.target.value})}
                placeholder={sourceDescription||'Describe this page for search results'}/>
              <small>{(seo.description||'').length} characters</small>
            </label>
          </div>
        </div>

        <div className="seo-robots-panel we-seo-card">
          <div className="seo-robots-head">
            <div><span className="we-eyebrow">ROBOTS META</span>
              <h3>Indexing & visibility</h3></div>
            <span className={'seo-index-state'+(seo.noindex?' is-noindex':'')}>
              {seo.noindex?'No Index':'Index'}
            </span>
          </div>
          <div className="seo-robots-grid" role="group" aria-label="Robots meta settings">
            {directives.map(d=><label key={d.key}
              className={'seo-robot-option'+(d.checked?' is-checked':'')}>
              <span className="seo-robot-control">
                <input type={d.exclusive?'radio':'checkbox'}
                  name={d.exclusive?'seo-indexing':undefined}
                  checked={d.checked} onChange={d.change} aria-label={d.name}/>
                <span className="seo-robot-square" aria-hidden="true"><Check size={13}/></span>
              </span>
              <span className="seo-robot-copy"><strong>{d.name}</strong><small>{d.detail}</small></span>
              {d.key==='noarchive'&&<CircleHelp size={14} className="seo-robot-help"
                aria-label="Google Search ignores this legacy directive"/>}
            </label>)}
          </div>
        </div>

        <div className="we-seo-card we-seo-advanced-card">
          <div className="we-seo-card-head"><div><span className="we-eyebrow">PAGE URL</span>
            <h3>Canonical URL</h3></div></div>
          <label>Canonical override (optional)
            <input aria-label="Canonical override (optional)" type="url"
              value={seo.canonical_override||''} maxLength={500}
              onChange={e=>onChange({canonical_override:e.target.value})}
              placeholder="Automatic self-canonical"/>
          </label>
          <small className="we-seo-hint">Leave empty to use the page’s own URL.</small>
          <details className="we-seo-social-fields">
            <summary>Social sharing settings <span>Optional</span></summary>
            <div className="we-seo-fields">
              <label>Social title
                <input value={seo.og_title||''} maxLength={500}
                  onChange={e=>onChange({og_title:e.target.value})}
                  placeholder={displayTitle}/>
              </label>
              <label>Social description
                <textarea rows={2} value={seo.og_description||''} maxLength={500}
                  onChange={e=>onChange({og_description:e.target.value})}
                  placeholder={displayDescription||'Social link description'}/>
              </label>
            </div>
          </details>
          {published&&<details className="we-seo-publication">
            <summary>Compare with published SEO</summary>
            <dl><dt>Title</dt><dd>{published.seo.seo_title||'Not set'}</dd>
              <dt>Meta description</dt><dd>{published.seo.description||'Not set'}</dd>
              <dt>Visibility</dt><dd>{robotsLabel(published.seo)}</dd></dl>
          </details>}
        </div>
      </div>

      <aside className="seo-rich-preview we-seo-preview-column" aria-label="Live search result preview">
        <div className="seo-rich-preview-head">
          <div><span className="we-eyebrow">03 / LIVE PREVIEW</span>
            <h3>How your page appears</h3></div>
          <span className="seo-preview-live"><span/> Live</span>
        </div>
        <div className="we-seo-preview-switches">
          <div role="tablist" aria-label="Preview type" className="we-seo-preview-tabs">
            <button type="button" role="tab" aria-selected={previewKind==='search'}
              onClick={()=>setPreviewKind('search')}><Globe2 size={14}/> Search</button>
            <button type="button" role="tab" aria-selected={previewKind==='social'}
              onClick={()=>setPreviewKind('social')}><LayoutTemplate size={14}/> Social</button>
          </div>
          {previewKind==='search'&&<div role="group" aria-label="Search result viewport" className="we-seo-device-buttons">
            <button type="button" aria-pressed={previewSize==='desktop'}
              onClick={()=>setPreviewSize('desktop')}>Desktop</button>
            <button type="button" aria-pressed={previewSize==='mobile'}
              onClick={()=>setPreviewSize('mobile')}>Mobile</button>
          </div>}
        </div>
        {seo.noindex&&<div className="seo-preview-alert"><CircleHelp size={15}/>
          <span>No Index is selected. The result below is a draft illustration only.</span></div>}
        {previewKind==='search'
          ?<div className={'seo-serp-result we-search-preview-'+previewSize}>
            <div className="seo-serp-origin">
              <span className="seo-serp-favicon">w<span>.</span></span>
              <span className="seo-serp-domain"><strong>Workspace by Emlen</strong>
                <small>{siteUrl}</small></span><MoreHorizontal size={18} aria-hidden="true"/>
            </div>
            <h4>{displayTitle}</h4>
            {seo.nosnippet
              ?<p className="seo-serp-muted">Text snippet hidden because No Snippet is selected.</p>
              :<p className={displayDescription?'':'seo-serp-muted'}>
                {displayDescription||'Enter a meta description to see the search preview.'}</p>}
          </div>
          :<div className="we-social-preview-card">
            <div className="we-social-preview-brand">workspace <small>BY EMLEN</small></div>
            <div className="we-social-preview-copy"><small>workspacebyemlen.co.in</small>
              <strong>{socialTitle}</strong>
              <p>{socialDescription||'Add a social description to preview it here.'}</p>
            </div>
          </div>}
        <div className="we-seo-preview-footer">
          <span><Check size={13}/> Uses the current unsaved page content</span>
          <p>Search engines and social platforms may choose a different preview.</p>
        </div>
      </aside>
    </div>
  </section>
}
