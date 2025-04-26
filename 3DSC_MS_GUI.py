import Metashape as ps
import os
import sys
import json
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

class MetashapeTools:
    def __init__(self):
        self.doc = ps.app.document
        self.init_gui()
    

    def init_gui(self):
        # Inizializza il menu principale
        label = "3DSC Metashape Tools"
        
        # Rimuovi i menu esistenti prima di aggiungerli (per evitare duplicazioni)
        try:
            ps.app.removeMenuItem(label)
        except:
            pass  # Ignora errori se il menu non esiste

        # Aggiungi i sottomenu per ogni gruppo di funzioni
        ps.app.addMenuItem(label + "/Import/Import Multiple Models", self.import_multiple_models)
        ps.app.addMenuItem(label + "/Import/Import Single Model with Shift", self.import_single_model_with_shift)
        ps.app.addMenuItem(label + "/Import/Import Tiled Models", self.import_tiled_models)
        
        ps.app.addMenuItem(label + "/Texturing/Texturize Models", self.texturize_models)
        ps.app.addMenuItem(label + "/Texturing/Texturize Models (200m² limit)", self.texturize_models_200)
        
        ps.app.addMenuItem(label + "/Export/Export Multiple Models", self.export_multiple_models)
        ps.app.addMenuItem(label + "/Export/Export Single Model with Shift", self.export_single_model_with_shift)
        ps.app.addMenuItem(label + "/Export/Export Tiled Models", self.export_tiled_models)
        
        ps.app.addMenuItem(label + "/Utility/Rename Chunks", self.rename_chunks)
        ps.app.addMenuItem(label + "/Utility/LOD Generator", self.lod_generator)
        
        ps.app.addMenuItem(label + "/iPad/Import iPad AR Camera Data", self.import_ipad_cameras)

    def show_menu(self):
        # Visualizza un messaggio quando si clicca sul menu principale
        ps.app.messageBox("3DSC Metashape Tools", "Select a specific tool from the submenu.") 

    # Implementation of existing scripts
    def import_multiple_models(self):
        try:
            # Get folder of 3D models
            path_folder = ps.app.getExistingDirectory("Specify folder with 3D models: ")
            if not path_folder:
                return
            path_folder += "/"
            
            # Process as in the original script
            file_list = os.listdir(path_folder)
            coord_shift = False
            
            # Look for shift file
            for ob_txt in file_list:
                if ob_txt.endswith(".txt"):
                    file_txt_fullpath = str(path_folder + ob_txt)
                    print(file_txt_fullpath)
                    with open(file_txt_fullpath, 'r', encoding='utf-8') as f:
                        first = f.readline()
                        projection_coor = str(first.split(' ')[0])
                        shift_coor_x = int(first.split(' ')[1])
                        shift_coor_y = int(first.split(' ')[2])
                        shift_coor_z = int(first.split(' ')[3])
                        shift_coor = ps.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
                        coord_shift = True
                        print(f"Using shift coordinates: {shift_coor_x}, {shift_coor_y}, {shift_coor_z}")
            
            # Import each model
            obj_list = []
            chunk_number = 1
            
            for ob in file_list:
                if ob.startswith("."):
                    continue
                    
                if ob.endswith((".obj", ".ply", ".dae")):
                    format_file = str(ob.split(".")[-1])
                    
                    if format_file == "obj":
                        format_file_import = ps.ModelFormat.ModelFormatOBJ
                    elif format_file == "ply":
                        format_file_import = ps.ModelFormat.ModelFormatPLY
                    elif format_file == "dae":
                        format_file_import = ps.ModelFormat.ModelFormatCOLLADA
                        
                    ob_fullpath = str(path_folder + ob)
                    obj_list.append(ob_fullpath)
                    print(f"Importing {ob}")
                    
                    # Create a new chunk or use existing one
                    if chunk_number >= len(self.doc.chunks):
                        # Copy the first chunk if it exists
                        if len(self.doc.chunks) > 0:
                            self.doc.chunk = self.doc.chunks[0]
                            chunk = self.doc.chunks[0].copy()
                        else:
                            chunk = self.doc.addChunk()
                    
                    self.doc.chunk = self.doc.chunks[chunk_number]
                    self.doc.chunk.label = ob
                    
                    # Import with or without shift
                    if coord_shift:
                        self.doc.chunk.importModel(path=ob_fullpath, format=format_file_import, 
                                                 crs=ps.CoordinateSystem(projection_coor), shift=shift_coor)
                    else:
                        self.doc.chunk.importModel(path=ob_fullpath, format=format_file_import)
                        
                    chunk_number += 1
            
            ps.app.update()
            ps.app.messageBox("Import complete", "Models imported successfully!")
            
        except Exception as e:
            ps.app.messageBox("Error", f"An error occurred: {str(e)}")
    
    def import_single_model_with_shift(self):
        try:
            # Ask user to specify a 3D model
            model_path = ps.app.getOpenFileName("Specify the 3D model file:")
            if not model_path:
                return
                
            # Ask user to specify a shift file (optional)
            shift_path = ps.app.getOpenFileName("Specify the shift file (optional):")
            shift_coor, projection_coor = None, None
            
            if shift_path:
                with open(shift_path, 'r', encoding='utf-8') as file:
                    first_line = file.readline()
                    parts = first_line.split()
                    projection_coor = parts[0]
                    shift_coor = ps.Vector([float(parts[1]), float(parts[2]), float(parts[3])])
            
            # Check for active chunk or create new one
            if self.doc.chunk is None:
                print("No active chunk found. Creating a new chunk.")
                chunk = self.doc.addChunk()
            else:
                chunk = self.doc.chunk
                print("Using active chunk.")
            
            # Import the model
            if shift_coor:
                chunk.importModel(path=model_path, shift=shift_coor, crs=ps.CoordinateSystem(projection_coor))
            else:
                chunk.importModel(path=model_path)
                
            ps.app.messageBox("Success", "Model imported successfully into the active chunk.")
            
        except Exception as e:
            ps.app.messageBox("Error", f"An error occurred: {str(e)}")
    
    def import_tiled_models(self):
        try:
            # Get the folder containing the tiles
            import_folder = ps.app.getExistingDirectory("Select the folder containing the exported tiles")
            if not import_folder:
                return
                
            # Get the shift.txt file
            shift_file = ps.app.getOpenFileName("Select the shift.txt file")
            if not shift_file:
                return
                
            # Read shift values
            with open(shift_file, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                projection_coor = str(first_line.split(' ')[0])
                shift_coor_x = float(first_line.split(' ')[1])
                shift_coor_y = float(first_line.split(' ')[2])
                shift_coor_z = float(first_line.split(' ')[3])
                shift = ps.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
            
            # Create a new chunk for the reimported model
            new_chunk = self.doc.addChunk()
            new_chunk.label = "Reimported_Tiles"
            
            # List OBJ files to import
            obj_files = [f for f in os.listdir(import_folder) if f.endswith('.obj')]
            
            # Import each OBJ file
            for obj_file in obj_files:
                obj_path = os.path.join(import_folder, obj_file)
                new_chunk.importModel(obj_path, ps.ModelFormat.ModelFormatOBJ, shift=shift)
            
            # Create unified mesh from imported tiles
            new_chunk.buildModel(surface_type=ps.Arbitrary, interpolation=ps.EnabledInterpolation)
            
            # Generate texture
            new_chunk.buildUV(mapping_mode=ps.GenericMapping)
            new_chunk.buildTexture(blending_mode=ps.MosaicBlending)
            
            # Build tiled model
            new_chunk.buildTiledModel()
            
            ps.app.messageBox("Success", "Tiles reimported and tiled model regenerated successfully.")
            
        except Exception as e:
            ps.app.messageBox("Error", f"An error occurred: {str(e)}")

    def texturize_models(self):
        try:
            x_res_a_terra = 1.26
            tex = 4096
            ratio = 0.6
            
            print("Starting texturize script")
            ps.app.update()
            
            for chunk in self.doc.chunks:
                if not chunk.model:
                    continue
                    
                current_model = chunk.model
                area_model = current_model.area()
                
                if area_model is None or area_model == 0.0:
                    print(f"{chunk.label} has no area. Maybe the model isn't metric.")
                    continue
                
                # Calculate number of textures needed
                numtex = pow((10000 / x_res_a_terra), 2) / (tex * tex * ratio)
                numtex_x_area = (numtex * area_model) / 100
                tex_num = max(1, round(numtex_x_area, 0))
                
                print(f"{chunk.label} has an area of {area_model} mq and needs {int(tex_num)} textures.")
                
                # Build UV and texture
                chunk.buildUV(mapping_mode=ps.GenericMapping, page_count=tex_num, texture_size=tex)
                chunk.buildTexture(blending_mode=ps.MosaicBlending, texture_size=tex, 
                                  fill_holes=True, ghosting_filter=True)
            
            ps.app.update()
            ps.app.messageBox("Success", "Texturization completed for all chunks.")
            
        except Exception as e:
            ps.app.messageBox("Error", f"An error occurred: {str(e)}")
    
    def texturize_models_200(self):
        try:
            x_res_a_terra = 1.26
            tex = 4096
            ratio = 0.6
            max_area = 200  # Maximum area in square meters
            
            print("Starting texturize script with 200m² limit")
            ps.app.update()
            
            # Count total chunks for progress reporting
            total_chunks = len(self.doc.chunks)
            chunks_processed = 0
            
            for chunk in self.doc.chunks:
                if not chunk.model:
                    continue
                    
                current_model = chunk.model
                area_model = current_model.area()
                
                if area_model is None or area_model == 0.0:
                    print(f"{chunk.label} has no area. Maybe the model isn't metric.")
                    chunks_processed += 1
                    continue
                
                # Calculate number of textures with area limit
                max_tex = 12  # Maximum number of textures for 200 sq meters
                if area_model > max_area:
                    tex_num = max_tex
                else:
                    numtex = pow((10000 / x_res_a_terra), 2) / (tex * tex * ratio)
                    numtex_x_area = (numtex * area_model) / 100
                    tex_num = max(1, round(numtex_x_area, 0))
                
                print(f"{chunk.label} has an area of {area_model} mq and needs {int(tex_num)} textures.")
                
                # Build UV and texture
                chunk.buildUV(mapping_mode=ps.GenericMapping, page_count=tex_num, texture_size=tex)
                chunk.buildTexture(blending_mode=ps.MosaicBlending, texture_size=tex, 
                                  fill_holes=True, ghosting_filter=True)
                
                chunks_processed += 1
                progress = (chunks_processed / total_chunks) * 100
                print(f"Progress: {progress:.2f}% completed ({chunks_processed}/{total_chunks} chunks processed)")
            
            ps.app.update()
            ps.app.messageBox("Success", "Texturization completed for all chunks with 200m² limit.")
            
        except Exception as e:
            ps.app.messageBox("Error", f"An error occurred: {str(e)}")
    
    def export_multiple_models(self):
        try:
            # Get export folder
            path_folder = ps.app.getExistingDirectory("Specify destination folder for 3D models: ")
            if not path_folder:
                return
            path_folder += "/"
            
            # Check for shift file
            file_list = os.listdir(path_folder)
            coord_shift = False
            
            for ob_txt in file_list:
                if ob_txt.endswith(".txt"):
                    file_txt_fullpath = str(path_folder + ob_txt)
                    print(file_txt_fullpath)
                    
                    with open(file_txt_fullpath, 'r', encoding='utf-8') as f:
                        first = f.readline()
                        projection_coor = str(first.split(' ')[0])
                        shift_coor_x = int(first.split(' ')[1])
                        shift_coor_y = int(first.split(' ')[2])
                        shift_coor_z = int(first.split(' ')[3])
                        shift_coor = ps.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
                        coord_shift = True
                        print(shift_coor_x)
            
            # Export each chunk
            number = 0
            for i in range(0, len(self.doc.chunks)):
                chunk = self.doc.chunks[i]
                
                if chunk.model:
                    ob_fullpath = str(path_folder + chunk.label + "_mt.obj")
                    
                    if coord_shift:
                        self.doc.chunks[i].exportModel(
                            path=ob_fullpath, 
                            binary=True, 
                            precision=6, 
                            texture_format=ps.ImageFormat.ImageFormatJPEG, 
                            save_texture=True, 
                            save_uv=True, 
                            save_normals=True, 
                            save_colors=True, 
                            save_cameras=False, 
                            save_markers=False, 
                            save_udim=False, 
                            save_alpha=False, 
                            strip_extensions=False, 
                            raster_transform=ps.RasterTransformNone, 
                            colors_rgb_8bit=True, 
                            format=ps.ModelFormat.ModelFormatOBJ,
                            crs=ps.CoordinateSystem(projection_coor), 
                            shift=shift_coor
                        )
                    else:
                        self.doc.chunks[i].exportModel(
                            path=ob_fullpath, 
                            binary=True, 
                            precision=6, 
                            texture_format=ps.ImageFormat.ImageFormatJPEG, 
                            save_texture=True, 
                            save_uv=True, 
                            save_normals=True, 
                            save_colors=True, 
                            save_cameras=False, 
                            save_markers=False, 
                            save_udim=False, 
                            save_alpha=False, 
                            strip_extensions=False, 
                            raster_transform=ps.RasterTransformNone, 
                            colors_rgb_8bit=True, 
                            format=ps.ModelFormat.ModelFormatOBJ
                        )
                
                number += 1
            
            ps.app.update()
            ps.app.messageBox("Success", f"Exported {number} models successfully.")
            
        except Exception as e:
            ps.app.messageBox("Error", f"An error occurred: {str(e)}")
    
    def export_single_model_with_shift(self):
        try:
            # Check if there's an active chunk
            if self.doc.chunk is None:
                ps.app.messageBox("Error", "No active chunk found.")
                return
            
            chunk = self.doc.chunk
            
            # Ask for shift file (optional)
            shift_path = ps.app.getOpenFileName("Specify the shift file (optional):")
            crs, shift_coor = None, None
            
            if shift_path:
                with open(shift_path, 'r', encoding='utf-8') as file:
                    first_line = file.readline()
                    parts = first_line.split()
                    projection_coor = parts[0]
                    shift_coor_x = float(parts[1])
                    shift_coor_y = float(parts[2])
                    shift_coor_z = float(parts[3])
                    crs = ps.CoordinateSystem(projection_coor)
                    shift_coor = ps.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
            
            # Ask for destination folder and filename
            save_folder = ps.app.getExistingDirectory("Specify the folder to save the OBJ file:")
            if not save_folder:
                return
            
            file_name = ps.app.getString("Enter the name of the OBJ file:", chunk.label)
            if not file_name:
                file_name = chunk.label
            
            save_path = os.path.join(save_folder, file_name + ".obj")
            
            # Export the model
            chunk.exportModel(path=save_path, format=ps.ModelFormat.ModelFormatOBJ, crs=crs, shift=shift_coor)
            
            ps.app.messageBox("Success", f"Model exported successfully to {save_path}.")
            
        except Exception as e:
            ps.app.messageBox("Error", f"An error occurred: {str(e)}")
    
    def export_tiled_models(self):
        try:
            # Get export folder
            export_folder = ps.app.getExistingDirectory("Specify destination folder for 3D models: ")
            if not export_folder:
                return
            export_folder += "/"
            
            # Get shift file
            shift_file = ps.app.getOpenFileName("Select the shift.txt file")
            if not shift_file:
                return
            
            # Read shift values
            with open(shift_file, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                projection_coor = str(first_line.split(' ')[0])
                shift_coor_x = float(first_line.split(' ')[1])
                shift_coor_y = float(first_line.split(' ')[2])
                shift_coor_z = float(first_line.split(' ')[3])
                shift = ps.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
            
            # Get active chunk
            chunk = self.doc.chunk
            
            # Set export parameters
            tile_format = ps.TileFormat.TileFormatOBJ
            texture_format = ps.ImageFormat.ImageFormatPNG
            
            # Check for tiled model
            tiled_model = chunk.tiled_model
            if not tiled_model:
                ps.app.messageBox("Error", "No tiled model found in the active chunk.")
                return
            
            # Create export folder if it doesn't exist
            if not os.path.exists(export_folder):
                os.makedirs(export_folder)
            
            # Export tiles
            for tile_index in range(len(tiled_model.tiles)):
                tile_name = f"tile_{tile_index:04d}"
                obj_path = os.path.join(export_folder, f"{tile_name}.obj")
                png_path = os.path.join(export_folder, f"{tile_name}.png")
                
                # Export the tile with shift
                tiled_model.exportTile(tile_index, obj_path, tile_format, translation=shift)
                
                # Export the texture
                tiled_model.exportTileTexture(tile_index, png_path, texture_format)
            
            ps.app.messageBox("Success", f"Exported {len(tiled_model.tiles)} tiled models successfully.")
            
        except Exception as e:
            ps.app.messageBox("Error", f"An error occurred: {str(e)}")
    
    def rename_chunks(self):
        try:
            number = 1
            for i in range(1, len(self.doc.chunks)):
                chunk = self.doc.chunks[i]
                chunk.label = str(number) + "_mt"
                number += 1
            
            ps.app.messageBox("Success", f"Renamed {number-1} chunks successfully.")
            
        except Exception as e:
            ps.app.messageBox("Error", f"An error occurred: {str(e)}")
    
    def lod_generator(self):
        ps.app.messageBox("Notice", "LOD Generator is not fully implemented in the GUI yet.")
    
    def import_ipad_cameras(self):
        try:
            # Get the folder containing the iPad captures
            image_folder = ps.app.getExistingDirectory("Select the folder with iPad captured images:")
            if not image_folder:
                return
            
            # Ask for options
            optimize_ar = ps.app.getBool("Optimize AR Alignment?")
            use_ar_constraints = False
            filter_bad_ar = False
            
            if optimize_ar:
                use_ar_constraints = ps.app.getBool("Use AR Data as Constraints?")
                filter_bad_ar = ps.app.getBool("Filter Bad AR Alignments?")
            
            # Create a new chunk for the imported data
            chunk = self.doc.addChunk()
            chunk.label = "iPad_Import_" + os.path.basename(image_folder)
            self.doc.chunk = chunk  # Rende attivo il nuovo chunk
            
            # Find all images and their corresponding JSON files
            image_files = [f for f in os.listdir(image_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            
            if not image_files:
                ps.app.messageBox("No image files found in the selected folder.")
                return
            
            # Load the images into the chunk
            image_list = []
            for img in image_files:
                image_path = os.path.join(image_folder, img)
                image_list.append(image_path)
            
            print(f"Adding {len(image_list)} photos to the chunk...")
            ps.app.update()
            chunk.addPhotos(image_list)
            
            # Initialize region with default values before processing any cameras
            # Questo garantisce che la region sia valida anche in caso di errori successivi
            region = chunk.region
            region.center = ps.Vector([0, 0, 0])
            region.size = ps.Vector([100, 100, 100])  # Dimensioni di default abbastanza grandi
            region.rot = ps.Matrix([[1, 0, 0], [0, 1, 0], [0, 0, 1]])  # Matrice identità
            
            # Find and process the camera alignment data from JSON files
            cameras_with_data = 0
            camera_positions = []  # To track camera positions for region calculation
            
            print("Processing camera alignment data from JSON files...")
            ps.app.update()
            
            for i, camera in enumerate(chunk.cameras):
                # Aggiorna UI periodicamente
                if i % 10 == 0:
                    ps.app.update()
                    print(f"Processed {i}/{len(chunk.cameras)} cameras...")
                
                # Prendi il nome del file senza estensione
                image_name = os.path.splitext(os.path.basename(camera.photo.path))[0]
                json_file = os.path.join(image_folder, image_name + ".json")
                
                if os.path.exists(json_file):
                    with open(json_file, 'r') as f:
                        try:
                            data = json.load(f)
                            
                            # Extract camera pose matrix from AR data
                            if "cameraPoseARFrame" in data:
                                camera_matrix = data["cameraPoseARFrame"]
                                
                                # Verifica dimensioni matrice
                                if len(camera_matrix) != 16:
                                    print(f"Unexpected matrix size for {image_name}: {len(camera_matrix)} elements")
                                    continue
                                
                                # Conversione coordinate ARKit (Y-up) a Metashape (Z-up)
                                arkit_to_metashape = ps.Matrix([
                                    [1, 0, 0, 0],
                                    [0, 0, 1, 0],
                                    [0, -1, 0, 0],
                                    [0, 0, 0, 1]
                                ])
                                
                                # Matrice di trasformazione ARKit
                                ar_transform = ps.Matrix([
                                    [camera_matrix[0], camera_matrix[1], camera_matrix[2], camera_matrix[3]],
                                    [camera_matrix[4], camera_matrix[5], camera_matrix[6], camera_matrix[7]],
                                    [camera_matrix[8], camera_matrix[9], camera_matrix[10], camera_matrix[11]],
                                    [0, 0, 0, 1]
                                ])
                                
                                # Inversione e conversione
                                try:
                                    ar_transform_inv = ar_transform.inv()
                                    transform = ar_transform_inv * arkit_to_metashape
                                    
                                    # Imposta trasformazione
                                    camera.transform = transform
                                    
                                    # Verifica che transform abbia funzionato correttamente
                                    if camera.center:
                                        camera_positions.append(camera.center)
                                        
                                        # Imposta reference
                                        camera.reference.location = camera.center
                                        camera.reference.enabled = True
                                        
                                        cameras_with_data += 1
                                    else:
                                        print(f"Warning: Failed to get camera center for {image_name}")
                                except Exception as matrix_error:
                                    print(f"Matrix error for {image_name}: {str(matrix_error)}")
                                    continue
                                
                                # Extract intrinsics if available
                                if "intrinsics" in data:
                                    intrinsics = data["intrinsics"]
                                    if len(intrinsics) >= 9:
                                        fx = intrinsics[0]
                                        fy = intrinsics[4]
                                        cx = intrinsics[2]
                                        cy = intrinsics[5]
                                        
                                        sensor = camera.sensor
                                        calib = sensor.calibration
                                        calib.f = (fx + fy) / 2
                                        calib.cx = cx - sensor.width / 2
                                        calib.cy = cy - sensor.height / 2
                                        sensor.fixed = True
                        
                        except json.JSONDecodeError:
                            print(f"Error reading JSON file: {json_file}")
                            continue
                        except Exception as e:
                            print(f"Error processing camera {image_name}: {str(e)}")
                            continue
            
            if cameras_with_data == 0:
                ps.app.messageBox("No AR camera data found in the JSON files.")
                return
            
            print(f"Imported {cameras_with_data} cameras with AR data")
            ps.app.update()
            
            # Ricalcola la region basata sulle posizioni delle camere
            if camera_positions:
                print("Calculating region from camera positions...")
                ps.app.update()
                
                try:
                    # Trova limiti del volume
                    min_x = min(pos.x for pos in camera_positions)
                    min_y = min(pos.y for pos in camera_positions)
                    min_z = min(pos.z for pos in camera_positions)
                    max_x = max(pos.x for pos in camera_positions)
                    max_y = max(pos.y for pos in camera_positions)
                    max_z = max(pos.z for pos in camera_positions)
                    
                    # Calcola centro e dimensione con margine
                    margin = 5.0  # Margine in metri
                    center_x = (min_x + max_x) / 2
                    center_y = (min_y + max_y) / 2
                    center_z = (min_z + max_z) / 2
                    
                    size_x = max(10.0, (max_x - min_x) + margin * 2)  # Minimo 10 metri
                    size_y = max(10.0, (max_y - min_y) + margin * 2)
                    size_z = max(10.0, (max_z - min_z) + margin * 2)
                    
                    # Imposta la region
                    region = chunk.region
                    region.center = ps.Vector([center_x, center_y, center_z])
                    region.size = ps.Vector([size_x, size_y, size_z])
                    
                    # Assicurati che la matrice di rotazione sia valida
                    region.rot = ps.Matrix([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
                    
                    print(f"Set region center to {center_x}, {center_y}, {center_z}")
                    print(f"Set region size to {size_x}, {size_y}, {size_z}")
                except Exception as region_error:
                    print(f"Error setting region: {str(region_error)}")
                    # Non interrompere il processo se non si riesce a impostare la region
            
            # AGGIUNGI QUI: Chiedi all'utente dove salvare il progetto
            save_path = ps.app.getSaveFileName("Specify where to save the project:")
            if save_path:
                self.doc.save(save_path)
                print(f"Project saved to {save_path}")
            else:
                # Fallback to default save if user cancels
                try:
                    self.doc.save()
                    print("Project saved with default name")
                except Exception as save_error:
                    print(f"Error saving project: {str(save_error)}")
                    ps.app.messageBox("Warning: Could not save the project automatically. Please save manually.")
            
            # Aggiorna il documento prima di procedere con l'allineamento
            ps.app.update()
            
            # Optimize the alignment if requested
            if optimize_ar:
                print("Optimizing AR alignment...")
                ps.app.update()
                
                if use_ar_constraints:
                    # Prepare AR constraints
                    for camera in chunk.cameras:
                        if camera.transform:
                            if not camera.reference.enabled:
                                camera.reference.location = camera.center
                                camera.reference.enabled = True
                            
                            # Accuracy for constraints
                            camera.reference.accuracy = ps.Vector([0.1, 0.1, 0.1])
                    
                    ps.app.update()
                
                # Match photos
                try:
                    print("Matching photos...")
                    ps.app.update()
                    
                    chunk.matchPhotos(
                        generic_preselection=True, 
                        reference_preselection=use_ar_constraints,
                        keypoint_limit=40000,
                        tiepoint_limit=4000
                    )
                    
                    # Salva dopo il matching
                    ps.app.update()
                    if save_path:
                        self.doc.save(save_path)
                    else:
                        try:
                            self.doc.save()
                        except:
                            pass
                    
                    print("Aligning cameras...")
                    ps.app.update()
                    
                    # Align cameras
                    chunk.alignCameras(
                        reset_alignment=False,
                        adaptive_fitting=True,
                        min_image=2
                    )
                    
                    # Salva dopo l'allineamento
                    ps.app.update()
                    if save_path:
                        self.doc.save(save_path)
                    else:
                        try:
                            self.doc.save()
                        except:
                            pass
                    
                except Exception as align_error:
                    print(f"Error during alignment: {str(align_error)}")
                    ps.app.update()
                    
                    # Alternative approach
                    try:
                        print("Trying alternative alignment approach...")
                        ps.app.update()
                        chunk.alignCameras()
                        ps.app.update()
                        if save_path:
                            self.doc.save(save_path)
                        else:
                            try:
                                self.doc.save()
                            except:
                                pass
                    except Exception as alt_error:
                        print(f"Alternative alignment also failed: {str(alt_error)}")
                        ps.app.update()
                
                # Filter bad alignments if requested
                if filter_bad_ar:
                    print("Filtering bad alignments...")
                    ps.app.update()
                    
                    disabled_count = 0
                    for camera in chunk.cameras:
                        if camera.transform is None:
                            continue
                            
                        if camera.reference.location:
                            # Calculate distance between estimated and reference
                            dist_x = abs(camera.center.x - camera.reference.location.x)
                            dist_y = abs(camera.center.y - camera.reference.location.y)
                            dist_z = abs(camera.center.z - camera.reference.location.z)
                            distance = math.sqrt(dist_x**2 + dist_y**2 + dist_z**2)
                            
                            if distance > 0.5:  # Threshold in meters
                                camera.enabled = False
                                disabled_count += 1
                    
                    print(f"Disabled {disabled_count} cameras due to large alignment differences")
                    ps.app.update()
                    
                    # Salva dopo il filtraggio
                    if save_path:
                        self.doc.save(save_path)
                    else:
                        try:
                            self.doc.save()
                        except:
                            pass
            
            # Final updates
            chunk.resetRegion()  # Reset region to ensure it's correctly set
            ps.app.update()
            
            # Salvataggio finale
            if save_path:
                self.doc.save(save_path)
            else:
                try:
                    self.doc.save()
                except:
                    pass
            
            # Breve pausa prima del messaggio finale
            import time
            time.sleep(0.5)
            
            ps.app.messageBox(f"Imported {len(image_files)} images with {cameras_with_data} AR camera positions.")
            
        except Exception as e:
            ps.app.update()
            print(f"Critical error: {str(e)}")
            ps.app.messageBox(f"An error occurred: {str(e)}")
            
            try:
                # Prova a salvare in caso di errore
                if 'save_path' in locals() and save_path:
                    self.doc.save(save_path)
                else:
                    self.doc.save()
            except:
                pass

# Create the tool
tool = MetashapeTools()