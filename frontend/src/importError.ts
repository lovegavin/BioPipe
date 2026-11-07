import {t} from './i18n';

export function importErrorMessage(value: {code?: string; message?: string; details?: unknown}) {
  const details = value.details as {resource?: unknown; directory?: unknown; reason?: string} | undefined;
  if (value.code !== 'workflow_resource_error' || typeof details?.resource !== 'string' || typeof details.directory !== 'string')
    return value.message;
  const reasons: Record<string, string> = {
    missing: t('文件不存在'), not_file: t('此路径是文件夹'), encoding: t('文件须为 UTF-8 编码'),
    invalid_json: t('JSON 格式有误'), invalid_script: t('脚本语法有误'), unreadable: t('文件不可读，请检查权限'),
  };
  return t('无法导入 {file}：{reason}。当前项目目录：{directory}。请将 YAML 和配套文件放在工作区的同一项目目录，修改导入基础目录后重试，或导入完整路线 ZIP。', {
    file: details.resource, directory: details.directory,
    reason: reasons[details.reason ?? ''] ?? value.message ?? t('文件不可读，请检查权限'),
  });
}
