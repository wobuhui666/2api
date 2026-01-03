"""Generate content router for Gemini API compatible endpoints."""

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse
from loguru import logger

from app.models.request import GenerateContentRequest
from app.models.response import GenerateContentResponse, ErrorResponse, ErrorDetail
from app.services.session import get_session
from app.services.provider import VertexAIAnonymousProvider


router = APIRouter()


# Supported models
SUPPORTED_MODELS = [
    "gemini-2.0-flash-preview-image-generation",
    "gemini-3-pro-image-preview",
]


@router.post(
    "/v1beta/models/{model}:generateContent",
    response_model=GenerateContentResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
        503: {"model": ErrorResponse, "description": "Service Unavailable"},
    },
    summary="Generate content",
    description="Generate content using the specified model. Supports text-to-image and image-to-image generation.",
)
async def generate_content(
    request: GenerateContentRequest,
    model: str = Path(..., description="Model name to use for generation"),
) -> GenerateContentResponse:
    """
    Generate content using the Vertex AI Anonymous API.

    Supported models:
    - gemini-2.0-flash-preview-image-generation
    - gemini-3-pro-image-preview

    The request format is compatible with Google Gemini API.
    """
    logger.info(f"Received generate request for model: {model}")

    # Validate model
    if model not in SUPPORTED_MODELS:
        logger.warning(f"Unsupported model requested: {model}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": 400,
                    "message": f"Unsupported model: {model}. Supported models: {', '.join(SUPPORTED_MODELS)}",
                    "status": "INVALID_ARGUMENT",
                }
            },
        )

    # Validate request has contents
    if not request.contents:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": 400,
                    "message": "Request must contain at least one content item",
                    "status": "INVALID_ARGUMENT",
                }
            },
        )

    # Validate at least one user content with parts
    has_user_content = False
    for content in request.contents:
        if content.role == "user" and content.parts:
            has_user_content = True
            break

    if not has_user_content:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": 400,
                    "message": "Request must contain at least one user content with parts",
                    "status": "INVALID_ARGUMENT",
                }
            },
        )

    try:
        # Get session and create provider
        session = await get_session()
        provider = VertexAIAnonymousProvider(session)

        # Generate content
        response, error = await provider.generate_content(model, request)

        if error:
            logger.error(f"Generation failed: {error}")

            # Determine appropriate status code
            if "recaptcha" in error.lower():
                status_code = 503
                status = "UNAVAILABLE"
            else:
                status_code = 500
                status = "INTERNAL"

            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": {
                        "code": status_code,
                        "message": error,
                        "status": status,
                    }
                },
            )

        logger.info(f"Generation successful for model: {model}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during generation: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": 500,
                    "message": f"Internal server error: {str(e)}",
                    "status": "INTERNAL",
                }
            },
        )


@router.get(
    "/v1beta/models",
    summary="List available models",
    description="List all available models for content generation.",
)
async def list_models():
    """List all supported models."""
    return {
        "models": [
            {
                "name": f"models/{model}",
                "displayName": model,
                "supportedGenerationMethods": ["generateContent"],
            }
            for model in SUPPORTED_MODELS
        ]
    }


@router.get(
    "/v1beta/models/{model}",
    summary="Get model info",
    description="Get information about a specific model.",
)
async def get_model(
    model: str = Path(..., description="Model name"),
):
    """Get information about a specific model."""
    if model not in SUPPORTED_MODELS:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": f"Model not found: {model}",
                    "status": "NOT_FOUND",
                }
            },
        )

    return {
        "name": f"models/{model}",
        "displayName": model,
        "supportedGenerationMethods": ["generateContent"],
    }