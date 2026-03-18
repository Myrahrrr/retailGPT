import asyncio
import json
import os
import sys

import aiohttp
from colorama import Fore
from openai.types.chat import ChatCompletionMessageToolCall

current_directory = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_directory)

from .prompts import chatbot_prompt_tools, get_system_prompt
from .schemas import ChatbotResponse
from .services.cart_handler import CartHandler
from .services.llm_handler import LLMHandler
from .services.memory_handler import MemoryHandler
from .services.product_handler import ProductHandler
from .services.guardrails.guardrails import Guardrails


class LLMChatbot:
    """Handles the chatbot logic for the LLM system.
    Modified to support dynamic style and product type.
    """

    _finish_purchase_function_message: str = (
        "Le panier a été sauvegardé. Informe l'utilisateur que la commande est finalisée."
    )
    _guardrails_warning: str = (
        "Votre message ne respecte pas les règles d'utilisation. Merci de reformuler."
    )
    _early_operation_warning: str = (
        "Opération non effectuée. Veuillez d'abord confirmer le produit souhaité parmi les résultats disponibles :\n"
    )

    @staticmethod
    async def _search_product_recommendation(
        user_id: str,
        product_query: str,
        produit: str,
        session: aiohttp.ClientSession | None = None,
    ) -> str:
        """Searches for a product recommendation.

        Args:
            user_id: The user's ID.
            product_query: Description of the desired product.
            produit: Product type — 'snacks' or 'medicaments'
            session: aiohttp session for concurrent searching.
        """
        recommendation = await ProductHandler.get_product_recommendation(
            user_id, product_query, produit, session
        )
        return recommendation

    @staticmethod
    def _edit_cart(user_id: str, operation: str, product: str, amount: str) -> str:
        """Edits the user's cart."""
        return CartHandler.process_cart_operation(user_id, operation, product, amount)

    @staticmethod
    def _tool_call_sorting(tool_call: ChatCompletionMessageToolCall) -> int:
        """Sorts tool calls prioritizing removal operations."""
        function_arguments = json.loads(tool_call.function.arguments)
        if (
            tool_call.function.name == "edit_cart"
            and function_arguments["operation"] == "remove"
        ):
            return 0
        return 1

    @staticmethod
    async def _process_sequential_tool_calls(
        user_id: str,
        produit: str,
        tool_calls: list[ChatCompletionMessageToolCall]
    ) -> list[dict]:
        """Processes tool calls in sequence."""
        output_messages = []
        tool_calls.sort(key=LLMChatbot._tool_call_sorting)

        for call in tool_calls:
            call_id = call.id
            function_arguments = json.loads(call.function.arguments)

            if call.function.name == "edit_cart":
                operation = function_arguments["operation"]
                product = function_arguments["product"]
                amount = function_arguments["amount"]

                if (
                    operation == "add"
                    and not ProductHandler.product_was_recommended(user_id, product)
                ):
                    print("Trying to add a product that was not recommended:", product)
                    function_output = LLMChatbot._early_operation_warning
                    function_output += await LLMChatbot._search_product_recommendation(
                        user_id, product, produit
                    )
                else:
                    function_output = LLMChatbot._edit_cart(
                        user_id, operation, product, amount
                    )
                    CartHandler.set_should_send_cart_summary(user_id, True)

            else:
                # finalize_order
                function_output = LLMChatbot._finish_purchase_function_message
                CartHandler.set_should_finish_purchase(user_id, True)

            output_messages.append(
                {"role": "tool", "content": function_output, "tool_call_id": call_id}
            )

        return output_messages

    @staticmethod
    async def _process_tool_calls(
        user_id: str,
        produit: str,
        tool_calls: list[ChatCompletionMessageToolCall]
    ) -> list[dict]:
        """Processes tool calls, dispatching to the appropriate handlers."""
        search_tool_calls = []
        sequential_tool_calls = []
        tasks = []
        output_messages = []
        call_ids = []

        for tool_call in tool_calls:
            if tool_call.function.name == "search_product_recommendation":
                search_tool_calls.append(tool_call)
            else:
                sequential_tool_calls.append(tool_call)

        async with aiohttp.ClientSession() as session:
            if search_tool_calls:
                for call in search_tool_calls:
                    call_id = call.id
                    function_arguments = json.loads(call.function.arguments)
                    task = asyncio.create_task(
                        LLMChatbot._search_product_recommendation(
                            user_id,
                            function_arguments["product_query"],
                            produit,
                            session,
                        )
                    )
                    tasks.append(task)
                    call_ids.append(call_id)

                results = await asyncio.gather(*tasks)
                for result, call_id in zip(results, call_ids):
                    output_messages.append(
                        {"role": "tool", "content": result, "tool_call_id": call_id}
                    )

        if sequential_tool_calls:
            sequential_output = await LLMChatbot._process_sequential_tool_calls(
                user_id, produit, sequential_tool_calls
            )
            output_messages.extend(sequential_output)

        return output_messages

    @staticmethod
    def _build_tool_call_message(tool_calls: list) -> dict:
        """Builds the tool call message for the conversation history."""
        tool_call_message = {"role": "assistant", "tool_calls": []}
        for tool_call in tool_calls:
            tool_call_message["tool_calls"].append(
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": dict(tool_call.function),
                }
            )
        return tool_call_message

    @staticmethod
    def _response_post_processing(
        user_id: str, final_answer: str
    ) -> list[ChatbotResponse]:
        """Processes the final answer before sending to the user."""
        final_answer_dict = {"role": "assistant", "content": final_answer}
        MemoryHandler.add_message_to_history(user_id, final_answer_dict)

        print(Fore.BLUE + "Final answer: ", final_answer)

        return_responses = []
        buttons = []

        if CartHandler.get_should_send_cart_summary(user_id):
            cart_summary = CartHandler.get_cart_summary(user_id)
            return_responses.append({"text": cart_summary, "buttons": None})
            buttons.append({
                "title": "Finaliser la commande",
                "payload": "/finish_purchase",
            })
            CartHandler.set_should_send_cart_summary(user_id, False)

        return_responses.append({"text": final_answer, "buttons": buttons})
        return return_responses

    @staticmethod
    def _response_pre_processing(
        user_id: str, user_message: str, style: str, produit: str
    ) -> list[dict]:
        """Builds the messages array for the completions API.
        Uses dynamic system prompt based on style and product type.
        """
        # Prompt dynamique selon la condition du participant
        system_prompt = get_system_prompt(style, produit)
        system_message_dict = {"role": "system", "content": system_prompt}

        user_message_dict = {"role": "user", "content": user_message}
        MemoryHandler.add_message_to_history(user_id, user_message_dict)
        history = MemoryHandler.get_history(user_id)
        messages = [system_message_dict] + history
        return messages

    @staticmethod
    async def get_response(
        user_id: str,
        style: str,
        produit: str,
        user_message: str,
        debug_mode: bool = False,
    ) -> list[ChatbotResponse] | dict:
        """Gets the chatbot's response to the user's message.

        Args:
            user_id: The user's ID.
            style: Conversational style (machine_like, human_like_formal, human_like_friendly)
            produit: Product type (snacks, medicaments)
            user_message: The user's message.
            debug_mode: Returns extra processing data if True.

        Returns:
            List of chatbot responses with text and optional buttons.
        """
        print(Fore.BLUE + "User message:", user_message)
        print(Fore.GREEN + f"Condition: style={style}, produit={produit}")

        # Guardrails — input check
        if not await Guardrails.run_input_guardrails(user_message):
            return [{"text": LLMChatbot._guardrails_warning, "buttons": None}]

        messages = LLMChatbot._response_pre_processing(
            user_id, user_message, style, produit
        )
        tools = chatbot_prompt_tools
        completion_response = await LLMHandler.call_completions_api(messages, tools)
        tool_calls = completion_response.get("tool_calls", None)

        if tool_calls is not None:
            tool_calls = [
                ChatCompletionMessageToolCall(**tc) for tc in tool_calls
            ]

            print(Fore.GREEN + "Tool calls:", str(completion_response))

            tools_output_messages = await LLMChatbot._process_tool_calls(
                user_id, produit, tool_calls
            )

            tool_call_message = LLMChatbot._build_tool_call_message(tool_calls)
            history = MemoryHandler.get_history(user_id)
            history.extend([tool_call_message] + tools_output_messages)

            # Final response without tools
            system_prompt = get_system_prompt(style, produit)
            messages = [{"role": "system", "content": system_prompt}] + history
            completion_response = await LLMHandler.call_completions_api(messages)

        final_answer = completion_response["content"]

        # Guardrails — output check
        if not Guardrails.run_output_guardrails(user_message):
            return [{"text": LLMChatbot._guardrails_warning, "buttons": None}]

        return_responses = LLMChatbot._response_post_processing(user_id, final_answer)

        if debug_mode:
            return {"tool_calls": tool_calls, "responses": return_responses}

        return return_responses
