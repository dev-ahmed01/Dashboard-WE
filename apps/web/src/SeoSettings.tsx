import {Check, CircleHelp, MoreHorizontal, WandSparkles} from 'lucide-react'

type SEO = {
  seo_title: string
  description: string
  noindex: boolean
  nofollow: boolean
  noarchive?: boolean
  noimageindex?: boolean
  nosnippet?: boolean
  canonical_override: string
  og_title?: string
  og_description?: string
}
type Page = {title:string; slug:string; seo:SEO; values:Record<string,string>}
type Field = {key:string; kind:string; attr:string; mode:string; default:string; tag?:string; global_key?:string|null}
type Published = {slug:string; version:number; seo:SEO}
type Props = {
  page:Page
  fields:Field[]
  shared:Record<string,string>
  published?:Published|null
  onChange:(patch:Partial<SEO>)=>void
}

function cleanText(value:string){
  return value.replace(/<[^>]*>/g,' ').replace(/&nbsp;/gi,' ')
    .replace(/&amp;/gi,'&').replace(/\s+/g,' ').trim()
}

function enabledRobots(seo:SEO){
  return [
    seo.noindex?'noindex':'index',
    seo.nofollow?'nofollow':'follow',
    ...(seo.noarchive?['noarchive']:[]),
    ...(seo.noimageindex?['noimageindex']:[]),
    ...(seo.nosnippet?['nosnippet']:[])
  ]
}

