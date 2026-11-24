from bs4 import BeautifulSoup
from app.solution_mapping import solution_mapping, select_solution_office
from app.template_engine import render

HTML = """<html><body><section data-we-section="section_3"><ul class="sol-grid">
<li data-we-field="card_1"><article><h3 class="sol-name">One Seater</h3><p class="sol-desc">Old description</p><a data-we-field="cta_1" href="#enquiry">Enquire now</a></article></li>
<li data-we-field="card_2"><article><h3 class="sol-name">Two Seater</h3><p class="sol-desc">Second description</p></article></li>
</ul></section><section data-we-section="section_7"><ol class="hs"><li data-we-field="step_1"><article class="hs-card"><h3>Old step</h3><p>Old instructions</p></article></li></ol></section></body></html>"""

def field(key, section, default, mode="page", tag="li"):
    return {"key":key,"section_id":section,"kind":"text","attr":"text","label":"Old",
            "tag":tag,"mode":mode,"default":default,"marker":"data-we-field"}

def template():
    return {"category":"Solution","sections":[{"id":"section_3","name":"Options","order":1},
            {"id":"section_7","name":"How to Get Started","order":2}],
            "fields":[field("card_1","section_3","One Seater Old description Enquire now"),
                      field("card_2","section_3","Two Seater Second description"),
                      field("cta_1","section_3","Enquire now",tag="a"),
                      field("step_1","section_7","Old step Old instructions")]}

def test_split_cards_and_steps_preserves_markup_and_repeaters():
    original=template()
    source, mapping=solution_mapping(HTML,original)
    assert len(original["fields"])==4
    keys={f["key"] for f in mapping["fields"]}
    assert "card_1" not in keys
    assert {"card_1_heading","card_1_description","step_1_heading","step_1_description"} <= keys
    assert mapping["sections"][0]["repeaters"][0]["max_additions"]==2
    values={"card_1_heading":"Team Office","card_1_description":"Furnished desks",
            "step_1_heading":"Tell us your requirements","step_1_description":"Share team size"}
    rendered=BeautifulSoup(render(source,mapping["fields"],values,{}),"html.parser")
    assert rendered.select_one(".sol-name").text=="Team Office"
    assert rendered.select_one(".sol-desc").text=="Furnished desks"
    assert rendered.select_one(".sol-grid a").text=="Enquire now"
    assert rendered.select_one(".hs-card h3").text=="Tell us your requirements"
    assert rendered.select_one(".hs-card p").text=="Share team size"
    assert solution_mapping(HTML,original,values)[1]==mapping

def test_old_combined_overrides_and_locked_fields_are_not_reinterpreted():
    t=template()
    t["fields"][1]["mode"]="static"
    _, mapped=solution_mapping(HTML,t,{"card_1":"Legacy manual content"})
    keys={f["key"] for f in mapped["fields"]}
    assert {"card_1","card_2","step_1_heading"} <= keys
    assert "card_1_heading" not in keys and "card_2_heading" not in keys
    t["category"]="Property"
    assert solution_mapping(HTML,t)==(HTML,t)

def test_existing_solution_option_is_selected_without_changing_options():
    html='<form><select id="officeSelect" name="office"><option selected>One Person Office</option><option>Small Team Office</option></select></form>'
    result=BeautifulSoup(select_solution_office(html,"Small Team Office"),"html.parser")
    assert len(result.select("option"))==2
    assert result.select_one("option[selected]").text=="Small Team Office"
    assert select_solution_office(html,"Unknown")==html
