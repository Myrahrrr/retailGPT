import os, uuid
import streamlit as st
from datetime import datetime
from openai import OpenAI
from supabase import create_client
from prompts import get_system_prompt

st.set_page_config(page_title=" L'IA, ce nouveau conseiller d'achat", layout="centered", initial_sidebar_state="collapsed")

# CSS exact des fichiers HTML + fond blanc forcé + badges colorés
st.markdown("""<style>
[data-testid="collapsedControl"]{display:none;}
[data-testid="stSidebar"]{display:none;}
#MainMenu{visibility:hidden;}footer{visibility:hidden;}


.block-container{padding-top:4rem!important;max-width:640px!important;}



/* Badges — gris (défaut), vert (courses), violet (pharma) */
.step-badge{display:inline-flex;align-items:center;gap:8px;background:#f5f5f4;border:0.5px solid #e0deda;border-radius:999px;font-size:12px;color:#888;padding:4px 14px;margin-bottom:1.5rem;letter-spacing:0.05em;}
.step-badge .dot{width:7px;height:7px;border-radius:50%;background:#888;}
.step-badge-green{display:inline-flex;align-items:center;gap:8px;background:#E1F5EE;border:0.5px solid #5DCAA5;border-radius:999px;font-size:12px;color:#085041;padding:4px 14px;margin-bottom:1.5rem;letter-spacing:0.05em;}
.step-badge-green .dot{width:7px;height:7px;border-radius:50%;background:#1D9E75;}
.step-badge-purple{display:inline-flex;align-items:center;gap:8px;background:#EEEDFE;border:0.5px solid #AFA9EC;border-radius:999px;font-size:12px;color:#3C3489;padding:4px 14px;margin-bottom:1.5rem;letter-spacing:0.05em;}
.step-badge-purple .dot{width:7px;height:7px;border-radius:50%;background:#7F77DD;}

/* Titres */
h1{font-size:22px;font-weight:500;color:#1a1a1a;margin-bottom:0.4rem;}
.subtitle{font-size:15px;color:#666;margin-bottom:2rem;}

/* Cards contexte */
.context-card{background:#f5f5f4;border:0.5px solid #e0deda;border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.75rem;}
.context-card-green{background:#E1F5EE;border:0.5px solid #5DCAA5;border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.75rem;display:flex;align-items:center;gap:12px;}
.context-card-purple{background:#EEEDFE;border:0.5px solid #AFA9EC;border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.75rem;}
.context-header{display:flex;align-items:center;gap:10px;margin-bottom:0.75rem;}
.context-icon{font-size:18px;flex-shrink:0;}
.context-details{display:flex;flex-direction:column;gap:6px;}
.detail-row{display:flex;align-items:flex-start;gap:8px;font-size:14px;color:#666;line-height:1.5;}
.detail-row span:first-child{color:#aaa;min-width:10px;}

/* Section title */
.section-title{font-size:11px;letter-spacing:0.08em;color:#aaa;margin-bottom:0.9rem;}

/* Goals */
.goal-list{display:flex;flex-direction:column;gap:8px;}
.goal-item{display:flex;align-items:flex-start;gap:10px;font-size:14px;color:#1a1a1a;line-height:1.55;padding:10px 14px;border:0.5px solid #e0deda;border-radius:8px;}
.goal-num{font-size:12px;font-weight:500;color:#888;min-width:18px;padding-top:1px;}

/* Alert */
.alert{background:#f5f5f4;border-left:2px solid #aaa;border-radius:0 8px 8px 0;padding:1rem 1.25rem;margin-bottom:1.75rem;}
.alert-green{background:#E1F5EE;border-left:2px solid #1D9E75;border-radius:0 8px 8px 0;padding:1rem 1.25rem;margin-bottom:1.75rem;}
.alert-purple{background:#EEEDFE;border-left:2px solid #7F77DD;border-radius:0 8px 8px 0;padding:1rem 1.25rem;margin-bottom:1.75rem;}
.alert-title{font-size:12px;letter-spacing:0.06em;color:#888;margin-bottom:0.6rem;}
.alert ul,.alert-green ul,.alert-purple ul{list-style:none;padding:0;display:flex;flex-direction:column;gap:6px;}
.alert li,.alert-green li,.alert-purple li{font-size:14px;color:#1a1a1a;line-height:1.55;padding-left:14px;position:relative;}
.alert li::before,.alert-green li::before,.alert-purple li::before{content:'—';position:absolute;left:0;color:#aaa;}

/* Example box */
.example-box{border:0.5px solid #e0deda;border-radius:12px;padding:1rem 1.25rem;margin-bottom:2rem;}
.example-label{font-size:11px;letter-spacing:0.08em;color:#aaa;margin-bottom:0.65rem;}
.bubble{background:#f5f5f4;border-radius:0 12px 12px 12px;padding:0.85rem 1rem;font-size:14px;color:#1a1a1a;line-height:1.6;font-style:italic;}

/* Onboarding card */
.card{background:#f5f5f4;border:0.5px solid #e0deda;border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:1.5rem;}
.card-sm{font-size:14px;color:#666;line-height:1.65;background:#f5f5f4;border:0.5px solid #e0deda;border-radius:12px;padding:1rem 1.5rem;margin-bottom:2rem;}

/* Step label */
.step-label{font-size:11px;color:#aaa;letter-spacing:0.08em;margin-bottom:1.75rem;}

/* Consent box */
.consent-box{background:#f5f5f4;border:0.5px solid #e0deda;border-radius:12px;padding:1.25rem;margin-bottom:1.75rem;}

/* Nav buttons */
.stButton>button{font-family:system-ui,sans-serif!important;font-size:14px!important;border-radius:8px!important;}

/* Chat card */
.chat-badge-green{display:inline-flex;align-items:center;gap:8px;background:#E1F5EE;border:0.5px solid #5DCAA5;border-radius:999px;font-size:12px;color:#085041;padding:4px 14px;margin-bottom:1rem;letter-spacing:0.05em;}
.chat-badge-purple{display:inline-flex;align-items:center;gap:8px;background:#EEEDFE;border:0.5px solid #AFA9EC;border-radius:999px;font-size:12px;color:#3C3489;padding:4px 14px;margin-bottom:1rem;letter-spacing:0.05em;}

/* Texte visible — ciblé uniquement */
.stMarkdown p,.stMarkdown li,.stMarkdown span{color:#1a1a1a!important;}
[data-testid="stChatMessage"] p{color:#1a1a1a!important;}

hr{border:none;border-top:0.5px solid #e0deda;margin:1.5rem 0;}
</style>""", unsafe_allow_html=True)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
CONDITIONS = ["machine_like", "human_like_formal", "human_like_friendly"]

