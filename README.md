# 3DSC for Metashape

3DSC tools for Metashape is a collection of Python scripts designed to create an efficient workflow between Metashape and the Blender 3DSC addon (3D Survey Collection). This toolkit simplifies the process of importing, texturizing, and exporting 3D models with proper georeferencing and optimization.

## The chain

Photos → alignment → a high mesh, cleaned (trees, scaffolding, noise) → three **masters** by polygon density:

1. **geometric super master**, above 10 000 polygons/m²: kept aside, also for print;
2. **texturable master**, 10 000/m²: the Cesium **tileset** and the normal maps come from it;
3. **tileable master**, 1 000/m² = LOD0: cut into **blocks**, textured with the Demetrescu-D'Annibale rule, then LODs and normal maps, for Blender.

Clean the high model and run *Masters* again: the lighter masters inherit the cleaning.
Two words are kept apart: a **block** is a piece of mesh physically cut (one file per block); the **tileset** is Metashape's quadtree exported as 3D Tiles.

## The menu

**3DSC Metashape Tools**
0. **Operator (ORCID)…** — who runs the operations, set once and remembered on this computer (like the shift); written in the stamp of every export. Optionally asked again at every export.
1. **Shift…** — load SHIFT.txt, see the file and the numbers, clear. The shift is saved **in the project** (`doc.meta`) and comes back with the .psx.
2. **Import ›** **Models…** (files or a folder, shift on/off, one chunk per model copied from the **master**, or all in one chunk) · **Photos from Another Project…**
3. **Masters…** — an **inventory** first: every model of the chunk with its faces, density and part in the chain, what is missing and from which model it can be decimated. Nothing is computed when the panel opens: «Measure» counts the faces and measures the surface once (on the lightest model; 40.9 M faces take about 13 s), and keeps the numbers in the model's meta. «Make what is missing» lists the exact decimations and asks before running them.
4. **Blocks…** — the cut of the tileable master on a grid **turned with the monument** and tight on the mesh (see below), with the checks of `ms_blocks`.
5. **Texturing…** — the Demetrescu-D'Annibale rule, **one row per model** (several models of a chunk are textured one by one), with a live simulation (pages, texel, memory) and the reference.
6. **LODs + Normal Maps** (blocks).
7. **Tileset…** — Cesium 3D Tiles (.3tz or folder) with the **screen space error** chosen (desktop 16 / web 24 / mobile 32), version, KTX2/JPEG, Draco, heights onto EGM2008 for that export only, and a check read from the written file.
8. **Export ›** blocks, models, active model with shift, undistorted images.
- **Utility ›** Rename Chunks (pattern `{n}`, `{name}`, `{model}`; the names become file names) · Flag LOD0 (old STEP1).
- **Help ›** Documentation of 3DSC for Metashape · About · Rule and References.

### The inventory of the masters

Rules: the highest model is the master to **clean** (trees, scaffolding, noise) — every lighter master is decimated from it. Above the texturable density it is the geometric super master (also for print). When no model reaches the texturable density, the highest is **kept for the tileset**: decimation removes detail, it never adds it. LOD0 is made only from a denser model. With no mesh yet, the surface of a reference chunk gives the target face counts.

On Templu Mare 2015 (40.9 M, 6.3 M and 0.6 M faces on about 6 040 m²) it reads: keep the 40.9 M model for the tileset and clean it; the 6.3 M model is already LOD0 (1 041/m²); the 0.6 M model is lighter than LOD0; nothing to make.

### The master

