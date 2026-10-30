import type { Catalog, DataSource, ReaderSpec } from './types';

export function rePointSource(previous: DataSource, uploaded: DataSource, catalog: Catalog): DataSource {
  const before = readerForPath(catalog, previous.path), after = readerForPath(catalog, uploaded.path);
  const source: DataSource = {...uploaded, location: {kind: 'local'}};
  if (!before || before.id !== after?.id) return source;
  const fileKeys = new Set((before.parameters ?? []).filter(p => p.path_kind).map(p => p.key));
  const retained = Object.fromEntries(Object.entries(previous.args).filter(([key]) => !fileKeys.has(key)));
  return {...source, dims: [...previous.dims], labels: structuredClone(previous.labels), args: {...retained, ...uploaded.args}};
}

export function renameSourceDimensions(source: DataSource, dims: string[]): DataSource {
  if (!dims.length || new Set(dims).size !== dims.length) throw Error('维度名称不能为空或重复。');
  const renamed = new Map(source.dims.map((name, index) => [name, dims[index]]));
  const labels: Record<string, unknown> = {};
  dims.forEach((name, index) => {
    const old = source.labels[source.dims[index]] ?? 'auto';
    // Cross-axis position rules (e.g. {feature: 0}) also name a dimension.
    if (old && typeof old === 'object' && !Array.isArray(old) && Object.keys(old).length === 1) {
      const [key, value] = Object.entries(old)[0];
      labels[name] = renamed.get(key) ? {[renamed.get(key)!]: value} : structuredClone(old);
    } else labels[name] = structuredClone(old);
  });
  return {...source, dims, labels};
}

export function readerForPath(catalog: Catalog, path: string): ReaderSpec | undefined {
  const candidates = (catalog.readers ?? []).filter(reader =>
    readerExtensions(reader).some(ext => path.toLowerCase().endsWith(ext.toLowerCase())));
  // A .bed path alone cannot distinguish BED text from PLINK binary.
  return candidates.length === 1 ? candidates[0] : undefined;
}

function readerExtensions(reader: ReaderSpec): string[] {
  const compression = reader.file_input?.compression ?? (reader.handles_compression ? [] : ['.gz', '.bz2', '.xz']);
  return reader.extensions.flatMap(extension => ['', ...compression].map(suffix => extension + suffix));
}

// File filters follow the current catalog, including hot-installed readers.
export function inputAccept(catalog: Catalog): string {
  const extensions = new Set<string>();
  for (const reader of catalog.readers ?? []) {
    for (const extension of readerExtensions(reader)) extensions.add(extension);
    for (const sibling of reader.requires_siblings ?? []) extensions.add(sibling);
    for (const group of reader.file_input?.companions ?? []) {
      for (const name of group) extensions.add(name.slice(name.indexOf('.')));
    }
  }
  return [...extensions].sort().join(',');
}
