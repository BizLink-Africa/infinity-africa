"""The standard API response envelope used by every /v1 endpoint.

Success:
  {"success": true, "data": ..., "meta": null | {...pagination...}}
Error:
  {"success": false, "error": {"code": ..., "message": ..., "details": ...}}
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    meta: PageMeta | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list | dict | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