def assign_condition():
    res = sb.table("condition_counts").select("style,count,completed").order("completed").order("count").order("style").limit(1).execute()
    return res.data[0]["style"] if res.data else "human_like_formal"

def save_participant(conv_id, p, style):
    cur = sb.table("condition_counts").select("count").eq("style", style).single().execute().data["count"]
    sb.table("condition_counts").update({"count": cur + 1}).eq("style", style).execute()
    sb.table("participants").upsert({
        "conversation_id": conv_id, "genre": p.get("genre"), "age": p.get("age"),
        "achat": p.get("achat"), "pref_achat": p.get("pref_achat"), "freq_ia": p.get("freq_ia"),
        "anciennete": p.get("anciennete"), "consulte": p.get("consulte"), "decision": p.get("decision"),
        "style": style, "timestamp": datetime.now().isoformat()
    }).execute()

def save_questionnaire(conv_id, r):
    sb.table("questionnaire").upsert({
        "conversation_id": conv_id, **r,
        "timestamp": datetime.now().isoformat()
    }).execute()
    try:
        row = sb.table("participants").select("style").eq("conversation_id", conv_id).execute()
        if row.data:
            style = row.data[0]["style"]
            cur_row = sb.table("condition_counts").select("completed").eq("style", style).execute()
            if cur_row.data:
                cur = cur_row.data[0]["completed"]
                sb.table("condition_counts").update({"completed": cur + 1}).eq("style", style).execute()
    except Exception:
        pass

def init_state():
    defaults = {"conv_id":str(uuid.uuid4()),"screen":"p1","style":None,"profil":{},
        "history_ep":[],"history_med":[],"started_ep":False,"started_med":False,
        "confirm_ep":False,"confirm_med":False}
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=v

init_state()

def llm(history, style, produit):
    msgs = [{"role":"system","content":get_system_prompt(style,produit)}]+history
    r = client.chat.completions.create(model="gpt-4o",messages=msgs,max_tokens=1000,temperature=0.7)
    return r.choices[0].message.content

# ── PROFIL 1 ──
def show_p1():
    st.markdown('<div class="step-badge"><div class="dot"></div>MÉMOIRE DE MASTER</div>', unsafe_allow_html=True)
    st.markdown('<h1>👋 Bienvenue !</h1>', unsafe_allow_html=True)
    st.markdown("""<div style="font-size:15px;color:#1a1a1a;line-height:1.7;margin-bottom:1.5rem;">
      Merci pour le temps que vous accordez à cette recherche. Cette expérience est réalisée pour mon mémoire de recherche à <strong>Paris 1 Panthéon Sorbonne</strong>. Votre contribution nous aidera dans notre étude des assistants d'achat tels que le chatbot reposant sur l'IA générative.
    </div>""", unsafe_allow_html=True)
    st.markdown("""<div class="card">
      <p style="font-size:13px;color:#aaa;letter-spacing:0.06em;margin-bottom:0.85rem;">DÉROULEMENT — ENVIRON 8 À 10 MINUTES</p>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <div style="display:flex;gap:12px;font-size:14px;color:#444;line-height:1.55;"><span style="font-weight:500;color:#1a1a1a;min-width:20px;">1.</span><span>Vous renseignez votre <strong>profil</strong>.</span></div>
        <div style="display:flex;gap:12px;font-size:14px;color:#444;line-height:1.55;"><span style="font-weight:500;color:#1D9E75;min-width:20px;">2.</span><span>Vous discutez avec un <strong>assistant d'achat de courses</strong>.</span></div>
        <div style="display:flex;gap:12px;font-size:14px;color:#444;line-height:1.55;"><span style="font-weight:500;color:#7F77DD;min-width:20px;">3.</span><span>Vous discutez avec un <strong>assistant pharmaceutique</strong>.</span></div>
        <div style="display:flex;gap:12px;font-size:14px;color:#444;line-height:1.55;"><span style="font-weight:500;color:#1a1a1a;min-width:20px;">4.</span><span>Vous répondez à un <strong>questionnaire</strong> sur votre expérience.</span></div>
      </div></div>""", unsafe_allow_html=True)
    st.markdown("""<div class="card-sm">Il n'y a pas de bonne ou de mauvaise réponse. Toutes vos données sont <strong>entièrement anonymes</strong> et utilisées uniquement à des fins de recherche académique.</div>""", unsafe_allow_html=True)
    st.markdown('<div class="step-label">ÉTAPE 1 / 4 — VOTRE PROFIL</div>', unsafe_allow_html=True)
    age = st.radio("Dans quelle tranche d'âge êtes-vous ?",
        ["18–24 ans","25–34 ans","35–44 ans","45–54 ans","55–64 ans","65 ans et plus"],index=None,key="r_age")
    genre = st.radio("À quel genre vous identifiez-vous ?",
        ["Femme","Homme","Non-binaire","Préfère ne pas répondre"],index=None,horizontal=True,key="r_genre")
    if st.button("Suivant →", type="primary"):
        if not age or not genre: st.error("Veuillez répondre à toutes les questions.")
        else:
            st.session_state["profil"].update({"age":age,"genre":genre})
            st.session_state["screen"]="p2"; st.rerun()

# ── PROFIL 2 ──
def show_p2():
    st.markdown('<div class="step-label">ÉTAPE 2 / 4 — VOS HABITUDES D\'ACHAT EN LIGNE</div>', unsafe_allow_html=True)
    achat = st.radio("À quelle fréquence effectuez-vous des achats en ligne ?",
        ["Jamais","Rarement","Parfois","Souvent"],
        index=None, key="r_achat")
    pref_achat = st.radio("Lorsque vous devez effectuer un achat, vous préférez :",
        ["Principalement en ligne",
         "Autant en ligne qu\'en magasin",
         "Principalement en magasin"],
        index=None, key="r_pref_achat")
    c1,c2 = st.columns([1,3])
    with c1:
        if st.button("← Retour"): st.session_state["screen"]="p1"; st.rerun()
    with c2:
        if st.button("Suivant →", type="primary"):
            if not achat or not pref_achat: st.error("Veuillez répondre à toutes les questions.")
            else:
                st.session_state["profil"]["achat"]=achat
                st.session_state["profil"]["pref_achat"]=pref_achat
                st.session_state["screen"]="p3"; st.rerun()

