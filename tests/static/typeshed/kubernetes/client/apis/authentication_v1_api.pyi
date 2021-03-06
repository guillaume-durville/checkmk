# Stubs for kubernetes.client.apis.authentication_v1_api (Python 2)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ..api_client import ApiClient
from typing import Any, Optional

class AuthenticationV1Api:
    api_client: Any = ...
    def __init__(self, api_client: Optional[Any] = ...) -> None: ...
    def create_token_review(self, body: Any, **kwargs: Any): ...
    def create_token_review_with_http_info(self, body: Any, **kwargs: Any): ...
    def get_api_resources(self, **kwargs: Any): ...
    def get_api_resources_with_http_info(self, **kwargs: Any): ...
