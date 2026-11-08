"""The Demetrescu-D'Annibale texturing rule, pure Python (no Metashape inside).

How many texture pages a mesh needs so that one texel covers about a
millimetre of surface: Eq. (1) of Demetrescu et al. 2026 (Remote Sensing 18,
203). The texel side is 1.26 mm, the pages are 4096 px atlases, and 0.6 is the
share of each atlas the UV islands really fill. The same rule, read backwards,
gives the texel a fixed number of pages reaches: so a large area never needs a
cap (the old «200 m²» limit), only a choice between more pages and a coarser
texel.

It also holds the polygon densities of the 3DSC chain of masters.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

TEXEL_MM = 1.26        # side of one texel on the surface, mm
ATLAS_PX = 4096        # side of one texture page, px
UV_RATIO = 0.6         # share of the page filled by UV islands

# polygons per m² of the masters (3DSC chain, E.D. 8 Nov 2026)
DENSITY_GEOMETRIC = 10000   # the geometric super master is ABOVE this
DENSITY_TEXTURABLE = 10000  # the texturable master: tileset and normal maps
DENSITY_TILEABLE = 1000     # the tileable master = LOD0, cut into blocks

BIBLIOGRAPHY = (
    "Demetrescu, E., Ferdani, D., Fanini, B., D'Annibale, E., Berto, S., "
    "Morretta, S., Rea, R. (2026). Digital Replicas and 3D Virtual "
    "Reconstructions for Large Excavations in Urban Archaeology: Methods, "
    "Tools, and Techniques Drawn from the “Metro C” Case Study in "
    "Rome. Remote Sensing 18(2), 203. https://doi.org/10.3390/rs18020203",
)
RULE_LINE = ("Pages = round(area · (1000 / texel)² / (atlas² · UV ratio)) "
             "— Demetrescu-D'Annibale rule, Eq. 1")


def _round_half_up(x: float) -> int:
    """The paper's rounding: 0.5 always goes up (Python's round() would not)."""
    return int(math.floor(x + 0.5))


def pages_for(area_m2: float, texel_mm: float = TEXEL_MM, atlas_px: int = ATLAS_PX,
              uv_ratio: float = UV_RATIO) -> int:
    """Texture pages for ``area_m2`` at ``texel_mm`` (at least 1)."""
    if area_m2 <= 0:
        return 0
    texels = area_m2 * (1000.0 / texel_mm) ** 2
    return max(1, _round_half_up(texels / (atlas_px * atlas_px * uv_ratio)))


def texel_for(area_m2: float, pages: int, atlas_px: int = ATLAS_PX,
              uv_ratio: float = UV_RATIO) -> float:
    """The texel (mm) that ``pages`` pages give on ``area_m2``."""
    if area_m2 <= 0 or pages <= 0:
        return 0.0
    usable = pages * atlas_px * atlas_px * uv_ratio
    return 1000.0 / math.sqrt(usable / area_m2)


def simulate(area_m2: float, texel_mm: float = TEXEL_MM, atlas_px: int = ATLAS_PX,
             uv_ratio: float = UV_RATIO, max_pages: Optional[int] = None) -> Dict[str, object]:
    """What the rule gives for one mesh, and the two roads when it is a lot.

    → ``{"area", "pages", "texel", "over", "pages_cap", "texel_cap"}``: ``pages``
    at ``texel_mm``; with ``max_pages`` and more pages than that, ``over`` is
    True and ``texel_cap`` is the texel the capped pages reach.
    """
    pages = pages_for(area_m2, texel_mm, atlas_px, uv_ratio)
    out = {"area": float(area_m2), "pages": pages,
           "texel": texel_for(area_m2, pages, atlas_px, uv_ratio) if pages else 0.0,
           "over": False, "pages_cap": None, "texel_cap": None}
    if max_pages and pages > max_pages:
        out.update(over=True, pages_cap=int(max_pages),
                   texel_cap=texel_for(area_m2, int(max_pages), atlas_px, uv_ratio))
    return out


def pixels_mb(pages: int, atlas_px: int = ATLAS_PX) -> float:
    """Uncompressed RGB size of ``pages`` pages, MB (a feel for memory)."""
    return pages * atlas_px * atlas_px * 3 / 1e6


def faces_for(area_m2: float, density_per_m2: float) -> int:
    """Faces a master of ``density_per_m2`` polygons/m² needs on ``area_m2``."""
    return max(1, int(round(area_m2 * density_per_m2)))
