import {useSyncExternalStore} from 'react';
import zh from './zh-CN.json';
import en from './en.json';
import {getPreferences, setPreferences, subscribePreferences, type LanguagePreference} from '../preferences';

export type Locale = 'zh-CN' | 'en';
export type {LanguagePreference} from '../preferences';
const listeners = new Set<() => void>();
const dictionaries: Record<Locale, Record<string, string>> = {'zh-CN': zh, en};
export function getLanguagePreference() {return getPreferences().language;}
export function getLocale(): Locale {
  const preference = getLanguagePreference();
  if (preference !== 'system') return preference;
  if (typeof document === 'undefined') return 'zh-CN';
  return typeof navigator !== 'undefined' && navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en';
}
function changed() {
  if (typeof document !== 'undefined') document.documentElement.lang = getLocale();
  listeners.forEach(listener => listener());
}
export function setLanguage(value: LanguagePreference) {
  setPreferences({language: value});
}
function subscribe(listener: () => void) {listeners.add(listener); return () => {listeners.delete(listener);};}
export function useLocale() {return useSyncExternalStore(subscribe, getLocale, () => 'zh-CN' as const);}
export function useLanguagePreference() {return useSyncExternalStore(subscribe, getLanguagePreference, () => 'system' as const);}
export function translate(locale: Locale, key: string, values: Record<string, unknown> = {}) {
  const text = Object.hasOwn(dictionaries[locale], key) ? dictionaries[locale][key]
    : Object.hasOwn(dictionaries['zh-CN'], key) ? dictionaries['zh-CN'][key] : key;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => Object.hasOwn(values, name) ? String(values[name]) : match);
}
export function t(key: string, values?: Record<string, unknown>) {return translate(getLocale(), key, values);}
if (typeof window !== 'undefined') {
  window.addEventListener('languagechange', changed);
  changed();
}
subscribePreferences(changed);
