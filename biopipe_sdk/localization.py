"""Optional v3.5 presentation resources. Discovery never imports operator code."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def relative_path(value):
    if not isinstance(value, str):
        raise ValueError('localization.path must be a relative JSON path')
    value = value.replace('\\', '/')
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or ':' in value or
            any(p in ('', '.', '..') for p in value.split('/')) or path.suffix != '.json'):
        raise ValueError('localization.path must remain inside the implementation directory and end in .json')
    return value


class ParameterText(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = None
    description: str | None = None
    # Keys are JSON-encoded enum values, so number 1 and string "1" differ.
    enum_labels: dict[str, str] = Field(default_factory=dict)


class OperatorText(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = None
    description: str | None = None
    parameters: dict[str, ParameterText] = Field(default_factory=dict)


class LanguagePack(BaseModel):
    model_config = ConfigDict(extra='forbid')
    default_locale: str = Field(pattern=r'^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$')
    translations: dict[str, OperatorText]

    @model_validator(mode='after')
    def validate_locales(self):
        import re
        locales = list(self.translations)
        if self.default_locale not in locales:
            raise ValueError('default_locale must exist in translations')
        if len({key.lower() for key in locales}) != len(locales):
            raise ValueError('Duplicate language tags')
        if any(not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*', key) for key in locales):
            raise ValueError('Invalid language tag')
        return self


class Localization(LanguagePack):
    path: str
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    minimum_sdk: Literal['3.5.0'] = '3.5.0'

    @field_validator('path')
    @classmethod
    def validate_path(cls, value):
        return relative_path(value)


def canonical_pack(content):
    value = json.loads(content)
    LanguagePack.model_validate(value)
    return value, json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')


def validate_parameters(pack, schema):
    from jsonschema import Draft202012Validator
    properties = schema.get('properties', {})
    for text in pack['translations'].values():
        for key, translated in text.get('parameters', {}).items():
            if key not in properties:
                raise ValueError(f'Unknown localized parameter: {key}')
            choices = properties[key].get('enum', [])
            for encoded in translated.get('enum_labels', {}):
                try:
                    value = json.loads(encoded)
                except (ValueError, TypeError) as error:
                    raise ValueError(f'Localized enum keys must be JSON values: {key}') from error
                if not choices or not Draft202012Validator({'enum': choices}).is_valid(value):
                    raise ValueError(f'Unknown localized enum value: {key}')


def compile_localization(source, metadata, schema):
    relative = relative_path(metadata if isinstance(metadata, str) else metadata.get('path'))
    parent = Path(source).parent.resolve()
    path = (parent / relative).resolve()
    if not path.is_relative_to(parent):
        raise ValueError('Language pack must remain inside the implementation directory')
    value, canonical = canonical_pack(path.read_bytes())
    validate_parameters(value, schema)
    return {**value, 'path': relative, 'sha256': sha256(canonical).hexdigest(), 'minimum_sdk': '3.5.0'}


def archive_path(entries, descriptor):
    module = descriptor['entry_point'].split(':')[0].replace('.', '/')
    entry = module + '.py' if module + '.py' in entries else module + '/__init__.py'
    return str(PurePosixPath(entry).parent / relative_path(descriptor['localization']['path']))


def verify_content(content, metadata, schema):
    value, canonical = canonical_pack(content)
    if sha256(canonical).hexdigest() != metadata['sha256']:
        raise ValueError('Language pack content hash mismatch: ' + metadata['path'])
    if any(value[k] != metadata[k] for k in ('default_locale', 'translations')):
        raise ValueError('Language pack differs from indexed translations')
    validate_parameters(value, schema)


def localized_text(pack, locale):
    """Field-level fallback: exact tag, base language, default, original text."""
    translations = {key.lower(): value for key, value in pack['translations'].items()}
    tag = locale.replace('_', '-').lower()
    result = {}
    for key in (pack['default_locale'].lower(), tag.split('-')[0], tag):
        def merge(target, source):
            for name, value in source.items():
                if isinstance(value, dict):
                    merge(target.setdefault(name, {}), value)
                elif value is not None:
                    target[name] = value
        merge(result, translations.get(key, {}))
    return result


def project(descriptor, locale):
    """Optional UI/API projection; never persist this over a signed descriptor."""
    result = deepcopy(descriptor)
    if not descriptor.get('localization'):
        return result
    text = localized_text(descriptor['localization'], locale)
    for key in ('title', 'description'):
        if key in text:
            result[key] = text[key]
    for key, value in text.get('parameters', {}).items():
        field = result['parameters_schema']['properties'][key]
        for attr in ('title', 'description'):
            if attr in value:
                field[attr] = value[attr]
        if value.get('enum_labels'):
            field['x-ui-enum-labels'] = value['enum_labels']
    return result