export default function SeoSettings({page,fields,shared,published,onChange}:Props){
  const seo=page.seo
  // Use the same editable values and original template defaults displayed in the page editor.
  // Never invent marketing copy or mistake button/CTA text for a meta description.
  const fieldText=(field:Field)=>{
    const edited=field.mode==='page'?page.values[field.key]:
      field.mode==='global'&&field.global_key?shared[field.global_key]:undefined
    return cleanText(typeof edited==='string'&&edited.trim()?edited:field.default||'')
  }
  const textFields=fields.filter(f=>f.kind==='text'&&f.attr==='text')
  const pageHeading=textFields.find(f=>f.tag==='h1'&&fieldText(f))||
    textFields.find(f=>f.tag==='h2'&&fieldText(f))
  const sourceHeading=pageHeading?fieldText(pageHeading):page.title
  const descriptive=textFields.filter(f=>f.tag==='p').map(fieldText).filter(s=>s.length>=24)
  const sourceDescription=(descriptive.find(s=>s.length>=55)||descriptive[0]||'').slice(0,160)
  const fallbackTitle=sourceHeading.toLowerCase().includes('workspace by emlen')?
    sourceHeading.slice(0,110):(sourceHeading+' | Workspace by Emlen').slice(0,110)
  const displayTitle=seo.seo_title.trim()||fallbackTitle
  const displayDescription=seo.description.trim()||sourceDescription
  const displayUrl='https://workspacebyemlen.co.in/'+page.slug.replace(/^\/+|\/+$/g,'')+'/'
  const autoFillAvailable=(!seo.seo_title.trim()&&!!fallbackTitle)||
    (!seo.description.trim()&&!!sourceDescription)

  const directives=[
    {key:'index',title:'Index',detail:'Allow this page to appear in search results.',checked:!seo.noindex,exclusive:true,choose:()=>onChange({noindex:false})},
    {key:'noindex',title:'No Index',detail:'Ask search engines not to show this page.',checked:seo.noindex,exclusive:true,choose:()=>onChange({noindex:true})},
    {key:'nofollow',title:'Nofollow',detail:'Ask crawlers not to follow links on this page.',checked:!!seo.nofollow,exclusive:false,choose:()=>onChange({nofollow:!seo.nofollow})},
    {key:'noarchive',title:'No Archive',detail:'Legacy cache instruction; ignored by Google Search.',checked:!!seo.noarchive,exclusive:false,choose:()=>onChange({noarchive:!seo.noarchive})},
    {key:'noimageindex',title:'No Image Index',detail:'Request that images not be indexed from this page.',checked:!!seo.noimageindex,exclusive:false,choose:()=>onChange({noimageindex:!seo.noimageindex})},
    {key:'nosnippet',title:'No Snippet',detail:'Ask search engines not to show a text preview.',checked:!!seo.nosnippet,exclusive:false,choose:()=>onChange({nosnippet:!seo.nosnippet})},
  ]

  function fillFromPage(){
    const patch:Partial<SEO>={}
    if(!seo.seo_title.trim())patch.seo_title=fallbackTitle
    if(!seo.description.trim()&&sourceDescription)patch.description=sourceDescription
    if(Object.keys(patch).length)onChange(patch)
  }

  return <section className="edit-panel editor-seo-panel" id="seo-settings" aria-labelledby="seo-heading">
    <div className="panel-heading seo-panel-title">
      <div><div className="small-label">02 / SEARCH</div><h2 id="seo-heading">SEO Settings</h2>
        <p>Manage how this page can appear in search results.</p></div>
      <button type="button" className="outline compact seo-autofill" onClick={fillFromPage}
        disabled={!autoFillAvailable} title="Fill only empty SEO fields using existing page text">
        <WandSparkles size={15}/> Use page content
      </button>
    </div>
    <div className="form-stack seo-form-stack">
      {published&&<div className="publication-diff">
        <strong>Currently published SEO · Version {published.version}</strong>
        <p>These are the values in the last local publication. Your draft changes will only apply after republishing.</p>
        <dl><dt>Title</dt><dd>{published.seo.seo_title||'Not set'}</dd>
          <dt>Meta description</dt><dd>{published.seo.description||'Not set'}</dd>
          <dt>Robots</dt><dd>{enabledRobots(published.seo).join(', ')}</dd>
          <dt>URL</dt><dd>/{published.slug}/</dd></dl>
      </div>}
      <div className="seo-primary-fields seo-simple-fields">
        <label>SEO title
          <input value={seo.seo_title||''} maxLength={500} onChange={e=>onChange({seo_title:e.target.value})}
            placeholder={fallbackTitle||'Your unique search title'}/>
        </label>
        <label className="wide-field">Meta description
          <textarea rows={3} value={seo.description||''} maxLength={500}
            onChange={e=>onChange({description:e.target.value})}
            placeholder={sourceDescription||'Describe this page for search results'}/>
        </label>
      </div>

      <div className="seo-robots-panel">
        <div className="seo-robots-head">
          <div><div className="seo-subtitle">ROBOTS META</div><h3>Search visibility controls</h3>
            <p>Choose which indexing and preview instructions to include in the page's HTML.</p></div>
          <span className={'seo-index-state'+(seo.noindex?' is-noindex':'')}>
            {seo.noindex?'No Index':'Index allowed'}
          </span>
        </div>
        <div className="seo-robots-grid" role="group" aria-label="Robots meta settings">
          {directives.map(option=><label className={'seo-robot-option'+(option.checked?' is-checked':'')}
            key={option.key}>
            <span className="seo-robot-control">
              <input type={option.exclusive?'radio':'checkbox'}
                name={option.exclusive?'seo-indexing':undefined}
                checked={option.checked} onChange={option.choose} aria-label={option.title}/>
              <span className="seo-robot-square" aria-hidden="true"><Check size={13}/></span>
            </span>
            <span className="seo-robot-copy"><strong>{option.title}</strong><small>{option.detail}</small></span>
            {option.key==='noarchive'&&<CircleHelp size={15} className="seo-robot-help" aria-label="Google no longer uses noarchive" />}
          </label>)}
        </div>
        <div className="seo-robots-footer"><span>Generated robots meta:</span>
          <code>{enabledRobots(seo).join(', ')}</code></div>
      </div>

      <label>Canonical override (optional)
        <input value={seo.canonical_override||''} maxLength={500}
          onChange={e=>onChange({canonical_override:e.target.value})}
          placeholder="Automatic self-canonical"/>
      </label>

      <div className="seo-rich-preview" aria-label="Live search result preview">
        <div className="seo-rich-preview-head">
          <div><div className="seo-subtitle">LIVE PREVIEW</div><h3>Search result preview</h3>
            <p>Built from this page's actual heading, description and current SEO fields.</p></div>
          <span className="seo-preview-live"><span/> Live</span>
        </div>
        {seo.noindex&&<div className="seo-preview-alert">
          <CircleHelp size={16}/><span><strong>No Index is enabled.</strong> This is an illustrative preview only; compliant search engines should omit this page from results.</span>
        </div>}
        <div className="seo-serp-result">
          <div className="seo-serp-origin">
            <span className="seo-serp-favicon">w<span>.</span></span>
            <span className="seo-serp-domain"><strong>Workspace by Emlen</strong><small>{displayUrl}</small></span>
            <MoreHorizontal size={19} aria-hidden="true" />
          </div>
          <h4>{displayTitle}</h4>
          {seo.nosnippet
            ?<p className="seo-serp-muted">Text snippet hidden because No Snippet is selected.</p>
            :<p className={displayDescription?'':'seo-serp-muted'}>{displayDescription||
              'No descriptive page content detected. Add a meta description to complete this preview.'}</p>}
        </div>
        <div className="seo-preview-note">
          Preview is illustrative. Search engines may change the title or description they display.
          {!seo.seo_title.trim()||!seo.description.trim()?' Empty SEO fields use existing page content for this preview only.':''}
        </div>
      </div>
    </div>
  </section>
}
