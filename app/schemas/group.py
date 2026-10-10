"""
app.schemas.group
===================
`name` becomes a bare identifier inside a generated tac_plus-ng
`group {}` block -- same identifier-safety reasoning as
app.schemas.device and app.schemas.user.

`policy_id` was removed here alongside app.models.group's own removal
of that field (PAM Expansion Plan Increment 1) -- a group no longer
"owns" a policy assignment; policies declare which group they target
via their own condition fields instead (app.schemas.policy). What a
group can still show is read-only: which policies currently target
it, a reverse lookup rather than a settable field.
"""
from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$")


class TacacsGroupBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authority: Literal["LEGACY", "EXTERNAL"] = "LEGACY"
    external_source_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_binding_fields(self):
        if self.authority == "EXTERNAL":
            if self.external_source_id is None or not self.ad_group_name or not self.ad_group_name.strip():
                raise ValueError("EXTERNAL requires an explicit source and directory group CN.")
        elif self.external_source_id is not None:
            raise ValueError("LEGACY groups cannot carry an external source binding.")
        return self

    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    ad_group_name: str | None = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _NAME_PATTERN.match(v):
            raise ValueError(
                "Group name must start with a letter or digit and contain only "
                "letters, digits, hyphens, and underscores (max 64 chars) -- it is "
                "used as a raw identifier in the generated tac_plus-ng configuration."
            )
        return v


class TacacsGroupCreate(TacacsGroupBase):
    pass


class TacacsGroupUpdate(TacacsGroupBase):
    pass


class TacacsGroupOut(TacacsGroupBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    binding_status: str = "unclassified"
    binding_diagnostics: list[dict] = Field(default_factory=list)
    external_source_name: str | None = None
    member_count: int = 0
    # Read-only reverse lookup: policies whose condition_group_id
    # points at this group -- not a field this group itself owns.
    referenced_by_policy_names: list[str] = Field(default_factory=list)
