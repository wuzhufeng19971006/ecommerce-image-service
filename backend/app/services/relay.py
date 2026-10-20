from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings
from .images import ImagePayload, ImageValidationError, decode_output_image

logger = logging.getLogger(__name__)


class RelayError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        upstream_detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.upstream_detail = upstream_detail


@dataclass(frozen=True)
class RelayResult:
    images: list[ImagePayload]
    usage: dict | None = None


class RelayClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.image_api_base.rstrip("/")

    @property
    def configured(self) -> bool:
        return self.settings.image_mock or bool(self.settings.image_api_key.strip())

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.image_api_key.strip()}",
            "Accept": "text/event-stream",
        }

    def _timeout(self) -> httpx.Timeout:
        read = max(30, self.settings.image_timeout_seconds)
        return httpx.Timeout(connect=15.0, read=float(read), write=120.0, pool=15.0)

    async def generate(self, prompt: str, size: str, quality: str) -> RelayResult:
        self._ensure_key()
        payload = {
            "model": self.settings.image_model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": quality,
            "stream": True,
            "response_format": "b64_json",
        }
        return await self._request(f"{self.base_url}/images/generations", payload=payload)

    async def edit(
        self,
        prompt: str,
        images: list[tuple[str, bytes, str]],
        size: str,
        quality: str,
    ) -> RelayResult:
        self._ensure_key()
        if not images:
            raise RelayError("RELAY_BAD_REQUEST", "图生图至少需要一张参考图")
        fields = {
            "model": self.settings.image_model,
            "prompt": prompt,
            "n": "1",
            "size": size,
            "quality": quality,
            "stream": "true",
            "response_format": "b64_json",
        }
        files = [("image", (name, data, mime)) for name, data, mime in images]
        return await self._request(
            f"{self.base_url}/images/edits",
            data=fields,
            files=files,
        )

    def _ensure_key(self) -> None:
        if not self.settings.image_api_key.strip():
            raise RelayError(
                "RELAY_NOT_CONFIGURED",
                "尚未配置中转站接口密钥，请在项目根目录 .env 中填写 IMAGE_API_KEY",
                status_code=503,
            )

    async def _request(
        self,
        url: str,
        *,
        payload: dict | None = None,
        data: dict | None = None,
        files: list | None = None,
    ) -> RelayResult:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout(),
                follow_redirects=False,
            ) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=self._headers(),
                    json=payload if payload is not None else None,
                    data=data if files is not None else None,
                    files=files,
                ) as response:
                    if response.status_code >= 400:
                        raw = await response.aread()
                        detail = _extract_upstream_message(raw)
                        code, message = _map_http_error(response.status_code, detail)
                        logger.warning(
                            "relay http error status=%s code=%s detail=%s",
                            response.status_code,
                            code,
                            detail[:300] if detail else "",
                        )
                        raise RelayError(
                            code,
                            message,
                            status_code=response.status_code,
                            upstream_detail=detail,
                        )

                    content_type = response.headers.get("content-type", "").lower()
                    if "text/event-stream" in content_type:
                        return await self._read_sse(response)
                    raw = await response.aread()
                    if len(raw) > self.settings.max_output_bytes * 2:
                        raise RelayError(
                            "RELAY_BAD_RESPONSE", "上游返回内容过大，请稍后重试"
                        )
                    return self._parse_json_payload(raw)
        except RelayError:
            raise
        except httpx.TimeoutException as exc:
            raise RelayError("RELAY_TIMEOUT", "生成超时，请稍后重试") from exc
        except httpx.RequestError as exc:
            logger.warning("relay network error: %s", exc.__class__.__name__)
            raise RelayError("RELAY_NETWORK", "无法连接中转站，请检查网络或接口地址") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RelayError("RELAY_BAD_RESPONSE", "中转站返回了无法解析的数据") from exc

    async def _read_sse(self, response: httpx.Response) -> RelayResult:
        data_lines: list[str] = []
        image_values: list[str] = []
        usage: dict | None = None
        total_chars = 0

        async def consume() -> bool:
            nonlocal usage
            if not data_lines:
                return False
            joined = "\n".join(data_lines).strip()
            data_lines.clear()
            if not joined:
                return False
            if joined == "[DONE]":
                return True
            try:
                event = json.loads(joined)
            except json.JSONDecodeError as exc:
                raise RelayError("RELAY_BAD_RESPONSE", "中转站返回的流式数据格式异常") from exc
            _raise_event_error(event)
            found = _collect_image_values(event)
            image_values.extend(found)
            found_usage = _collect_usage(event)
            if found_usage:
                usage = found_usage
            return False

        async for line in response.aiter_lines():
            total_chars += len(line)
            if total_chars > self.settings.max_output_bytes * 2:
                raise RelayError("RELAY_BAD_RESPONSE", "上游返回内容过大，请稍后重试")
            if line == "":
                if await consume():
                    break
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
            elif line.startswith("event:") or line.startswith("id:") or line.startswith("retry:"):
                continue
            else:
                # Some gateways omit the data: prefix for a single JSON object.
                stripped = line.strip()
                if stripped.startswith("{") or stripped.startswith("["):
                    data_lines.append(stripped)

        if data_lines:
            await consume()

        result = self._decode_images(image_values, usage)
        return result

    def _parse_json_payload(self, raw: bytes) -> RelayResult:
        if not raw.strip():
            raise RelayError("RELAY_NO_IMAGE", "接口没有返回图片")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RelayError("RELAY_BAD_RESPONSE", "中转站返回了无法解析的数据") from exc
        _raise_event_error(payload)
        usage = _collect_usage(payload)
        image_values = _collect_image_values(payload)
        return self._decode_images(image_values, usage)

    def _decode_images(
        self,
        image_values: list[str],
        usage: dict | None,
    ) -> RelayResult:
        if not image_values:
            raise RelayError("RELAY_NO_IMAGE", "接口没有返回图片，请检查模型与提示词")
        images: list[ImagePayload] = []
        last_error: Exception | None = None
        for value in image_values[:4]:
            try:
                images.append(
                    decode_output_image(value, self.settings.max_output_bytes)
                )
            except ImageValidationError as exc:
                last_error = exc
                logger.warning("invalid relay image skipped: %s", exc)
        if not images:
            raise RelayError(
                "RELAY_BAD_IMAGE",
                "接口返回的图片无法识别或已损坏",
                upstream_detail=str(last_error) if last_error else None,
            )
        return RelayResult(images=images, usage=usage)


