"""Request models for Gemini API compatible requests."""

from typing import Literal
from pydantic import BaseModel, Field


class InlineData(BaseModel):
    """Inline data for image content."""

    mimeType: str = Field(..., description="MIME type of the data")
    data: str = Field(..., description="Base64 encoded data")


class Part(BaseModel):
    """Part of content, can be text or inline data."""

    text: str | None = Field(default=None, description="Text content")
    inlineData: InlineData | None = Field(default=None, description="Inline data")


class Content(BaseModel):
    """Content with role and parts."""

    role: Literal["user", "model"] = Field(default="user", description="Role of the content")
    parts: list[Part] = Field(..., description="Parts of the content")


class ImageConfig(BaseModel):
    """Image configuration for generation."""

    aspectRatio: str | None = Field(default=None, description="Aspect ratio (e.g., '1:1', '16:9')")
    imageSize: str | None = Field(default=None, description="Image size")
    personGeneration: str | None = Field(default="ALLOW_ALL", description="Person generation setting")


class GenerationConfig(BaseModel):
    """Generation configuration."""

    temperature: float = Field(default=1.0, description="Temperature for generation")
    topP: float = Field(default=0.95, description="Top P for generation")
    maxOutputTokens: int = Field(default=32768, description="Maximum output tokens")
    responseModalities: list[str] = Field(
        default=["TEXT", "IMAGE"], description="Response modalities"
    )
    imageConfig: ImageConfig | None = Field(default=None, description="Image configuration")


class SafetySetting(BaseModel):
    """Safety setting for content generation."""

    category: str = Field(..., description="Safety category")
    threshold: str = Field(default="OFF", description="Safety threshold")


class ToolGoogleSearch(BaseModel):
    """Google Search tool configuration."""
    pass


class Tool(BaseModel):
    """Tool configuration."""
    
    googleSearch: ToolGoogleSearch | None = Field(default=None, description="Google Search tool")


class GenerateContentRequest(BaseModel):
    """Request model for generateContent endpoint."""

    contents: list[Content] = Field(..., description="Contents to generate from")
    generationConfig: GenerationConfig | None = Field(
        default=None, description="Generation configuration"
    )
    safetySettings: list[SafetySetting] | None = Field(
        default=None, description="Safety settings"
    )
    systemInstruction: Content | None = Field(
        default=None, description="System instruction"
    )
    tools: list[Tool] | None = Field(default=None, description="Tools configuration")