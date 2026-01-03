"""Vertex AI Anonymous Provider for image generation."""

import json
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import Timeout
from loguru import logger

from app.config import settings
from app.models.request import GenerateContentRequest, Part, Content
from app.models.response import (
    GenerateContentResponse,
    Candidate,
    UsageMetadata,
)
from app.services.recaptcha import recaptcha_manager


class VertexAIAnonymousProvider:
    """Provider for Vertex AI Anonymous image generation API."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_content(
        self, model: str, request: GenerateContentRequest
    ) -> tuple[GenerateContentResponse | None, str | None]:
        """
        Generate content using Vertex AI Anonymous API.

        Args:
            model: Model name to use for generation
            request: The generation request

        Returns:
            Tuple of (response, error_message)
        """
        # Build request body
        body = self._build_request_body(model, request)

        # Get recaptcha token
        recaptcha_token = await recaptcha_manager.get_token(self.session)
        if recaptcha_token is None:
            return None, "Failed to get recaptcha token"

        error_msg = None

        # Retry loop
        for attempt in range(settings.max_retry):
            body["variables"]["recaptchaToken"] = recaptcha_token

            result, status, error_msg = await self._call_api(body)

            if result is not None:
                # Build successful response
                response = self._build_response(result, model)
                return response, None

            # Status 3: Token expired or parameter error
            if status == 3:
                recaptcha_token = await recaptcha_manager.invalidate_and_refresh(
                    self.session
                )
                if recaptcha_token is None:
                    logger.error("Failed to refresh recaptcha token")
                    return None, "Failed to refresh recaptcha token"

            # Status 999: Content blocked, no point in retrying
            if status == 999:
                return None, error_msg

            logger.warning(
                f"Generation failed, retrying ({attempt + 1}/{settings.max_retry})"
            )

        return None, error_msg or "Generation failed: max retries exceeded"

    async def _call_api(
        self, body: dict
    ) -> tuple[list[tuple[str, str]] | None, int | None, str | None]:
        """
        Call the Vertex AI Anonymous API.

        Returns:
            Tuple of (images, status_code, error_message)
            images: List of (mime_type, base64_data) tuples
        """
        headers = {
            "referer": "https://console.cloud.google.com/",
            "Content-Type": "application/json",
        }

        try:
            response = await self.session.post(
                url=f"{settings.vertex_ai_base_api}/v3/entityServices/AiplatformEntityService/schemas/AIPLATFORM_GRAPHQL:batchGraphql?key=AIzaSyCI-zsRP85UVOi0DjtiCwWBwQ1djDy741g&prettyPrint=false",
                headers=headers,
                json=body,
                timeout=settings.timeout,
                impersonate="chrome131",
                proxy=settings.proxy,
            )

            result = response.json()

            if response.status_code == 200:
                b64_images = []
                text_parts = []

                # Process each element in response
                for elem in result:
                    for item in elem.get("results", []):
                        # Check for errors
                        errors = item.get("errors", [])
                        for err in errors:
                            status = (
                                err.get("extensions", {})
                                .get("status", {})
                                .get("code", None)
                            )
                            err_msg = err.get("message", "")
                            logger.error(
                                f"API error - code: {status}, message: {err_msg}"
                            )
                            return None, status, err_msg

                        # Process candidates
                        for candidate in item.get("data", {}).get("candidates", []):
                            finish_reason = candidate.get("finishReason", "")

                            if finish_reason == "STOP":
                                parts = candidate.get("content", {}).get("parts", [])
                                for part in parts:
                                    # Handle inline data (images)
                                    if "inlineData" in part and part["inlineData"].get(
                                        "data"
                                    ):
                                        data = part["inlineData"]
                                        b64_images.append(
                                            (data["mimeType"], data["data"])
                                        )
                                    # Handle text
                                    if "text" in part:
                                        text_parts.append(part["text"])
                            elif finish_reason == "FINISH_REASON_UNSPECIFIED":
                                # This may indicate the response is still processing
                                # or there's a temporary issue, log the full response
                                logger.warning(
                                    f"Generation incomplete with FINISH_REASON_UNSPECIFIED, "
                                    f"candidate: {candidate}"
                                )
                                # Try to extract any partial data if available
                                parts = candidate.get("content", {}).get("parts", [])
                                for part in parts:
                                    if "inlineData" in part and part["inlineData"].get("data"):
                                        data = part["inlineData"]
                                        b64_images.append((data["mimeType"], data["data"]))
                                    if "text" in part:
                                        text_parts.append(part["text"])
                                # Continue to next candidate if no images found
                                if not b64_images:
                                    continue
                            else:
                                logger.warning(
                                    f"Generation failed with finish reason: {finish_reason}, "
                                    f"response: {response.text[:500] if response.text else 'empty'}"
                                )
                                return (
                                    None,
                                    999,
                                    f"Generation failed: {finish_reason}",
                                )

                # Check if we got any images
                if not b64_images:
                    logger.warning("Request succeeded but no images in response")
                    return None, 999, "No images in response"

                # Return images and text parts combined
                return (b64_images, text_parts), None, None
            else:
                logger.error(
                    f"API request failed - status: {response.status_code}, "
                    f"response: {response.text[:1024]}"
                )
                return None, None, f"API request failed: status {response.status_code}"

        except Timeout as e:
            logger.error(f"Request timeout: {e}")
            return None, None, "Request timeout"
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, response text: {response.text[:500] if response.text else 'empty'}")
            return None, None, "Invalid JSON response"
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            return None, None, f"Unexpected error: {str(e)}"

    def _build_request_body(
        self, model: str, request: GenerateContentRequest
    ) -> dict:
        """Build the request body for Vertex AI API."""
        # Extract prompt and images from contents
        prompt_parts = []
        image_parts = []

        for content in request.contents:
            if content.role == "user":
                for part in content.parts:
                    if part.text:
                        prompt_parts.append(part.text)
                    if part.inlineData:
                        image_parts.append(
                            {
                                "inlineData": {
                                    "mimeType": part.inlineData.mimeType,
                                    "data": part.inlineData.data,
                                }
                            }
                        )

        prompt = "\n".join(prompt_parts)

        # Build parts for request
        parts = [{"text": prompt}]
        parts.extend(image_parts)

        # Determine response modalities
        response_modalities = ["IMAGE"]
        if settings.text_response:
            response_modalities.insert(0, "TEXT")

        # Override with request config if provided
        if request.generationConfig and request.generationConfig.responseModalities:
            response_modalities = request.generationConfig.responseModalities

        # Determine maxOutputTokens based on model
        # gemini-2.0-flash-preview-image-generation supports 1-8192
        # gemini-3-pro-image-preview supports up to 32768
        if "gemini-2" in model.lower():
            max_output_tokens = 8192
        else:
            max_output_tokens = 32768

        # Build context
        context = {
            "model": model,
            "contents": [{"parts": parts, "role": "user"}],
            "generationConfig": {
                "temperature": 1,
                "topP": 0.95,
                "maxOutputTokens": max_output_tokens,
                "responseModalities": response_modalities,
                "imageConfig": {
                    "imageOutputOptions": {"mimeType": "image/png"},
                    "personGeneration": "ALLOW_ALL",
                },
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
            ],
            "region": "global",
        }

        # Override with request generation config
        if request.generationConfig:
            config = request.generationConfig
            context["generationConfig"]["temperature"] = config.temperature
            context["generationConfig"]["topP"] = config.topP
            context["generationConfig"]["maxOutputTokens"] = config.maxOutputTokens

            # Handle image config
            if config.imageConfig:
                if config.imageConfig.aspectRatio:
                    context["generationConfig"]["imageConfig"]["aspectRatio"] = (
                        config.imageConfig.aspectRatio
                    )
                if config.imageConfig.imageSize:
                    context["generationConfig"]["imageConfig"]["imageSize"] = (
                        config.imageConfig.imageSize
                    )
                if config.imageConfig.personGeneration:
                    context["generationConfig"]["imageConfig"]["personGeneration"] = (
                        config.imageConfig.personGeneration
                    )

        # Override with request safety settings
        if request.safetySettings:
            context["safetySettings"] = [
                {"category": s.category, "threshold": s.threshold}
                for s in request.safetySettings
            ]

        # Handle system instruction
        if request.systemInstruction:
            system_text_parts = []
            for part in request.systemInstruction.parts:
                if part.text:
                    system_text_parts.append(part.text)
            if system_text_parts:
                context["systemInstruction"] = {
                    "parts": [{"text": "\n".join(system_text_parts)}]
                }
        elif settings.system_prompt:
            context["systemInstruction"] = {
                "parts": [{"text": settings.system_prompt}]
            }

        # Handle tools (e.g., Google Search) - only for gemini-3 models
        if "gemini-3" in model.lower():
            if request.tools:
                tools = []
                for tool in request.tools:
                    if tool.googleSearch is not None:
                        tools.append({"googleSearch": {}})
                if tools:
                    context["tools"] = tools

        # Build final body
        body = {
            "querySignature": "2/l8eCsMMY49imcDQ/lwwXyL8cYtTjxZBF2dNqy69LodY=",
            "operationName": "StreamGenerateContentAnonymous",
            "variables": context,
        }

        return body

    def _build_response(
        self, result: tuple[list[tuple[str, str]], list[str]], model: str
    ) -> GenerateContentResponse:
        """Build a GenerateContentResponse from API result."""
        images, texts = result

        # Build parts for response
        parts = []

        # Add text parts first
        for text in texts:
            parts.append(Part(text=text))

        # Add image parts
        from app.models.request import InlineData

        for mime_type, data in images:
            parts.append(
                Part(
                    inlineData=InlineData(
                        mimeType=mime_type,
                        data=data,
                    )
                )
            )

        # Build candidate
        candidate = Candidate(
            content=Content(role="model", parts=parts),
            finishReason="STOP",
            index=0,
        )

        # Build response
        response = GenerateContentResponse(
            candidates=[candidate],
            usageMetadata=UsageMetadata(),
            modelVersion=model,
        )

        return response