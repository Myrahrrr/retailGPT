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
st.set_page_config(page_title="Assistant en ligne", page_icon=im)

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CONDITIONS EXPÉRIMENTALES — ROUND-ROBIN
# ─────────────────────────────────────────────
CONDITIONS = [
    {"style": "machine_like",        "produit": "epicerie"},
    {"style": "human_like_formal",   "produit": "epicerie"},
    {"style": "human_like_friendly", "produit": "epicerie"},
    {"style": "machine_like",        "produit": "medicaments"},
    {"style": "human_like_formal",   "produit": "medicaments"},
    {"style": "human_like_friendly", "produit": "medicaments"},
]

MISSIONS = {
    "medicaments": {
        "titre": "🏥 Votre mission",
        "texte": (
            "Votre amie Julie, 45 ans, souffre de douleurs articulaires au genou droit "
            "depuis 4 jours avec des raideurs le matin. "
            "Elle prend de l'Aspirine 100mg tous les jours pour protéger son cœur "
            "et ne peut pas consulter un médecin avant 2 semaines.\n\n"
            "**Utilisez le chatbot pour trouver un médicament sans ordonnance "
            "adapté à sa situation et compatible avec son traitement, "
            "et l'ajouter au panier.**"
        ),
    },
    "epicerie": {
        "titre": "🍽️ Votre mission",
        "texte": (
            "Vous organisez une soirée conviviale chez vous pour 12 personnes ce week-end. "
            "Vous souhaitez préparer un repas maison complet : apéro, plat et dessert, "
            "pour un budget total de 80 euros.\n\n"
            "**Utilisez le chatbot pour planifier votre menu, "
            "trouver les produits adaptés dans le catalogue "
            "et les ajouter à votre panier.**"
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
            produit TEXT,
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
            style TEXT,
            produit TEXT,
            count INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            PRIMARY KEY (style, produit)
        )
    """)

    # Table questionnaire — une ligne par participant
    c.execute("""
        CREATE TABLE IF NOT EXISTS questionnaire (
            conversation_id TEXT PRIMARY KEY,
            ant_1 INTEGER,
            ant_2 INTEGER,
            ant_3 INTEGER,
            ant_4 INTEGER,
            ant_5 INTEGER,
            trust_1 INTEGER,
            trust_2 INTEGER,
            trust_3 INTEGER,
            trust_4 INTEGER,
            trust_5 INTEGER,
            trust_6 INTEGER,
            adequation_1 INTEGER,
            adequation_2 INTEGER,
            adequation_3 INTEGER,
            timestamp TEXT
        )
    """)

    for cond in CONDITIONS:
        c.execute("""
            INSERT OR IGNORE INTO condition_counts (style, produit, count)
            VALUES (?, ?, 0)
        """, (cond["style"], cond["produit"]))

    conn.commit()
    conn.close()


init_db()


def assign_condition() -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT style, produit FROM condition_counts
        ORDER BY completed ASC, count ASC, style ASC
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    if row:
        return {"style": row[0], "produit": row[1]}
    return CONDITIONS[0]


def increment_condition_count(style: str, produit: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE condition_counts SET count = count + 1
        WHERE style = ? AND produit = ?
    """, (style, produit))
    conn.commit()
    conn.close()


def increment_completed_count(style: str, produit: str):
    """Incremente le compteur de completions quand le questionnaire est soumis."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE condition_counts SET completed = completed + 1
        WHERE style = ? AND produit = ?
    """, (style, produit))
    conn.commit()
    conn.close()


