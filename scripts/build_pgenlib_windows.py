"""Build the missing Windows pgenlib wheel from verified upstream sources.

Run with CPython 3.11 x64, NumPy 2.x, Cython >=3.1, build and setuptools in an
x64 MSVC developer prompt with clang-cl on PATH. Windows compiler flags, standard
C runtime aliases/headers and an explicit NumPy int32 pointer cast adapt the
upstream binding without changing genotype algorithms. zlib is linked statically.
The patched source
archive is retained beside the wheel for reproducibility and LGPL compliance.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile


def extract(archive, destination, digest):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError(f'Unexpected upstream source hash: {archive.name}')
    with tarfile.open(archive) as source:
        source.extractall(destination, filter='data')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pgenlib-sdist', required=True, type=Path)
    parser.add_argument('--zlib-sdist', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pgen-build-') as temp:
        work = Path(temp)
        extract(args.pgenlib_sdist, work, '3807cbf34888a51bf5de60ad242d95258fc78619725c1410190e407c1c3aca20')
        extract(args.zlib_sdist, work, 'bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16')
        source = work / 'pgenlib-0.95.1'
        shutil.copytree(work / 'zlib-1.3.2', source / 'src/zlib')
        setup = source / 'setup.py'
        text = setup.read_text(encoding='utf-8')
        text = text.replace('import setuptools', '''import setuptools
import shutil
from setuptools.command.build_ext import build_ext
from setuptools.command.build_clib import build_clib
# PLINK uses GNU/Clang vector extensions. Use clang-cl with the Microsoft ABI,
# SDK, linker and C runtime, rather than rewriting scientific native code.
_clang = shutil.which('clang-cl.exe')
if not _clang:
    raise RuntimeError('clang-cl.exe must be on PATH')
def configure(compiler):
    if not compiler.initialized:
        compiler.initialize()
    compiler.cc = _clang
    compiler.compile_options = [v for v in compiler.compile_options if v != '/GL']
class ClangExt(build_ext):
    def build_extensions(self):
        configure(self.compiler)
        super().build_extensions()
class ClangLib(build_clib):
    def build_libraries(self, libraries):
        configure(self.compiler)
        super().build_libraries(libraries)
''')
        text = text.replace('setuptools.setup(', 'setuptools.setup(cmdclass={"build_ext": ClangExt, "build_clib": ClangLib},')
        old_flags = '["-std=c++11", "-Wno-unused-function", "-Wno-cpp", "-DNO_CPP11_TYPE_ENFORCEMENT", "-DZSTD_DISABLE_ASM", "-DLIBDEFLATE_STATIC"]'
        if old_flags not in text or '["-std=c++11", "-lz"]' not in text:
            raise ValueError('Upstream setup.py changed; review the Windows build recipe')
        text = text.replace(old_flags, '["/std:c++17", "/DNO_CPP11_TYPE_ENFORCEMENT", "/DZSTD_DISABLE_ASM", "/DLIBDEFLATE_STATIC", "/Dfseeko64=_fseeki64", "/Dftello64=_ftelli64"]')
        text = text.replace('["-std=c++11", "-lz"]', '[]')
        text = text.replace("['src/plink2/libdeflate']", "['src/plink2/libdeflate', 'src/zlib']")
        zlib_files = ['adler32', 'compress', 'crc32', 'deflate', 'gzclose', 'gzlib',
                      'gzread', 'gzwrite', 'inflate', 'infback', 'inftrees',
                      'inffast', 'trees', 'uncompr', 'zutil']
        text = text.replace('ext_modules = [',
            "# BioPipe Windows build: zlib 1.3.2 is linked into the extension.\n"
            + f"clib[1]['sources'] += {['src/zlib/'+name+'.c' for name in zlib_files]!r}\n\n"
            + 'ext_modules = [')
        setup.write_text(text, encoding='utf-8')
        binding = source / 'src/pgenlib/pgenlib.pyx'
        code = binding.read_text(encoding='utf-8')
        old = 'GenoarrToInt32sMinus9(raregeno_buf, difflist_len, &(geno_arr[0]))'
        if old not in code:
            raise ValueError('Review the upstream NumPy int32 pointer conversion')
        # On Windows NumPy int32 is a C long, while stdint int32_t is an int.
        # Both are 32 bits; use the explicit cast already used by other calls.
        code = code.replace(old, 'GenoarrToInt32sMinus9(raregeno_buf, difflist_len, <int32_t*>(&(geno_arr[0])))')
        binding.write_text(code, encoding='utf-8')
        for name in ['pgenlib_write.cc', 'plink2_memory.cc']:
            native = source / 'src/plink2/include' / name
            code = native.read_text().replace('#include <unistd.h>', '#include <io.h>')
            native.write_text(code)
        # The Python binding accepts UTF-8 bytes, whereas the Windows CRT's
        # narrow fopen/unlink use the process ANSI code page. Convert filenames
        # explicitly without changing the process locale or copying input data.
        base = source / 'src/plink2/include/plink2_base.h'
        shim = r'''
#include <errno.h>
#include <io.h>
#include <windows.h>
static inline wchar_t* BiopipeWidePath(const char* path) {
  int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, NULL, 0);
  if (!count) { errno = EINVAL; return NULL; }
  wchar_t* result = (wchar_t*)malloc((size_t)count * sizeof(wchar_t));
  if (!result) { errno = ENOMEM; return NULL; }
  if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, result, count)) {
    free(result); errno = EINVAL; return NULL;
  }
  return result;
}
static inline FILE* BiopipeFopenUtf8(const char* path, const char* mode) {
  wchar_t* wide = BiopipeWidePath(path);
  if (!wide) return NULL;
  wchar_t wide_mode[16];
  size_t n = strlen(mode);
  if (n >= 16) { free(wide); errno = EINVAL; return NULL; }
  for (size_t i = 0; i <= n; ++i) wide_mode[i] = (unsigned char)mode[i];
  FILE* result = _wfopen(wide, wide_mode);
  free(wide);
  return result;
}
static inline int BiopipeUnlinkUtf8(const char* path) {
  wchar_t* wide = BiopipeWidePath(path);
  if (!wide) return -1;
  int result = _wunlink(wide);
  free(wide);
  return result;
}
'''
        base.write_text(base.read_text().replace('#endif  // __PLINK2_BASE_H__', shim + '\n#endif  // __PLINK2_BASE_H__'))
        for native in (source / 'src/plink2/include').glob('*.cc'):
            code = native.read_text().replace('fopen(', 'BiopipeFopenUtf8(').replace('unlink(', 'BiopipeUnlinkUtf8(')
            native.write_text(code)
        # Record sources before generated objects/wheels enter the tree.
        shutil.copy2(Path(__file__), source / 'BIOPIPE_WINDOWS_BUILD.py')
        with tarfile.open(output / 'pgenlib-0.95.1-biopipe-windows-source.tar.gz', 'w:gz') as archive:
            archive.add(source, arcname=source.name)
        subprocess.run([sys.executable, '-I', '-m', 'build', '--wheel', '--no-isolation',
                        '--outdir', str(output), str(source)], check=True)


if __name__ == '__main__':
    main()
