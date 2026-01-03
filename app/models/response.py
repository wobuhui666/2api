"""Response models for Gemini API compatible responses."""

from pydantic import BaseModel, Field
from .request import Content


class Candidate(BaseModel):
    """Candidate response from the model."""

    content: Content = Field(..., description="Content of the candidate")
    finishReason: str = Field(default="STOP", description="Reason for finishing")
    index: int = Field(default=0, description="Index of the candidate")


class UsageMetadata(BaseModel):
    """Usage metadata for the response."""

    promptTokenCount: int = Field(default=0, description="Prompt token count")
    candidatesTokenCount: int = Field(default=0, description="Candidates token count")
    totalTokenCount: int = Field(default=0, description="Total token count")


class GenerateContentResponse(BaseModel):
    """Response model for generateContent endpoint."""

    candidates: list[Candidate] = Field(..., description="Candidates from generation")
    usageMetadata: UsageMetadata = Field(
        default_factory=UsageMetadata, description="Usage metadata"
    )
    modelVersion: str = Field(..., description="Model version used")


class ErrorDetail(BaseModel):
    """Error detail in response."""

    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    status: str = Field(..., description="Error status")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: ErrorDetail = Field(..., description="Error details")