def save_participant(conversation_id: str, profil: dict, condition: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO participants
        (conversation_id, genre, age, achat_en_ligne, usage_ia, style, produit, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        conversation_id,
        profil.get("genre", ""),
        profil.get("age", ""),
        profil.get("achat_en_ligne", ""),
        profil.get("usage_ia", ""),
        condition.get("style", ""),
        condition.get("produit", ""),
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
    """Sauvegarde les réponses au questionnaire dans SQLite."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO questionnaire (
            conversation_id,
            ant_1, ant_2, ant_3, ant_4, ant_5,
            trust_1, trust_2, trust_3, trust_4, trust_5, trust_6,
            adequation_1, adequation_2, adequation_3,
            timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        conversation_id,
        reponses.get("ant_1"), reponses.get("ant_2"),
        reponses.get("ant_3"), reponses.get("ant_4"), reponses.get("ant_5"),
        reponses.get("trust_1"), reponses.get("trust_2"),
        reponses.get("trust_3"), reponses.get("trust_4"),
        reponses.get("trust_5"), reponses.get("trust_6"),
        reponses.get("adequation_1"), reponses.get("adequation_2"),
        reponses.get("adequation_3"),
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

    # Incrementer le compteur de completions pour le round-robin
    try:
        p_conn = sqlite3.connect(DB_PATH)
        pc = p_conn.cursor()
        pc.execute("SELECT style, produit FROM participants WHERE conversation_id = ?", (conversation_id,))
        row = pc.fetchone()
        p_conn.close()
        if row:
            increment_completed_count(row[0], row[1])
    except Exception as e:
        print(f"Error incrementing completed count: {e}")


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "conversation_id" not in st.session_state:
    st.session_state["conversation_id"] = generate_conversation_id()
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "profil" not in st.session_state:
    st.session_state["profil"] = None
if "condition" not in st.session_state:
    st.session_state["condition"] = None
if "profil_saved" not in st.session_state:
    st.session_state["profil_saved"] = False
# Écrans : "profil" | "mission" | "chat" | "questionnaire" | "fin"
if "screen" not in st.session_state:
    st.session_state["screen"] = "profil"


def process_reset_button_click() -> None:
    st.session_state.pop("messages", None)
    st.session_state["conversation_id"] = generate_conversation_id()
    st.session_state["profil"] = None
    st.session_state["condition"] = None
    st.session_state["profil_saved"] = False
    st.session_state["screen"] = "profil"
    reset_chatbot_conversation(st.session_state["conversation_id"])


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.write("Utilisez cette interface pour interagir avec l'assistant.")
    st.button("Recommencer la conversation", on_click=process_reset_button_click)
    st.write("👇 Télécharger la conversation sous forme de document Word.")
    conversation_docx = chat_to_word(
        st.session_state.messages,
        profil=st.session_state.get("profil"),
        conversation_id=st.session_state["conversation_id"]
    )
    st.download_button(
        "Télécharger la conversation",
        conversation_docx,
        file_name=f"{st.session_state['conversation_id']}.docx",
    )
    st.header("Instructions")
    st.write("**Lisez les instructions ci-dessous avant de commencer.**")
    st.write(
        "Envoyez un message pour démarrer la conversation. "
        "L'assistant peut effectuer les actions suivantes :"
    )
    st.write("- Vérifier la disponibilité des produits souhaités")
    st.write("- Fournir des recommandations selon vos besoins")
    st.write("- Ajouter et retirer des produits de votre panier")
    st.write("- Finaliser la commande lorsque vous êtes prêt.")
    st.write("N'hésitez pas à écrire naturellement.")


# ─────────────────────────────────────────────
# ÉCRAN 1 — FORMULAIRE DE PROFIL
# ─────────────────────────────────────────────
def show_profil_form():
    st.title("💬 Assistant en ligne")
    st.markdown("### Bienvenue dans cette expérience")
    st.write(
        "Merci de renseigner quelques informations avant de commencer. "
        "Ces données sont anonymes et utilisées uniquement à des fins de recherche."
    )
    st.divider()

    with st.form("profil_form"):
        st.subheader("Genre")
        genre = st.radio(
            "Votre genre :",
            options=["Homme", "Femme", "Autre", "Préfère ne pas répondre"],
            horizontal=True,
            label_visibility="collapsed"
        )

        st.subheader("Âge")
        age = st.selectbox(
            "Votre tranche d'âge :",
            options=[
                "Sélectionnez...",
                "Moins de 18 ans", "18-24 ans", "25-34 ans",
                "35-44 ans", "45-54 ans", "55 ans et plus",
            ],
            label_visibility="collapsed"
        )

        st.subheader("Fréquence d'achat en ligne")
        achat_en_ligne = st.selectbox(
            "Fréquence :",
            options=[
                "Sélectionnez...",
                "Jamais",
                "Rarement (moins d'une fois par mois)",
                "Occasionnellement (1-3 fois par mois)",
                "Régulièrement (1-2 fois par semaine)",
                "Très souvent (plusieurs fois par semaine)",
            ],
            label_visibility="collapsed"
        )

        st.subheader("Utilisation d'IA générative")
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
            if (
                age == "Sélectionnez..."
                or achat_en_ligne == "Sélectionnez..."
                or usage_ia == "Sélectionnez..."
            ):
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
                    increment_condition_count(condition["style"], condition["produit"])
                    store_condition_in_redis(st.session_state["conversation_id"], condition)
                    save_participant(st.session_state["conversation_id"], profil, condition)
                    st.session_state["profil_saved"] = True

                st.session_state["screen"] = "mission"
                st.rerun()


# ─────────────────────────────────────────────
# ÉCRAN 2 — MISSION
# ─────────────────────────────────────────────
def show_mission():
    st.title("💬 Assistant en ligne")
    st.divider()

    condition = st.session_state.get("condition", {})
    produit = condition.get("produit", "epicerie")
    mission = MISSIONS.get(produit, MISSIONS["epicerie"])

    st.markdown(f"## {mission['titre']}")
    st.info(mission["texte"])
    st.divider()
    st.write("Lorsque vous êtes prêt(e), cliquez sur le bouton ci-dessous pour démarrer.")

    if st.button("Démarrer la conversation →", type="primary"):
        st.session_state["screen"] = "chat"
        st.rerun()


# ─────────────────────────────────────────────
# ÉCRAN 3 — CHAT
# ─────────────────────────────────────────────
def show_chat():
    st.title("💬 Assistant en ligne")

    condition = st.session_state.get("condition", {})
    produit = condition.get("produit", "epicerie")
    mission = MISSIONS.get(produit, MISSIONS["epicerie"])
    with st.expander("📋 Rappel de votre mission", expanded=False):
        st.write(mission["texte"])

    def process_button_click(value, title) -> None:
        # Détecter "Tout est correct" → passer au questionnaire
        if title in ["Tout est correct !", "Everything is correct!", "ok"]:
            st.session_state["screen"] = "questionnaire"
            st.rerun()
            return
        st.session_state.messages.append({"role": "user", "content": title})
        save_message(st.session_state["conversation_id"], "user", title)
        process_message(value)

    def display_textual_message(message: dict) -> None:
        role = message["role"]
        content = message["content"].replace("\n\n", "\n")
        st.chat_message(role).write(content)

    def display_messages(messages=st.session_state.messages) -> None:
        for msg in messages:
            if msg["role"] == "assistant" or msg["role"] == "user":
                display_textual_message(msg)
        if messages and messages[-1]["role"] == "button_pair":
            for button in messages[-1]["content"]:
                title = button["title"]
                value = button["payload"]
                st.button(
                    title,
                    on_click=lambda value=value, title=title: process_button_click(
                        value, title
                    ),
                )

    def process_message(user_message: str) -> None:
        with st.spinner("Veuillez patienter..."):
            bot_responses = get_chatbot_response(
                user_message,
                st.session_state["conversation_id"]
            )
            for bot_response in bot_responses:
                if "text" in bot_response:
                    content = bot_response["text"].replace("$", "\\$")
                    response_dict = {"role": "assistant", "content": content}
                    st.session_state.messages.append(response_dict)
                    save_message(
                        st.session_state["conversation_id"],
                        "assistant",
                        content
                    )
                if "buttons" in bot_response and bot_response["buttons"]:
                    response_dict = {
                        "role": "button_pair",
                        "content": bot_response["buttons"],
                    }
                    st.session_state.messages.append(response_dict)

    display_messages()

    if user_message := st.chat_input(placeholder="Écrivez votre message ici..."):
        st.session_state.messages.append({"role": "user", "content": user_message})
        st.chat_message("user").write(user_message)
        save_message(st.session_state["conversation_id"], "user", user_message)
        process_message(user_message)
        st.rerun()


# ─────────────────────────────────────────────
# ÉCRAN 4 — QUESTIONNAIRE
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


def likert_item(label: str, key: str) -> int:
    """Affiche un item Likert 1-5 et retourne la valeur sélectionnée."""
    st.write(f"**{label}**")
    choix = st.radio(
        label,
        options=LIKERT_LABELS,
        index=2,  # Neutre par défaut
        horizontal=True,
        label_visibility="collapsed",
        key=key
    )
    return LIKERT_VALUES[LIKERT_LABELS.index(choix)]


def show_questionnaire():
    st.title("📋 Questionnaire")
    st.write(
        "Merci d'avoir utilisé l'assistant. "
        "Veuillez répondre aux questions suivantes en vous basant sur votre expérience."
    )
    st.caption("Échelle : 1 = Pas du tout d'accord → 5 = Tout à fait d'accord")
    st.divider()

    with st.form("questionnaire_form"):

        # ── SECTION 1 — Anthropomorphisme perçu ──
        st.subheader("Section 1 — Perception de l'assistant")

        ant_1 = likert_item(
            "1. L'assistant me semble humain dans sa manière de communiquer.",
            "ant_1"
        )
        ant_2 = likert_item(
            "2. J'ai l'impression de parler à une personne réelle plutôt qu'à un système.",
            "ant_2"
        )
        ant_3 = likert_item(
            "3. L'assistant me paraît chaleureux.",
            "ant_3"
        )
        ant_4 = likert_item(
            "4. L'assistant semble avoir des intentions propres.",
            "ant_4"
        )
        ant_5 = likert_item(
            "5. L'interaction avec l'assistant me donne un sentiment de contact humain.",
            "ant_5"
        )

        st.divider()

        # ── SECTION 2 — Confiance perçue ──
        st.subheader("Section 2 — Confiance envers l'assistant")

        trust_1 = likert_item("1. J'ai confiance dans cet assistant.", "trust_1")
        trust_2 = likert_item("2. Je considère cet assistant comme fiable.", "trust_2")
        trust_3 = likert_item("3. Je pense que cet assistant est digne de confiance.", "trust_3")
        trust_4 = likert_item("4. Je peux compter sur cet assistant pour m'aider à choisir.", "trust_4")
        trust_5 = likert_item("5. Je crois que cet assistant agit dans mon intérêt.", "trust_5")
        trust_6 = likert_item("6. Je me sens en sécurité en suivant ses recommandations.", "trust_6")

        st.divider()

        # ── SECTION 3 — Adéquation du ton ──
        st.subheader("Section 3 — Style de communication")

        adequation_1 = likert_item("1. Le ton de l'assistant est adapté à la situation.", "adequation_1")
        adequation_2 = likert_item("2. L'assistant me semble professionnel.", "adequation_2")
        adequation_3 = likert_item(
            "3. Le style de communication de l'assistant renforce sa crédibilité.",
            "adequation_3"
        )

        st.divider()

        submitted = st.form_submit_button("Envoyer mes réponses →", type="primary")

        if submitted:
            reponses = {
                "ant_1": ant_1, "ant_2": ant_2, "ant_3": ant_3,
                "ant_4": ant_4, "ant_5": ant_5,
                "trust_1": trust_1, "trust_2": trust_2, "trust_3": trust_3,
                "trust_4": trust_4, "trust_5": trust_5, "trust_6": trust_6,
                "adequation_1": adequation_1, "adequation_2": adequation_2,
                "adequation_3": adequation_3,
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
elif screen == "mission":
    show_mission()
elif screen == "chat":
    show_chat()
elif screen == "questionnaire":
    show_questionnaire()
else:
    show_fin()
