"""Test doubles: a fake OpenAI-compatible client for Meta's API, and drawings to upload."""

import base64
import io
import json
import random
import re
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.avatar.catalog import load_catalog
from app.avatar.spec import palette
from app.providers.meta import MetaLLMProvider
from app.providers.muse_image import MuseImageProvider
from tests.conftest import app_state

TEXT_MODEL = "muse-test"
VISION_MODEL = "muse-vision-test"
IMAGE_MODEL = "muse-image-test"

Reply = dict[str, Any] | str | Exception | Callable[[dict[str, Any]], Any]


def timeout_error() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=httpx2.Request("POST", "http://meta.invalid/v1"))


def server_error() -> openai.InternalServerError:
    request = httpx2.Request("POST", "http://meta.invalid/v1")
    return openai.InternalServerError(
        "Internal error", response=httpx2.Response(500, request=request), body=None
    )


class FakeMeta:
    """Stands in for openai.OpenAI: `client.chat.completions.create(**kwargs)`.

    Replies are set per JSON schema name ("safety_verdicts", "avatar_suggestion", ...): a dict is
    sent back as JSON, an exception is raised, a callable gets the request. A list is used up one
    item per call (the last item repeats). The safety classifier says "safe" unless told otherwise.
    """

    def __init__(self) -> None:
        self.replies: dict[str, Reply | list[Reply]] = {}
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def calls_for(self, schema_name: str) -> list[dict[str, Any]]:
        return [c for c in self.calls if schema_of(c)["name"] == schema_name]

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        name = schema_of(kwargs)["name"]
        reply = self.replies.get(name, DEFAULTS.get(name))
        if isinstance(reply, list):
            reply = reply.pop(0) if len(reply) > 1 else reply[0]
        if reply is None:
            raise AssertionError(f"FakeMeta has no reply for {name}")
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            reply = reply(kwargs)
        content = reply if isinstance(reply, str) else json.dumps(reply)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        message = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def schema_of(call: dict[str, Any]) -> dict[str, Any]:
    schema: dict[str, Any] = call["response_format"]["json_schema"]
    return schema


def user_text(call: dict[str, Any]) -> str:
    content = call["messages"][1]["content"]
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content)
    return str(content)


def all_safe(call: dict[str, Any]) -> dict[str, Any]:
    count = len(re.findall(r"^\d+\. ", user_text(call), re.MULTILINE))
    return {"verdicts": [{"safe": True, "categories": []} for _ in range(count)]}


SAFE_PICTURE = {
    "safe_for_kids": True,
    "shows_real_person": False,
    "has_text_or_logos": False,
    "is_scary": False,
}
# The safety checks say "safe" unless a test says otherwise.
DEFAULTS: dict[str, Reply] = {"safety_verdicts": all_safe, "image_safety": SAFE_PICTURE}


def picture(**flags: bool) -> dict[str, bool]:
    """An image-check reply: safe, except the flags given."""
    return SAFE_PICTURE | flags


