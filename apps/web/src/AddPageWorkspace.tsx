import {ArrowUpRight, Check, ChevronRight, FileText, LayoutTemplate, Plus} from 'lucide-react'

type ApprovedTemplate={
  id:number
  name:string
  category:string
  sections:{id:string;name:string}[]
}
type Props={
  name:string
  selectedId:number|null
  templates:ApprovedTemplate[]
  selected:ApprovedTemplate|null
  previewHtml:string
  busy:boolean
  isAdmin:boolean
  onNameChange:(value:string)=>void
  onSelect:(id:number|null)=>void
  onSubmit:()=>void
  onCancel:()=>void
  onUpload:()=>void
}

export default function AddPageWorkspace({
  name,selectedId,templates,selected,previewHtml,busy,isAdmin,
  onNameChange,onSelect,onSubmit,onCancel,onUpload
}:Props){
  return <div className="category-create-screen we-add-workspace" role="tabpanel" aria-label="Create a new page">
    <section className="category-form-card we-add-form">
      <header className="we-add-heading">
        <span className="small-label">01 / NEW PAGE</span>
        <h2>Add Page</h2>
        <p>Create a draft using an approved page design.</p>
      </header>

      <div className="we-add-field">
        <label htmlFor="category-new-page-name">Page name</label>
        <input id="category-new-page-name" value={name} maxLength={200}
          onChange={e=>onNameChange(e.target.value)}
          placeholder="Enter page name"/>
        <small>This name identifies the page in your dashboard.</small>
      </div>

      <div className="we-add-template-heading">
        <div><h3>Choose template</h3><p>Select an approved layout for this page.</p></div>
        <span className="we-add-count">{templates.length} available</span>
      </div>
      <div className="we-add-field we-add-template-select">
        <label htmlFor="category-template-select">Template</label>
        <select id="category-template-select" value={selectedId??''}
          onChange={e=>onSelect(e.target.value?Number(e.target.value):null)}>
          <option value="">Select approved template</option>
          {templates.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>

      <div className="we-template-options" role="group" aria-label="Approved templates">
        {templates.map(template=><button type="button" key={template.id}
          className={'we-template-choice'+(selectedId===template.id?' is-selected':'')}
          aria-pressed={selectedId===template.id}
          onClick={()=>onSelect(template.id)}>
          <span className="we-choice-icon"><LayoutTemplate size={18}/></span>
          <span className="we-choice-label">
            <strong>{template.name}</strong>
            <small>{template.category} · {template.sections.length} sections</small>
          </span>
          <span className="we-choice-select">{selectedId===template.id?<Check size={15}/>:<ChevronRight size={16}/>}</span>
        </button>)}
        {templates.length===0&&<div className="we-no-templates">
          <LayoutTemplate size={24}/>
          <strong>No approved templates yet</strong>
          <p>Approve a template first to create a page.</p>
          {isAdmin&&<button type="button" className="outline compact" onClick={onUpload}>Upload template <ArrowUpRight size={14}/></button>}
        </div>}
      </div>

      <div className="category-form-actions we-add-actions">
        <button type="button" className="outline" onClick={onCancel}>Cancel</button>
        <button type="button" className="primary" onClick={onSubmit}
          disabled={busy||!selectedId||!name.trim()}>
          <Plus size={16}/> Add Page <ArrowUpRight size={15}/>
        </button>
      </div>
    </section>

    <aside className="category-template-summary we-add-preview" aria-label="Selected template preview">
      <div className="we-add-preview-top">
        <div><span className="small-label">02 / PREVIEW</span><h2>Template preview</h2></div>
        <span className="we-preview-tag">Original design</span>
      </div>
      {selected
        ?<>
          <div className="we-add-preview-frame">
            {previewHtml
              ?<iframe title="Selected template preview" sandbox="" srcDoc={previewHtml}/>
              :<div className="we-add-preview-loading">Loading template preview…</div>}
          </div>
          <div className="we-add-template-info">
            <div className="we-add-template-name"><div><strong>{selected.name}</strong><small>{selected.category}</small></div>
              <span className="category-status category-approved">Approved</span></div>
            <div className="we-add-section-list">
              <div><FileText size={15}/><strong>Page sections</strong><span>{selected.sections.length}</span></div>
              <div className="we-add-section-chips">
                {selected.sections.map((section,index)=><span key={section.id}>{String(index+1).padStart(2,'0')} · {section.name}</span>)}
              </div>
            </div>
          </div>
        </>
        :<div className="we-add-preview-empty"><LayoutTemplate size={29}/>
          <strong>Select a template</strong>
          <p>The approved page design will appear here before you create the draft.</p></div>}
    </aside>
  </div>
}
