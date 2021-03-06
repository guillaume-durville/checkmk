# Stubs for kubernetes.client.models.v1_pod_dns_config (Python 2)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

class V1PodDNSConfig:
    swagger_types: Any = ...
    attribute_map: Any = ...
    discriminator: Any = ...
    nameservers: Any = ...
    options: Any = ...
    searches: Any = ...
    def __init__(self, nameservers: Optional[Any] = ..., options: Optional[Any] = ..., searches: Optional[Any] = ...) -> None: ...
    @property
    def nameservers(self): ...
    @nameservers.setter
    def nameservers(self, nameservers: Any) -> None: ...
    @property
    def options(self): ...
    @options.setter
    def options(self, options: Any) -> None: ...
    @property
    def searches(self): ...
    @searches.setter
    def searches(self, searches: Any) -> None: ...
    def to_dict(self): ...
    def to_str(self): ...
    def __eq__(self, other: Any): ...
    def __ne__(self, other: Any): ...