def scene_png(
    size: tuple[int, int] = (1024, 768), colour: tuple[int, int, int] = (120, 200, 255)
) -> bytes:
    """A full scene (no magenta), as an image model would paint a place."""
    image = Image.new("RGB", size, colour)
    ImageDraw.Draw(image).ellipse(
        (size[0] // 4, size[1] // 4, size[0] // 2, size[1] // 2), fill="yellow"
    )
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


ImageReply = bytes | Exception


class FakeImages:
    """Stands in for openai.OpenAI for Muse Image: `client.images.generate(**kwargs)`, and
    `client.post("/images/edits", body=..., files=...)` for edits. Each call uses the next reply
    (the last one repeats): bytes come back as b64_json, an exception is raised. Edits record the
    multipart field names and each reference's bytes as read at call time (a used-up file object
    would read as b"")."""

    def __init__(self, *replies: ImageReply) -> None:
        self.replies: list[ImageReply] = list(replies) or [scene_png()]
        self.calls: list[dict[str, Any]] = []
        self.images = SimpleNamespace(generate=self._generate)

    def _generate(self, **kwargs: Any) -> Any:
        return self._reply({"kind": "generate", **kwargs})

    def post(self, path: str, *, body: dict[str, Any], files: list[Any], **kwargs: Any) -> Any:
        assert path == "/images/edits"
        call = {"kind": "edit", **body, "options": kwargs.get("options", {})}
        call["fields"] = [field for field, _ in files]
        call["filenames"] = [file[0] for _, file in files]
        call["references"] = [file[1].read() for _, file in files]
        return self._reply(call)

    def _reply(self, call: dict[str, Any]) -> Any:
        self.calls.append(call)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        item = SimpleNamespace(b64_json=base64.b64encode(reply).decode("ascii"), url=None)
        return SimpleNamespace(data=[item])


def muse(fake: FakeImages) -> MuseImageProvider:
    return MuseImageProvider(
        api_key="test-key", model=IMAGE_MODEL, base_url="http://meta.invalid/v1", client=fake
    )


def use_muse(client: TestClient, fake: FakeImages | None = None) -> FakeImages:
    """Switches the running app to IMAGE_PROVIDER=muse, talking to a fake client."""
    fake = fake or FakeImages()
    app_state(client).image_provider = muse(fake)
    return fake


def flag(match: str, *categories: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """A classifier reply that marks unsafe each numbered text containing `match` (and every other
    text safe), however many texts the call checks."""

    def reply(call: dict[str, Any]) -> dict[str, Any]:
        texts = re.findall(r"^\d+\. (.*)$", user_text(call), re.MULTILINE)
        return {
            "verdicts": [
                {"safe": False, "categories": list(categories) or ["other"]}
                if match in text
                else {"safe": True, "categories": []}
                for text in texts
            ]
        }

    return reply


def use_meta(client: TestClient, fake: FakeMeta | None = None) -> FakeMeta:
    """Switches the running app to LLM_PROVIDER=meta, talking to a fake client."""
    fake = fake or FakeMeta()
    app_state(client).llm = MetaLLMProvider(
        api_key="test-key",
        model=TEXT_MODEL,
        vision_model=VISION_MODEL,
        base_url="http://meta.invalid/v1",
        client=fake,
    )
    return fake


def colour_id(slot: str, hex_color: str, body_type: str = "kid") -> str:
    return next(e["id"] for e in palette(slot, body_type) if e["hex"] == hex_color)


def suggestion(spec: dict[str, Any], **changes: Any) -> dict[str, Any]:
    """A well-formed avatar_suggestion reply: the spec as ids (every category, as the strict
    schema requires), with `changes` applied on top."""
    cat = load_catalog()
    body_type = changes.pop("body_type", spec["body_type"])
    parts = {c: spec["parts"].get(c, "none") for c in cat["categories"]}
    parts |= changes.pop("parts", {})
    colors = {s: colour_id(s, spec["colors"][s], spec["body_type"]) for s in cat["color_slots"]}
    colors |= changes.pop("colors", {})
    reply = {
        "body_type": body_type,
        "parts": parts,
        "colors": colors,
        "extras": list(spec["extras"]),
        "name_ideas": ["Nova", "Pip", "Zuri"],
        "traits": list(spec["personality"]["traits"]),
        "catchphrase": "Up, up and away!",
        "reply": "Ta-da! Here's your character.",
        "unmatched": [],
    }
    return reply | changes


def data_url(image: Image.Image, fmt: str = "PNG", **save: Any) -> str:
    out = io.BytesIO()
    image.save(out, fmt, **save)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(out.getvalue()).decode()


def drawing(size: int = 400) -> Image.Image:
    """A kid's drawing: a few flat colours with black lines on white paper."""
    image = Image.new("RGB", (size, size), "white")
    pen = ImageDraw.Draw(image)
    pen.ellipse((120, 30, 280, 190), fill="#F2C29B", outline="black", width=6)
    pen.rectangle((110, 190, 290, 330), fill="#E53935", outline="black", width=6)
    pen.rectangle((130, 330, 270, 390), fill="#1F5BD1", outline="black", width=6)
    return image


def photo(size: int = 400) -> Image.Image:
    """Photo-like: smooth gradients plus noise, so the colours spread over many bins."""
    rng = random.Random(7)
    image = Image.new("RGB", (size, size))
    image.putdata(
        [
            (
                min(255, x * 255 // size + rng.randint(-40, 40)) % 256,
                min(255, y * 255 // size + rng.randint(-40, 40)) % 256,
                rng.randint(0, 255),
            )
            for y in range(size)
            for x in range(size)
        ]
    )
    return image
