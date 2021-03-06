# Stubs for kubernetes.client.models.v1_downward_api_volume_source (Python 2)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

class V1DownwardAPIVolumeSource:
    swagger_types: Any = ...
    attribute_map: Any = ...
    discriminator: Any = ...
    default_mode: Any = ...
    items: Any = ...
    def __init__(self, default_mode: Optional[Any] = ..., items: Optional[Any] = ...) -> None: ...
    @property
    def default_mode(self): ...
    @default_mode.setter
    def default_mode(self, default_mode: Any) -> None: ...
    @property
    def items(self): ...
    @items.setter
    def items(self, items: Any) -> None: ...
    def to_dict(self): ...
    def to_str(self): ...
    def __eq__(self, other: Any): ...
    def __ne__(self, other: Any): ...
