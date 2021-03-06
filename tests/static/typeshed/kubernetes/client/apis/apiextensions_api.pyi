# Stubs for kubernetes.client.apis.apiextensions_api (Python 2)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ..api_client import ApiClient
from typing import Any, Optional

class ApiextensionsApi:
    api_client: Any = ...
    def __init__(self, api_client: Optional[Any] = ...) -> None: ...
    def get_api_group(self, **kwargs: Any): ...
    def get_api_group_with_http_info(self, **kwargs: Any): ...
