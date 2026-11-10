"""What a chunk has and what it lacks for the 3DSC chain of masters, pure Python.

From the models of a chunk (faces, and the surface area of the mesh) this
module says which model plays which part, what is missing and what can be
derived, before anything is computed. Rules of E.D. (10 Nov 2026):

- the highest model is the master to CLEAN (trees, scaffolding, noise): the
  lighter masters are decimated from it, so they inherit the cleaning;
- above the texturable density it is the geometric super master (also print);
- when no model reaches the texturable density, the highest is kept for the
  Cesium tileset: decimation removes detail, it never adds it;
- the tileable master (LOD0) is made only if a denser model exists.

Densities are faces per m² of mesh surface. The surface is measured once, on
the lightest model of the chunk (decimations keep the surface: measured on
Templu Mare 2015, 6 287 / 6 242 / 6 039 m² for 40.9 M / 6.3 M / 0.6 M faces),
or taken from a reference chunk when the chunk has no mesh yet.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

TOLERANCE = 0.25   # a model within ±25 % of a target density counts as that master


def _fmt(n: float) -> str:
    return "{:,.0f}".format(n).replace(",", " ")


def name_of(m: Dict[str, object]) -> str:
    return str(m.get("label") or "model %s" % (int(m.get("key", 0)) + 1))


def inventory(models: Sequence[Dict[str, object]], area_m2: Optional[float],
              d_tex: float = 10000, d_til: float = 1000,
              tol: float = TOLERANCE) -> Dict[str, object]:
    """→ ``{"rows", "high", "texturable", "tileable", "plan", "lines", "area"}``.

    ``models``: dicts with ``key``, ``label``, ``faces`` (int or None),
    ``textured`` (bool). ``rows`` adds ``density`` and ``role`` to each;
    ``plan`` lists what would be made (``{"level", "density", "from", "faces"}``);
    ``lines`` is the plain-language report, one finding per line.
    """
    lines: List[str] = []
    rows = []
    for m in models:
        r = dict(m)
        f = m.get("faces")
        r["density"] = (f / area_m2) if (f and area_m2) else None
        r["role"] = ""
        rows.append(r)
    out = {"rows": rows, "high": None, "texturable": None, "tileable": None,
           "plan": [], "lines": lines, "area": area_m2}

    if not rows:
        lines.append("No mesh in this chunk yet: build one at high quality (Workflow › Build Mesh) "
                     "and clean it; the masters come from it.")
        if area_m2:
            lines.append("At the reference surface (%s m²): texturable ≈ %s faces, tileable ≈ %s faces."
                         % (_fmt(area_m2), _fmt(area_m2 * d_tex), _fmt(area_m2 * d_til)))
        return out
    if not area_m2:
        lines.append("Surface not measured yet: press «Measure».")
        return out
    measured = [r for r in rows if r["density"]]
    if not measured:
        lines.append("Models not measured yet: press «Measure».")
        return out

    high = max(measured, key=lambda r: r["faces"])
    out["high"] = high["key"]
    lo_tex, hi_tex = d_tex * (1 - tol), d_tex * (1 + tol)
    lo_til, hi_til = d_til * (1 - tol), d_til * (1 + tol)

    # the high master
    if high["density"] > hi_tex:
        high["role"] = "geometric master (clean it)"
        lines.append("«%s» (%s faces, %s/m²) is the geometric super master, also for print: clean it "
                     "(trees, scaffolding, noise) — the lighter masters are decimated from it."
                     % (name_of(high), _fmt(high["faces"]), _fmt(high["density"])))
    else:
        high["role"] = "high master (clean it)"
        lines.append("«%s» (%s faces, %s/m²) is the highest model: clean it first, it is the base "
                     "of every decimation." % (name_of(high), _fmt(high["faces"]), _fmt(high["density"])))

    # texturable
    tex = [r for r in measured if lo_tex <= r["density"] <= hi_tex]
    if tex:
        t = min(tex, key=lambda r: abs(r["density"] - d_tex))
        t["role"] = (t["role"] + " · " if t["role"] else "") + "texturable → tileset"
        out["texturable"] = t["key"]
        lines.append("Texturable master: «%s» (%s/m²) — the tileset comes from it."
                     % (name_of(t), _fmt(t["density"])))
    elif high["density"] > hi_tex:
        n = int(round(area_m2 * d_tex))
        out["plan"].append({"level": "texturable", "density": d_tex, "from": high["key"], "faces": n})
        lines.append("Missing: texturable master at %s/m² — it can be decimated from «%s» (≈ %s faces)."
                     % (_fmt(d_tex), name_of(high), _fmt(n)))
    else:
        high["role"] += " · keep for the tileset"
        out["texturable"] = high["key"]
        lines.append("No model reaches %s/m²: keep «%s» (%s/m²) for the Cesium tileset — "
                     "decimation removes detail, it never adds it."
                     % (_fmt(d_tex), name_of(high), _fmt(high["density"])))

    # tileable = LOD0
    til = [r for r in measured if lo_til <= r["density"] <= hi_til]
    if til:
        t = min(til, key=lambda r: abs(r["density"] - d_til))
        t["role"] = (t["role"] + " · " if t["role"] else "") + "tileable = LOD0 → blocks"
        out["tileable"] = t["key"]
        lines.append("Tileable master (LOD0): «%s» (%s/m²) — the blocks are cut from it."
                     % (name_of(t), _fmt(t["density"])))
    elif high["density"] > hi_til:
        n = int(round(area_m2 * d_til))
        out["plan"].append({"level": "tileable", "density": d_til, "from": high["key"], "faces": n})
        lines.append("Missing: tileable master (LOD0) at %s/m² — it can be decimated from «%s» (≈ %s faces)."
                     % (_fmt(d_til), name_of(high), _fmt(n)))
    else:
        lines.append("Every model is lighter than %s/m²: LOD0 cannot be made by decimation; "
                     "build a denser mesh." % _fmt(d_til))

    for r in measured:
        if not r["role"] and r["density"] < lo_til:
            r["role"] = "lighter than LOD0 (preview, LOD)"
        elif not r["role"]:
            r["role"] = "intermediate"
    if not out["plan"]:
        lines.append("Nothing to make: the chain is complete for this chunk.")
    return out


def seconds_to_measure(faces_hint: Optional[int]) -> float:
    """A feel for the wait: about 0.3 s per million faces to count them
    (Templu Mare, M4 Max: 40.9 M faces in 5.6 s)."""
    if not faces_hint:
        return 0.0
    return 0.14 * faces_hint / 1e6
