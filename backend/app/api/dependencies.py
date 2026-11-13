"""Pagination parameters shared by HTTP routers."""

from typing import Annotated

from fastapi import Query

PageNumber = Annotated[int, Query(ge=1, le=1000000)]
PageSize = Annotated[int, Query(ge=1, le=100, alias="perPage")]
