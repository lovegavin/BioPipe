export type Viewer = {id: string; name: string; domain: string; extensions: string[];
  kind: 'desktop' | 'web'; mode: 'file' | 'manual'; available: boolean; status: string;
  notes: string; executable: string | null; configured_path?: string | null; url?: string; source: string};
export type ViewerCatalog = {viewers: Viewer[]; defaults: Record<string, string>};
export type ViewerOptions = {viewers: Viewer[]; default_viewer: string | null; default_source: 'configured' | 'automatic'};
export const viewerStatus: Record<string, string> = {not_found: '未找到程序', unsupported_system: '当前系统不支持', java_required: '需要 Java', desktop_required: '需要桌面会话'};
