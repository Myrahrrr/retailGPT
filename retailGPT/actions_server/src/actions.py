import json
import os
import sys
import unicodedata
from typing import Any, Dict, List, Text

import redis
from rasa_sdk import Action, Tracker
from rasa_sdk.events import ActiveLoop, FollowupAction, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict

current_directory = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_directory)

from LLMChatbot.chatbot import LLMChatbot
from LLMChatbot.services.cart_handler import CartHandler

# ─────────────────────────────────────────────
# CLIENT REDIS — pour lire la condition du participant
# ─────────────────────────────────────────────
_redis_client = redis.Redis(host="database", port=6379, decode_responses=True)

# Valeurs par défaut si la condition n'est pas trouvée dans Redis
_DEFAULT_STYLE = "human_like_formal"
_DEFAULT_PRODUIT = "snacks"


def get_condition(user_id: str) -> tuple[str, str]:
    """Reads the participant's condition from Redis.

    Args:
        user_id: The conversation ID used as Redis key.

    Returns:
        Tuple (style, produit) for this participant.
    """
    try:
        condition_data = _redis_client.get(f"condition:{user_id}")
        if condition_data:
            condition = json.loads(condition_data)
            return condition.get("style", _DEFAULT_STYLE), condition.get("produit", _DEFAULT_PRODUIT)
    except Exception as e:
        print(f"Error reading condition from Redis: {e}")
    return _DEFAULT_STYLE, _DEFAULT_PRODUIT


# ─────────────────────────────────────────────
# HELPER — dispatch responses
# ─────────────────────────────────────────────
def return_responses(messages: list[dict], dispatcher: CollectingDispatcher) -> None:
    """Formats and dispatches responses to the user."""
    for message in messages:
        if "text" in message:
            try:
                dispatcher.utter_message(text=message["text"])
            except Exception as e:
                print(f"Dispatcher error: {e}")
        if "buttons" in message and message["buttons"]:
            try:
                dispatcher.utter_message(buttons=message["buttons"])
            except Exception as e:
                print(f"Dispatcher error: {e}")


# ─────────────────────────────────────────────
# ACTION — Retour du statut du panier
# ─────────────────────────────────────────────
class CartStatus(Action):
    """Returns the user's cart summary."""

    def name(self) -> Text:
        return "return_cart_status"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        cart = CartHandler.get_cart_summary(tracker.sender_id)
        dispatcher.utter_message(text=cart)
        return [FollowupAction("action_listen")]


# ─────────────────────────────────────────────
# ACTION PRINCIPALE — Traitement LLM
# Lit la condition depuis Redis et appelle LLMChatbot
# ─────────────────────────────────────────────
class LLMProcessing(Action):
    """Processes the user's message using the LLM with the correct style and product."""

    def name(self) -> Text:
        return "llm_processing"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        user_id = tracker.sender_id
        message = tracker.latest_message.get("text")

        # Lecture de la condition depuis Redis
        style, produit = get_condition(user_id)
        print(f"LLMProcessing — user_id: {user_id}, style: {style}, produit: {produit}")

        responses = await LLMChatbot.get_response(
            user_id=user_id,
            style=style,
            produit=produit,
            user_message=message,
        )

        return_responses(responses, dispatcher)

        # Vérification si la commande doit être finalisée
        if CartHandler.get_should_finish_purchase(user_id):
            CartHandler.set_should_finish_purchase(user_id, False)
            return [
                FollowupAction("payment_method_form"),
                ActiveLoop("payment_method_form"),
            ]

        return [FollowupAction("action_listen")]


# ─────────────────────────────────────────────
# ACTION FALLBACK
# ─────────────────────────────────────────────
class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        form = tracker.active_loop.get("name") if tracker.active_loop else None

        if form is not None:
            return [FollowupAction(form), ActiveLoop(form)]

        dispatcher.utter_message(response="utter_default")
        return [FollowupAction("action_listen")]


# ─────────────────────────────────────────────
# VALIDATION PAIEMENT
# ─────────────────────────────────────────────
def normalize_string(string: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", string)
        if unicodedata.category(c) != "Mn"
    ).lower()


def valid_methods() -> List[str]:
    return [normalize_string(x) for x in ["Espèces", "Carte bancaire", "Sans contact"]]


class ValidatePaymentForm(FormValidationAction):
    def name(self) -> str:
        return "validate_payment_method_form"

    def validate_payment_method(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        original_string = slot_value
        slot_value = normalize_string(slot_value)
        if slot_value in valid_methods():
            return {"payment_method": original_string}
        else:
            dispatcher.utter_message(response="utter_ask_payment_method")
            return {"payment_method": None}


# ─────────────────────────────────────────────
# RÉSUMÉ DE COMMANDE
# ─────────────────────────────────────────────
class ActionSummarizeDetails(Action):
    def name(self) -> str:
        return "summarize_details"

    async def run(self, dispatcher, tracker, domain):
        payment_method = tracker.get_slot("payment_method")
        cart = CartHandler.get_cart_summary(tracker.sender_id)

        message = (
            "Veuillez confirmer votre commande :\n"
            f"Mode de paiement : {payment_method}\n"
            f"{cart}"
        )
        dispatcher.utter_message(text=message)
        return []


# ─────────────────────────────────────────────
# CORRECTION DE DÉTAILS
# ─────────────────────────────────────────────
def valid_details() -> List[str]:
    return ["payment_method", "ok", "cart"]


class ValidateConfirmationForm(FormValidationAction):
    def name(self):
        return "validate_confirmation_form"

    def validate_modify_details(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value in valid_details():
            return {"modify_details": slot_value}
        return {"modify_details": None}


class CorrectDetail(Action):
    def name(self) -> Text:
        return "correct_detail"

    async def run(
        self,
        dispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        detail_to_correct = tracker.get_slot("modify_details")

        if detail_to_correct == "ok":
            dispatcher.utter_message(
                text="Parfait ! Votre commande est confirmée. Merci !"
            )
            return []
        elif detail_to_correct == "cart":
            dispatcher.utter_message(
                text="D'accord, continuez à constituer votre panier."
            )
            return [SlotSet("modify_details", None), FollowupAction("action_listen")]
        elif detail_to_correct is not None:
            return [
                SlotSet("modify_details", None),
                SlotSet(detail_to_correct, None),
                FollowupAction(name=f"{detail_to_correct}_form"),
                ActiveLoop(f"{detail_to_correct}_form"),
            ]

        dispatcher.utter_message(
            text="Désolé, je n'ai pas compris. Pouvez-vous reformuler ?"
        )
        return []