def _map_http_error(status_code: int, detail: str) -> tuple[str, str]:
    suffix = f"：{detail}" if detail else ""
    if status_code in {401, 403}:
        return "RELAY_AUTH", "接口密钥无效或无权限" + suffix
    if status_code == 402:
        return "RELAY_BALANCE", "中转站余额不足" + suffix
    if status_code == 429:
        return "RELAY_RATE_LIMIT", "请求过于频繁，请稍后重试" + suffix
    if 500 <= status_code < 600:
        return "RELAY_UPSTREAM", "上游生图服务异常" + suffix
    return "RELAY_BAD_REQUEST", "生图请求被上游拒绝" + suffix


def _extract_upstream_message(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text[:500]
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code") or error.get("type")
            if message:
                return str(message)[:500]
        if isinstance(error, str):
            return error[:500]
        for key in ("message", "detail", "msg"):
            if payload.get(key):
                return str(payload[key])[:500]
    return text[:500]


def _raise_event_error(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    error = payload.get("error")
    if error:
        message = ""
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("code") or "上游生成失败")
        else:
            message = str(error)
        raise RelayError(
            "RELAY_UPSTREAM",
            message[:500] or "上游生成失败",
            upstream_detail=message[:1000],
        )
    event_type = str(payload.get("type") or payload.get("event") or "").lower()
    if event_type in {"error", "image_generation.failed", "failed"}:
        message = str(
            payload.get("message") or payload.get("detail") or "上游生成失败"
        )
        raise RelayError("RELAY_UPSTREAM", message[:500], upstream_detail=message[:1000])


def _collect_image_values(payload: Any) -> list[str]:
    values: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key in ("b64_json", "b64"):
                value = node.get(key)
                if isinstance(value, str) and value:
                    values.append(value)
            if isinstance(node.get("data"), list):
                walk(node["data"])
            for key, value in node.items():
                if key in {"b64_json", "b64"}:
                    continue
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _collect_usage(payload: Any) -> dict | None:
    if isinstance(payload, dict):
        if isinstance(payload.get("usage"), dict):
            return payload["usage"]
        if isinstance(payload.get("usageMetadata"), dict):
            return payload["usageMetadata"]
        for value in payload.values():
            if isinstance(value, (dict, list)):
                found = _collect_usage(value)
                if found:
                    return found
    elif isinstance(payload, list):
        for value in payload:
            found = _collect_usage(value)
            if found:
                return found
    return None
