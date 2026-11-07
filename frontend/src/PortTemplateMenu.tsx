import {useState} from 'react';
import type {PortContract} from './types';
import {t} from './i18n';

export type ScriptLanguage = 'python' | 'r' | 'c' | 'cpp';
export function fileFormats(contract?: PortContract | null): string[] {
  if (!contract || contract.kind !== 'file') return [];
  const representation = contract.info?.representation;
  const candidates = [...(contract.data_format?.representations || []).filter(value => value.startsWith('file.')).map(value => value.slice(5)),
    ...(typeof representation?.const === 'string' ? [representation.const] : representation?.enum?.filter(value => typeof value === 'string') as string[] || [])];
  return [...new Set(candidates.filter(value => /^[A-Za-z0-9_.-]+$/.test(value)))];
}

/** File-path ABI only; a copy preserves bytes and deliberately performs no scientific conversion. */
export function portTemplate(language: ScriptLanguage, format: string): string {
  if (!/^[A-Za-z0-9_.-]+$/.test(format)) throw Error('A declared file format is required');
  const comment = language === 'c' || language === 'cpp' ? '//' : '#';
  const header = `${comment} input: data file.${format}\n${comment} output: result file.${format}\n${comment} Replace the byte-preserving copy with your analysis.\n`;
  if (language === 'python') return header + `import argparse\nimport shutil\n\np = argparse.ArgumentParser()\np.add_argument('--in-data', required=True)\np.add_argument('--out-result', required=True)\nargs = p.parse_args()\nshutil.copyfile(args.in_data, args.out_result)\n`;
  if (language === 'r') return header + `args <- commandArgs(trailingOnly = TRUE)\nvalue <- function(flag) {\n  i <- match(flag, args)\n  if (is.na(i) || i == length(args)) stop(paste('Missing', flag))\n  args[[i + 1L]]\n}\nif (!file.copy(value('--in-data'), value('--out-result'), overwrite = TRUE)) stop('Copy failed')\n`;
  if (language === 'cpp') return header + `#include <fstream>\n#include <string>\nint main(int argc, char** argv) {\n  std::string input, output;\n  for (int i = 1; i + 1 < argc; i += 2) {\n    if (std::string(argv[i]) == "--in-data") input = argv[i + 1];\n    else if (std::string(argv[i]) == "--out-result") output = argv[i + 1];\n    else return 2;\n  }\n  if (input.empty() || output.empty()) return 2;\n  std::ifstream src(input, std::ios::binary);\n  std::ofstream dst(output, std::ios::binary);\n  if (!src || !dst) return 1;\n  char buffer[65536];\n  while (src.read(buffer, sizeof(buffer)) || src.gcount()) dst.write(buffer, src.gcount());\n  dst.flush();\n  return src.bad() || !dst ? 1 : 0;\n}\n`;
  return header + `#include <stdio.h>\n#include <string.h>\nint main(int argc, char** argv) {\n  const char *input = NULL, *output = NULL;\n  for (int i = 1; i + 1 < argc; i += 2) {\n    if (!strcmp(argv[i], "--in-data")) input = argv[i + 1];\n    else if (!strcmp(argv[i], "--out-result")) output = argv[i + 1];\n    else return 2;\n  }\n  if (!input || !output) return 2;\n  FILE *src = fopen(input, "rb"), *dst = fopen(output, "wb");\n  if (!src || !dst) { if (src) fclose(src); if (dst) fclose(dst); return 1; }\n  char buffer[65536]; size_t n; int failed = 0;\n  while ((n = fread(buffer, 1, sizeof(buffer), src))) if (fwrite(buffer, 1, n, dst) != n) { failed = 1; break; }\n  failed |= ferror(src); fclose(src);\n  if (fclose(dst)) failed = 1;\n  return failed ? 1 : 0;\n}\n`;
}

export function PortTemplateMenu({ports, initialIndex, direction, onCopy}: {
  ports: (PortContract | null)[]; initialIndex: number; direction: 'input' | 'output'; onCopy: (code: string) => void;
}) {
  const [index, setIndex] = useState(initialIndex), [chosen, setChosen] = useState('');
  const formats = fileFormats(ports[index]);
  const format = formats.includes(chosen) ? chosen : formats[0];
  return <div className="port-template-menu">
    <div className="context-caption">{direction === 'input' ? t('输入接头模板') : t('输出接头模板')}</div>
    {ports.length > 1 && <label className="field"><span>{t('端口')}</span><select value={index} onChange={event => setIndex(Number(event.target.value))}>{ports.map((_, i) => <option key={i} value={i}>{i + 1}</option>)}</select></label>}
    {formats.length ? <>
      {formats.length > 1 && <label className="field"><span>{t('文件格式')}</span><select value={format} onChange={event => setChosen(event.target.value)}>{formats.map(value => <option key={value}>{value}</option>)}</select></label>}
      {(['python', 'r', 'c', 'cpp'] as const).map(language => <button key={language} role="menuitem" onClick={() => onCopy(portTemplate(language, format))}>{t('复制 {language} 接头', {language: {python: 'Python', r: 'R', c: 'C', cpp: 'C++'}[language]})}<small>{format}</small></button>)}
    </> : <p className="helper">{t('此端口未声明文件格式。请先使用输出或显式转换算子。')}</p>}
  </div>;
}
