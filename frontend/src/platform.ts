/** Windows can run BioPipe, but a few optional readers depend on
 * pysam/pyBigWig, which are not available in the native Windows env. */
export function isWindowsBlocked(platforms?: string[] | null): boolean {
  if (!platforms?.length) return false;
  return !platforms.some((platform) => {
    const value = platform.toLowerCase();
    return value === "win32" || value === "windows";
  });
}
