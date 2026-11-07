"""Static, optional data-format capabilities. No scientific imports."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


def effective_formats(descriptor):
    """Read-only legacy projection from explicit contracts, never source scanning."""
    from copy import deepcopy
    if descriptor.get('data_formats') is not None:
        return deepcopy(descriptor['data_formats'])
    def port(rule):
        if not isinstance(rule, dict):
            return None
        mode = rule.get('mode')
        kind = rule.get('kind', 'form')
        if isinstance(kind, list):
            if len(set(kind)) != 1:
                return None
            kind = kind[0]
        if kind == 'file' or mode in {'file', 'artifact'}:
            return {'logical_type': 'file_artifact', 'representations': ['file_artifact'], 'metadata': {}}
        form_modes = {'form', 'pca', 'regress', 'compare_groups', 'correction', 'subset',
                      'select', 'drop', 'rename', 'transpose', 'transform', 'concat', 'attach',
                      'cox_regression', 'logrank_test'}
        if mode in form_modes or (mode is None and kind == 'form'):
            return {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}
        if mode == 'declare':
            return port(rule.get('schema'))
        return None
    contracts = descriptor.get('contracts') or {}
    inputs = contracts.get('inputs') or []
    count = 1 if descriptor.get('inputs_arity') == '*' else descriptor.get('inputs_arity', 0)
    output_count = 1 if descriptor.get('kind') == 'reader' or descriptor.get('output_parameter') else len(descriptor.get('outputs', []))
    return {'inputs': [port(inputs[min(i, len(inputs)-1)]) if inputs else None for i in range(count)],
            'outputs': [port(contracts.get('output')) for _ in range(output_count)]}


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
