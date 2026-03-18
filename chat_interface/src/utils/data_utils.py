import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches


def generate_conversation_id() -> str:
    """Generates a conversation ID with a UUID."""
    return str(uuid.uuid4())


def chat_to_word(messages: dict, profil: dict = None, conversation_id: str = None) -> bytes:
    """Converts a chat to a Word document.
    Includes participant profile at the top if provided.
    The filename will be the conversation_id.
    """

    document = Document()

    style = document.styles["Normal"]
    font = style.font
    font.name = "Arial"

    section = document.sections[0]
    header = section.header
    header_paragraph = header.paragraphs[0]
    run = header_paragraph.add_run()
    image_path = Path(__file__).parent.parent / "images" / "neuralmind.png"
    run.add_picture(str(image_path), width=Inches(0.5))
    header_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    document.add_heading("Historique de conversation", 0)
    document.add_heading(
        f"Date et heure : {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        level=1,
    )

    if conversation_id:
        document.add_heading(f"ID : {conversation_id}", level=2)

    # ─── Profil du participant ───
    if profil:
        document.add_heading("Informations du participant", level=1)
        table = document.add_table(rows=4, cols=2)
        table.style = "Table Grid"

        infos = [
            ("Genre", profil.get("genre", "—")),
            ("Tranche d'âge", profil.get("age", "—")),
            ("Fréquence d'achat en ligne", profil.get("achat_en_ligne", "—")),
            ("Utilisation d'IA générative", profil.get("usage_ia", "—")),
        ]

        for i, (label, valeur) in enumerate(infos):
            row = table.rows[i]
            run_label = row.cells[0].paragraphs[0].add_run(label)
            run_label.bold = True
            row.cells[1].paragraphs[0].add_run(valeur)

        document.add_paragraph("")

    # ─── Messages ───
    document.add_heading("Messages :", level=1)

    for message in messages:
        p = document.add_paragraph()
        if message["role"] == "assistant":
            role = p.add_run("Assistant : ")
            role.bold = True
            p.add_run(f"{message['content']}")
        elif message["role"] == "user":
            role = p.add_run("Utilisateur : ")
            role.bold = True
            p.add_run(f"{message['content']}")

    word_file_io = BytesIO()
    document.save(word_file_io)
    word_file_io.seek(0)
    return word_file_io