A copy of the photo chunk with **photos and tie points only** (*Import › Models… › Create master from the active chunk*, flagged `3dsc_master` in the chunk's meta). Every imported model and every block lands in a copy of it, so it can be textured from the photos without carrying depth maps, point clouds or other meshes along.

### Blocks on a rotated grid

Metashape's Block Model lays its grid in the CRS, i.e. on the north. 3DSC hands the cut a **local oblique Mercator** centred on the site, scale 1, whose grid is turned by the monument's bearing (`buildModel(blocks_crs=…, blocks_origin=…)`, Metashape 2.3.2; Metashape calls the projection `Oblique_Mercator`, EPSG 9815). The bearing comes from, in order of preference:
- the **project grid** (see below);
- a **line drawn** along the walls (Draw Polyline, then select it);
- **two markers** along the axis;
- a bearing typed;
- **fit to the mesh**: the tightest rectangle around the mesh footprint — right for a monument alone, not for a site surrounded by terrain, where the terrain decides the rectangle;
- north.

**Preview the grid in the view** draws the cells that hold mesh as orange shapes (group «3DSC grid preview»), with the bearing, where it comes from and the count against a north grid; «Remove preview», Cancel and the cut take it away.

### More epochs, one grid

The first cut can be saved as the **project grid** (`doc.meta["3dsc_grid"]`: the grid CRS, origin, side, bearing). Cutting another chunk — another epoch or hypothesis of the same site — on the project grid gives **the same cells the same names**: `block_x003_y002` is the same piece of ground in 2013 and in 2015. Measured on two synthetic epochs (the second covering half the site): six blocks of 2013, each in the place of its namesake of 2015.

### Blocks as models

By default the blocks become **models of one new chunk** per epoch, copied from the master: no copy of the photos for every block. Metashape 2.3 textures several models of one chunk one by one (each made active in turn): measured on Templu Mare 2015, two pieces textured in 26 s and 16 s, each kept its own texture, and the models already there were untouched. One chunk per block is still offered, and files only. The intermediate block models Metashape leaves in the source chunk are removed after the cut.

The **chunk is never touched**: its CRS and transform stay as they are, nothing rotated is ever saved, and the same bearing gives the same cut. The block files are then exported again by Metashape in the chunk's CRS with a `metadata.xml` like the one of a north cut, plus `grid_crs.wkt`: from there on a rotated cut is the same folder as a north one.

Measured on a 40 × 16 m slab turned by 10° (Stereo70, 8 m blocks): north grid 18 cells, rotated grid 10; the 10 blocks brought back into master copies lie on the slab, cell by cell.

### Texturing: the Demetrescu-D'Annibale rule

Pages = round(area · (1000 / texel)² / (atlas² · UV ratio)), with texel 1.26 mm, atlas 4096 px, UV ratio 0.6 (Eq. 1). A large area needs no cap: either more pages at the same texel, or a maximum of pages and the coarser texel it gives (the old «200 m²» command did the latter without saying so). With many chunks the panel offers a new project holding the reference chunk and the blocks only; the open project is unchanged.

> Demetrescu, E., Ferdani, D., Fanini, B., D'Annibale, E., Berto, S., Morretta, S., Rea, R. (2026). Digital Replicas and 3D Virtual Reconstructions for Large Excavations in Urban Archaeology: Methods, Tools, and Techniques Drawn from the "Metro C" Case Study in Rome. *Remote Sensing* 18(2), 203. https://doi.org/10.3390/rs18020203

### Tileset: heights

When the chunk's CRS has no vertical datum and its markers carry heights, the panel says so. If they are orthometric, the export can move them onto EGM2008 **in memory**: marker heights H + N − Δdatum, `updateTransform`, export, then markers and transform are put back exactly (measured on Templu Mare 2015: restored to the last bit). N comes from Metashape's EGM2008 geoid, or from a JSON table `{marker: N}`.

## Installation

1. Download the repository to a folder on your computer (keep the files together)
2. In Metashape, go to **Tools > Run Script** and select the `3DSC_MS_GUI.py` file
3. The **3DSC Metashape Tools** menu will appear in the Metashape interface

### The files

`3DSC_MS_GUI.py` is the menu. It imports modules that must stay **in the same folder**:
- **`ms_panels.py`** - the panels (PySide2)
- **`ms_dd.py`** - the Demetrescu-D'Annibale rule and the master densities (pure)
- **`ms_grid.py`** - the rotated grid of the cut (pure)
- **`ms_tileset.py`** - the check of an exported tileset, read from the file (pure)
- **`ms_blocks.py`** - the STEP2 blocks read from the files Metashape writes: the check, the grid names, the small tiles
- **`dtc_stamp_ms.py`** - the stamp of every export, with `vendor/dtcstamp.py` (dtcstamp 0.1.3, Apache 2.0)

- **`ms_appender.py`**, **`ms_append_ms.py`**, **`ms_append_gui.py`** - the appender between projects: the decisions (pure), their application with the Metashape API, the dialog

`ms_blocks.py`, `dtc_stamp_ms.py`, `ms_appender.py`, `ms_dd.py`, `ms_grid.py` and `ms_tileset.py` are pure Python and are tested without Metashape: `python3 -m unittest discover tests`.
The version number is aligned with the 3DSC Blender extension (`dsc_tools`).

### STEP2 - the blocks

STEP2 builds a Metashape **Block Model** (`buildModel(split_in_blocks=True, export_blocks=True)`) and then, on the files:
- **stops** when two blocks have the same content (the file without its `mtllib` line), or the same bbox and face count, or when all the blocks add up to more than 1.5 × the faces of the source model. This is what the 0c2559a version produced: 32 copies of the whole model (`exportModel(clip_to_boundary=True)` clips to the boundary *shapes*, not to the region);
- with **min faces** (2000 by default, 0 = off), merges each smaller tile into its largest touching neighbour, or only flags it. The merged tile's files go into `_absorbed/`, never deleted;
- **names** each tile `block_xNNN_yNNN` from its centre, in the grid of the cut (side `blocks_size`), counted from the corner of the model; `.obj`, `.mtl`, `.tls` and the `mtllib` line are renamed together, and Metashape's name («Tile 93341-516978») stays in `chunk.meta["3dsc_tile_source_name"]` and in the stamp.

### Append photos from another project

*Import › Append Photos from Another Project…* opens a dialog. You choose the source project and chunk, and which photos: the selected cameras, one camera group, the enabled ones or all. They are added to the **active chunk** as a new camera group; photos already in the project (same file, or same content if you ask) are skipped. Along with them, as you choose:
- **calibration**: the source calibration groups copied as initial values (optionally fixed), or the target group with the same name, or new groups from EXIF;
- **markers**: projections merged into the markers with the same name, or new markers with a prefix; their reference coordinates are copied, transformed between two coordinate systems, or brought along unchecked when one of the two systems is local;
- **masks**, **camera reference**, the enabled/disabled state.

Nothing is aligned: afterwards run *Align Photos* with «Reset current alignment» unchecked, then *Optimize Cameras*. The target chunk records the operation in its `meta` (`3dsc_append_<time>`: source, counts, options).

### Stamps

Every export (mesh, blocks, tiles, undistorted images) writes `<file>.stamp.json` beside each file (an OBJ with its MTL and textures is one *file set*). The stamp says what Metashape recorded: the parameters of the operations in the chunk's and the asset's `meta`, the photos by sensor (by their own stamps, or as the tree of their folder), the software. The asset in the project is the master; its address (`psx://<project>#<chunk>/<asset>/<key>`) is private and only goes in the `<file>.hints.json` beside the stamp.

At each export a dialog asks for an **ORCID iD (optional)**: it is checked (ISO 7064 MOD 11-2), remembered for the next export, and written as a declared operator. Left empty, the stamp names no operator: the agent is the software.

---

## SHIFT.txt File Format

The **SHIFT.txt** file is used to apply coordinate transformations during import and export operations.

### Format

```
CRS X Y Z
```

Where:
- **CRS**: Coordinate Reference System or special keyword
- **X, Y, Z**: Shift values (integers or decimals)

### Supported CRS Options

#### 1. Local Coordinates (No Geographic Reference)

For models in local coordinate systems:

```
LOCAL 16000.0 29000.0 0.0
```

Alternative keywords: `NONE`, `LOCAL_CS`

✅ **Applies shift only, without setting a geographic CRS**

#### 2. Geographic Coordinates (EPSG)

For georeferenced models:

```
EPSG::32633 500000.0 4500000.0 0.0
```

Common EPSG codes:
- `EPSG::32633` - UTM 33N WGS84
- `EPSG::32632` - UTM 32N WGS84
- `EPSG::3004` - Monte Mario Italy zone 2
- `EPSG::4326` - WGS84 lat/lon

✅ **Applies shift AND sets the coordinate system**

### When to Use Which Option

| Situation | SHIFT.txt Format | Example |
|-----------|------------------|---------|
| Local coordinates (Blender export) | `LOCAL` | `LOCAL 16000.0 29000.0 0.0` |
| High coordinates to normalize | `LOCAL` | `LOCAL 16000.0 29000.0 100.0` |
| Georeferenced model (UTM, etc.) | `EPSG::xxxxx` | `EPSG::32633 500000.0 4500000.0 0.0` |
| Export for GIS software | `EPSG::xxxxx` | `EPSG::3004 1000000.0 2000000.0 0.0` |

### Scripts Supporting SHIFT.txt

All of these tools support both LOCAL and EPSG coordinate systems:

1. ✅ Import Multiple Models
2. ✅ Import Single Model with Shift
3. ✅ Import Tiled Models
4. ✅ Export Multiple Models
5. ✅ Export Single Model with Shift
6. ✅ Export Tiled Models

---

## Workflow Examples

### Example 1: Importing and Texturizing Models

**Step 1: Prepare Your Data**
- Export segmented tiles from Blender using 3DSC
- Create a folder with your OBJ files
- Add SHIFT.txt file if needed (see format above)

**Step 2: Import into Metashape**
1. Open Metashape project with aligned photos and sparse point cloud
2. **3DSC Metashape Tools > Import > Import Multiple Models**
3. Select folder containing OBJ files (and SHIFT.txt if present)
4. Script creates one chunk per tile

**Step 3: Apply Textures**
1. **3DSC Metashape Tools > Texturing > Texturize Models**
2. Script automatically calculates optimal texture resolution using the **Demetrescu-d'Annibale formula**:
   - Standard: 100m² with 6×4096px textures (1.26mm/px)
   - Extended: Up to 200m² with 12×4096px textures

**Step 4: Rename Chunks (Optional)**
1. **3DSC Metashape Tools > Utility > Rename Chunks**
2. Simplifies chunk management with sequential numbering

**Step 5: Export Textured Models**
1. **3DSC Metashape Tools > Export > Export Multiple Models**
2. Select destination folder
3. Add SHIFT.txt if needed (same format as import)
4. Exports OBJ + MTL + textures

### Example 2: Single Model Workflow

For working with a single model instead of tiles:

1. **Import Single Model with Shift** - Import one model with optional SHIFT
2. **Texturize Models** - Apply automatic texturing
3. **Export Single Model with Shift** - Export with preserved coordinates

### Example 3: Tiled Model Workflow

For working with Metashape's tiled models:

1. **Import Tiled Models** - Reimport previously exported tiles
2. **Export Tiled Models** - Export each tile separately with shift

---

## Texture Resolution Formula

The texturing tools use the **Demetrescu-d'Annibale formula** to calculate optimal texture resolution:

```
N_tex = (10000 / r_texel)² / (t_res² × ratio)
```

Where:
- `r_texel` = target resolution in mm/texel (default: 1.26 mm)
- `t_res` = texture resolution in pixels (default: 4096)
- `ratio` = surface coverage ratio (default: 0.6)

**Example:** For a 100m² tile:
- Calculation: `(10000 / 1.26)² / (4096² × 0.6) ≈ 6`
- Result: **6 textures at 4096×4096 pixels**

### Two Texturing Modes

1. **Standard Mode** (Texturize Models)
   - Optimal for models up to 100m²
   - Uses formula directly

2. **Extended Mode** (Texturize Models 200m² limit)
   - For models up to 200m²
   - Caps at 12 textures maximum
   - Prevents excessive texture generation

---

## Version History

### Version 1.7.0 (Current)
- **Version alignment**: numbering realigned with the 3DSC Blender extension (`dsc_tools`)
- **Global Shift menu**: load a coordinate shift once and reuse it across all import/export operations
- **Guided Workflow menu**: end-to-end pipeline (STEP1 prepare/flag LOD0 → STEP2 cut mesh into blocks → STEP3 texturize → STEP4 generate LODs + normal maps → STEP5 export), preceded by an optional STEP0 global shift
- **Cut Giant Mesh into Blocks**: segment a large mesh directly in Metashape via tiled models, one chunk per block
- **Export Undistorted Images**: export undistorted photos of the active chunk
- STEP2 blocks checked (no identical blocks), named `block_xNNN_yNNN`, small tiles merged or flagged (`ms_blocks.py`)
- Every export stamped with dtcstamp 0.1.3, ORCID optional (`dtc_stamp_ms.py`)

### Version 2.1 (legacy numbering)
- **Single-file architecture**: Consolidated all tools into `3DSC_MS_GUI.py`
- **LOCAL coordinate support**: Full support for local coordinates without EPSG
- **Fixed messageBox errors**: All Metashape API calls corrected
- **Fixed float parsing**: Handles decimal values in SHIFT.txt
- **iPad feature disabled**: Experimental feature commented out

### Version 2.0
- New graphical user interface with organized menu system
- iPad 3D Scanner App integration (experimental)
- Extended texture support for models up to 200m²
- Improved mesh validation and error handling
- Enhanced tiled model import/export

---

## File Structure

### Required Files (keep them together)
- `3DSC_MS_GUI.py` - Main script with the menu
- `ms_blocks.py` - STEP2 blocks: check, names, small tiles
- `dtc_stamp_ms.py` + `vendor/dtcstamp.py` - the stamp of every export

### Optional Files
- `SHIFT.txt` - Coordinate transformation file (placed in same folder as models)
- `README_SHIFT.md` - Detailed SHIFT.txt documentation

### Legacy Files (Can Be Removed)
The following individual script files are no longer needed:
- ~~`import_multiple_models.py`~~
- ~~`export_multiple_models.py`~~
- ~~`texturize_it.py`~~
- ~~`rename_chunks.py`~~
- ~~Any other individual .py scripts~~

---

## Troubleshooting

### Common Issues

**Error: "wrong crs definition string"**
- Check SHIFT.txt format
- Use `LOCAL` for non-georeferenced models
- Verify EPSG code is valid if using geographic coordinates

**Error: "invalid literal for int() with base 10"**
- Use float values in SHIFT.txt: `16000.0` instead of `16000.0`
- Latest version handles this automatically

**Error: "messageBox() takes exactly 1 argument (2 given)"**
- Update to `3DSC_MS_GUI.py` (latest version)

**Models import with wrong position**
- Check SHIFT.txt values match your coordinate system
- Verify shift direction (positive vs negative)

---

## Integration with Extended Matrix Framework

3DSC for Metashape is part of the Extended Matrix ecosystem:

- **3DSC (Blender)** - Model preparation and segmentation
- **3DSC for Metashape** - High-resolution texturing
- **Extended Matrix** - Stratigraphic annotation and analysis

### Typical EM Structure Workflow

```
05_RB/
├── 01_RAW/photos/                    # Original photos
├── 02_PROCESSING/metashape/          # Metashape projects
└── 03_Model_Library/
    └── [ModelName]/
        ├── meshpoly/                 # Segmented tiles (from Blender)
        └── meshpolytex/              # Textured tiles (from Metashape)
```

---

## Experimental Features

### iPad AR Camera Import

⚠️ **Currently Disabled** - This feature is experimental and under development.

To enable (advanced users only):
1. Edit `3DSC_MS_GUI.py`
2. Uncomment line ~41:
   ```python
   ps.app.addMenuItem(label + "/iPad/Import iPad AR Camera Data (EXPERIMENTAL)", self.import_ipad_cameras)
   ```

---

## Credits and License

**Author:** Emanuel Demetrescu  
**Email:** emanuel.demetrescu@gmail.com  
**License:** GNU GPL-3  

**Part of the Extended Matrix Project**
- Website: https://www.extendedmatrix.org
- Documentation: https://www.extendedmatrix.org/docs

---

## Support and Contributions

For issues, questions, or contributions:
- GitHub Issues: [Create an issue]
- Documentation: https://www.extendedmatrix.org/docs
- Email: emanuel.demetrescu@gmail.com

---

## See Also

- [3DSC Blender Add-on](https://github.com/zalmoxes-laran/3D-survey-collection)
- [Extended Matrix Documentation](https://www.extendedmatrix.org/docs)
- [Digital Replica Preparation Workflow](docs/digital_replica_preparation.rst)