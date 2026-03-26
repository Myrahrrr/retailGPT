import redis
import requests


def get_chatbot_response(message: str, conversation_id: str) -> list:
    """Sends user message to chatbot and returns response."""

    url = "http://rasa:5005/webhooks/rest/webhook"
    body = {"sender": conversation_id, "message": message}
    try:
        response = requests.post(url, json=body, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return [{"text": "L'assistant est momentanément indisponible. Veuillez réessayer dans quelques instants."}]
    except requests.exceptions.Timeout:
        return [{"text": "L'assistant met trop de temps à répondre. Veuillez réessayer."}]
    except Exception as e:
        print(f"Rasa error: {e}")
        return [{"text": "Une erreur inattendue s'est produite. Veuillez réessayer."}]


def reset_chatbot_conversation(conversation_id: str) -> None:
    """Resets chatbot's conversation state."""

    # Reset rasa history:
    try:
        url = f"http://rasa:5005/conversations/{conversation_id}/tracker/events"
        requests.post(url, json={"event": "restart"}, timeout=10)
    except Exception as e:
        print(f"Rasa reset error: {e}")

    # Reset conversation database:
    try:
        redis_client = redis.StrictRedis(host="database", port=6379, db=0)
        redis_client.delete(conversation_id)
        redis_client.delete(f"condition:{conversation_id}")
    except Exception as e:
        print(f"Redis reset error: {e}")
