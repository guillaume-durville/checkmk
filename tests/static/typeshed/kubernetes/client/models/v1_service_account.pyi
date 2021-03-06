# Stubs for kubernetes.client.models.v1_service_account (Python 2)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

class V1ServiceAccount:
    swagger_types: Any = ...
    attribute_map: Any = ...
    discriminator: Any = ...
    api_version: str = ...
    automount_service_account_token: Any = ...
    image_pull_secrets: Any = ...
    kind: str = ...
    metadata: Any = ...
    secrets: Any = ...
    def __init__(self, api_version: Optional[Any] = ..., automount_service_account_token: Optional[Any] = ..., image_pull_secrets: Optional[Any] = ..., kind: Optional[Any] = ..., metadata: Optional[Any] = ..., secrets: Optional[Any] = ...) -> None: ...
    @property
    def api_version(self) -> str: ...
    @api_version.setter
    def api_version(self, api_version: str) -> None: ...
    @property
    def automount_service_account_token(self): ...
    @automount_service_account_token.setter
    def automount_service_account_token(self, automount_service_account_token: Any) -> None: ...
    @property
    def image_pull_secrets(self): ...
    @image_pull_secrets.setter
    def image_pull_secrets(self, image_pull_secrets: Any) -> None: ...
    @property
    def kind(self) -> str: ...
    @kind.setter
    def kind(self, kind: str) -> None: ...
    @property
    def metadata(self): ...
    @metadata.setter
    def metadata(self, metadata: Any) -> None: ...
    @property
    def secrets(self): ...
    @secrets.setter
    def secrets(self, secrets: Any) -> None: ...
    def to_dict(self): ...
    def to_str(self): ...
    def __eq__(self, other: Any): ...
    def __ne__(self, other: Any): ...
