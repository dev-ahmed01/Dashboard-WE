"""V23: rich design persistence, sanitized overlays and immutable publications."""
import json
from bs4 import BeautifulSoup
from tests.test_persona_qa import client, login, imported, approve, page, put_page, seo, publish
from tests.test_repeaters_v20 import PAGE_HTML

def overlay(id='ov_test_element_01',type='text',section_id='hero',**patch):
    result=dict(id=id,type=type,sectionId=section_id,text='Visual text',url='',
      x=32,y=80,width=250,height=90,fontSize=28,fontFamily='Poppins',
      fontWeight=600,color='#161616',background='#FFFFFF',
      opacity=90,rotate=12,radius=12,textAlign='center',zIndex=20)
    result.update(patch)
    if type=='image':
        result['url']=patch.get('url','https://example.com/office.png')
    if type=='button':
        result['url']=patch.get('url','https://kommodo.ai/i/sCYKuA1fO4ob1o92TkHk')
        result['text']='See office'
    return result

def test_canva_page_elements_render_and_survive_save(client):
    auth=login(client)
    t=approve(client,auth,imported(client,auth,PAGE_HTML.encode(),name="Canvas controls"),
       {'Workspaces for your team':'page','Prime locations':'page'})
    p=page(client,auth,t)
    loaded=client.get(f"/api/pages/{p['id']}",headers=auth).json()
    first_sec=loaded['template']['sections'][0]['id']
    h1=next(f for f in loaded['template']['fields'] if f['default']=='Workspaces for your team')
    groups=[g for sec in loaded['template']['sections'] for g in sec.get('repeaters',[])]
    highlights=next(g for g in groups if g['kind']=='highlights')
    item_id=highlights['items'][0]['id']
    design={
      'fields':{h1['key']:{'fontPx':48,'color':'#ED2024','x':24,'y':-10,
                  'rotate':5,'textAlign':'center','opacity':85,
                  'fontFamily':'Bricolage Grotesque','fontWeight':800}},
      'items':{item_id:{'span':2,'heightPx':410,'radius':22,'background':'#FFB900','zIndex':12,
                          'order':3,'hidden':False}},
      'page':{'background':'#FFF4F2'},
      'elements':[
        overlay(section_id=first_sec,text='Custom <img src=x onerror=alert(1)>'),
        overlay(id='ov_button_added',type='button',section_id=first_sec),
        overlay(id='ov_shape_added',type='shape',section_id=first_sec,text='',rotate:-20),
        overlay(id='ov_image_added',type='image',section_id=first_sec),
      ]
    }
    saved=put_page(client,p['id'],auth,{'values':{'__design__':json.dumps(design)}})
    assert saved.status_code==200,saved.text
    rendered=client.get(f"/api/pages/{p['id']}/preview",headers=auth)
    assert rendered.status_code==200,rendered.text
    soup=BeautifulSoup(rendered.text,'html.parser')
    heading=soup.find('h1')
    assert 'font-size:48px!important' in heading['style']
    assert 'color:#ED2024!important' in heading['style']
    assert 'translate:24px -10px!important' in heading['style']
    assert 'rotate:5deg!important' in heading['style']
    card=soup.find(attrs={'data-we-repeat-item':item_id})
    assert 'background-color:#FFB900!important' in card['style']
    assert 'order:3!important' in card['style']
    assert 'height:410px!important' in card['style']
    assert 'background-color:#FFF4F2!important' in soup.body['style']
    els=soup.select('[data-we-design-element]')
    assert len(els)==4
    assert els[0].get_text()=='Custom <img src=x onerror=alert(1)>'
    assert els[0].find('img') is None
    assert els[1]['href']=='https://kommodo.ai/i/sCYKuA1fO4ob1o92TkHk'
    assert els[2]['data-we-design-type']=='shape'
    assert els[3]['src']=='https://example.com/office.png'
    assert 'script' not in rendered.text.lower()
    persisted=client.get(f"/api/pages/{p['id']}",headers=auth).json()
    assert json.loads(persisted['page']['values']['__design__'])==design

def test_visual_designer_rejects_unsafe_values_and_keeps_published_snapshot(client):
    auth=login(client)
    t=approve(client,auth,imported(client,auth,PAGE_HTML.encode(),name="Design safety"),
              {'Workspaces for your team':'page'})
    p=page(client,auth,t)
    seo(client,auth,p)
    publication=publish(client,auth,p)
    published_before=client.get(publication['url']).text
    sec=client.get(f"/api/pages/{p['id']}",headers=auth).json()['template']['sections'][0]['id']
    bad=[
      {'elements':[overlay(section_id=sec,color='red;transform:rotate(100deg)')]},
      {'elements':[overlay(id='ov_crafted_code',type='button',section_id=sec,url='javascript:alert(1)')]},
      {'elements':[overlay(section_id='unknown_section')]},
      {'elements':[overlay(section_id=sec,rotate=181)]},
      {'elements':[overlay(section_id=sec,opacity=-1)]},
      {'elements':[overlay(section_id=sec,fontFamily='evil"onmouseover') ]},
      {'elements':[overlay(section_id=sec),overlay(section_id=sec)]},
      {'fields':{'forged_key':{'x':10}}},
      {'page':{'background':'url(https://bad.example)'}},
      {'elements':[overlay(section_id=sec) for _ in range(51)]},
      {'groups':{'hero':{'columns':9}}},
    ]
    for x in bad:
      r=put_page(client,p['id'],auth,{'values':{'__design__':json.dumps(x)}})
      assert r.status_code==422,(x,r.text)
    good={'elements':[overlay(section_id=sec)]}
    r=put_page(client,p['id'],auth,{'values':{'__design__':json.dumps(good)}})
    assert r.status_code==200,r.text
    assert client.get(publication['url']).text==published_before
    assert 'data-we-design-element' in client.get(f"/api/pages/{p['id']}/preview",headers=auth).text
