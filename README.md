# 3DSC for Metashape

3DSC tools for Metashape is a collection of Python scripts designed to create an efficient workflow between Metashape and the Blender 3DSC addon (3D Survey Collection). This toolkit simplifies the process of importing, texturizing, and exporting 3D models with proper georeferencing and optimization.

## Main Features

With these scripts you can:

1. Import 3D models (single, multiple, tiled) with or without coordinate shifts
2. Apply intelligent texturization based on model area (with regular and 200m² limit options)
3. Export models in various formats with coordinate systems preserved
4. Import camera positions from iPad's 3D Scanner App, leveraging AR tracking for better initial alignment
5. Generate Level of Detail (LOD) models for visualization optimization

## Installation

1. Download the scripts to a folder on your computer
2. In Metashape, go to Tools > Run Script and select the `3DSC_MS_GUI.py` file
3. The 3DSC Metashape Tools menu will appear in the Metashape interface

## Workflow Example

### Importing and Texturizing Models

1. **Import Models**: Use "Import Multiple Models" to import OBJ files prepared in Blender using the 3DSC addon
   - You need to open a Metashape project with a single chunk containing only a sparse point cloud (delete meshes and dense point clouds if any)
   - Prepare a folder with meshes (tiles) to be texturized with an optional SHIFT.txt file (e.g., "EPSG::3004 1000 1000 0")
   - The script will create several chunks for each imported mesh

2. **Texturize Models**: Apply the Demetrescu-d'Annibale formula for texture resolution
   - Regular mode: 100m² with 6×4096px textures (1.26mm/px resolution, suitable for high-resolution VR)
   - Extended mode: Support for models up to 200m² without compromising detail

3. **Rename Chunks**: Simplify chunk management by renaming them sequentially (1, 2, 3, etc.)

4. **Export Models**: Export textured meshes with coordinate shifts preserved for seamless integration with other GIS or 3D software

### Working with iPad 3D Scanner App Data

1. Capture your subject using the "3D Scanner App" on iPad
2. Transfer the captured data folder to your computer
3. Use the "Import iPad AR Camera Data" function in 3DSC Tools
4. The script will:
   - Import the images
   - Read the JSON files containing camera position data from the AR tracking
   - Apply the initial alignment from the AR data
   - Optionally refine the alignment while maintaining the AR data as constraints
   - Filter out poorly aligned cameras if requested

## Version 2.0 Release Notes
Release Date: April 25, 2025

This major update introduces several significant improvements and new features:

### New Graphical User Interface
- Added a comprehensive menu system in Metashape for easy access to all tools
- Organized tools into logical categories for better workflow management

### iPad 3D Scanner App Integration
- Support for importing data from the iPad 3D Scanner App
- Utilizes AR tracking data for better initial camera alignment
- Options to optimize alignment while respecting AR constraints
- Intelligent filtering of poorly aligned cameras

### Extended Texture Support for Large Models
- Added modules to support texturing of models up to 200 square meters (previously limited to 100 square meters)
- Optimized algorithms for handling larger environments without compromising on detail

### Mesh Validation Enhancements
- Improved controllers that accurately identify and manage meshes with no area
- Prevents errors that previously occurred during processing
- Ensures a smoother workflow and improved error handling

### Tiled Model Import and Export
- Enhanced support for importing and exporting tiled models
- Better handling of large datasets through tiling
- Maintains proper coordinate systems across tiles

### Additional Improvements
- Unified interface for all import/export operations
- Performance optimizations for handling large datasets
- Improved error handling and user feedback
- Minor bug fixes and UI/UX improvements

## Planned Future Features
- Direct integration with GIS and BIM workflows
- Support for additional 3D data capture devices and formats
- Machine learning-based optimization for texture generation
- Expanded LOD generation capabilities

## Credits and License
Developed by Emanuel Demetrescu (emanuel.demetrescu@gmail.com)
Licensed under CC-BY