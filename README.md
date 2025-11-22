# 3DSC for Metashape

3DSC tools for Metashape is a collection of Python scripts designed to create an efficient workflow between Metashape and the Blender 3DSC addon (3D Survey Collection). This toolkit simplifies the process of importing, texturizing, and exporting 3D models with proper georeferencing and optimization.

## Main Features

With these scripts you can:

1. Import 3D models (single, multiple, tiled) with or without coordinate shifts
2. Apply intelligent texturization based on model area (with regular and 200m² limit options)
3. Export models in various formats with coordinate systems preserved
4. Generate Level of Detail (LOD) models for visualization optimization
5. ~~Import camera positions from iPad's 3D Scanner App~~ *(experimental - currently disabled)*

## Installation

1. Download the scripts to a folder on your computer
2. In Metashape, go to **Tools > Run Script** and select the `3DSC_MS_GUI_FIXED.py` file
3. The **3DSC Metashape Tools** menu will appear in the Metashape interface

### Single File Solution

**Version 2.1** consolidates all functionality into a single file:
- **`3DSC_MS_GUI_FIXED.py`** - Main GUI with all tools integrated

This replaces the previous multiple-script approach for easier management and installation.

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

### Version 2.1 (Current)
- **Single-file architecture**: Consolidated all tools into `3DSC_MS_GUI_FIXED.py`
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

### Required File
- `3DSC_MS_GUI_FIXED.py` - Main script with all functionality

### Optional Files
- `SHIFT.txt` - Coordinate transformation file (placed in same folder as models)
- `README_SHIFT.md` - Detailed SHIFT.txt documentation

### Legacy Files (Can Be Removed)
The following individual script files are no longer needed as all functionality is now in `3DSC_MS_GUI_FIXED.py`:
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
- Update to `3DSC_MS_GUI_FIXED.py` (latest version)

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
1. Edit `3DSC_MS_GUI_FIXED.py`
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