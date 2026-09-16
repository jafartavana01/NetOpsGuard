"""
app.schemas.command_set
=========================
PAM Expansion Plan §5. Mirrors app.schemas.policy's command-rule
sub-editing pattern closely on purpose: a CommandSet's rules are
edited as a whole (the full ordered list sent on every save, replaced
wholesale server-side) rather than through separate rule-level CRUD
endpoints, same reasoning as Policy's command_rules list had in
Phase 5 -- this is how the GUI actually edits it (one form, one
ordered list, one save).
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$")
_VALID_ACTIONS = {"permit", "deny"}


class CommandRuleInput(BaseModel):
    order: int = Field(ge=0, le=9999)
    action: str
    command_pattern: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=500)
    category_id: str | None = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in _VALID_ACTIONS:
            raise ValueError("action must be 'permit' or 'deny'.")
        return v

    @field_validator("command_pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        """
        A command pattern is emitted into the generated configuration
        between slash delimiters:

            if (cmd =~ /<pattern>/) { permit }

        Checking only that it COMPILES is not enough, and that was the
        previous behaviour. `x/ } permit } ` is a perfectly valid
        regular expression, and produces:

            if (cmd =~ /x/ } permit } /) { deny }

        -- which closes the rule early and turns a deny into a
        permit-everything. Anyone able to edit a command set could
        therefore rewrite arbitrary authorization rules, which is a
        privilege escalation, not a formatting bug.

        So the pattern is constrained to characters that cannot break
        out of the delimiter or the surrounding block. Slash is
        rejected outright rather than escaped: there is no confirmed
        escape syntax for it inside this config language, and guessing
        one would be the same mistake in a new place.
        """
        if not v or not v.strip():
            raise ValueError("A command pattern cannot be empty.")

        # Characters that terminate the regex, the rule, or the line.
        #
        # `/` is included and that has a real cost: matching an
        # interface name like GigabitEthernet0/1 is a normal thing to
        # want. It is still rejected, because the alternative is to
        # emit it escaped as `\/` and no confirmed evidence exists that
        # this config language accepts that inside `/.../`. Guessing at
        # escape syntax is precisely the mistake this fix exists to
        # correct, and getting it wrong would break every command
        # authorization rather than one pattern.
        #
        # `.` matches any character including `/`, so the rule remains
        # expressible -- the error message says so rather than leaving
        # the operator to work it out.
        # Backslash is deliberately NOT here: `\s`, `\d` and `\.` are
        # necessary regex constructs. Only a TRAILING backslash is
        # dangerous, because it escapes the closing delimiter; that is
        # checked separately below.
        forbidden = set('/{}\n\r\x00"')
        present = sorted(c for c in set(v) if c in forbidden)
        if present:
            shown = ", ".join(repr(c) for c in present)
            hint = ""
            if "/" in present:
                hint = (
                    " To match a path such as GigabitEthernet0/1, use '.' which matches any "
                    "character -- for example 'interface [A-Za-z]+[0-9]+.[0-9]+'."
                )
            raise ValueError(
                f"A command pattern may not contain {shown}. These characters would end the "
                f"pattern or the rule early in the generated configuration.{hint}"
            )

        if any(ord(c) < 0x20 or ord(c) == 0x7F for c in v):
            raise ValueError("A command pattern may not contain control characters.")

        if (len(v) - len(v.rstrip("\\"))) % 2 == 1:
            raise ValueError(
                "A command pattern may not end with a single backslash -- it would escape the "
                "closing delimiter in the generated configuration."
            )

        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"'{v}' is not a valid regular expression: {exc}")

        # Nested quantifiers are the classic catastrophic-backtracking
        # shape. This regex is evaluated by the DAEMON on every command
        # authorization, so a pathological pattern is a denial of
        # service against AAA itself, not merely a slow page.
        if re.search(r"\([^)]*[+*]\)[+*]", v):
            raise ValueError(
                "A command pattern may not nest one repetition inside another (for example "
                "'(a+)+'). Such patterns can take exponential time to evaluate and would "
                "stall command authorization."
            )

        return v


class CommandRuleOut(CommandRuleInput):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category_name: str | None = None


class CommandSetBase(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    vendor: str = Field(default="cisco_ios", max_length=32)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _NAME_PATTERN.match(v):
            raise ValueError(
                "Command set name must start with a letter or digit and contain only "
                "letters, digits, hyphens, and underscores (max 64 chars)."
            )
        return v


class CommandSetCreate(CommandSetBase):
    rules: list[CommandRuleInput] = Field(default_factory=list)


class CommandSetUpdate(CommandSetBase):
    rules: list[CommandRuleInput] = Field(default_factory=list)


class CommandSetOut(CommandSetBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rules: list[CommandRuleOut] = Field(default_factory=list)
    policy_count: int = 0  # how many policies currently reference this set
