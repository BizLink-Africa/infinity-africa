from app.core.pagination import PaginationParams, build_page_meta


def test_pagination_params_start_end():
    params = PaginationParams(page=1, page_size=20)
    assert params.start == 0
    assert params.end == 19

    params = PaginationParams(page=3, page_size=10)
    assert params.start == 20
    assert params.end == 29


def test_build_page_meta_computes_total_pages():
    params = PaginationParams(page=2, page_size=10)
    meta = build_page_meta(params, total=25)

    assert meta.page == 2
    assert meta.page_size == 10
    assert meta.total == 25
    assert meta.total_pages == 3


def test_build_page_meta_empty_result():
    params = PaginationParams(page=1, page_size=20)
    meta = build_page_meta(params, total=0)

    assert meta.total == 0
    assert meta.total_pages == 0
