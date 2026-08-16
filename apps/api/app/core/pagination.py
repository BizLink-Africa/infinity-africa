from dataclasses import dataclass

from fastapi import Query

from app.schemas.common import PageMeta


@dataclass
class PaginationParams:
    page: int
    page_size: int

    @property
    def start(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def end(self) -> int:
        """Inclusive end index, as required by supabase-py's `.range()`."""
        return self.start + self.page_size - 1


def pagination_params(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(20, ge=1, le=100, description="Rows per page (max 100)"),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


def build_page_meta(params: PaginationParams, total: int) -> PageMeta:
    total_pages = (total + params.page_size - 1) // params.page_size if params.page_size else 0
    return PageMeta(page=params.page, page_size=params.page_size, total=total, total_pages=total_pages)
