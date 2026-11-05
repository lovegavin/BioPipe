import {useSyncExternalStore} from 'react';

export type LanguagePreference = 'system' | 'zh-CN' | 'en';
export type ThemePreference = 'system' | 'light' | 'dark';
export type UiPreferences = {language: LanguagePreference; theme: ThemePreference};
const KEY = 'biopipe-studio-config-v1';
const defaults: UiPreferences = {language: 'system', theme: 'system'};
const listeners = new Set<() => void>();
function stored(): UiPreferences {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || '{}');
    const language = value.language ?? localStorage.getItem('biopipe-studio-language-v1');
    const theme = value.theme ?? localStorage.getItem('biopipe-studio-theme-v1');
    return {language: language === 'en' || language === 'zh-CN' ? language : 'system',
      theme: theme === 'light' || theme === 'dark' ? theme : 'system'};
  } catch {return defaults;}
}
let current = stored();
export function getPreferences() {return current;}
export function subscribePreferences(listener: () => void) {listeners.add(listener); return () => {listeners.delete(listener);};}
export function setPreferences(value: Partial<UiPreferences>) {
  current = {...current, ...value};
  try {localStorage.setItem(KEY, JSON.stringify(current));} catch { /* The profile remains authoritative. */ }
  listeners.forEach(listener => listener());
}
export function usePreferences() {return useSyncExternalStore(subscribePreferences, getPreferences, () => defaults);}
if (typeof window !== 'undefined') {
  window.addEventListener('storage', event => {
    if (event.key === KEY || event.key === null) {current = stored(); listeners.forEach(listener => listener());}
  });
}
