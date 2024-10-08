# 3DSC for Metashape
3DSC tools for Metashape

This collection of scripts is aimed to make it possible a pipeline between Metashape and Blender 3DSC addon (3D survey collection). Using these scripts you can:

1 - "3DSC_MS_import_multiple_models": import a folder with a series of mesh tiles (OBJs) prepared in Blender using the 3DSC add-on.

1a - you need to open in metashape a project with a single chunk containing only a sparse point cloud (delete meshes and dense point clouds, if any).
1b - prepare a folder with meshes (tiles) to be texturized and, eventually with a txt file (I suggest SHIFT.txt as a name) with shifting coordinates values. This file should contain a single line like this: "EPSG::3004 1000 1000 0" that means that Metashape will import meshes as EPSG:3004 (don't miss the double ":") shifting the coordinates of 1000 units on x and y axes (no shifting on z axis).
1c - start the script and, when asked, select the folder that contains the meshes (OBJs) and eventually the txt file. Metashape will create several chunks for each imported mesh .
 
2 - "3DSC_MS_texturize": This script will texturize the chunks (imported meshes) using the Demetrescu-d'Annibale formula to texture resolution (100squared meters with 6x4096px = 1.26mm/px resolution, suitable for HI resolution VR experiences).

3 - "3DSC_MS_rename_chunks": This script will rename the chunks using a numbered list (1,2,3 etc..). In the majority of cases you need to do it.

4 - "3DSC_MS_export_multiple_models": This script will export the textured meshes. When asked, select a folder for the export. If you provide a folder with a SHIFT.txt file, you will get a shifted model, suitable for a pipeline inside a CG software (like Blender).

--------------------------------------------------------

## 3DSC for Metashape - Version 1.0 Release Notes
Release Date: 07/10/2024

We are excited to announce the release of 3DSC for Metashape version 1.0! This update introduces several new features and improvements aimed at enhancing performance and flexibility when working with large-scale 3D models.

Key Features and Updates:
### Extended Texture Support for Large Models

Added modules to support the texturing of models up to 200 square meters (previously limited to 100 square meters). This allows for better handling of larger environments and assets without compromising on detail.

Mesh Validation Enhancements

Improved controllers that now accurately identify and manage meshes that have no area, preventing the errors that previously occurred during processing. This ensures a smoother workflow and improved error handling.

### Tiled Model Import

Introduced support for importing tiled models, expanding the range of model types that can be efficiently processed and integrated into your projects.

### New Import/Export Scripts

Added new scripts for importing and exporting models. These include options to import a second model or export using the Shift function, offering greater flexibility in model manipulation and positioning.

### Additional Improvements:
Performance optimizations for handling large datasets.
Minor bug fixes and UI/UX improvements.
