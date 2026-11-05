import {getLocale} from './i18n';
import type {Operator, ReaderSpec} from './types';

export type ParameterText = {title?: string | null; description?: string | null; enum_labels?: Record<string, string>};
export type OperatorText = {title?: string | null; description?: string | null; parameters?: Record<string, ParameterText>};
export type OperatorLanguagePack = {default_locale: string; translations: Record<string, OperatorText>};
// JSON values are compared structurally; 1 and "1" remain distinct.
export function enumKey(value: unknown): string {
  return JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
}
export function operatorText(pack: OperatorLanguagePack, locale: string): OperatorText {
  const translations = Object.fromEntries(Object.entries(pack.translations).map(([key, text]) => [key.toLowerCase(), text]));
  const tag = locale.replaceAll('_', '-').toLowerCase();
  const result: OperatorText = {parameters: Object.create(null) as Record<string, ParameterText>};
  for (const key of [pack.default_locale.toLowerCase(), tag.split('-')[0], tag]) {
    const text = translations[key];
    if (!text) continue;
    if (text.title != null) result.title = text.title;
    if (text.description != null) result.description = text.description;
    for (const [name, field] of Object.entries(text.parameters || {})) {
      const previous = result.parameters![name] || {};
      result.parameters![name] = {...previous, ...Object.fromEntries(Object.entries(field).filter(([, value]) => value != null)),
        enum_labels: {...previous.enum_labels, ...field.enum_labels}};
    }
  }
  return result;
}
export function localizeOperator<T extends Operator | ReaderSpec>(spec: T, locale: string = getLocale()): T {
  if (!spec.localization) return spec;
  const text = operatorText(spec.localization, locale);
  return {...spec, title: text.title ?? spec.title, description: text.description ?? spec.description,
    title_aliases: [...new Set([spec.title, ...('title_aliases' in spec ? spec.title_aliases || [] : []),
      ...Object.values(spec.localization.translations).map(value => value.title)].filter((value): value is string => typeof value === 'string'))],
    parameters: spec.parameters?.map(field => {
      const translated = text.parameters?.[field.key];
      return translated ? {...field, label: translated.title ?? field.label,
        description: translated.description ?? field.description,
        option_labels: Object.fromEntries(Object.entries(translated.enum_labels || {}).map(([key, label]) => [enumKey(JSON.parse(key)), label]))} : field;
    })};
}
