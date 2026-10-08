# src/core/forms/__init__.py
"""In-memory forms: the canonical domain objects of BioPipe.

A *form* is a minimal, closed, well-defined data structure that
pipelines consume and produce. Readers convert file formats into
forms; writers convert forms back into files; pipelines never touch
raw file formats.

Design principles
-----------------
* One form = one physical data class.
* Every form exposes ``validate()`` and raises :class:`ValidationError`.
* Indexes are always IDs (sample_id, variant_id), never positional.
* Sample-indexed forms implement the :class:`SampleIndexed` protocol,
  enabling form-agnostic alignment.
"""

from src.core.forms.protocol import SampleIndexed
from src.core.forms.genotype import GenotypeMatrix
from src.core.forms.variant import VariantTable
from src.core.forms.sample import SampleTable
from src.core.forms.table import Table
from src.core.forms.result import ResultTable

__all__ = [
    "SampleIndexed",
    "GenotypeMatrix",
    "VariantTable",
    "SampleTable",
    "Table",
    "ResultTable",
]