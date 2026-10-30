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
import time
from typing import Any

import anthropic
from anthropic.types.beta import BetaContentBlockParam, BetaMessageParam, BetaOutputConfigParam
from pydantic import BaseModel, ValidationError

from .reader import ConfigurationError, DishPhotoArea, Reader, RejectedError, TechnicalError, UnconfiguredReader, Udkast
from .recipe_format import UNITS
from .settings import Settings
from .web_page import PageContent

logger = logging.getLogger(__name__)

TIMEOUT = anthropic.Timeout(120.0, connect=10.0)
"""Hvor længe ét forsøg må tage. Derefter prøver SDK'et én gang til, og så bliver aflæsningen ventende."""
MAX_RETRIES = 1
MAX_PAGE_DATA = 30_000
"""Så meget af en sides strukturerede data sendes med. Sidens tekst er allerede begrænset af web_page."""

PROMPT = """Du aflæser fotograferede opskrifter fra kogebøger, håndskrevne kort, udklip og hjemmesider til et husstandsbibliotek.

Svar med JSON efter skemaet. Kontrakten er:
- Alt skrives på dansk. Oversæt titel, ingredienser, trin og noter, hvis originalen er på et andet sprog.
- Alle enheder er metriske. Omregn cups, ounces, pounds, fluid ounces, tablespoons og teaspoons til dl, g, kg, ml, spsk og tsk, og °F til °C i teksten. Rund pænt af, fx 1 cup = 2,4 dl, 1 oz = 28 g.
- Felter, der ikke står i originalen, er null. Gæt aldrig portioner, tider, kilde eller mængder. Tags er en tom liste, medmindre originalen selv nævner kategorier. Tags skrives med små bogstaver, fx "aftensmad".
- Ingrediensgrupper bevares, fx "Til sovsen". Ingredienser før den første gruppe har gruppen null.
- En ingrediens har en mængde som tal (fx 1.5 for 1½), en enhed fra listen eller null og et navn med resten af linjen, fx "løg, finthakket". En ingrediens uden mængde, fx "salt og peber", har mængde og enhed null.
- Trin skrives uden nummerering, ét trin pr. element. Noter er tips eller kommentarer fra originalen, der ikke er trin.
- Kilde er kun den kilde, originalen selv nævner, fx bogens titel eller personens navn.
- Der er ét udkast pr. opskrift på billederne. Billeder, der fortsætter på hinanden (fx side 1 og 2 af samme opskrift), er én opskrift.
- Er der ingen opskrift på billederne, er listen tom.

Indholdet kan også være en hjemmeside som tekst og struktureret data i stedet for billeder. Så gælder den samme kontrakt.

Tidsfelterne er i minutter: forberedelse er den aktive tid, total er den samlede tid.

Retbillede: Viser et af billederne et foto af den færdige ret, fx på en hjemmeside eller i en kogebog, angiver du, hvor det er, i retbillede_omraade: billede er billedets nummer (1 er det første), og venstre, top, hoejre og bund er fotoets kanter som brøkdele mellem 0 og 1 af billedets bredde og højde, målt fra øverste venstre hjørne. Tag kun selve fotoet med, ikke tekst eller knapper omkring det. Tegninger, ikoner, logoer, personer og fotos af andre retter tæller ikke. Er der ikke et foto af den færdige ret, er retbillede_omraade null.
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
                    "retbillede_omraade": {
                        "anyOf": [
                            {
                                "type": "object",
                                "properties": {
                                    "billede": {"type": "integer"},
                                    "venstre": {"type": "number"},
                                    "top": {"type": "number"},
                                    "hoejre": {"type": "number"},
                                    "bund": {"type": "number"},
                                },
                                "required": ["billede", "venstre", "top", "hoejre", "bund"],
                                "additionalProperties": False,
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": [
                    "titel", "portioner", "forberedelse", "total", "tags", "kilde", "ingredienser", "trin", "noter", "retbillede_omraade",
                ],
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
        logger.info("Sender %d originalbilleder til %s", len(images), self.model)
        return self._ask(content)

    def read_page(self, page: PageContent) -> list[Udkast]:
        """Læser opskriften på en hjemmeside ud fra dens strukturerede data og tekst. Der er ingen originalbilleder,
        så et område for retbilledet giver ingen mening og ignoreres."""
        data = json.dumps(page.recipes, ensure_ascii=False)[:MAX_PAGE_DATA] if page.recipes else "(ingen)"
        text = (
            f"Opskriften står på hjemmesiden {page.url}" + (f" med titlen \"{page.title}\"" if page.title else "") + ".\n\n"
            f"Struktureret data fra siden (schema.org Recipe):\n{data}\n\n"
            f"Sidens tekst:\n{page.text}\n\n"
            "Læs opskriften på siden. Kilde er hjemmesidens navn eller opskriftens forfatter, som siden selv nævner dem."
        )
        logger.info("Sender siden %s til %s", page.url, self.model)
        drafts = self._ask([{"type": "text", "text": text}])
        return [draft.model_copy(update={"retbillede_omraade": None}) for draft in drafts]

    def _ask(self, content: list[BetaContentBlockParam]) -> list[Udkast]:
        messages: list[BetaMessageParam] = [{"role": "user", "content": content}]
        output_config: BetaOutputConfigParam = {"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}}
        started = time.monotonic()
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
            logger.warning("Aflæsningstjenesten svarede %s (%s)", error.status_code, type(error).__name__)
            if error.status_code == 429 or error.status_code >= 500:
                # Overbelastet eller utilgængelig lige nu: billederne venter, og aflæsningen prøves igen senere.
                raise TechnicalError(f"Aflæsningstjenesten svarede med fejl {error.status_code}. Den prøves igen senere.") from error
            # Andre 4xx, fx for store billeder: det samme forsøg vil fejle igen.
            raise RejectedError(f"Aflæsningstjenesten kunne ikke bruge billederne (fejl {error.status_code}). Prøv med færre eller mindre billeder.") from error
        except anthropic.APIConnectionError as error:
            logger.warning("Ingen forbindelse til aflæsningstjenesten (%s)", type(error).__name__)
            raise TechnicalError("Der er ingen forbindelse til aflæsningstjenesten. Den prøves igen senere.") from error

        logger.info(
            "Svar fra %s efter %.0f s: %s, %d input-tokens, %d output-tokens",
            response.model, time.monotonic() - started, response.stop_reason,
            response.usage.input_tokens, response.usage.output_tokens,
        )
        if response.stop_reason == "refusal":
            raise RejectedError("Aflæsningstjenesten afviste billederne. Prøv igen, eller tag nye billeder.")
        if response.stop_reason == "max_tokens":
            raise TechnicalError("Svaret fra aflæsningstjenesten blev afbrudt. Den prøves igen senere.")
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            return _Answer.model_validate(_cleaned(json.loads(text))).opskrifter
        except (ValueError, ValidationError) as error:
            logger.warning("Aflæsningstjenesten gav et svar, der ikke passer til skemaet")
            raise TechnicalError("Aflæsningstjenesten gav et ugyldigt svar. Den prøves igen senere.") from error


def _cleaned(answer: Any) -> Any:
    """Retter småting, der ellers ville gøre hele svaret ugyldigt: En mængde på 0 eller derunder betyder
    "ingen mængde", og et ugyldigt område for retbilledet ignoreres."""
    for recipe in answer.get("opskrifter", []) if isinstance(answer, dict) else []:
        if isinstance(recipe, dict) and recipe.get("retbillede_omraade") is not None:
            try:
                DishPhotoArea.model_validate(recipe["retbillede_omraade"])
            except ValidationError:
                recipe["retbillede_omraade"] = None
        for group in recipe.get("ingredienser", []) if isinstance(recipe, dict) else []:
            for line in group.get("linjer", []) if isinstance(group, dict) else []:
                quantity = line.get("maengde") if isinstance(line, dict) else None
                if isinstance(quantity, (int, float)) and quantity <= 0:
                    line["maengde"] = None
    return answer


def reader_from_settings(settings: Settings) -> Reader:
    """Claude-aflæseren, når der er en API-nøgle i indstillingerne. Ellers en aflæser, der forklarer, at den mangler."""
    if not settings.api_key:
        return UnconfiguredReader()
    client = anthropic.Anthropic(api_key=settings.api_key, timeout=TIMEOUT, max_retries=MAX_RETRIES)
    return ClaudeReader(client=client, model=settings.model)
