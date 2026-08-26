from pydantic import BaseModel, Field

_EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


class InquiryCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    business_name: str | None = Field(default=None, max_length=200)
    email: str = Field(pattern=_EMAIL_PATTERN)
    phone: str | None = Field(default=None, max_length=40)
    message: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="contact_page", max_length=60)
