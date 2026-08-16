from pydantic import BaseModel


class EndpointGroup(BaseModel):
    name: str
    base_path: str
    description: str


class DeveloperDocsResponse(BaseModel):
    api_version: str
    swagger_ui_url: str
    openapi_schema_url: str
    authentication: dict[str, str]
    endpoint_groups: list[EndpointGroup]