# ── PROFIL 3 ──
def show_p3():
    st.markdown('<div class="step-label">ÉTAPE 3 / 4 — VOTRE USAGE DE L\'IA</div>', unsafe_allow_html=True)
    freq_ia = st.radio("À quelle fréquence utilisez-vous des IA génératives (ChatGPT, Claude, Gemini…) ?",
        ["Jamais","Rarement","Parfois (quelques fois par mois)","Souvent (toutes les semaines)","Quotidiennement"],index=None,key="r_freq")
    anciennete = st.radio("Depuis combien de temps utilisez-vous des agents conversationnels ?",
        ["Je n'en utilise pas","Moins de 6 mois","6 mois – 1 an","1 – 2 ans","Plus de 2 ans"],index=None,key="r_anc")
    consulte = st.radio("Avez-vous déjà consulté un agent IA avant de faire un achat ?",
        ["Oui","Non"],index=None,horizontal=True,key="r_cons")
    decision = st.radio("Avez-vous déjà basé une décision d'achat sur une recommandation de l'IA ?",
        ["Oui","Non"],index=None,horizontal=True,key="r_dec")
    c1,c2 = st.columns([1,3])
    with c1:
        if st.button("← Retour"): st.session_state["screen"]="p2"; st.rerun()
    with c2:
        if st.button("Suivant →", type="primary"):
            if not freq_ia or not anciennete or not consulte or not decision:
                st.error("Veuillez répondre à toutes les questions.")
            else:
                st.session_state["profil"].update({"freq_ia":freq_ia,"anciennete":anciennete,"consulte":consulte,"decision":decision})
                st.session_state["screen"]="p4"; st.rerun()

# ── PROFIL 4 ──
def show_p4():
    st.markdown('<div class="step-label">ÉTAPE 4 / 4 — CONSENTEMENT</div>', unsafe_allow_html=True)
    st.markdown("""<div class="consent-box">
      <p style="font-size:14px;color:#666;line-height:1.65;margin-bottom:1rem;">
        Cette étude est réalisée dans le cadre d'un mémoire de fin de master. Votre participation est entièrement
        <strong>volontaire</strong> et anonyme. Les données collectées ne seront utilisées qu'à des fins de recherche
        académique et ne seront jamais associées à votre identité.
      </p>
      <p style="font-size:14px;color:#666;line-height:1.65;">Vous êtes libre de vous retirer à tout moment sans aucune conséquence.</p>
    </div>""", unsafe_allow_html=True)
    consent = st.checkbox("J'accepte librement et volontairement de participer à cette recherche.")
    c1,c2 = st.columns([1,3])
    with c1:
        if st.button("← Retour"): st.session_state["screen"]="p3"; st.rerun()
    with c2:
        if st.button("Commencer l'expérience →", type="primary"):
            if not consent: st.error("Veuillez accepter les conditions pour continuer.")
            else:
                style = assign_condition()
                st.session_state["style"]=style
                save_participant(st.session_state["conv_id"],st.session_state["profil"],style)
                st.session_state["screen"]="mission_ep"; st.rerun()

