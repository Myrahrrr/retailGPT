import json
import os
import redis
import sqlite3
import streamlit as st
from datetime import datetime
from chatbot import get_chatbot_response, reset_chatbot_conversation
from PIL import Image
from utils.data_utils import chat_to_word, generate_conversation_id

# ─────────────────────────────────────────────
# CONFIG PAGE
# ─────────────────────────────────────────────
im = Image.open("./images/neuralmind.png")
st.set_page_config(page_title="Assistant en ligne", page_icon=im, initial_sidebar_state="collapsed")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="collapsedControl"] {display: none;}
[data-testid="stSidebar"] {display: none;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CONDITIONS — 3 styles, 2 missions chacun
# ─────────────────────────────────────────────
CONDITIONS = [
    {"style": "machine_like"},
    {"style": "human_like_formal"},
    {"style": "human_like_friendly"},
]

MISSIONS = {
    "epicerie": {
        "titre": "📋 Mission 1 — Épicerie",
        "texte": (
            "**Organisez votre soirée de ce week-end avec le chatbot.**\n\n"
            "👉 **Objectif :** créer un panier de courses complet pour un repas "
            "(apéritif, plat, dessert).\n\n"
            "Utilisez le chatbot comme en situation réelle : exprimez vos envies, "
            "contraintes et préférences (budget, régime, goûts…). "
            "Le chatbot vous proposera des idées et vous aidera à remplir votre panier.\n\n"
            "---\n\n"
            "💡 **Comment interagir avec le chatbot ?**\n\n"
            "- Une proposition vous convient → demandez au chatbot de l'ajouter au panier.\n"
            "- La proposition n'est pas satisfaisante → demandez des ajustements selon vos besoins.\n"
            "- Aucune des propositions ne vous a plu → appuyez sur le bouton **Passer directement au questionnaire**."
        ),
    },
    "medicaments": {
        "titre": "📋 Mission 2 — Médicaments",
        "texte": (
            "**Aidez votre amie Julie (45 ans)**, qui souffre de douleurs lombaires aiguës "
            "depuis ce matin et ne peut pas consulter avant deux semaines. "
            "Elle prend de l'aspirine (100 mg/jour) pour un traitement cardiaque.\n\n"
            "👉 **Objectif :** trouver un médicament sans ordonnance adapté avec le chatbot, "
            "puis l'ajouter au panier.\n\n"
            "Utilisez le chatbot comme en situation réelle : posez vos questions, "
            "précisez les contraintes (traitement, allergies, préférences, inquiétudes…).\n\n"
            "---\n\n"
            "💡 **Comment interagir avec le chatbot ?**\n\n"
            "- Une proposition vous convient → demandez au chatbot de l'ajouter au panier.\n"
            "- La proposition n'est pas satisfaisante → demandez des ajustements selon vos besoins.\n"
            "- Aucune des propositions ne vous a plu → appuyez sur le bouton **Passer directement au questionnaire**."
        ),
    },
}

# ─────────────────────────────────────────────
# REDIS
# ─────────────────────────────────────────────
try:
    _redis = redis.Redis(host="database", port=6379, decode_responses=True)
    _redis.ping()
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False


def store_condition_in_redis(conversation_id: str, condition: dict):
    if REDIS_AVAILABLE:
        try:
            _redis.set(
                f"condition:{conversation_id}",
                json.dumps(condition),
                ex=60 * 60 * 24
            )
        except Exception as e:
            print(f"Redis error: {e}")


# ─────────────────────────────────────────────
# SQLITE
# ─────────────────────────────────────────────
DB_PATH = "/data/study.db"
os.makedirs("/data", exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            conversation_id TEXT PRIMARY KEY,
            genre TEXT,
            age TEXT,
            achat_en_ligne TEXT,
            usage_ia TEXT,
            style TEXT,
            timestamp TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS condition_counts (
            style TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS questionnaire (
            conversation_id TEXT PRIMARY KEY,
            ant_1_ep INTEGER, ant_2_ep INTEGER, ant_3_ep INTEGER, adequation_1_ep INTEGER,
            trust_ab_1_ep INTEGER, trust_ab_2_ep INTEGER, trust_ab_3_ep INTEGER,
            trust_in_1_ep INTEGER, trust_in_2_ep INTEGER, trust_in_3_ep INTEGER,
            trust_be_1_ep INTEGER, trust_be_2_ep INTEGER, trust_be_3_ep INTEGER, trust_be_4_ep INTEGER,
            trust_share_ep INTEGER, added_to_cart_ep TEXT,
            ant_1_med INTEGER, ant_2_med INTEGER, ant_3_med INTEGER, adequation_1_med INTEGER,
            trust_ab_1_med INTEGER, trust_ab_2_med INTEGER, trust_ab_3_med INTEGER,
            trust_in_1_med INTEGER, trust_in_2_med INTEGER, trust_in_3_med INTEGER,
            trust_be_1_med INTEGER, trust_be_2_med INTEGER, trust_be_3_med INTEGER, trust_be_4_med INTEGER,
            trust_share_med INTEGER, added_to_cart_med TEXT,
            timestamp TEXT
        )
    """)

    for cond in CONDITIONS:
        c.execute("""
            INSERT OR IGNORE INTO condition_counts (style, count, completed)
            VALUES (?, 0, 0)
        """, (cond["style"],))

    conn.commit()
    conn.close()


init_db()


def assign_condition() -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT style FROM condition_counts
        ORDER BY completed ASC, count ASC, style ASC
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    if row:
        return {"style": row[0]}
    return CONDITIONS[0]


def increment_condition_count(style: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE condition_counts SET count = count + 1 WHERE style = ?", (style,))
    conn.commit()
    conn.close()


def increment_completed_count(style: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE condition_counts SET completed = completed + 1 WHERE style = ?", (style,))
    conn.commit()
    conn.close()


def save_participant(conversation_id: str, profil: dict, condition: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO participants
        (conversation_id, genre, age, achat_en_ligne, usage_ia, style, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        conversation_id,
        profil.get("genre", ""),
        profil.get("age", ""),
        profil.get("achat_en_ligne", ""),
        profil.get("usage_ia", ""),
        condition.get("style", ""),
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()


def save_message(conversation_id: str, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO messages (conversation_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)
    """, (conversation_id, role, content, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def save_questionnaire(conversation_id: str, reponses: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO questionnaire (
            conversation_id,
            ant_1_ep, ant_2_ep, ant_3_ep, adequation_1_ep,
            trust_ab_1_ep, trust_ab_2_ep, trust_ab_3_ep,
            trust_in_1_ep, trust_in_2_ep, trust_in_3_ep,
            trust_be_1_ep, trust_be_2_ep, trust_be_3_ep, trust_be_4_ep,
            trust_share_ep, added_to_cart_ep,
            ant_1_med, ant_2_med, ant_3_med, adequation_1_med,
            trust_ab_1_med, trust_ab_2_med, trust_ab_3_med,
            trust_in_1_med, trust_in_2_med, trust_in_3_med,
            trust_be_1_med, trust_be_2_med, trust_be_3_med, trust_be_4_med,
            trust_share_med, added_to_cart_med,
            timestamp
        ) VALUES (
            ?,
            ?, ?, ?, ?,  ?, ?, ?,  ?, ?, ?,  ?, ?, ?, ?,  ?, ?,
            ?, ?, ?, ?,  ?, ?, ?,  ?, ?, ?,  ?, ?, ?, ?,  ?, ?,
            ?
        )
    """, (
        conversation_id,
        reponses.get("ant_1_ep"), reponses.get("ant_2_ep"), reponses.get("ant_3_ep"), reponses.get("adequation_1_ep"),
        reponses.get("trust_ab_1_ep"), reponses.get("trust_ab_2_ep"), reponses.get("trust_ab_3_ep"),
        reponses.get("trust_in_1_ep"), reponses.get("trust_in_2_ep"), reponses.get("trust_in_3_ep"),
        reponses.get("trust_be_1_ep"), reponses.get("trust_be_2_ep"), reponses.get("trust_be_3_ep"), reponses.get("trust_be_4_ep"),
        reponses.get("trust_share_ep"), reponses.get("added_to_cart_ep"),
        reponses.get("ant_1_med"), reponses.get("ant_2_med"), reponses.get("ant_3_med"), reponses.get("adequation_1_med"),
        reponses.get("trust_ab_1_med"), reponses.get("trust_ab_2_med"), reponses.get("trust_ab_3_med"),
        reponses.get("trust_in_1_med"), reponses.get("trust_in_2_med"), reponses.get("trust_in_3_med"),
        reponses.get("trust_be_1_med"), reponses.get("trust_be_2_med"), reponses.get("trust_be_3_med"), reponses.get("trust_be_4_med"),
        reponses.get("trust_share_med"), reponses.get("added_to_cart_med"),
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

    try:
        p_conn = sqlite3.connect(DB_PATH)
        pc = p_conn.cursor()
        pc.execute("SELECT style FROM participants WHERE conversation_id = ?", (conversation_id,))
        row = pc.fetchone()
        p_conn.close()
        if row:
            increment_completed_count(row[0])
    except Exception as e:
        print(f"Error incrementing completed count: {e}")


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "conversation_id" not in st.session_state:
    st.session_state["conversation_id"] = generate_conversation_id()
if "messages_ep" not in st.session_state:
    st.session_state["messages_ep"] = []
if "messages_med" not in st.session_state:
    st.session_state["messages_med"] = []
if "profil" not in st.session_state:
    st.session_state["profil"] = None
if "condition" not in st.session_state:
    st.session_state["condition"] = None
if "profil_saved" not in st.session_state:
    st.session_state["profil_saved"] = False
if "screen" not in st.session_state:
    st.session_state["screen"] = "profil"
if "chat_started_ep" not in st.session_state:
    st.session_state["chat_started_ep"] = False
if "chat_started_med" not in st.session_state:
    st.session_state["chat_started_med"] = False
if "cart_finalized_ep" not in st.session_state:
    st.session_state["cart_finalized_ep"] = False
if "cart_finalized_med" not in st.session_state:
    st.session_state["cart_finalized_med"] = False


def get_conv_id(produit: str) -> str:
    base = st.session_state["conversation_id"]
    return f"{base}_ep" if produit == "epicerie" else f"{base}_med"


def process_reset_button_click() -> None:
    cid = st.session_state["conversation_id"]
    reset_chatbot_conversation(f"{cid}_ep")
    reset_chatbot_conversation(f"{cid}_med")
    st.session_state["messages_ep"] = []
    st.session_state["messages_med"] = []
    st.session_state["conversation_id"] = generate_conversation_id()
    st.session_state["profil"] = None
    st.session_state["condition"] = None
    st.session_state["profil_saved"] = False
    st.session_state["screen"] = "profil"
    st.session_state["chat_started_ep"] = False
    st.session_state["chat_started_med"] = False
    st.session_state["cart_finalized_ep"] = False
    st.session_state["cart_finalized_med"] = False



# ─────────────────────────────────────────────
# ÉCRAN 1 — FORMULAIRE DE PROFIL
# ─────────────────────────────────────────────
def show_profil_form():
    st.title("💬 Assistant en ligne")

    st.markdown("### 👋 Bonjour et bienvenue !")
    st.markdown(
        "Cette expérience se déroule en **deux étapes** :\n\n"
        "1. Vous allez d'abord **échanger avec un chatbot** pour réaliser une tâche.\n"
        "2. Vous répondrez ensuite à **quelques questionnaires** afin de recueillir votre ressenti.\n\n"
        "Avant de commencer, merci de **renseigner les informations ci-dessous**.\n"
        "Ces données sont anonymes et utilisées uniquement à des fins de recherche académique."
    )
    st.divider()

    with st.form("profil_form"):
        st.subheader("Genre")
        genre = st.radio(
            "Votre genre :",
            options=["Homme", "Femme", "Autre", "Préfère ne pas répondre"],
            index=None,
            horizontal=True,
            label_visibility="collapsed"
        )

        st.subheader("Âge")
        age = st.selectbox(
            "Votre tranche d'âge :",
            options=["Sélectionnez...", "18–25 ans", "26–35 ans", "36–50 ans", "51 ans et plus"],
            label_visibility="collapsed"
        )

        st.subheader("Fréquence d'achat en ligne")
        achat_en_ligne = st.selectbox(
            "Fréquence :",
            options=["Sélectionnez...", "Rare", "Occasionnelle", "Fréquente"],
            label_visibility="collapsed"
        )

        st.subheader("Fréquence d'utilisation d'IA générative comme Claude, Gemini, ChatGPT...")
        usage_ia = st.selectbox(
            "Usage IA :",
            options=[
                "Sélectionnez...",
                "Jamais",
                "Rarement (quelques fois)",
                "Occasionnellement (quelques fois par mois)",
                "Régulièrement (plusieurs fois par semaine)",
                "Quotidiennement",
            ],
            label_visibility="collapsed"
        )

        submitted = st.form_submit_button("Commencer l'expérience →")

        if submitted:
            if age == "Sélectionnez..." or achat_en_ligne == "Sélectionnez..." or usage_ia == "Sélectionnez...":
                st.error("Merci de renseigner toutes les informations avant de continuer.")
            else:
                profil = {
                    "genre": genre,
                    "age": age,
                    "achat_en_ligne": achat_en_ligne,
                    "usage_ia": usage_ia,
                }
                st.session_state["profil"] = profil

                if not st.session_state["profil_saved"]:
                    condition = assign_condition()
                    st.session_state["condition"] = condition
                    increment_condition_count(condition["style"])
                    store_condition_in_redis(get_conv_id("epicerie"), {"style": condition["style"], "produit": "epicerie"})
                    store_condition_in_redis(get_conv_id("medicaments"), {"style": condition["style"], "produit": "medicaments"})
                    save_participant(st.session_state["conversation_id"], profil, condition)
                    st.session_state["profil_saved"] = True

                st.session_state["screen"] = "mission_ep"
                st.rerun()


# ─────────────────────────────────────────────
# ÉCRAN 2a — MISSION ÉPICERIE
# ─────────────────────────────────────────────
def show_mission(produit: str):
    st.title("💬 Assistant en ligne")
    st.divider()
    mission = MISSIONS[produit]
    st.markdown(f"## {mission['titre']}")
    with st.container(border=True):
        st.markdown(mission["texte"])
    st.divider()
    st.write("Lorsque vous êtes prêt(e), cliquez sur le bouton ci-dessous pour démarrer.")

    next_screen = "chat_ep" if produit == "epicerie" else "chat_med"
    if st.button("Démarrer la conversation →", type="primary", use_container_width=True):
        st.session_state["screen"] = next_screen
        st.rerun()


# ─────────────────────────────────────────────
# ÉCRAN 3 — CHAT (générique)
# ─────────────────────────────────────────────
def show_chat(produit: str):
    next_screen = "mission_med" if produit == "epicerie" else "questionnaire"
    next_label = "Passer à la mission 2 →" if produit == "epicerie" else "Passer directement au questionnaire"
    messages_key = "messages_ep" if produit == "epicerie" else "messages_med"
    chat_started_key = "chat_started_ep" if produit == "epicerie" else "chat_started_med"
    conv_id = get_conv_id(produit)
    condition = st.session_state.get("condition", {})
    style = condition.get("style", "human_like_formal")

    st.title("💬 Assistant en ligne")
    mission = MISSIONS[produit]
    with st.expander(f"📋 {mission['titre']}", expanded=False):
        st.markdown(mission["texte"])
        st.divider()
        if st.button(f"⏭️ {next_label}", type="secondary", use_container_width=True, key=f"skip_{produit}"):
            st.session_state["screen"] = next_screen
            st.rerun()

    cart_finalized_key = "cart_finalized_ep" if produit == "epicerie" else "cart_finalized_med"

    def process_button_click(value, title) -> None:
        if title in ["Tout est correct !", "Everything is correct!", "ok",
                     "Finaliser la commande", "Finaliser", "finalize"]:
            st.session_state[cart_finalized_key] = True
            return
        st.session_state[messages_key].append({"role": "user", "content": title})
        save_message(conv_id, "user", title)
        process_message(value)

    def display_textual_message(message: dict) -> None:
        role = message["role"]
        content = message["content"].replace("\n\n", "\n")
        st.chat_message(role).write(content)

    def display_messages(messages=None) -> None:
        if messages is None:
            messages = st.session_state[messages_key]
        for msg in messages:
            if msg["role"] in ("assistant", "user"):
                display_textual_message(msg)
        if messages and messages[-1]["role"] == "button_pair":
            for button in messages[-1]["content"]:
                title = button["title"]
                value = button["payload"]
                st.button(
                    title,
                    on_click=lambda value=value, title=title: process_button_click(value, title),
                )

    def process_message(user_message: str) -> None:
        with st.spinner("Veuillez patienter..."):
            bot_responses = get_chatbot_response(user_message, conv_id)
            for bot_response in bot_responses:
                if "text" in bot_response:
                    content = bot_response["text"].replace("$", "\\$")
                    response_dict = {"role": "assistant", "content": content}
                    st.session_state[messages_key].append(response_dict)
                    save_message(conv_id, "assistant", content)
                if "buttons" in bot_response and bot_response["buttons"]:
                    response_dict = {"role": "button_pair", "content": bot_response["buttons"]}
                    st.session_state[messages_key].append(response_dict)

    # Bouton après finalisation du panier
    if st.session_state.get(cart_finalized_key, False):
        st.divider()
        if produit == "epicerie":
            st.success("🛒 Votre panier a été finalisé !")
            if st.button("➡️ Passer à la mission 2", type="primary", use_container_width=True):
                st.session_state["screen"] = next_screen
                st.rerun()
        else:
            st.success("🛒 Votre panier a été finalisé !")
            if st.button("➡️ Passer au questionnaire", type="primary", use_container_width=True):
                st.session_state["screen"] = next_screen
                st.rerun()

    # Présentation automatique
    if not st.session_state[messages_key] and not st.session_state.get(chat_started_key, False):
        st.session_state[chat_started_key] = True
        process_message("start")
        st.rerun()

    display_messages()

    if user_message := st.chat_input(placeholder="Écrivez votre message ici..."):
        st.session_state[messages_key].append({"role": "user", "content": user_message})
        st.chat_message("user").write(user_message)
        save_message(conv_id, "user", user_message)
        process_message(user_message)
        st.rerun()


# ─────────────────────────────────────────────
# ÉCRAN 4 — QUESTIONNAIRE (côte à côte)
# ─────────────────────────────────────────────
LIKERT_OPTIONS = {
    1: "1 — Pas du tout d'accord",
    2: "2 — Pas d'accord",
    3: "3 — Neutre",
    4: "4 — D'accord",
    5: "5 — Tout à fait d'accord",
}
LIKERT_LABELS = list(LIKERT_OPTIONS.values())
LIKERT_VALUES = list(LIKERT_OPTIONS.keys())


def likert_pair(label: str, key_ep: str, key_med: str):
    """Affiche un item Likert côte à côte pour les 2 missions."""
    st.write(f"**{label}**")
    col1, col2 = st.columns(2)
    with col1:
        choix_ep = st.radio(
            "Épicerie",
            options=LIKERT_LABELS,
            index=None,
            horizontal=False,
            label_visibility="visible",
            key=key_ep
        )
    with col2:
        choix_med = st.radio(
            "Médicaments",
            options=LIKERT_LABELS,
            index=None,
            horizontal=False,
            label_visibility="visible",
            key=key_med
        )
    val_ep = LIKERT_VALUES[LIKERT_LABELS.index(choix_ep)] if choix_ep else None
    val_med = LIKERT_VALUES[LIKERT_LABELS.index(choix_med)] if choix_med else None
    return val_ep, val_med


def show_questionnaire():
    st.title("📋 Questionnaire")
    st.write(
        "Merci d'avoir utilisé l'assistant pour les deux missions. "
        "Veuillez répondre aux questions suivantes pour chaque mission."
    )
    st.divider()

    # En-tête colonnes
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🍽️ Mission 1 — Épicerie")
    with col2:
        st.markdown("### 🏥 Mission 2 — Médicaments")

    st.caption("Échelle : 1 = Pas du tout d'accord → 5 = Tout à fait d'accord")

    with st.form("questionnaire_form"):

        # ── SECTION 1 — Anthropomorphisme + Adéquation ──
        st.subheader("Section 1 — Perception de l'assistant")

        ant_1_ep, ant_1_med = likert_pair("1. J'ai l'impression de parler à une personne réelle.", "ant_1_ep", "ant_1_med")
        ant_2_ep, ant_2_med = likert_pair("2. L'assistant me paraît chaleureux.", "ant_2_ep", "ant_2_med")
        ant_3_ep, ant_3_med = likert_pair("3. L'assistant semble avoir des intentions propres.", "ant_3_ep", "ant_3_med")
        adequation_1_ep, adequation_1_med = likert_pair(
            "4. Le style conversationnel de l'assistant me semble adapté à la situation.",
            "adequation_1_ep", "adequation_1_med"
        )

        st.divider()

        # ── SECTION 2 — Confiance ──
        st.subheader("Section 2 — Confiance envers l'assistant")
        st.caption("Échelle : 1 = Pas du tout d'accord → 5 = Tout à fait d'accord")

        st.markdown("**Compétence**")
        trust_ab_1_ep, trust_ab_1_med = likert_pair("5. Le chatbot semble bien connaître les produits qu'il recommande.", "trust_ab_1_ep", "trust_ab_1_med")
        trust_ab_2_ep, trust_ab_2_med = likert_pair("6. Je pense que le chatbot est capable de m'aider à faire de bons choix.", "trust_ab_2_ep", "trust_ab_2_med")
        trust_ab_3_ep, trust_ab_3_med = likert_pair("7. Les recommandations du chatbot me semblent adaptées à ma situation.", "trust_ab_3_ep", "trust_ab_3_med")

        st.markdown("**Honnêteté**")
        trust_in_1_ep, trust_in_1_med = likert_pair("8. J'ai l'impression que le chatbot me donne des informations fiables.", "trust_in_1_ep", "trust_in_1_med")
        trust_in_2_ep, trust_in_2_med = likert_pair("9. Le chatbot ne semble pas chercher à m'induire en erreur.", "trust_in_2_ep", "trust_in_2_med")
        trust_in_3_ep, trust_in_3_med = likert_pair("10. Je pense que le chatbot est transparent dans ses recommandations.", "trust_in_3_ep", "trust_in_3_med")

        st.markdown("**Bienveillance**")
        trust_be_1_ep, trust_be_1_med = likert_pair("11. J'ai le sentiment que le chatbot cherche vraiment à m'aider.", "trust_be_1_ep", "trust_be_1_med")
        trust_be_2_ep, trust_be_2_med = likert_pair("12. Le chatbot semble prendre en compte mes besoins avant tout.", "trust_be_2_ep", "trust_be_2_med")
        trust_be_3_ep, trust_be_3_med = likert_pair("13. Je me sens bien conseillé(e) par le chatbot.", "trust_be_3_ep", "trust_be_3_med")
        trust_be_4_ep, trust_be_4_med = likert_pair("14. Je pense que le chatbot agit dans mon intérêt.", "trust_be_4_ep", "trust_be_4_med")

        st.markdown("**Confiance à partager mes informations**")
        trust_share_ep, trust_share_med = likert_pair(
            "15. Partager des informations avec l'assistant ne m'a pas fait peur durant l'expérience.",
            "trust_share_ep", "trust_share_med"
        )

        st.divider()

        # ── PANIER ──
        st.subheader("Votre expérience")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🍽️ Mission 1 — Épicerie**")
            added_to_cart_ep = st.radio(
                "Avez-vous ajouté des recommandations au panier ?",
                options=["Oui", "Non"],
                index=None,
                horizontal=True,
                key="added_to_cart_ep"
            )
        with col2:
            st.markdown("**🏥 Mission 2 — Médicaments**")
            added_to_cart_med = st.radio(
                "Avez-vous ajouté des recommandations au panier ?",
                options=["Oui", "Non"],
                index=None,
                horizontal=True,
                key="added_to_cart_med"
            )

        st.divider()
        submitted = st.form_submit_button("Envoyer mes réponses →", type="primary")

        if submitted:
            reponses = {
                "ant_1_ep": ant_1_ep, "ant_2_ep": ant_2_ep, "ant_3_ep": ant_3_ep, "adequation_1_ep": adequation_1_ep,
                "trust_ab_1_ep": trust_ab_1_ep, "trust_ab_2_ep": trust_ab_2_ep, "trust_ab_3_ep": trust_ab_3_ep,
                "trust_in_1_ep": trust_in_1_ep, "trust_in_2_ep": trust_in_2_ep, "trust_in_3_ep": trust_in_3_ep,
                "trust_be_1_ep": trust_be_1_ep, "trust_be_2_ep": trust_be_2_ep, "trust_be_3_ep": trust_be_3_ep, "trust_be_4_ep": trust_be_4_ep,
                "trust_share_ep": trust_share_ep, "added_to_cart_ep": added_to_cart_ep,
                "ant_1_med": ant_1_med, "ant_2_med": ant_2_med, "ant_3_med": ant_3_med, "adequation_1_med": adequation_1_med,
                "trust_ab_1_med": trust_ab_1_med, "trust_ab_2_med": trust_ab_2_med, "trust_ab_3_med": trust_ab_3_med,
                "trust_in_1_med": trust_in_1_med, "trust_in_2_med": trust_in_2_med, "trust_in_3_med": trust_in_3_med,
                "trust_be_1_med": trust_be_1_med, "trust_be_2_med": trust_be_2_med, "trust_be_3_med": trust_be_3_med, "trust_be_4_med": trust_be_4_med,
                "trust_share_med": trust_share_med, "added_to_cart_med": added_to_cart_med,
            }
            save_questionnaire(st.session_state["conversation_id"], reponses)
            st.session_state["screen"] = "fin"
            st.rerun()


# ─────────────────────────────────────────────
# ÉCRAN 5 — FIN
# ─────────────────────────────────────────────
def show_fin():
    st.title("💬 Assistant en ligne")
    st.divider()
    st.markdown("## ✅ Merci pour votre participation !")
    st.success(
        "Vos réponses ont bien été enregistrées. "
        "Vous pouvez maintenant fermer cette page."
    )
    st.write(
        "Cette étude porte sur les interactions entre les utilisateurs et les assistants "
        "conversationnels. Vos réponses resteront anonymes et seront utilisées "
        "uniquement à des fins de recherche académique."
    )


# ─────────────────────────────────────────────
# ROUTEUR PRINCIPAL
# ─────────────────────────────────────────────
screen = st.session_state.get("screen", "profil")

if screen == "profil":
    show_profil_form()
elif screen == "mission_ep":
    show_mission("epicerie")
elif screen == "chat_ep":
    show_chat("epicerie")
elif screen == "mission_med":
    show_mission("medicaments")
elif screen == "chat_med":
    show_chat("medicaments")
elif screen == "questionnaire":
    show_questionnaire()
else:
    show_fin()
