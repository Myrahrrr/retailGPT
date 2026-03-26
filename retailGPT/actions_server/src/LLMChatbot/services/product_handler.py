import json
from pathlib import Path
from typing import List

import aiohttp
from ..prompts import product_search_prompt
from ..schemas import Product
from .database import Database
from .llm_handler import LLMHandler

# Chemin de base des datasets
_DATASETS_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "datasets"
)

_PRODUCT_NOT_FOUND_MESSAGE = (
    "Désolé, aucun produit dans le catalogue ne correspond à votre demande."
)


class ProductHandler:
    """Handles the product recommendation based on the user's demand.
    Modified to support two catalogs: snacks and medicaments.
    """

    _recommendation_max_size: int = 5

    @staticmethod
    def _get_catalog_path(produit: str) -> Path:
        """Returns the correct catalog path based on the product type.

        Args:
            produit: Product type — 'snacks', 'epicerie' or 'medicaments'

        Returns:
            Path to the corresponding JSON catalog.
        """
        if produit == "medicaments":
            return _DATASETS_PATH / "medicaments_products.json"
        if produit in ("snacks", "epicerie"):
            return _DATASETS_PATH / "epicerie_products.json"
        return _DATASETS_PATH / "epicerie_products.json"

    @staticmethod
    def _get_product_catalog(produit: str) -> str:
        """Gets the product catalog for the given product type.

        Args:
            produit: Product type — 'snacks' or 'medicaments'

        Returns:
            String representation of the product catalog.
        """
        catalog_path = ProductHandler._get_catalog_path(produit)
        catalog_string = ""

        try:
            with open(catalog_path, "r", encoding="utf-8") as file:
                dataset = json.load(file)
                products = dataset["products"]

                for product in products:
                    name = product["product_name"]
                    unit_price = round(product["full_price"], 2)
                    line = f"Nom: {name} - Prix: {unit_price}€"
                    # Attributs médicaments
                    if "active_ingredient" in product:
                        line += f" - Principe actif: {product['active_ingredient']}"
                    if "mechanism" in product:
                        line += f" - Mécanisme: {product['mechanism']}"
                    if "indication" in product:
                        line += f" - Indication: {product['indication']}"
                    if "dosage" in product:
                        line += f" - Posologie: {product['dosage']}"
                    if "frequence" in product:
                        line += f" - Fréquence: {product['frequence']}"
                    if "duree_max" in product:
                        line += f" - Durée max: {product['duree_max']}"
                    if "dose_max_jour" in product:
                        line += f" - Dose max/jour: {product['dose_max_jour']}"
                    if "aspirine_compatible" in product:
                        compat = "Oui" if product["aspirine_compatible"] else "NON - CONTRE-INDIQUÉ"
                        line += f" - Compatible Aspirine: {compat}"
                    if "interactions" in product:
                        line += f" - Interactions: {product['interactions']}"
                    if "niveau_risque" in product:
                        line += f" - Niveau risque: {product['niveau_risque']}"
                    # Attributs épicerie
                    if "sous_categorie" in product:
                        line += f" - Sous-catégorie: {product['sous_categorie']}"
                    if "portions_estimees" in product:
                        line += f" - Portions estimées: {product['portions_estimees']}"
                    if "usage" in product:
                        line += f" - Usage: {product['usage']}"
                    if "description" in product:
                        line += f" - Description: {product['description']}"
                    if "type" in product:
                        line += f" - Type: {product['type']}"
                    catalog_string += line + "\n"
        except FileNotFoundError:
            print(f"Catalog file not found: {catalog_path}")

        return catalog_string

    @staticmethod
    async def _search_engine(
        product_query: str,
        produit: str,
        session: aiohttp.ClientSession | None = None,
    ) -> list[Product]:
        """Searches for product recommendations based on user demand.

        Args:
            product_query: Description of what the user wants.
            produit: Product type — 'snacks' or 'medicaments'
            session: aiohttp ClientSession for concurrent searching.

        Returns:
            List of matching products from the catalog.
        """
        catalog = ProductHandler._get_product_catalog(produit)

        system_prompt = product_search_prompt.format(
            product_catalog=catalog,
            search=product_query,
        )

        llm_response = await LLMHandler.call_completions_api(
            [{"role": "system", "content": system_prompt}],
            session=session,
            response_format={"type": "json_object"},
        )

        llm_response = json.loads(llm_response["content"])

        # Load full product data from catalog
        catalog_path = ProductHandler._get_catalog_path(produit)
        with open(catalog_path, "r", encoding="utf-8") as file:
            full_dataset = json.load(file)

        available_products = full_dataset["products"]
        recommended_names = [
            p.lower() for p in llm_response.get("recommended_products", [])
        ]

        recommendation = []
        for product in available_products:
            if product["product_name"].lower() in recommended_names:
                recommendation.append(product)

        return recommendation[: ProductHandler._recommendation_max_size]

    @staticmethod
    def _format_product_recommendation(raw_recommendation: list[Product]) -> str:
        """Formats the product recommendation into a readable string."""
        formatted = ""
        for product in raw_recommendation:
            price = round(product["full_price"], 2)
            formatted += f"{product['product_name']} - {price}€ par unité\n"
        return formatted

    @staticmethod
    def _add_recommended_product_data(user_id: str, product_data: dict) -> None:
        """Adds a recommended product to the user's Redis data."""
        user_data = Database.get_data(user_id)
        if "recommended_products" in user_data:
            user_data["recommended_products"].append(product_data)
        else:
            user_data["recommended_products"] = [product_data]
        Database.set_data(user_id, user_data)

    @staticmethod
    def _get_recommendations_data(user_id: str) -> list[Product]:
        """Gets all recommended products for a user from Redis."""
        user_data = Database.get_data(user_id)
        return user_data.get("recommended_products", [])

    @staticmethod
    def _get_product_data(user_id: str, product_name: str) -> dict | None:
        """Gets product data by name from user recommendations.
        Uses partial matching to handle abbreviated or approximate names from the LLM.
        """
        name_user = product_name.lower().strip()
        for product in ProductHandler._get_recommendations_data(user_id):
            name_db = product["product_name"].lower().strip()
            if name_user == name_db:
                return product
            if name_user in name_db or name_db in name_user:
                return product
        return None

    @staticmethod
    def product_was_recommended(user_id: str, product_name: str) -> bool:
        """Checks if a product was already recommended to the user."""
        return ProductHandler._get_product_data(user_id, product_name) is not None

    @staticmethod
    def get_product_unit_price(user_id: str, product_name: str) -> float | None:
        """Gets the unit price of a recommended product."""
        product_data = ProductHandler._get_product_data(user_id, product_name)
        if product_data:
            return round(product_data["full_price"], 2)
        return None

    @staticmethod
    def get_product_unit_volume(user_id: str, product_name: str) -> float | None:
        """Gets the unit volume in liters of a recommended product."""
        product_data = ProductHandler._get_product_data(user_id, product_name)
        if product_data:
            return round(100 * product_data["product_volume_in_hectoliters"], 3)
        return None

    @staticmethod
    async def get_product_recommendation(
        user_id: str,
        product_query: str,
        produit: str,
        session: aiohttp.ClientSession | None = None,
    ) -> str:
        """Searches for a product recommendation based on the user's demand.

        Args:
            user_id: The user's ID.
            product_query: Description of the desired product.
            produit: Product type — 'snacks' or 'medicaments'
            session: aiohttp ClientSession for concurrent searching.

        Returns:
            Formatted product recommendation string.
        """
        search_output = await ProductHandler._search_engine(
            product_query, produit, session
        )

        if not search_output:
            return _PRODUCT_NOT_FOUND_MESSAGE

        for product in search_output:
            ProductHandler._add_recommended_product_data(user_id, product)

        formatted = ProductHandler._format_product_recommendation(search_output)
        print("Recommandation finale:", formatted)
        return formatted
