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
# 3 styles × 2 produits = 6 conditions
# ─────────────────────────────────────────────
CONDITIONS = [
    {"style": "machine_like",        "produit": "snacks"},
    {"style": "human_like_formal",   "produit": "snacks"},
    {"style": "human_like_friendly", "produit": "snacks"},
    {"style": "machine_like",        "produit": "medicaments"},
    {"style": "human_like_formal",   "produit": "medicaments"},
    {"style": "human_like_friendly", "produit": "medicaments"},
]

# ─────────────────────────────────────────────
# REDIS — stockage de la condition du participant
# ─────────────────────────────────────────────
try:
    _redis = redis.Redis(host="database", port=6379, decode_responses=True)
    _redis.ping()
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False


def store_condition_in_redis(conversation_id: str, condition: dict):
    """Stocke la condition du participant dans Redis.
    actions.py la lit avec la clé condition:{conversation_id}
    """
    if REDIS_AVAILABLE:
        try:
            _redis.set(
                f"condition:{conversation_id}",
                json.dumps(condition),
                ex=60 * 60 * 24  # expire après 24h
            )
        except Exception as e:
            print(f"Redis error: {e}")


# ─────────────────────────────────────────────
# SQLITE — stockage des données de l'étude
# ─────────────────────────────────────────────
DB_PATH = "/data/study.db"
os.makedirs("/data", exist_ok=True)


def init_db():
    """Crée toutes les tables nécessaires."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table participants — profil + condition assignée
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

    # Table messages — toute la conversation
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )
    """)

    # Table condition_counts — compteur pour le round-robin
    c.execute("""
        CREATE TABLE IF NOT EXISTS condition_counts (
            style TEXT,
            produit TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (style, produit)
        )
    """)

    # Initialiser les compteurs si vides
    for cond in CONDITIONS:
        c.execute("""
            INSERT OR IGNORE INTO condition_counts (style, produit, count)
            VALUES (?, ?, 0)
        """, (cond["style"], cond["produit"]))

    conn.commit()
    conn.close()


init_db()


def assign_condition() -> dict:
    """Attribue la condition la moins représentée (round-robin équilibré).

    Returns:
        dict avec keys 'style' et 'produit'
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Trouver la condition avec le moins de participants
    c.execute("""
        SELECT style, produit, count
        FROM condition_counts
        ORDER BY count ASC, style ASC
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()

    if row:
        return {"style": row[0], "produit": row[1]}

    # Fallback si table vide
    return CONDITIONS[0]


def increment_condition_count(style: str, produit: str):
    """Incrémente le compteur de la condition assignée."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE condition_counts
        SET count = count + 1
        WHERE style = ? AND produit = ?
    """, (style, produit))
    conn.commit()
    conn.close()


def save_participant(conversation_id: str, profil: dict, condition: dict):
    """Sauvegarde le profil du participant avec sa condition assignée."""
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
    """Sauvegarde un message en temps réel."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO messages (conversation_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)
    """, (conversation_id, role, content, datetime.now().isoformat()))
    conn.commit()
    conn.close()


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


def process_reset_button_click() -> None:
    """Resets the chatbot conversation and assigns a new condition."""
    st.session_state.pop("messages", None)
    st.session_state["conversation_id"] = generate_conversation_id()
    st.session_state["profil"] = None
    st.session_state["condition"] = None
    st.session_state["profil_saved"] = False
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
                "Moins de 18 ans",
                "18-24 ans",
                "25-34 ans",
                "35-44 ans",
                "45-54 ans",
                "55 ans et plus",
            ],
            label_visibility="collapsed"
        )

        st.subheader("Fréquence d'achat en ligne")
        achat_en_ligne = st.selectbox(
            "À quelle fréquence achetez-vous en ligne ?",
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
            "À quelle fréquence utilisez-vous des outils d'IA générative (ChatGPT, Copilot, etc.) ?",
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
                    # ① Assigner la condition round-robin
                    condition = assign_condition()
                    st.session_state["condition"] = condition

                    # ② Incrémenter le compteur
                    increment_condition_count(
                        condition["style"],
                        condition["produit"]
                    )

                    # ③ Stocker dans Redis pour actions.py
                    store_condition_in_redis(
                        st.session_state["conversation_id"],
                        condition
                    )

                    # ④ Sauvegarder dans SQLite avec style + produit
                    save_participant(
                        st.session_state["conversation_id"],
                        profil,
                        condition
                    )

                    st.session_state["profil_saved"] = True

                st.rerun()


# ─────────────────────────────────────────────
# ÉCRAN 2 — CHAT
# ─────────────────────────────────────────────
def show_chat():
    st.title("💬 Assistant en ligne")

    def process_button_click(value, title) -> None:
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
# ROUTEUR PRINCIPAL
# ─────────────────────────────────────────────
if st.session_state["profil"] is None:
    show_profil_form()
else:
    show_chat()
