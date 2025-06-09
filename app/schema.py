from pydantic import BaseModel, Field, HttpUrl


class ImagePost(BaseModel):
    """
    Schema for uploading an image to the service.
    """

    image: str = Field(
        ..., description="Base64-encoded image data (png, jpeg, webp, avif)."
    )
    project: str = Field(..., description="Project name to categorize the image.")
    key: str = Field(
        ...,
        description="Unique key for the image within the project (overrides if exists).",
    )


class ImagePostReturn(BaseModel):
    url: HttpUrl
    width: int
    height: int
    size: int
