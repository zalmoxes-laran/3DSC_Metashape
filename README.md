# 3DSC for Metashape

3DSC tools for Metashape is a collection of Python scripts designed to create an efficient workflow between Metashape and the Blender 3DSC addon (3D Survey Collection). This toolkit simplifies the process of importing, texturizing, and exporting 3D models with proper georeferencing and optimization.

## Main Features

With these scripts you can:

1. Load a **global coordinate shift** once and apply it to every import/export
2. Import 3D models (single, multiple, tiled) with or without coordinate shifts
3. Apply intelligent texturization based on model area (with regular and 200m² limit options)
4. **Cut a giant mesh into blocks directly in Metashape** (Block Model), with a check that stops identical blocks, grid names `block_xNNN_yNNN` and the small edge tiles merged or flagged
5. Run a **guided end-to-end workflow** (prepare LOD0 → cut → texturize → LOD → export)
6. Export models in various formats with coordinate systems preserved
7. Export undistorted images of the active chunk
8. Generate Level of Detail (LOD) models for visualization optimization
9. **Stamp every export**: each exported file gets its `<file>.stamp.json` (dtcstamp), read from what Metashape recorded
10. ~~Import camera positions from iPad's 3D Scanner App~~ *(experimental - currently disabled)*

## Installation

1. Download the repository to a folder on your computer (keep the files together)
2. In Metashape, go to **Tools > Run Script** and select the `3DSC_MS_GUI.py` file
3. The **3DSC Metashape Tools** menu will appear in the Metashape interface

### The files

`3DSC_MS_GUI.py` is the menu. It imports two modules that must stay **in the same folder**:
- **`ms_blocks.py`** - the STEP2 blocks read from the files Metashape writes: the check, the grid names, the small tiles
- **`dtc_stamp_ms.py`** - the stamp of every export, with `vendor/dtcstamp.py` (dtcstamp 0.1.3, Apache 2.0)

Both are pure Python and are tested without Metashape: `python3 -m unittest discover tests`.
The version number is aligned with the 3DSC Blender extension (`dsc_tools`).

### STEP2 - the blocks

STEP2 builds a Metashape **Block Model** (`buildModel(split_in_blocks=True, export_blocks=True)`) and then, on the files:
- **stops** when two blocks have the same content (the file without its `mtllib` line), or the same bbox and face count, or when all the blocks add up to more than 1.5 × the faces of the source model. This is what the 0c2559a version produced: 32 copies of the whole model (`exportModel(clip_to_boundary=True)` clips to the boundary *shapes*, not to the region);
- with **min faces** (2000 by default, 0 = off), merges each smaller tile into its largest touching neighbour, or only flags it. The merged tile's files go into `_absorbed/`, never deleted;
- **names** each tile `block_xNNN_yNNN` from its centre, in the grid of the cut (side `blocks_size`), counted from the corner of the model; `.obj`, `.mtl`, `.tls` and the `mtllib` line are renamed together, and Metashape's name («Tile 93341-516978») stays in `chunk.meta["3dsc_tile_source_name"]` and in the stamp.

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