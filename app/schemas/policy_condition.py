"""Reusable, strictly validated condition-tree request models."""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from ..models.policy_condition import DATABASE_BACKED_OBJECT_TYPES, VALID_OBJECT_TYPES
from ..models.policy_condition_group import VALID_LOGICAL_OPERATORS

class ConditionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_type: str
    operator: str
    # NOT min_length=1 -- for a database-backed object_type (user,
    # user_group, device, device_group), the backend never reads this
    # field at all (see _validate_and_build_condition below: it
    # resolves the real display name fresh from the referenced row),
    # so the GUI legitimately sends an empty string for those --
    # exactly what the Multi-select condition builder does for every
    # entry. A min_length constraint here was rejecting that ordinary,
    # correct payload with a raw Pydantic error ("String should have
    # at least 1 character") instead of the backend's own clearer
    # messages. Still validated as genuinely required, but only for
    # the one object_type where it's actually used -- source_ip's
    # manual value -- via the model_validator below.
    value: str = Field(default="", max_length=500)
    referenced_object_id: str | None = None

    @field_validator("object_type")
    @classmethod
    def validate_object_type(cls, v: str) -> str:
        if v not in VALID_OBJECT_TYPES:
            raise ValueError(f"'{v}' is not a supported condition object type.")
        return v

    @model_validator(mode="after")
    def validate_value_required_for_manual_types(self) -> "ConditionInput":
        if self.object_type not in DATABASE_BACKED_OBJECT_TYPES and not self.value.strip():
            raise ValueError(f"A {self.object_type} condition needs a value.")
        return self


class ConditionGroupInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    logical_operator: str
    conditions: list[ConditionInput] = Field(default_factory=list)
    child_groups: list["ConditionGroupInput"] = Field(default_factory=list)

    @field_validator("logical_operator")
    @classmethod
    def validate_logical_operator(cls, v: str) -> str:
        if v not in VALID_LOGICAL_OPERATORS:
            raise ValueError(f"'{v}' is not a supported logical operator (must be AND, OR, or NOT).")
        return v


ConditionGroupInput.model_rebuild()

