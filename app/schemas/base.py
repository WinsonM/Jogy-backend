"""Base schema classes with camelCase serialization for API responses."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model that serializes field names to camelCase.

    Use for response schemas that don't need ORM mode.
    Request schemas should continue to use plain BaseModel.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )


class CamelORMModel(CamelModel):
    """Base model with camelCase serialization + ORM mode.

    Use for response schemas that are populated from SQLAlchemy models.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )
