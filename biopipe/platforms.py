"""Derived catalog compatibility, not part of the operator authoring protocol."""
from packaging.requirements import Requirement, InvalidRequirement

SYSTEMS = ('linux', 'windows', 'macos')
# Capabilities of BioPipe's supported external execution adapters. Windows may
# use a Linux WSL environment; that does not make the executable Windows-native.
EXTERNAL_SYSTEMS = {name: {'linux'} for name in ('bwa', 'samtools', 'pairtools', 'cooltools')}
EXTERNAL_SYSTEMS['cooler'] = set(SYSTEMS)
PYTHON_SYSTEMS = {'pysam': {'linux', 'macos'}, 'cyvcf2': {'linux', 'macos'},
                  'pywin32': {'windows'}, 'pyobjc': {'macos'}}
PORTABLE = {'numpy', 'scipy', 'pandas', 'matplotlib', 'statsmodels', 'scikit-learn', 'scikit-bio',
            'scikit-image', 'h5py', 'h5netcdf', 'anndata', 'zarr', 'pyarrow', 'fastparquet',
            'networkx', 'seaborn', 'lifelines', 'pydeseq2', 'pyyaml', 'packaging', 'psutil',
            'pillow', 'biopython', 'openpyxl', 'xlrd', 'tables', 'fsspec', 'cooler'}


def systems_status(descriptor):
    unknown = set(descriptor.get('resources', {}).get('external_tools', [])) - EXTERNAL_SYSTEMS.keys()
    if descriptor.get('resources', {}).get('r') is not None:
        unknown.add('R packages')
    for value in descriptor.get('dependencies', []):
        try:
            requirement = Requirement(value)
            if requirement.marker is not None or requirement.name.lower().replace('_', '-') not in PORTABLE | PYTHON_SYSTEMS.keys():
                unknown.add(requirement.name)
        except InvalidRequirement:
            unknown.add(value)
    return 'unknown' if unknown else 'inferred'


def supported_systems(descriptor):
    allowed = set(SYSTEMS)
    for tool in descriptor.get('resources', {}).get('external_tools', []):
        allowed &= EXTERNAL_SYSTEMS.get(tool, set(SYSTEMS))
    for value in descriptor.get('dependencies', []):
        try:
            requirement = Requirement(value)
        except InvalidRequirement:
            continue
        # A platform-conditional dependency can be an implementation fallback;
        # it is not proof that the whole operator requires that platform.
        if requirement.marker is None:
            allowed &= PYTHON_SYSTEMS.get(requirement.name.lower().replace('_', '-'), set(SYSTEMS))
    return [system for system in SYSTEMS if system in allowed]