# ── MISSION ÉPICERIE ──
def show_mission_ep():
    st.markdown('<div class="step-badge-green"><div class="dot"></div>ÉTAPE 1 / 2</div>', unsafe_allow_html=True)
    st.markdown('<h1>Assistant courses</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Préparez votre soirée avec l\'aide d\'un assistant d\'achat.</p>', unsafe_allow_html=True)
    st.markdown("""<div class="context-card-green">
      <div style="font-size:20px;flex-shrink:0;">🏠</div>
      <p style="font-size:14px;color:#085041;line-height:1.55;"><strong>Contexte :</strong> vous organisez une soirée chez vous ce week-end et souhaitez préparer un repas fait maison pour vos invités.</p>
    </div>""", unsafe_allow_html=True)
    st.markdown('<div class="section-title">VOTRE OBJECTIF</div>', unsafe_allow_html=True)
    st.markdown("""<div class="goal-list" style="margin-bottom:1.75rem;">
      <div class="goal-item"><span class="goal-num">1.</span>Trouver des idées de repas complet (apéritif, plat, dessert)</div>
      <div class="goal-item"><span class="goal-num">2.</span>Identifier les ingrédients nécessaires pour les préparer</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("""<div class="alert-green"><div class="alert-title">À SAVOIR</div><ul>
      <li>Parlez librement : exprimez vos goûts, votre budget ou vos contraintes.</li>
      <li>Si une proposition vous convient, demandez à l'assistant d'ajouter les ingrédients au panier.</li>
      <li>Vous pouvez demander des modifications ou des alternatives à tout moment.</li>
      <li>Cliquez sur <strong>« Passer à l'étape suivante »</strong> une fois votre panier constitué, ou si aucune proposition ne vous convient.</li>
    </ul></div>""", unsafe_allow_html=True)
    import streamlit.components.v1 as _components
    _components.html("""<div style="border:0.5px solid #e0deda;border-radius:12px;padding:1rem 1.25rem;margin-bottom:2rem;position:relative;font-family:system-ui,sans-serif;">
      <div style="font-size:11px;letter-spacing:0.08em;color:#aaa;margin-bottom:0.65rem;">EXEMPLE POUR COMMENCER</div>
      <button id="btn_ep1" onclick="copyEx_ep1()" style="position:absolute;top:0.75rem;right:0.75rem;font-size:11px;color:#888;background:#fff;border:0.5px solid #e0deda;border-radius:6px;padding:2px 8px;cursor:pointer;">Copier</button>
      <div style="background:#f5f5f4;border-radius:0 12px 12px 12px;padding:0.85rem 1rem;font-size:14px;color:#1a1a1a;line-height:1.6;font-style:italic;">« J'organise une soirée chez moi ce week-end. Je voudrais un repas maison. Qu'est-ce que tu me proposes et quels ingrédients dois-je acheter ? »</div>
    </div>
    <script>
    function copyEx_ep1(){
      var ta=document.createElement('textarea');
      ta.value="J'organise une soirée chez moi ce week-end. Je voudrais un repas maison. Qu'est-ce que tu me proposes et quels ingrédients dois-je acheter ?";
      ta.style.position='fixed';ta.style.opacity='0';
      document.body.appendChild(ta);ta.focus();ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      var b=document.getElementById('btn_ep1');
      b.textContent='Copié !';b.style.color='#1D9E75';b.style.borderColor='#1D9E75';
      setTimeout(function(){b.textContent='Copier';b.style.color='#888';b.style.borderColor='#e0deda';},2000);
    }
    </script>""", height=160)
    if st.button("J'ai compris →", type="primary", use_container_width=True):
        st.session_state["screen"]="chat_ep"; st.rerun()

# ── MISSION MÉDICAMENTS ──
def show_mission_med():
    st.markdown('<div class="step-badge-purple"><div class="dot"></div>ÉTAPE 2 / 2</div>', unsafe_allow_html=True)
    st.markdown('<h1>Assistant pharmaceutique</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Trouvez une solution adaptée pour soulager votre amie.</p>', unsafe_allow_html=True)
    st.markdown("""<div class="context-card-purple">
      <div class="context-header">
        <div class="context-icon">💊</div>
        <strong style="color:#3C3489;">Contexte : la situation de Julie</strong>
      </div>
      <div class="context-details">
        <div class="detail-row"><span>—</span><span>Femme de <strong>45 ans</strong></span></div>
        <div class="detail-row"><span>—</span><span>Forte douleur dans le <strong>bas du dos</strong> depuis ce matin</span></div>
        <div class="detail-row"><span>—</span><span>Ne peut pas consulter un médecin avant <strong>deux semaines</strong></span></div>
        <div class="detail-row"><span>—</span><span>Prend déjà de l'<strong>aspirine (100 mg/jour)</strong> pour le cœur</span></div>
      </div>
    </div>""", unsafe_allow_html=True)
    st.markdown('<div class="section-title">VOTRE OBJECTIF</div>', unsafe_allow_html=True)
    st.markdown("""<div class="goal-list" style="margin-bottom:1.75rem;">
      <div class="goal-item"><span class="goal-num">1.</span>Identifier une solution adaptée pour soulager sa douleur</div>
      <div class="goal-item"><span class="goal-num">2.</span>Vérifier que cette solution est compatible avec sa situation</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("""<div class="alert-purple"><div class="alert-title">À SAVOIR</div><ul>
      <li>Posez librement vos questions : effets, risques, interactions médicamenteuses, alternatives.</li>
      <li>Si une proposition vous convient, demandez à l'assistant d'ajouter le produit au panier.</li>
      <li>Vous pouvez demander des ajustements ou des alternatives à tout moment.</li>
      <li>Cliquez sur <strong>« Passer à l'étape suivante »</strong> une fois votre panier constitué, ou si aucune solution ne vous convient.</li>
    </ul></div>""", unsafe_allow_html=True)
    import streamlit.components.v1 as _components
    _components.html("""<div style="border:0.5px solid #e0deda;border-radius:12px;padding:1rem 1.25rem;margin-bottom:2rem;position:relative;font-family:system-ui,sans-serif;">
      <div style="font-size:11px;letter-spacing:0.08em;color:#aaa;margin-bottom:0.65rem;">EXEMPLE POUR COMMENCER</div>
      <button id="btn_med1" onclick="copyEx_med1()" style="position:absolute;top:0.75rem;right:0.75rem;font-size:11px;color:#888;background:#fff;border:0.5px solid #e0deda;border-radius:6px;padding:2px 8px;cursor:pointer;">Copier</button>
      <div style="background:#f5f5f4;border-radius:0 12px 12px 12px;padding:0.85rem 1rem;font-size:14px;color:#1a1a1a;line-height:1.6;font-style:italic;">« Mon amie Julie a très mal au bas du dos depuis ce matin. Elle prend déjà de l'aspirine pour le cœur. Que peut-elle prendre pour soulager la douleur ? »</div>
    </div>
    <script>
    function copyEx_med1(){
      var ta=document.createElement('textarea');
      ta.value="Mon amie Julie a très mal au bas du dos depuis ce matin. Elle prend déjà de l'aspirine pour le coeur. Que peut-elle prendre pour soulager la douleur ?";
      ta.style.position='fixed';ta.style.opacity='0';
      document.body.appendChild(ta);ta.focus();ta.select();
      document.execCommand('copy');document.body.removeChild(ta);
      var b=document.getElementById('btn_med1');
      b.textContent='Copié !';b.style.color='#1D9E75';b.style.borderColor='#1D9E75';
      setTimeout(function(){b.textContent='Copier';b.style.color='#888';b.style.borderColor='#e0deda';},2000);
    }
    </script>""", height=160)
    if st.button("J'ai compris →", type="primary", use_container_width=True):
        st.session_state["screen"]="chat_med"; st.rerun()

# ── RAPPELS ──
RAPPEL = {
    "epicerie": """
    <div class="context-card-green">
      <div style="font-size:18px;flex-shrink:0;">🏠</div>
      <p style="font-size:14px;color:#085041;line-height:1.55;"><strong>Contexte :</strong> vous organisez une soirée chez vous ce week-end et souhaitez préparer un repas fait maison pour vos invités.</p>
    </div>
    <div class="section-title">VOTRE OBJECTIF</div>
    <div class="goal-list" style="margin-bottom:1.25rem;">
      <div class="goal-item"><span class="goal-num">1.</span>Trouver des idées de repas complet (apéritif, plat, dessert)</div>
      <div class="goal-item"><span class="goal-num">2.</span>Identifier les ingrédients nécessaires pour les préparer</div>
    </div>
    <div class="alert-green"><div class="alert-title">À SAVOIR</div><ul>
      <li>Parlez librement : exprimez vos goûts, votre budget ou vos contraintes.</li>
      <li>Si une proposition vous convient, demandez à l'assistant d'ajouter les ingrédients au panier.</li>
      <li>Vous pouvez demander des modifications ou des alternatives à tout moment.</li>
      <li>Cliquez <strong>« Passer à l'étape suivante »</strong> une fois votre panier constitué, ou si aucune proposition ne vous convient.</li>
    </ul></div>
    """,
    "medicaments": """
    <div class="context-card-purple">
      <div class="context-header"><div class="context-icon">💊</div><strong style="color:#3C3489;">La situation de Julie</strong></div>
      <div class="context-details">
        <div class="detail-row"><span>—</span><span>Femme de <strong>45 ans</strong></span></div>
        <div class="detail-row"><span>—</span><span>Forte douleur dans le <strong>bas du dos</strong> depuis ce matin</span></div>
        <div class="detail-row"><span>—</span><span>Ne peut pas consulter un médecin avant <strong>deux semaines</strong></span></div>
        <div class="detail-row"><span>—</span><span>Prend déjà de l'<strong>aspirine (100 mg/jour)</strong> pour le cœur</span></div>
      </div>
    </div>
    <div class="section-title">VOTRE OBJECTIF</div>
    <div class="goal-list" style="margin-bottom:1.25rem;">
      <div class="goal-item"><span class="goal-num">1.</span>Identifier une solution adaptée pour soulager sa douleur</div>
      <div class="goal-item"><span class="goal-num">2.</span>Vérifier que cette solution est compatible avec sa situation</div>
    </div>
    <div class="alert-purple"><div class="alert-title">À SAVOIR</div><ul>
      <li>Posez librement vos questions : effets, risques, interactions médicamenteuses, alternatives.</li>
      <li>Si une proposition vous convient, demandez à l'assistant d'ajouter le produit au panier.</li>
      <li>Vous pouvez demander des ajustements ou des alternatives à tout moment.</li>
      <li>Cliquez <strong>« Passer à l'étape suivante »</strong> une fois votre panier constitué, ou si aucune solution ne vous convient.</li>
    </ul></div>
    """
}

# ── CHAT ──
def show_chat(produit):
    hk = "history_ep" if produit=="epicerie" else "history_med"
    sk = "started_ep" if produit=="epicerie" else "started_med"
    ck = "confirm_ep" if produit=="epicerie" else "confirm_med"
    ns = "mission_med" if produit=="epicerie" else "questionnaire"
    badge = '<div class="chat-badge-green"><div style="width:7px;height:7px;border-radius:50%;background:#1D9E75;"></div>ÉTAPE 1 / 2 — ASSISTANT COURSES</div>' if produit=="epicerie" \
        else '<div class="chat-badge-purple"><div style="width:7px;height:7px;border-radius:50%;background:#7F77DD;"></div>ÉTAPE 2 / 2 — ASSISTANT PHARMACIE</div>'
    st.markdown(badge, unsafe_allow_html=True)

    with st.expander("📋 Rappel de l'étape en cours", expanded=False):
        import streamlit.components.v1 as _comp
        st.markdown(RAPPEL[produit], unsafe_allow_html=True)
        if produit == "epicerie":
            _comp.html("""<div style="border:0.5px solid #e0deda;border-radius:12px;padding:1rem 1.25rem;position:relative;font-family:system-ui,sans-serif;">
              <div style="font-size:11px;letter-spacing:0.08em;color:#aaa;margin-bottom:0.65rem;">EXEMPLE POUR COMMENCER</div>
              <button id="btn_ep2" onclick="copyEp2()" style="position:absolute;top:0.75rem;right:0.75rem;font-size:11px;color:#888;background:#fff;border:0.5px solid #e0deda;border-radius:6px;padding:2px 8px;cursor:pointer;">Copier</button>
              <div style="background:#f5f5f4;border-radius:0 12px 12px 12px;padding:0.85rem 1rem;font-size:14px;color:#1a1a1a;line-height:1.6;font-style:italic;">« J'organise une soirée chez moi ce week-end. Je voudrais un repas maison. Qu'est-ce que tu me proposes et quels ingrédients dois-je acheter ? »</div>
            </div>
            <script>function copyEp2(){var ta=document.createElement('textarea');ta.value="J'organise une soirée chez moi ce week-end. Je voudrais un repas maison. Qu'est-ce que tu me proposes et quels ingrédients dois-je acheter ?";ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.focus();ta.select();document.execCommand('copy');document.body.removeChild(ta);var b=document.getElementById('btn_ep2');b.textContent='Copié !';b.style.color='#1D9E75';b.style.borderColor='#1D9E75';setTimeout(function(){b.textContent='Copier';b.style.color='#888';b.style.borderColor='#e0deda';},2000);}</script>""", height=160)
        else:
            _comp.html("""<div style="border:0.5px solid #e0deda;border-radius:12px;padding:1rem 1.25rem;position:relative;font-family:system-ui,sans-serif;">
              <div style="font-size:11px;letter-spacing:0.08em;color:#aaa;margin-bottom:0.65rem;">EXEMPLE POUR COMMENCER</div>
              <button id="btn_med2" onclick="copyMed2()" style="position:absolute;top:0.75rem;right:0.75rem;font-size:11px;color:#888;background:#fff;border:0.5px solid #e0deda;border-radius:6px;padding:2px 8px;cursor:pointer;">Copier</button>
              <div style="background:#f5f5f4;border-radius:0 12px 12px 12px;padding:0.85rem 1rem;font-size:14px;color:#1a1a1a;line-height:1.6;font-style:italic;">« Mon amie Julie a très mal au bas du dos depuis ce matin. Elle prend déjà de l'aspirine pour le cœur. Que peut-elle prendre pour soulager la douleur ? »</div>
            </div>
            <script>function copyMed2(){var ta=document.createElement('textarea');ta.value="Mon amie Julie a très mal au bas du dos depuis ce matin. Elle prend déjà de l'aspirine pour le coeur. Que peut-elle prendre pour soulager la douleur ?";ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.focus();ta.select();document.execCommand('copy');document.body.removeChild(ta);var b=document.getElementById('btn_med2');b.textContent='Copié !';b.style.color='#1D9E75';b.style.borderColor='#1D9E75';setTimeout(function(){b.textContent='Copier';b.style.color='#888';b.style.borderColor='#e0deda';},2000);}</script>""", height=160)

    if not st.session_state[sk]:
        st.session_state[sk]=True
        with st.spinner(""):
            r = llm([{"role":"user","content":"start"}], st.session_state["style"], produit)
        st.session_state[hk].append({"role":"assistant","content":r}); st.rerun()

    for msg in st.session_state[hk]:
        st.chat_message(msg["role"]).write(msg["content"])

    # Ancre invisible pour le scroll auto mobile
    st.markdown('<div id="chat-bottom-anchor" style="height:1px;"></div>', unsafe_allow_html=True)

    # Grand espace entre messages et bouton
    st.markdown("<br><br><br><br><br>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    if not st.session_state.get(ck,False):
        c1,c2,c3 = st.columns([2,3,2])
        with c2:
            if st.button("Passer à l'étape suivante", key=f"next_{produit}", type="secondary"):
                st.session_state[ck]=True; st.rerun()
    else:
        st.markdown('<div style="text-align:center;font-size:14px;color:#666;background:#f5f5f4;border:0.5px solid #e0deda;border-radius:12px;padding:1rem;margin-bottom:0.75rem;">Êtes-vous sûr(e) de vouloir passer à l\'étape suivante ?</div>', unsafe_allow_html=True)
        c1,c2,c3 = st.columns([2,1,1])
        with c2:
            if st.button("Oui", key=f"yes_{produit}", type="primary", use_container_width=True):
                st.session_state[ck]=False; st.session_state["screen"]=ns; st.rerun()
        with c3:
            if st.button("Non", key=f"no_{produit}", use_container_width=True):
                st.session_state[ck]=False; st.rerun()

    if user_input := st.chat_input("Écrivez votre message ici..."):
        st.session_state[hk].append({"role":"user","content":user_input})
        st.chat_message("user").write(user_input)
        with st.spinner(""):
            r = llm(st.session_state[hk], st.session_state["style"], produit)
        st.session_state[hk].append({"role":"assistant","content":r}); st.rerun()

    # ── SCROLL AUTO VERS LE DERNIER MESSAGE (mobile principalement) ──
    import streamlit.components.v1 as _scroll_comp
    nb_msgs = len(st.session_state.get(hk, []))
    _scroll_comp.html(f"""
    <script>
      (function() {{
        const token = "{produit}-{nb_msgs}";
        function scrollToBottom() {{
          try {{
            const doc = window.parent.document;
            const anchor = doc.getElementById('chat-bottom-anchor');
            if (anchor) {{
              anchor.scrollIntoView({{ behavior: 'smooth', block: 'end' }});
            }} else {{
              window.parent.scrollTo({{ top: doc.body.scrollHeight, behavior: 'smooth' }});
            }}
          }} catch (e) {{ console.log('scroll error', e); }}
        }}
        setTimeout(scrollToBottom, 100);
        setTimeout(scrollToBottom, 400);
        setTimeout(scrollToBottom, 800);
      }})();
    </script>
    """, height=0)

# ── QUESTIONNAIRE HTML ──
QUESTIONS = [
    (1,"s1","J'ai l'impression de parler à une personne réelle."),
    (2,"s1","L'assistant me paraît chaleureux."),
    (3,"s1","L'assistant semble avoir des intentions propres."),
    (4,"s1","Le style conversationnel de l'assistant me semble adapté à la situation."),
    (5,"s2","L'assistant dispose des connaissances nécessaires pour me faire de bonnes recommandations."),
    (6,"s2","Les informations fournies m'ont semblé précises."),
    (7,"s2","L'assistant m'a fourni suffisamment d'informations pour prendre une décision éclairée."),
    (8,"s2","Les recommandations de l'assistant me semblent adaptées aux contraintes."),
    (9,"s2","J'ai l'impression que l'assistant me donne des informations vraies."),
    (10,"s2","Je pense que l'assistant me cache certaines informations."),
    (11,"s2","J'ai le sentiment que l'assistant cherche vraiment à m'aider."),
    (12,"s2","Globalement, je fais confiance à cet assistant pour m'aider dans mes décisions d'achat."),
]

import json as _json

QUESTIONS_S1 = [
    (1, "J'ai l'impression de parler à une personne réelle."),
    (2, "L'assistant me paraît chaleureux."),
    (3, "L'assistant semble avoir des intentions propres."),
    (4, "Le style conversationnel de l'assistant me semble adapté à la situation."),
]
QUESTIONS_S2 = [
    (5,  "L'assistant dispose des connaissances nécessaires pour me faire de bonnes recommandations."),
    (6,  "Les informations fournies m'ont semblé précises."),
    (7,  "L'assistant m'a fourni suffisamment d'informations pour prendre une décision éclairée."),
    (8,  "Les recommandations de l'assistant me semblent adaptées aux contraintes."),
    (9,  "J'ai l'impression que l'assistant me donne des informations vraies."),
    (10, "Je pense que l'assistant me cache certaines informations."),
    (11, "J'ai le sentiment que l'assistant cherche vraiment à m'aider."),
    (12, "Globalement, je fais confiance à cet assistant pour m'aider dans mes décisions d'achat."),
]
OPTS = ["1", "2", "3", "4", "5"]

def show_questionnaire():
    st.markdown("""<style>
/* Layout horizontal radio */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    flex-direction: row !important;
    gap: 6px !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    gap: 2px !important;
    padding: 2px 4px !important;
    min-width: 32px;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label > div > p {
    font-size: 10px !important;
    color: #888 !important;
    margin: 0 !important;
}
/* Cercles radio plus grands */
div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
    width: 24px !important;
    height: 24px !important;
    border-radius: 50% !important;
}
</style>""", unsafe_allow_html=True)

    st.markdown('<div class="step-badge"><div class="dot"></div>ÉTAPE FINALE</div>', unsafe_allow_html=True)
    st.markdown('<h1>Questionnaire</h1>', unsafe_allow_html=True)
    st.markdown("""<div style="font-size:13px;color:#555;margin-bottom:1.5rem;line-height:1.6;padding:10px 14px;background:#ebebeb;border-radius:8px;">
      Pour chaque affirmation, indiquez votre niveau d'accord de 1 (pas du tout d'accord) à 5 (tout à fait d'accord) pour chacun des deux assistants.<br><br>
      <strong>Il n'y a pas de bonne ou de mauvaise réponse.</strong><br>
      Merci d'y répondre de la manière la plus honnête et spontanée possible.
    </div>""", unsafe_allow_html=True)

    with st.form("questionnaire_form"):
        results = {}

        for section_label, questions in [
            ("Section 1 — Perception de l'assistant", QUESTIONS_S1),
            ("Section 2 — Confiance envers l'assistant", QUESTIONS_S2)
        ]:
            st.markdown(f'<div class="section-title">{section_label}</div>', unsafe_allow_html=True)

            for n, text in questions:
                # Texte de la question
                st.markdown(f"""<div style="background:#fff;border:0.5px solid #ddd;border-radius:12px;padding:1rem 1.25rem;margin-bottom:0.5rem;">
                  <p style="font-size:14px;line-height:1.6;color:#1a1a1a;">
                    <span style="font-size:12px;color:#888;margin-right:6px;">{n}.</span>{text}
                  </p>
                </div>""", unsafe_allow_html=True)

                # Assistant courses (label + radio)
                c1, c2 = st.columns([1.6, 5])
                with c1:
                    st.markdown('<div style="padding-top:6px;"><span style="font-size:11px;font-weight:500;background:#E1F5EE;color:#0F6E56;padding:2px 8px;border-radius:6px;">Assistant courses</span></div>', unsafe_allow_html=True)
                with c2:
                    ep = st.radio("e", OPTS, index=None, horizontal=True,
                                  label_visibility="collapsed", key=f"q{n}_ep")

                # Assistant pharmaceutique (label + radio)
                c3, c4 = st.columns([1.6, 5])
                with c3:
                    st.markdown('<div style="padding-top:6px;"><span style="font-size:11px;font-weight:500;background:#EEEDFE;color:#3C3489;padding:2px 8px;border-radius:6px;">Assistant pharmaceutique</span></div>', unsafe_allow_html=True)
                with c4:
                    med = st.radio("m", OPTS, index=None, horizontal=True,
                                   label_visibility="collapsed", key=f"q{n}_med")

                # Légende sous le dernier radio
                c5, c6 = st.columns([1.6, 5])
                with c6:
                    st.markdown("<div style='display:flex;justify-content:space-between;font-size:10px;color:#aaa;margin-bottom:0.75rem;'><span>Pas du tout d&apos;accord</span><span>Tout &agrave; fait d&apos;accord</span></div>", unsafe_allow_html=True)

                results[f"q{n}_ep"] = int(ep) if ep else None
                results[f"q{n}_med"] = int(med) if med else None

        st.markdown("---")
        if st.form_submit_button("Envoyer mes réponses →", type="primary", use_container_width=True):
            if any(v is None for v in results.values()):
                st.error("Veuillez répondre à toutes les questions avant de continuer.")
            else:
                save_questionnaire(st.session_state["conv_id"], results)
                st.session_state["screen"] = "fin"
                st.rerun()


# ── FIN ──
def show_fin():
    st.markdown("""<div style="text-align:center;padding:3rem 0 1.5rem;">
      <div style="width:48px;height:48px;border-radius:50%;background:#f5f5f4;border:0.5px solid #e0deda;display:flex;align-items:center;justify-content:center;margin:0 auto 1.25rem;">
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M4 11L9 16L18 6" stroke="#1a1a1a" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </div>
      <h2 style="font-size:20px;font-weight:500;margin-bottom:0.5rem;">Merci pour votre contribution à cette recherche !</h2>
      <p style="color:#666;font-size:15px;line-height:1.65;">Vos réponses ont bien été enregistrées et resteront strictement anonymes.</p>
      <p style="color:#888;font-size:14px;margin-top:0.75rem;font-style:italic;">— Myrah</p>
    </div>""", unsafe_allow_html=True)

    # ── BLOC NOTIFICATION RÉSULTATS ──
    if not st.session_state.get("email_submitted", False):
        st.markdown("""
        <div style="background:#f5f5f4;border:0.5px solid #e0deda;border-radius:12px;padding:1.25rem;margin-top:1rem;">
          <p style="font-size:14px;color:#1a1a1a;font-weight:500;margin-bottom:0.3rem;text-align:center;">📬 Recevoir les résultats</p>
          <p style="font-size:13px;color:#666;line-height:1.5;margin-bottom:0.4rem;text-align:center;">
            Laissez votre email pour recevoir un résumé du mémoire.
          </p>
          <p style="font-size:12px;color:#888;line-height:1.5;margin-bottom:0.9rem;text-align:center;">
            Votre email ne sera utilisé que dans ce cadre, jamais partagé, et restera dissocié de vos réponses anonymes.
          </p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])
        with col1:
            email_input = st.text_input("Votre email", key="notify_email_input", label_visibility="collapsed", placeholder="votre@email.com")
        with col2:
            if st.button("Me prévenir", key="notify_btn", use_container_width=True):
                email_clean = (email_input or "").strip().lower()
                if "@" not in email_clean or "." not in email_clean or len(email_clean) < 5:
                    st.error("Email invalide")
                else:
                    try:
                        sb.table("notify_emails").insert({"email": email_clean}).execute()
                        st.session_state["email_submitted"] = True
                        st.rerun()
                    except Exception as e:
                        if "duplicate" in str(e).lower() or "unique" in str(e).lower() or "23505" in str(e):
                            st.session_state["email_submitted"] = True
                            st.rerun()
                        else:
                            st.error("Erreur, veuillez réessayer.")
    else:
        st.markdown("""
        <div style="background:#E1F5EE;border:0.5px solid #5DCAA5;border-radius:12px;padding:1rem;margin-top:1rem;text-align:center;">
          <p style="font-size:14px;color:#085041;font-weight:500;margin:0;">✓ Vous serez prévenu(e) dès la fin de l'étude.</p>
        </div>
        """, unsafe_allow_html=True)

    # ── SURVEYCIRCLE (obligatoire) ──
    st.markdown("""
    <div style="background:#E8F4FB;border:0.5px solid #B6DCEF;border-radius:12px;padding:1rem;margin-top:1.25rem;text-align:center;">
      <p style="font-size:14px;color:#0B5A82;margin:0;line-height:1.5;">
        Pour les membres du surveycircle, vous pouvez utiliser le Survey Code suivant sur <a href="https://www.surveycircle.com" target="_blank" rel="noopener" style="color:#0B5A82;font-weight:600;">www.surveycircle.com</a> et obtenez gratuitement des participants pour votre étude grâce à SurveyCircle :<br>
        <strong style="font-size:18px;letter-spacing:1px;display:inline-block;margin-top:0.5rem;">S2G1-YQZL-64U7-NU49</strong>
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── BLOC PARTAGE ──
    import urllib.parse
    url = "https://assistant-achat.streamlit.app"
    msg = "Hello ! Je viens de tester une étude sur la confiance qu'on accorde aux assistants d'achat IA (style ChatGPT). C'est pour un mémoire de recherche à Paris 1 Panthéon Sorbonne, anonyme, 8-10 min. Ta participation aiderait énormément à faire avancer cette étude . Merci ! Voici le lien de l'expérience:"
    msg_enc = urllib.parse.quote(msg + " " + url)
    url_enc = urllib.parse.quote(url)

    wa = f"https://wa.me/?text={msg_enc}"
    messenger = f"https://www.facebook.com/sharer/sharer.php?u={url_enc}"
    linkedin = f"https://www.linkedin.com/sharing/share-offsite/?url={url_enc}"
    mail = f"mailto:?subject={urllib.parse.quote('Étude mémoire — assistants IA')}&body={msg_enc}"

    st.markdown(f"""
    <div style="background:#f5f5f4;border:0.5px solid #e0deda;border-radius:12px;padding:1.25rem;margin-top:1rem;">
      <p style="font-size:14px;color:#1a1a1a;font-weight:500;margin-bottom:1rem;text-align:center;">Aidez-moi à faire connaître cette étude 💛</p>
      <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center;">
        <a href="{wa}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;background:#25D366;color:white;text-decoration:none;padding:9px 16px;border-radius:8px;font-size:13px;font-weight:500;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="white"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/></svg>
          WhatsApp
        </a>
        <a href="{messenger}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;background:#0084FF;color:white;text-decoration:none;padding:9px 16px;border-radius:8px;font-size:13px;font-weight:500;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.486 2 2 6.262 2 11.5c0 2.665 1.166 5.071 3.063 6.797V22l2.812-1.547A10.95 10.95 0 0012 21c5.514 0 10-4.262 10-9.5S17.514 2 12 2zm1.063 12.781l-2.594-2.766-4.969 2.766 5.469-5.797 2.625 2.766 4.938-2.766-5.469 5.797z"/></svg>
          Messenger
        </a>
        <a href="{linkedin}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;background:#0A66C2;color:white;text-decoration:none;padding:9px 16px;border-radius:8px;font-size:13px;font-weight:500;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="white"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.063 2.063 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
          LinkedIn
        </a>
        <a href="{mail}" style="display:inline-flex;align-items:center;gap:6px;background:#1a1a1a;color:white;text-decoration:none;padding:9px 16px;border-radius:8px;font-size:13px;font-weight:500;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
          Mail
        </a>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── BOUTONS COPIER + WEB SHARE API (mobile) ──
    import streamlit.components.v1 as components
    copy_text = (msg + " " + url).replace("'", "\\'").replace('"', '\\"')
    components.html(f"""
    <div style="text-align:center;margin-top:0.8rem;display:flex;gap:8px;justify-content:center;flex-wrap:wrap;font-family:system-ui,-apple-system,sans-serif;">
      <button id="btn-copy" onclick="
        var t=document.createElement('textarea');
        t.value='{copy_text}';
        document.body.appendChild(t);t.select();
        document.execCommand('copy');
        document.body.removeChild(t);
        this.innerText='✓ Lien copié !';
        this.style.background='#1D9E75';this.style.color='white';this.style.borderColor='#1D9E75';
        setTimeout(()=>{{this.innerText='📋 Copier le lien'; this.style.background='white';this.style.color='#1a1a1a';this.style.borderColor='#e0deda';}},2000);
      " style="background:white;border:0.5px solid #e0deda;border-radius:8px;padding:9px 18px;font-size:13px;color:#1a1a1a;cursor:pointer;font-family:inherit;">
        📋 Copier le lien
      </button>
      <button id="btn-share" style="display:none;background:white;border:0.5px solid #e0deda;border-radius:8px;padding:9px 18px;font-size:13px;color:#1a1a1a;cursor:pointer;font-family:inherit;" onclick="
        navigator.share({{
          title: 'Étude assistants IA',
          text: '{copy_text}',
        }}).catch(function(err){{ console.log('Partage annulé', err); }});
      ">
        📤 Partager (Instagram, etc.)
      </button>
    </div>
    <script>
      if (navigator.share) {{
        document.getElementById('btn-share').style.display = 'inline-flex';
      }}
    </script>
    """, height=70)

# ── ADMIN ──
def show_admin():
    import pandas as pd
    st.title("Admin — RetailGPT")
    st.divider()

    # Round-robin
    rr = sb.table("condition_counts").select("*").order("style").execute()
    st.subheader("Round-robin")
    st.dataframe(pd.DataFrame(rr.data), use_container_width=True)
    st.divider()

    # Données complètes
    p = sb.table("participants").select("*").order("timestamp", desc=True).execute()
    q = sb.table("questionnaire").select("*").execute()
    df_p = pd.DataFrame(p.data) if p.data else pd.DataFrame()
    df_q = pd.DataFrame(q.data) if q.data else pd.DataFrame()

    if not df_p.empty and not df_q.empty:
        df = df_p.merge(df_q, on="conversation_id", how="inner", suffixes=("","_q"))
        df = df.drop(columns=[c for c in df.columns if c.endswith("_q")])
    else:
        df = pd.DataFrame()

    rename = {
        "q1_ep":"ANT1_ep","q2_ep":"ANT2_ep","q3_ep":"ANT3_ep","q4_ep":"ADEQ_ep",
        "q5_ep":"TAB1_ep","q6_ep":"TAB2_ep","q7_ep":"TAB3_ep","q8_ep":"TAB4_ep",
        "q9_ep":"TIN1_ep","q10_ep":"TIN2_ep","q11_ep":"TBE1_ep","q12_ep":"TBE2_ep",
        "q1_med":"ANT1_med","q2_med":"ANT2_med","q3_med":"ANT3_med","q4_med":"ADEQ_med",
        "q5_med":"TAB1_med","q6_med":"TAB2_med","q7_med":"TAB3_med","q8_med":"TAB4_med",
        "q9_med":"TIN1_med","q10_med":"TIN2_med","q11_med":"TBE1_med","q12_med":"TBE2_med",
    }
    st.subheader(f"{len(df)} participants complétés")
    if not df.empty:
        st.dataframe(df.rename(columns=rename), use_container_width=True)
        st.download_button("⬇️ Télécharger CSV", df.to_csv(index=False).encode("utf-8"),
            file_name=f"retailgpt_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv", type="primary", use_container_width=True)

    st.divider()
    st.subheader("Zone dangereuse")
    if st.button("Remettre à zéro toutes les données", type="secondary"):
        st.session_state["confirm_reset"] = True
    if st.session_state.get("confirm_reset"):
        st.warning("Cette action supprime toutes les données collectées.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirmer", type="primary"):
                sb.table("questionnaire").delete().neq("conversation_id","").execute()
                sb.table("participants").delete().neq("conversation_id","").execute()
                for s in CONDITIONS:
                    sb.table("condition_counts").update({"count":0,"completed":0}).eq("style",s).execute()
                st.session_state["confirm_reset"] = False
                st.success("Données supprimées."); st.rerun()
        with c2:
            if st.button("Annuler"):
                st.session_state["confirm_reset"] = False; st.rerun()


# ── ROUTEUR ──
if st.query_params.get("admin")=="true":
    show_admin()
else:
    s=st.session_state["screen"]
    if s=="p1": show_p1()
    elif s=="p2": show_p2()
    elif s=="p3": show_p3()
    elif s=="p4": show_p4()
    elif s=="mission_ep": show_mission_ep()
    elif s=="chat_ep": show_chat("epicerie")
    elif s=="mission_med": show_mission_med()
    elif s=="chat_med": show_chat("medicaments")
    elif s=="questionnaire": show_questionnaire()
    else: show_fin()
