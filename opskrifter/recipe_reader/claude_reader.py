"""Aflæser-adapter mod Claude API'et: originalbilleder ind, udkast ud.

Svaret begrænses med structured outputs til et JSON-skema og valideres derefter
mod udkastets skema. Et ugyldigt svar giver en teknisk fejl og aldrig et halvt
udkast. Netværksfejl, timeout, 5xx og rate limit giver en teknisk fejl, så
aflæsningen bliver en ventende aflæsning. En ugyldig API-nøgle eller model giver
en konfigurationsfejl, som vises i UI'et.
"""

import base64
import json
import logging
from typing import Any

import anthropic
from anthropic.types.beta import BetaContentBlockParam, BetaMessageParam, BetaOutputConfigParam
from pydantic import BaseModel, ValidationError

from .reader import ConfigurationError, Reader, TechnicalError, UnconfiguredReader, Udkast
from .recipe_format import UNITS
from .settings import Settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 180.0
"""Hvor længe én aflæsning må tage. SDK'et prøver selv igen ved netværksfejl, 429 og 5xx."""

PROMPT = """Du aflæser fotograferede opskrifter fra kogebøger, håndskrevne kort, udklip og hjemmesider til et husstandsbibliotek.

Svar med JSON efter skemaet. Kontrakten er:
- Alt skrives på dansk. Oversæt titel, ingredienser, trin og noter, hvis originalen er på et andet sprog.
- Alle enheder er metriske. Omregn cups, ounces, pounds, fluid ounces, tablespoons og teaspoons til dl, g, kg, ml, spsk og tsk, og °F til °C i teksten. Rund pænt af, fx 1 cup = 2,4 dl, 1 oz = 28 g.
- Felter, der ikke står i originalen, er null. Gæt aldrig portioner, tider, kilde eller mængder. Tags er en tom liste, medmindre originalen selv nævner kategorier.
- Ingrediensgrupper bevares, fx "Til sovsen". Ingredienser før den første gruppe har gruppen null.
- En ingrediens har en mængde som tal (fx 1.5 for 1½), en enhed fra listen eller null og et navn med resten af linjen, fx "løg, finthakket". En ingrediens uden mængde, fx "salt og peber", har mængde og enhed null.
- Trin skrives uden nummerering, ét trin pr. element. Noter er tips eller kommentarer fra originalen, der ikke er trin.
- Kilde er kun den kilde, originalen selv nævner, fx bogens titel eller personens navn.
- Der er ét udkast pr. opskrift på billederne. Billeder, der fortsætter på hinanden (fx side 1 og 2 af samme opskrift), er én opskrift.
- Er der ingen opskrift på billederne, er listen tom.

Tidsfelterne er i minutter: forberedelse er den aktive tid, total er den samlede tid.
"""

_NULLABLE_STRING = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_NULLABLE_INTEGER = {"anyOf": [{"type": "integer"}, {"type": "null"}]}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "opskrifter": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titel": _NULLABLE_STRING,
                    "portioner": _NULLABLE_INTEGER,
                    "forberedelse": _NULLABLE_INTEGER,
                    "total": _NULLABLE_INTEGER,
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "kilde": _NULLABLE_STRING,
                    "ingredienser": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "gruppe": _NULLABLE_STRING,
                                "linjer": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "maengde": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                                            "enhed": {"anyOf": [{"type": "string", "enum": sorted(UNITS)}, {"type": "null"}]},
                                            "navn": {"type": "string"},
                                        },
                                        "required": ["maengde", "enhed", "navn"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["gruppe", "linjer"],
                            "additionalProperties": False,
                        },
                    },
                    "trin": {"type": "array", "items": {"type": "string"}},
                    "noter": _NULLABLE_STRING,
                },
                "required": ["titel", "portioner", "forberedelse", "total", "tags", "kilde", "ingredienser", "trin", "noter"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["opskrifter"],
    "additionalProperties": False,
}


class _Answer(BaseModel):
    opskrifter: list[Udkast]


class ClaudeReader:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self.client = client
        self.model = model

    def __repr__(self) -> str:
        return f"ClaudeReader(model={self.model!r})"

    def read(self, images: list[bytes]) -> list[Udkast]:
        content: list[BetaContentBlockParam] = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(image).decode()}}
            for image in images
        ]
        content.append({"type": "text", "text": f"Aflæs opskrifterne på de {len(images)} billeder."})
        messages: list[BetaMessageParam] = [{"role": "user", "content": content}]
        output_config: BetaOutputConfigParam = {"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}}
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=PROMPT,
                messages=messages,
                output_config=output_config,
                # Afviser sikkerhedsfiltrene en side ved en fejl, prøves samme forespørgsel på en anden model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as error:
            raise ConfigurationError("API-nøglen til aflæsningen er ugyldig. Ret den i add-on'ens indstillinger.") from error
        except anthropic.NotFoundError as error:
            raise ConfigurationError(f"Modellen {self.model!r} findes ikke. Ret den i add-on'ens indstillinger.") from error
        except anthropic.APIStatusError as error:
            # 429, 5xx og afviste forespørgsler: billederne venter, og aflæsningen prøves igen senere.
            logger.warning("Aflæsningstjenesten svarede %s (%s)", error.status_code, type(error).__name__)
            raise TechnicalError(f"Aflæsningstjenesten svarede med fejl {error.status_code}. Den prøves igen senere.") from error
        except anthropic.APIConnectionError as error:
            logger.warning("Ingen forbindelse til aflæsningstjenesten (%s)", type(error).__name__)
            raise TechnicalError("Der er ingen forbindelse til aflæsningstjenesten. Den prøves igen senere.") from error

        if response.stop_reason == "refusal":
            raise TechnicalError("Aflæsningstjenesten afviste billederne. Prøv igen, eller tag nye billeder.")
        if response.stop_reason == "max_tokens":
            raise TechnicalError("Svaret fra aflæsningstjenesten blev afbrudt. Den prøves igen senere.")
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            return _Answer.model_validate(json.loads(text)).opskrifter
        except (ValueError, ValidationError) as error:
            logger.warning("Aflæsningstjenesten gav et svar, der ikke passer til skemaet")
            raise TechnicalError("Aflæsningstjenesten gav et ugyldigt svar. Den prøves igen senere.") from error


def reader_from_settings(settings: Settings) -> Reader:
    """Claude-aflæseren, når der er en API-nøgle i indstillingerne. Ellers en aflæser, der forklarer, at den mangler."""
    if not settings.api_key:
        return UnconfiguredReader()
    client = anthropic.Anthropic(api_key=settings.api_key, timeout=TIMEOUT_SECONDS, max_retries=2)
    return ClaudeReader(client=client, model=settings.model)
