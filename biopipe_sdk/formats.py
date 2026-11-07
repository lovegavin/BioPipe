"""Static, optional data-format capabilities. No scientific imports."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class FormatPort(BaseModel):
    model_config = ConfigDict(extra='forbid')
    logical_type: str = Field(pattern=r'^[a-z][a-z0-9_.-]{0,79}$')
    representations: list[str] = Field(min_length=1, max_length=16)
    # These are logical invariants, not instructions to reinterpret data.
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def distinct_representations(self):
        import re
        if len(set(self.representations)) != len(self.representations) or any(
                not re.fullmatch(r'[a-z][a-z0-9_.-]{0,79}', value) for value in self.representations):
            raise ValueError('Representations must be distinct registered identifiers')
        return self


class DataFormats(BaseModel):
    model_config = ConfigDict(extra='forbid')
    inputs: list[FormatPort] = Field(default_factory=list, max_length=20)
    outputs: list[FormatPort] = Field(default_factory=list, max_length=20)


class Adaptation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['auto', 'disabled', 'fixed'] = 'auto'
    converters: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode='after')
    def fixed_only(self):
        if bool(self.converters) != (self.mode == 'fixed'):
            raise ValueError('Only fixed adaptation requires a nonempty converter chain')
        return self
