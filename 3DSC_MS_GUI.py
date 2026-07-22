# 3DSC for Metashape
# Version aligned with the 3D Survey Collection (3DSC) Blender extension.
# See https://www.extendedmatrix.org
__version__ = "1.7.0"

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
        self.global_shift_file = None
        self.global_shift_line = None
        self.global_shift_vector = None
        self.global_shift_crs_string = None
        self.global_shift_crs = None
        self.workflow_state = {
            "lod0_chunk_key": None,
            "cut_blocks": [],
            "cut_mode": None,
            "cut_folder": None,
            "cut_source_chunk_key": None,
            "generated_chunk_keys": [],
        }
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
        shift_preview = self.get_global_shift_preview(compact=True)
        ps.app.addMenuItem(label + "/Shift/STEP0 - Load Global Shift File (optional)", self.load_global_shift_file)
        ps.app.addMenuItem(label + "/Shift/Current Shift -> " + shift_preview, self.show_global_shift_preview)
        ps.app.addMenuItem(label + "/Shift/Clear Global Shift", self.clear_global_shift)

        ps.app.addMenuItem(label + "/Import/Import Multiple Models", self.import_multiple_models)
        ps.app.addMenuItem(label + "/Import/Import Single Model with Shift", self.import_single_model_with_shift)
        ps.app.addMenuItem(label + "/Import/Import Tiled Models", self.import_tiled_models)
        
        ps.app.addMenuItem(label + "/Texturing/Texturize Models", self.texturize_models)
        ps.app.addMenuItem(label + "/Texturing/Texturize Models (200m² limit)", self.texturize_models_200)
        
        ps.app.addMenuItem(label + "/Export/Export Multiple Models", self.export_multiple_models)
        ps.app.addMenuItem(label + "/Export/Export Single Model with Shift", self.export_single_model_with_shift)
        ps.app.addMenuItem(label + "/Export/Export Tiled Models", self.export_tiled_models)
        ps.app.addMenuItem(label + "/Export/Cut Giant Mesh into Blocks (with Shift)", self.cut_giant_mesh_into_blocks_with_shift)
        ps.app.addMenuItem(label + "/Export/Workflow Export Blocks (Textured First)", self.export_workflow_blocks_textured)
        ps.app.addMenuItem(label + "/Export/Export Undistorted Images (Active Chunk)", self.export_undistorted_images_active_chunk)

        ps.app.addMenuItem(label + "/Workflow/STEP1 Prepare or Flag LOD0", self.prepare_or_flag_lod0)
        ps.app.addMenuItem(label + "/Workflow/STEP2 Cut Mesh into Blocks (Options)", self.cut_giant_mesh_into_blocks_with_shift)
        ps.app.addMenuItem(label + "/Workflow/STEP3 Texturize Workflow Blocks", self.texturize_workflow_blocks)
        ps.app.addMenuItem(label + "/Workflow/STEP4 Generate LODs + Normal Maps (Experimental)", self.generate_workflow_lods_experimental)
        ps.app.addMenuItem(label + "/Workflow/STEP5 Export Workflow Blocks", self.export_workflow_blocks_textured)

        ps.app.addMenuItem(label + "/Utility/Rename Chunks", self.rename_chunks)
        ps.app.addMenuItem(label + "/Utility/LOD Generator", self.lod_generator)
        
        # EXPERIMENTAL - iPad AR Camera Import
        # ps.app.addMenuItem(label + "/iPad/Import iPad AR Camera Data (EXPERIMENTAL)", self.import_ipad_cameras)

    def show_menu(self):
        # Visualizza un messaggio quando si clicca sul menu principale
        ps.app.messageBox("3DSC Metashape Tools - Select a specific tool from the submenu.")

    def _chunk_key(self, chunk):
        return getattr(chunk, "key", id(chunk))

    def _get_chunk_by_key(self, chunk_key):
        for chunk in self.doc.chunks:
            if self._chunk_key(chunk) == chunk_key:
                return chunk
        return None

    def _read_shift_parameters_from_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        parts = first_line.split()
        if len(parts) < 4:
            raise Exception("Invalid shift.txt format. Expected: CRS SHIFT_X SHIFT_Y SHIFT_Z")

        crs_string = parts[0]
        shift = ps.Vector([float(parts[1]), float(parts[2]), float(parts[3])])
        crs = None
        if crs_string.upper() not in ['LOCAL', 'LOCAL_CS', 'NONE']:
            crs = ps.CoordinateSystem(crs_string)

        return {
            "line": first_line,
            "crs_string": crs_string,
            "crs": crs,
            "shift": shift,
        }

    def _set_global_shift_state(self, file_path, parsed_shift):
        self.global_shift_file = file_path
        self.global_shift_line = parsed_shift["line"]
        self.global_shift_vector = parsed_shift["shift"]
        self.global_shift_crs_string = parsed_shift["crs_string"]
        self.global_shift_crs = parsed_shift["crs"]
        self.init_gui()

    def get_global_shift_preview(self, compact=False):
        if self.global_shift_vector is None:
            return "NONE"
        text = (
            f"{self.global_shift_crs_string} "
            f"{self.global_shift_vector.x:.3f} "
            f"{self.global_shift_vector.y:.3f} "
            f"{self.global_shift_vector.z:.3f}"
        )
        if compact and len(text) > 56:
            return text[:56] + "..."
        return text

    def load_global_shift_file(self):
        try:
            shift_path = ps.app.getOpenFileName("Select global shift.txt file")
            if not shift_path:
                return
            parsed = self._read_shift_parameters_from_file(shift_path)
            self._set_global_shift_state(shift_path, parsed)
            ps.app.messageBox(
                "Global shift loaded:\n"
                + self.get_global_shift_preview(compact=False)
            )
        except Exception as e:
            ps.app.messageBox(f"Error: Unable to load global shift: {str(e)}")

    def show_global_shift_preview(self):
        if self.global_shift_vector is None:
            ps.app.messageBox("Global shift is not set.")
            return
        origin = self.global_shift_file if self.global_shift_file else "N/A"
        ps.app.messageBox(
            "Current global shift:\n"
            + self.get_global_shift_preview(compact=False)
            + f"\n\nSource file:\n{origin}"
        )

    def clear_global_shift(self):
        self.global_shift_file = None
        self.global_shift_line = None
        self.global_shift_vector = None
        self.global_shift_crs_string = None
        self.global_shift_crs = None
        self.init_gui()
        ps.app.messageBox("Global shift cleared.")

    def _resolve_shift_for_operation(self, operation_label, ask_if_missing=True):
        if self.global_shift_vector is not None:
            return self.global_shift_crs, self.global_shift_vector, self.global_shift_line

        if not ask_if_missing:
            return None, None, None

        shift_path = ps.app.getOpenFileName(f"{operation_label} - Select shift.txt (optional)")
        if not shift_path:
            return None, None, None
        parsed = self._read_shift_parameters_from_file(shift_path)
        return parsed["crs"], parsed["shift"], parsed["line"]

    def _set_chunk_textured_flag(self, chunk, value):
        if hasattr(chunk, "meta"):
            chunk.meta["3dsc_workflow_textured"] = "1" if value else "0"

    def _is_chunk_textured(self, chunk):
        try:
            if hasattr(chunk, "meta") and chunk.meta.get("3dsc_workflow_textured") == "1":
                return True
        except Exception:
            pass

        model = getattr(chunk, "model", None)
        if not model:
            return False

        try:
            if hasattr(model, "textures") and len(model.textures) > 0:
                return True
        except Exception:
            pass
        return False

    def _safe_remove_asset(self, chunk, asset):
        if asset is None:
            return
        try:
            chunk.remove(asset)
        except Exception:
            pass

    def _clear_all_models_in_chunk(self, chunk):
        models = []
        try:
            models = list(chunk.models)
        except Exception:
            pass

        for model in models:
            self._safe_remove_asset(chunk, model)

        if getattr(chunk, "model", None):
            self._safe_remove_asset(chunk, chunk.model)

    def _prepare_lightweight_chunk(self, chunk):
        self._clear_all_models_in_chunk(chunk)
        for attr in ["tiled_model", "dense_cloud", "depth_maps", "elevation", "orthomosaic"]:
            asset = getattr(chunk, attr, None)
            self._safe_remove_asset(chunk, asset)

    def _extract_models(self, chunk):
        try:
            models = list(chunk.models)
            if models:
                return models
        except Exception:
            pass
        return [chunk.model] if getattr(chunk, "model", None) else []

    def _activate_model(self, chunk, model):
        try:
            chunk.model = model
            return True
        except Exception:
            return False

    def _build_tiled_model_with_area_hint(self, chunk, target_area_m2):
        side_len = max(0.5, math.sqrt(target_area_m2))
        last_error = None
        attempts = [
            {"tile_size": side_len},
            {"tile_size": int(max(64, side_len * 100))},
            {},
        ]
        for kwargs in attempts:
            try:
                chunk.buildTiledModel(**kwargs)
                return side_len
            except Exception as e:
                last_error = e
                continue
        raise Exception(f"Unable to build tiled model: {str(last_error)}")

    def _get_workflow_chunks(self):
        chunks = []
        for chunk_key in self.workflow_state.get("generated_chunk_keys", []):
            chunk = self._get_chunk_by_key(chunk_key)
            if chunk:
                chunks.append(chunk)
        return chunks

    def _show_step3_options_dialog(self, has_tiled_model=False):
        result = {}

        root = tk.Tk()
        root.title("3DSC STEP2 - Cut Mesh Options")
        root.resizable(False, False)
        root.geometry("820x420")
        root.lift()

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Workflow Cut Options", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Global Shift: " + self.get_global_shift_preview(compact=False),
            foreground="#333333"
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 12))

        area_var = tk.StringVar(value="80")
        run_step2_var = tk.BooleanVar(value=True)
        output_multi_chunks_var = tk.BooleanVar(value=True)
        grid_naming_var = tk.BooleanVar(value=True)
        export_temp_textures_var = tk.BooleanVar(value=False)
        cleanup_temp_files_var = tk.BooleanVar(value=False)
        rebuild_tiled_var = tk.BooleanVar(value=True if has_tiled_model else True)

        default_folder = self.workflow_state.get("cut_folder") or os.getcwd()
        export_root_var = tk.StringVar(value=default_folder)

        ttk.Label(frame, text="Block plan area (m²):").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=area_var, width=14).grid(row=2, column=1, sticky="w")

        ttk.Checkbutton(
            frame,
            text="Run STEP1 now (prepare/flag LOD0 before cut)",
            variable=run_step2_var
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Checkbutton(
            frame,
            text="Output mode: one chunk per block (recommended)",
            variable=output_multi_chunks_var
        ).grid(row=4, column=0, columnspan=3, sticky="w")

        ttk.Checkbutton(
            frame,
            text="Use grid naming for blocks (x_y)",
            variable=grid_naming_var
        ).grid(row=5, column=0, columnspan=3, sticky="w")

        ttk.Checkbutton(
            frame,
            text="Export temporary PNG textures during STEP2 (slower)",
            variable=export_temp_textures_var
        ).grid(row=6, column=0, columnspan=3, sticky="w")

        ttk.Checkbutton(
            frame,
            text="Delete temporary files after block import",
            variable=cleanup_temp_files_var
        ).grid(row=7, column=0, columnspan=3, sticky="w")

        ttk.Checkbutton(
            frame,
            text="Rebuild tiled model with current area settings",
            variable=rebuild_tiled_var
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Label(frame, text="STEP2 output folder:").grid(row=9, column=0, sticky="w")
        folder_entry = ttk.Entry(frame, textvariable=export_root_var, width=70)
        folder_entry.grid(row=10, column=0, columnspan=2, sticky="we", pady=(2, 0))

        def browse_output_folder():
            selected = filedialog.askdirectory(
                title="Select STEP2 output folder",
                initialdir=export_root_var.get() if export_root_var.get() else os.getcwd()
            )
            if selected:
                export_root_var.set(selected)

        ttk.Button(frame, text="Browse...", command=browse_output_folder).grid(row=10, column=2, padx=(8, 0), sticky="w")

        status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=status_var, foreground="#b00020").grid(
            row=11, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        def on_ok():
            try:
                area_value = float(str(area_var.get()).replace(",", "."))
                if area_value <= 0:
                    raise ValueError("Block area must be > 0.")
                out_dir = export_root_var.get().strip()
                if not out_dir:
                    raise ValueError("Select a STEP2 output folder.")
                result.update(
                    {
                        "target_area_m2": area_value,
                        "run_step2_now": bool(run_step2_var.get()),
                        "output_multi_chunks": bool(output_multi_chunks_var.get()),
                        "grid_naming": bool(grid_naming_var.get()),
                        "export_temp_textures": bool(export_temp_textures_var.get()),
                        "cleanup_temp_files": bool(cleanup_temp_files_var.get()),
                        "rebuild_tiled_model": bool(rebuild_tiled_var.get()),
                        "export_root": out_dir,
                    }
                )
                root.destroy()
            except Exception as e:
                status_var.set(str(e))

        def on_cancel():
            result.clear()
            root.destroy()

        btn_row = ttk.Frame(frame)
        btn_row.grid(row=12, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(btn_row, text="Cancel", command=on_cancel).pack(side="right")
        ttk.Button(btn_row, text="Run STEP2", command=on_ok).pack(side="right", padx=(0, 8))

        root.protocol("WM_DELETE_WINDOW", on_cancel)
        root.mainloop()
        return result if result else None

    def _show_step7_options_dialog(self):
        result = {}

        root = tk.Tk()
        root.title("3DSC STEP5 - Export Workflow Blocks")
        root.resizable(False, False)
        root.geometry("820x300")
        root.lift()

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)

        has_global_shift = self.global_shift_vector is not None
        use_shift_var = tk.BooleanVar(value=True if has_global_shift else False)
        save_textures_var = tk.BooleanVar(value=True)

        default_export = self.workflow_state.get("cut_folder") or os.getcwd()
        export_folder_var = tk.StringVar(value=default_export)
        shift_file_var = tk.StringVar(value="")

        ttk.Label(frame, text="Workflow STEP5 Export", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Export folder:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=export_folder_var, width=70).grid(row=2, column=0, columnspan=2, sticky="we", pady=(2, 0))

        def browse_export_folder():
            selected = filedialog.askdirectory(
                title="Select STEP5 export folder",
                initialdir=export_folder_var.get() if export_folder_var.get() else os.getcwd()
            )
            if selected:
                export_folder_var.set(selected)

        ttk.Button(frame, text="Browse...", command=browse_export_folder).grid(row=2, column=2, padx=(8, 0), sticky="w")

        ttk.Checkbutton(frame, text="Use shift for export", variable=use_shift_var).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )
        ttk.Checkbutton(frame, text="Export UV + textures", variable=save_textures_var).grid(
            row=4, column=0, columnspan=3, sticky="w"
        )

        if has_global_shift:
            ttk.Label(
                frame,
                text="Using GLOBAL shift: " + self.get_global_shift_preview(compact=False),
                foreground="#333333"
            ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
        else:
            ttk.Label(frame, text="Shift file (optional, used only if 'Use shift' is enabled):").grid(
                row=5, column=0, columnspan=3, sticky="w", pady=(8, 0)
            )
            shift_entry = ttk.Entry(frame, textvariable=shift_file_var, width=70)
            shift_entry.grid(row=6, column=0, columnspan=2, sticky="we", pady=(2, 0))

            def browse_shift_file():
                selected = ps.app.getOpenFileName("Select shift.txt file for STEP5")
                if selected:
                    shift_file_var.set(selected)

            ttk.Button(frame, text="Browse...", command=browse_shift_file).grid(row=6, column=2, padx=(8, 0), sticky="w")

            def update_shift_file_state(*_):
                state = "normal" if use_shift_var.get() else "disabled"
                shift_entry.configure(state=state)

            use_shift_var.trace_add("write", update_shift_file_state)
            update_shift_file_state()

        status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=status_var, foreground="#b00020").grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )

        def on_ok():
            try:
                out_dir = export_folder_var.get().strip()
                if not out_dir:
                    raise ValueError("Select an export folder.")

                shift_file = shift_file_var.get().strip() if not has_global_shift else ""
                if use_shift_var.get() and not has_global_shift and not shift_file:
                    raise ValueError("Select a shift.txt file or disable 'Use shift'.")

                result.update(
                    {
                        "export_folder": out_dir,
                        "use_shift": bool(use_shift_var.get()),
                        "save_textures": bool(save_textures_var.get()),
                        "shift_file": shift_file,
                    }
                )
                root.destroy()
            except Exception as e:
                status_var.set(str(e))

        def on_cancel():
            result.clear()
            root.destroy()

        btn_row = ttk.Frame(frame)
        btn_row.grid(row=8, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(btn_row, text="Cancel", command=on_cancel).pack(side="right")
        ttk.Button(btn_row, text="Run STEP5 Export", command=on_ok).pack(side="right", padx=(0, 8))

        root.protocol("WM_DELETE_WINDOW", on_cancel)
        root.mainloop()
        return result if result else None

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
            projection_coor = None
            for ob_txt in file_list:
                if ob_txt.endswith(".txt"):
                    file_txt_fullpath = str(path_folder + ob_txt)
                    print(file_txt_fullpath)
                    with open(file_txt_fullpath, 'r', encoding='utf-8') as f:
                        first = f.readline()
                        parts = first.split()
                        crs_string = parts[0]
                        shift_coor_x = float(parts[1])
                        shift_coor_y = float(parts[2])
                        shift_coor_z = float(parts[3])
                        shift_coor = ps.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
                        coord_shift = True
                        
                        # Handle CRS: only set if not LOCAL or NONE
                        if crs_string.upper() not in ['LOCAL', 'LOCAL_CS', 'NONE']:
                            projection_coor = crs_string
                        
                        print(f"Using shift coordinates: {shift_coor_x}, {shift_coor_y}, {shift_coor_z}")
                        if projection_coor:
                            print(f"Using CRS: {projection_coor}")
                        else:
                            print("Using local coordinates (no CRS)")

            if not coord_shift and self.global_shift_vector is not None:
                coord_shift = True
                shift_coor = self.global_shift_vector
                projection_coor = self.global_shift_crs_string if self.global_shift_crs else None
                print("Using global shift from GUI settings.")
            
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
                        if projection_coor:
                            # Import with CRS and shift
                            self.doc.chunk.importModel(path=ob_fullpath, format=format_file_import, 
                                                     crs=ps.CoordinateSystem(projection_coor), shift=shift_coor)
                        else:
                            # Import with shift only (local coordinates)
                            self.doc.chunk.importModel(path=ob_fullpath, format=format_file_import, shift=shift_coor)
                    else:
                        self.doc.chunk.importModel(path=ob_fullpath, format=format_file_import)
                        
                    chunk_number += 1
            
            ps.app.update()
            ps.app.messageBox("Import complete - Models imported successfully!")
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def import_single_model_with_shift(self):
        try:
            # Ask user to specify a 3D model
            model_path = ps.app.getOpenFileName("Specify the 3D model file:")
            if not model_path:
                return

            projection_coor_obj, shift_coor, _ = self._resolve_shift_for_operation(
                "Import Single Model with Shift", ask_if_missing=True
            )
            
            # Check for active chunk or create new one
            if self.doc.chunk is None:
                print("No active chunk found. Creating a new chunk.")
                chunk = self.doc.addChunk()
            else:
                chunk = self.doc.chunk
                print("Using active chunk.")
            
            # Import the model
            if shift_coor:
                if projection_coor_obj:
                    chunk.importModel(path=model_path, shift=shift_coor, crs=projection_coor_obj)
                else:
                    chunk.importModel(path=model_path, shift=shift_coor)
            else:
                chunk.importModel(path=model_path)
                
            ps.app.messageBox("Success - Model imported successfully into the active chunk.")
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def import_tiled_models(self):
        try:
            # Get the folder containing the tiles
            import_folder = ps.app.getExistingDirectory("Select the folder containing the exported tiles")
            if not import_folder:
                return
                
            _, shift, _ = self._resolve_shift_for_operation(
                "Import Tiled Models", ask_if_missing=True
            )
            
            # Create a new chunk for the reimported model
            new_chunk = self.doc.addChunk()
            new_chunk.label = "Reimported_Tiles"
            
            # List OBJ files to import
            obj_files = [f for f in os.listdir(import_folder) if f.endswith('.obj')]
            
            # Import each OBJ file
            for obj_file in obj_files:
                obj_path = os.path.join(import_folder, obj_file)
                if shift:
                    new_chunk.importModel(obj_path, ps.ModelFormat.ModelFormatOBJ, shift=shift)
                else:
                    new_chunk.importModel(obj_path, ps.ModelFormat.ModelFormatOBJ)
            
            # Create unified mesh from imported tiles
            new_chunk.buildModel(surface_type=ps.Arbitrary, interpolation=ps.EnabledInterpolation)
            
            # Generate texture
            new_chunk.buildUV(mapping_mode=ps.GenericMapping)
            new_chunk.buildTexture(blending_mode=ps.MosaicBlending)
            
            # Build tiled model
            new_chunk.buildTiledModel()
            
            ps.app.messageBox("Success - Tiles reimported and tiled model regenerated successfully.")
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def _compute_texture_pages(self, area_model, tex_size, ratio, x_res_a_terra, max_area=None):
        if max_area is not None and area_model > max_area:
            return 12
        numtex = pow((10000 / x_res_a_terra), 2) / (tex_size * tex_size * ratio)
        numtex_x_area = (numtex * area_model) / 100
        return max(1, round(numtex_x_area, 0))

    def _texturize_chunk_models(self, chunk, tex_size=4096, ratio=0.6, x_res_a_terra=1.26, max_area=None):
        models = self._extract_models(chunk)
        if not models:
            return 0

        textured_models = 0
        for model in models:
            if not self._activate_model(chunk, model):
                if textured_models > 0:
                    break

            current_model = chunk.model
            if not current_model:
                continue

            area_model = current_model.area()
            if area_model is None or area_model == 0.0:
                print(f"{chunk.label} has no area. Maybe the model isn't metric.")
                continue

            tex_num = self._compute_texture_pages(
                area_model=area_model,
                tex_size=tex_size,
                ratio=ratio,
                x_res_a_terra=x_res_a_terra,
                max_area=max_area,
            )
            print(f"{chunk.label} has an area of {area_model} mq and needs {int(tex_num)} textures.")

            chunk.buildUV(mapping_mode=ps.GenericMapping, page_count=tex_num, texture_size=tex_size)
            chunk.buildTexture(
                blending_mode=ps.MosaicBlending,
                texture_size=tex_size,
                fill_holes=True,
                ghosting_filter=True
            )
            textured_models += 1

        if textured_models > 0:
            self._set_chunk_textured_flag(chunk, True)
        return textured_models

    def _texturize_chunk_list(self, chunks, max_area=None, progress_title="Texturizing"):
        processed = 0
        total = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            if not chunk.model:
                continue
            processed += self._texturize_chunk_models(chunk, max_area=max_area)
            if total > 0:
                progress = (idx / total) * 100
                print(f"{progress_title}: {progress:.2f}% ({idx}/{total} chunks)")
            ps.app.update()
        return processed

    def texturize_models(self):
        try:
            print("Starting texturize script")
            ps.app.update()
            processed = self._texturize_chunk_list(list(self.doc.chunks), max_area=None, progress_title="Texturize")
            ps.app.update()
            ps.app.messageBox(f"Success - Texturization completed. Textured models: {processed}.")
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def texturize_models_200(self):
        try:
            print("Starting texturize script with 200m² limit")
            ps.app.update()
            processed = self._texturize_chunk_list(list(self.doc.chunks), max_area=200, progress_title="Texturize200")
            ps.app.update()
            ps.app.messageBox(f"Success - Texturization with 200m² limit completed. Textured models: {processed}.")
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def prepare_or_flag_lod0(self):
        try:
            chunk = self.doc.chunk
            if chunk is None or not chunk.model:
                ps.app.messageBox("Error - Select a chunk with a mesh model first.")
                return

            create_decimated_copy = ps.app.getBool(
                "STEP1 - Create an optional LOD0 decimated copy?\n"
                "(No = use current giant mesh as LOD0)"
            )

            target_chunk = chunk
            mode = "original"
            info = "Current mesh flagged as LOD0."

            if create_decimated_copy:
                density_str = ps.app.getString(
                    "Target polygon density for LOD0 (polygons per m²):",
                    "10000"
                )
                if not density_str:
                    return
                target_density = float(str(density_str).replace(",", "."))
                if target_density <= 0:
                    raise Exception("Polygon density must be > 0.")

                target_chunk = chunk.copy()
                target_chunk.label = (chunk.label if chunk.label else "chunk") + "_LOD0"
                self.doc.chunk = target_chunk

                area_m2 = target_chunk.model.area() if target_chunk.model else 0
                target_faces = int(max(10000, area_m2 * target_density))

                try:
                    target_chunk.decimateModel(face_count=target_faces)
                    mode = "decimated"
                    info = f"LOD0 decimated copy created with target ~{target_faces} faces."
                except Exception as dec_err:
                    mode = "copy_no_decimation"
                    info = (
                        "LOD0 copy created, but decimation was not applied by Metashape API.\n"
                        f"Reason: {str(dec_err)}"
                    )

            if hasattr(target_chunk, "meta"):
                target_chunk.meta["3dsc_workflow_lod0"] = "1"
                target_chunk.meta["3dsc_workflow_lod0_mode"] = mode
            self.workflow_state["lod0_chunk_key"] = self._chunk_key(target_chunk)
            self.workflow_state["cut_source_chunk_key"] = self._chunk_key(target_chunk)
            self._set_chunk_textured_flag(target_chunk, False)

            ps.app.messageBox("STEP1 completed.\n" + info)

        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def texturize_workflow_blocks(self):
        try:
            if not self.workflow_state.get("cut_blocks"):
                ps.app.messageBox("No workflow blocks found. Run STEP2 first.")
                return

            mode = self.workflow_state.get("cut_mode")
            chunks = []
            if mode == "multi_chunk":
                chunks = self._get_workflow_chunks()
            else:
                source_chunk = self._get_chunk_by_key(self.workflow_state.get("cut_source_chunk_key"))
                if source_chunk:
                    chunks = [source_chunk]

            if not chunks:
                ps.app.messageBox("No target chunks available for STEP3 texturing.")
                return

            processed = self._texturize_chunk_list(chunks, max_area=None, progress_title="Workflow STEP3")
            ps.app.update()
            ps.app.messageBox(f"STEP3 completed. Textured models: {processed}.")
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def generate_workflow_lods_experimental(self):
        try:
            if not self.workflow_state.get("cut_blocks"):
                ps.app.messageBox("No workflow blocks found. Run STEP2 first.")
                return

            ratio1_str = ps.app.getString("STEP4 - LOD1 decimation ratio (0..1):", "0.5")
            ratio2_str = ps.app.getString("STEP4 - LOD2 decimation ratio (0..1):", "0.25")
            if not ratio1_str or not ratio2_str:
                return

            ratio1 = float(str(ratio1_str).replace(",", "."))
            ratio2 = float(str(ratio2_str).replace(",", "."))
            if ratio1 <= 0 or ratio1 >= 1 or ratio2 <= 0 or ratio2 >= 1:
                raise Exception("LOD ratios must be between 0 and 1.")

            preserve_borders = ps.app.getBool("Try to preserve borders during decimation? (if supported)")
            build_normal_maps = ps.app.getBool("Build normal maps for generated LOD chunks? (if supported)")

            source_chunks = []
            mode = self.workflow_state.get("cut_mode")
            if mode == "multi_chunk":
                source_chunks = self._get_workflow_chunks()
            else:
                source_chunk = self._get_chunk_by_key(self.workflow_state.get("cut_source_chunk_key"))
                if source_chunk:
                    source_chunks = [source_chunk]

            if not source_chunks:
                raise Exception("No source chunk available for STEP4.")

            created = 0
            for source_chunk in source_chunks:
                if not source_chunk.model:
                    continue

                base_area = source_chunk.model.area() if source_chunk.model else 0.0
                base_faces = int(max(1000, base_area * 10000)) if base_area else 100000

                for lod_name, ratio in [("LOD1", ratio1), ("LOD2", ratio2)]:
                    lod_chunk = source_chunk.copy()
                    lod_chunk.label = f"{source_chunk.label}_{lod_name}"
                    try:
                        face_count = int(max(500, base_faces * ratio))
                        try:
                            lod_chunk.decimateModel(face_count=face_count, preserve_boundary=preserve_borders)
                        except Exception:
                            lod_chunk.decimateModel(face_count=face_count)
                    except Exception as dec_err:
                        print(f"STEP4 warning - decimation failed for {lod_chunk.label}: {str(dec_err)}")

                    if build_normal_maps:
                        try:
                            lod_chunk.buildNormalMap()
                        except Exception as nm_err:
                            print(f"STEP4 warning - normal map not generated for {lod_chunk.label}: {str(nm_err)}")

                    self._set_chunk_textured_flag(lod_chunk, self._is_chunk_textured(source_chunk))
                    created += 1
                    ps.app.update()

            ps.app.messageBox(
                f"STEP4 completed (experimental). Created {created} LOD chunks.\n"
                "Normal map and border preservation depend on the Metashape API version."
            )

        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def export_workflow_blocks_textured(self):
        try:
            if not self.workflow_state.get("cut_blocks"):
                ps.app.messageBox("No workflow blocks found. Run STEP2 first.")
                return

            panel = self._show_step7_options_dialog()
            if not panel:
                return

            export_folder = panel["export_folder"]
            use_shift = False
            shift_line = None
            crs = None
            shift = None

            use_shift = panel["use_shift"]
            if use_shift:
                if self.global_shift_vector is not None:
                    crs = self.global_shift_crs
                    shift = self.global_shift_vector
                    shift_line = self.global_shift_line
                else:
                    shift_file = panel.get("shift_file")
                    parsed = self._read_shift_parameters_from_file(shift_file)
                    crs = parsed["crs"]
                    shift = parsed["shift"]
                    shift_line = parsed["line"]

            save_textures = panel["save_textures"]
            mode = self.workflow_state.get("cut_mode")
            exported = 0

            if mode == "multi_chunk":
                chunks = self._get_workflow_chunks()
                if not chunks:
                    ps.app.messageBox("No workflow chunks found. Run STEP2 again.")
                    return

                for chunk in chunks:
                    if not self._is_chunk_textured(chunk):
                        raise Exception(f"Chunk '{chunk.label}' is not marked as textured. Run STEP3 first.")
                    if not chunk.model:
                        continue

                    out_name = (chunk.label if chunk.label else "block") + ".obj"
                    out_path = os.path.join(export_folder, out_name)
                    kwargs = dict(
                        path=out_path,
                        format=ps.ModelFormat.ModelFormatOBJ,
                        save_texture=save_textures,
                        save_uv=save_textures,
                        save_normals=True,
                        save_colors=True
                    )
                    if use_shift and shift is not None:
                        kwargs["shift"] = shift
                        if crs is not None:
                            kwargs["crs"] = crs
                    chunk.exportModel(**kwargs)
                    exported += 1
            else:
                chunk = self._get_chunk_by_key(self.workflow_state.get("cut_source_chunk_key"))
                if chunk is None:
                    chunk = self.doc.chunk
                if chunk is None or not chunk.model:
                    raise Exception("No chunk/model available for STEP5 export.")
                if not self._is_chunk_textured(chunk):
                    raise Exception("Current workflow chunk is not marked as textured. Run STEP3 first.")

                models = self._extract_models(chunk)
                block_defs = self.workflow_state.get("cut_blocks", [])

                if len(models) <= 1:
                    out_path = os.path.join(export_folder, "workflow_block.obj")
                    kwargs = dict(
                        path=out_path,
                        format=ps.ModelFormat.ModelFormatOBJ,
                        save_texture=save_textures,
                        save_uv=save_textures,
                        save_normals=True,
                        save_colors=True
                    )
                    if use_shift and shift is not None:
                        kwargs["shift"] = shift
                        if crs is not None:
                            kwargs["crs"] = crs
                    chunk.exportModel(**kwargs)
                    exported = 1
                else:
                    for idx, model in enumerate(models):
                        if not self._activate_model(chunk, model):
                            continue
                        block_name = f"block_{idx:04d}"
                        if idx < len(block_defs):
                            block_name = block_defs[idx]["name"]
                        out_path = os.path.join(export_folder, block_name + ".obj")
                        kwargs = dict(
                            path=out_path,
                            format=ps.ModelFormat.ModelFormatOBJ,
                            save_texture=save_textures,
                            save_uv=save_textures,
                            save_normals=True,
                            save_colors=True
                        )
                        if use_shift and shift is not None:
                            kwargs["shift"] = shift
                            if crs is not None:
                                kwargs["crs"] = crs
                        chunk.exportModel(**kwargs)
                        exported += 1

            if use_shift and shift_line:
                with open(os.path.join(export_folder, "shift.txt"), "w", encoding="utf-8") as f:
                    f.write(shift_line + "\n")

            ps.app.messageBox(f"STEP5 completed. Exported meshes: {exported}.")
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
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
            projection_coor = None
            
            for ob_txt in file_list:
                if ob_txt.endswith(".txt"):
                    file_txt_fullpath = str(path_folder + ob_txt)
                    print(file_txt_fullpath)
                    
                    with open(file_txt_fullpath, 'r', encoding='utf-8') as f:
                        first = f.readline()
                        parts = first.split()
                        crs_string = parts[0]
                        shift_coor_x = float(parts[1])
                        shift_coor_y = float(parts[2])
                        shift_coor_z = float(parts[3])
                        shift_coor = ps.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
                        coord_shift = True
                        
                        # Handle CRS: only set if not LOCAL or NONE
                        if crs_string.upper() not in ['LOCAL', 'LOCAL_CS', 'NONE']:
                            projection_coor = crs_string
                        
                        print(shift_coor_x)
                        if projection_coor:
                            print(f"Using CRS: {projection_coor}")
                        else:
                            print("Using local coordinates (no CRS)")

            if not coord_shift and self.global_shift_vector is not None:
                coord_shift = True
                shift_coor = self.global_shift_vector
                projection_coor = self.global_shift_crs_string if self.global_shift_crs else None
                print("Using global shift from GUI settings.")
            
            # Export each chunk
            number = 0
            for i in range(0, len(self.doc.chunks)):
                chunk = self.doc.chunks[i]
                
                if chunk.model:
                    ob_fullpath = str(path_folder + chunk.label + "_mt.obj")
                    
                    if coord_shift:
                        if projection_coor:
                            # Export with CRS and shift
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
                            # Export with shift only (local coordinates)
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
            ps.app.messageBox(f"Success - Exported {number} models successfully.")
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def export_single_model_with_shift(self):
        try:
            # Check if there's an active chunk
            if self.doc.chunk is None:
                ps.app.messageBox("Error - No active chunk found.")
                return
            
            chunk = self.doc.chunk
            
            crs, shift_coor, _ = self._resolve_shift_for_operation(
                "Export Single Model with Shift", ask_if_missing=True
            )
            
            # Ask for destination folder and filename
            save_folder = ps.app.getExistingDirectory("Specify the folder to save the OBJ file:")
            if not save_folder:
                return
            
            file_name = ps.app.getString("Enter the name of the OBJ file:", chunk.label)
            if not file_name:
                file_name = chunk.label
            
            save_path = os.path.join(save_folder, file_name + ".obj")
            
            # Export the model
            if crs and shift_coor:
                chunk.exportModel(path=save_path, format=ps.ModelFormat.ModelFormatOBJ, crs=crs, shift=shift_coor)
            elif shift_coor:
                chunk.exportModel(path=save_path, format=ps.ModelFormat.ModelFormatOBJ, shift=shift_coor)
            else:
                chunk.exportModel(path=save_path, format=ps.ModelFormat.ModelFormatOBJ)
            
            ps.app.messageBox(f"Success - Model exported successfully to {save_path}.")
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def export_tiled_models(self):
        try:
            # Get export folder
            export_folder = ps.app.getExistingDirectory("Specify destination folder for 3D models: ")
            if not export_folder:
                return
            export_folder += "/"

            _, shift, shift_line = self._resolve_shift_for_operation(
                "Export Tiled Models", ask_if_missing=True
            )
            
            # Get active chunk
            chunk = self.doc.chunk
            
            # Set export parameters
            tile_format = ps.TileFormat.TileFormatOBJ
            texture_format = ps.ImageFormat.ImageFormatPNG
            
            # Check for tiled model
            tiled_model = chunk.tiled_model
            if not tiled_model:
                ps.app.messageBox("Error - No tiled model found in the active chunk.")
                return
            
            # Create export folder if it doesn't exist
            if not os.path.exists(export_folder):
                os.makedirs(export_folder)
            
            # Export tiles
            for tile_index in range(len(tiled_model.tiles)):
                tile_name = f"tile_{tile_index:04d}"
                obj_path = os.path.join(export_folder, f"{tile_name}.obj")
                png_path = os.path.join(export_folder, f"{tile_name}.png")
                
                if shift:
                    tiled_model.exportTile(tile_index, obj_path, tile_format, translation=shift)
                else:
                    tiled_model.exportTile(tile_index, obj_path, tile_format)
                
                # Export the texture
                tiled_model.exportTileTexture(tile_index, png_path, texture_format)

            if shift_line:
                with open(os.path.join(export_folder, "shift.txt"), "w", encoding="utf-8") as f:
                    f.write(shift_line + "\n")
            
            ps.app.messageBox(f"Success - Exported {len(tiled_model.tiles)} tiled models successfully.")
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def cut_giant_mesh_into_blocks_with_shift(self):
        try:
            if self.doc.chunk is None:
                ps.app.messageBox("Error - No active chunk found.")
                return

            chunk = self.doc.chunk
            if not chunk.model:
                ps.app.messageBox("Error - No mesh model found in the active chunk.")
                return

            panel = self._show_step3_options_dialog(has_tiled_model=bool(chunk.tiled_model))
            if not panel:
                return

            run_step2_now = panel["run_step2_now"]
            if run_step2_now:
                self.prepare_or_flag_lod0()
                lod_chunk = self._get_chunk_by_key(self.workflow_state.get("lod0_chunk_key"))
                if lod_chunk and lod_chunk.model:
                    chunk = lod_chunk
                    self.doc.chunk = chunk

            target_area_m2 = panel["target_area_m2"]
            output_multi_chunks = panel["output_multi_chunks"]
            grid_naming = panel["grid_naming"]
            export_temp_textures = panel["export_temp_textures"]
            cleanup_temp_files = panel["cleanup_temp_files"]
            export_root = panel["export_root"]
            rebuild_tiled = panel["rebuild_tiled_model"]
            if rebuild_tiled or not chunk.tiled_model:
                self._build_tiled_model_with_area_hint(chunk, target_area_m2)
                ps.app.update()

            tiled_model = chunk.tiled_model
            if not tiled_model:
                raise Exception("Failed to build tiled model from the active chunk model.")

            chunk_label = chunk.label if chunk.label else "active_chunk"
            safe_label = "".join(c if c.isalnum() or c in ('_', '-', '.') else '_' for c in chunk_label)
            blocks_folder = os.path.join(export_root, safe_label + "_workflow_blocks")
            os.makedirs(blocks_folder, exist_ok=True)

            tile_format = ps.TileFormat.TileFormatOBJ
            texture_format = ps.ImageFormat.ImageFormatPNG
            texture_errors = 0
            cut_blocks = []
            tile_count = len(tiled_model.tiles)
            grid_cols = int(max(1, math.ceil(math.sqrt(tile_count))))

            for tile_index in range(tile_count):
                if grid_naming:
                    row = (tile_index // grid_cols) + 1
                    col = (tile_index % grid_cols) + 1
                    block_name = f"block_x{col:03d}_y{row:03d}"
                else:
                    block_name = f"block_{tile_index:04d}"

                obj_path = os.path.join(blocks_folder, block_name + ".obj")
                png_path = os.path.join(blocks_folder, block_name + ".png")
                tiled_model.exportTile(tile_index, obj_path, tile_format)

                if export_temp_textures:
                    try:
                        tiled_model.exportTileTexture(tile_index, png_path, texture_format)
                    except Exception:
                        texture_errors += 1
                        png_path = None
                else:
                    png_path = None

                cut_blocks.append(
                    {
                        "index": tile_index,
                        "name": block_name,
                        "obj_path": obj_path,
                        "png_path": png_path,
                    }
                )

            generated_chunk_keys = []
            same_chunk_warning = None

            if output_multi_chunks:
                for block in cut_blocks:
                    new_chunk = chunk.copy()
                    new_chunk.label = f"{safe_label}_{block['name']}"
                    self._prepare_lightweight_chunk(new_chunk)
                    new_chunk.importModel(path=block["obj_path"], format=ps.ModelFormat.ModelFormatOBJ)
                    self._set_chunk_textured_flag(new_chunk, False)
                    if hasattr(new_chunk, "meta"):
                        new_chunk.meta["3dsc_workflow_block_name"] = block["name"]
                    generated_chunk_keys.append(self._chunk_key(new_chunk))
                self.workflow_state["cut_mode"] = "multi_chunk"
                self.workflow_state["generated_chunk_keys"] = generated_chunk_keys
            else:
                self.workflow_state["cut_mode"] = "same_chunk"
                self.workflow_state["generated_chunk_keys"] = []
                existing_models = self._extract_models(chunk)
                existing_ids = set(id(m) for m in existing_models)
                for block in cut_blocks:
                    chunk.importModel(path=block["obj_path"], format=ps.ModelFormat.ModelFormatOBJ)
                models_after = self._extract_models(chunk)
                new_models = [m for m in models_after if id(m) not in existing_ids]
                for i, model in enumerate(new_models):
                    if i >= len(cut_blocks):
                        break
                    try:
                        model.label = cut_blocks[i]["name"]
                    except Exception:
                        pass
                if len(cut_blocks) > 1 and len(new_models) <= 1:
                    same_chunk_warning = (
                        "Metashape API may not support robust multi-model management in one chunk in this version. "
                        "Use the multi-chunk output mode for full control on naming/texturing/export."
                    )
                self._set_chunk_textured_flag(chunk, False)

            if cleanup_temp_files and output_multi_chunks:
                for block in cut_blocks:
                    if os.path.exists(block["obj_path"]):
                        os.remove(block["obj_path"])
                    if block["png_path"] and os.path.exists(block["png_path"]):
                        os.remove(block["png_path"])

            self.workflow_state["cut_blocks"] = cut_blocks
            self.workflow_state["cut_folder"] = blocks_folder
            self.workflow_state["cut_source_chunk_key"] = self._chunk_key(chunk)

            msg = (
                f"STEP2 completed.\n"
                f"Blocks created: {len(cut_blocks)}\n"
                f"Output mode: {'multi-chunk' if output_multi_chunks else 'same-chunk'}\n"
                f"Blocks folder: {blocks_folder}\n\n"
                f"Next: run STEP3 texturing, then STEP5 export."
            )
            if texture_errors > 0:
                msg += f"\nNotice: {texture_errors} block textures were not exported in STEP2."
            if same_chunk_warning:
                msg += f"\nWarning: {same_chunk_warning}"
            ps.app.messageBox(msg)

        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def export_undistorted_images_active_chunk(self):
        try:
            if self.doc.chunk is None:
                ps.app.messageBox("Error - No active chunk found.")
                return

            chunk = self.doc.chunk
            if not chunk.cameras:
                ps.app.messageBox("Error - Active chunk has no cameras.")
                return

            export_root = ps.app.getExistingDirectory("Select destination folder for undistorted images:")
            if not export_root:
                return

            chunk_label = chunk.label if chunk.label else "active_chunk"
            safe_label = "".join(c if c.isalnum() or c in ('_', '-', '.') else '_' for c in chunk_label)
            export_folder = os.path.join(export_root, safe_label + "_undistorted")
            os.makedirs(export_folder, exist_ok=True)

            output_pattern = os.path.join(export_folder, "{filename}.{fileext}")
            chunk.convertImages(
                path=output_pattern,
                use_initial_calibration=True,
                color_correction=False,
                merge_planes=False,
                update_gps_tags=False,
            )

            exported = len([cam for cam in chunk.cameras if cam.photo is not None])
            ps.app.update()
            ps.app.messageBox(
                f"Success - Exported {exported} undistorted images to {export_folder}."
            )

        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")

    def rename_chunks(self):
        try:
            number = 1
            for i in range(1, len(self.doc.chunks)):
                chunk = self.doc.chunks[i]
                chunk.label = str(number) + "_mt"
                number += 1
            
            ps.app.messageBox(f"Success - Renamed {number-1} chunks successfully.")
            
        except Exception as e:
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
    
    def lod_generator(self):
        ps.app.messageBox("Notice - LOD Generator is not fully implemented in the GUI yet.")
    
    def import_ipad_cameras(self):
        """
        EXPERIMENTAL FEATURE
        Import camera positions from iPad's 3D Scanner App using AR tracking data.
        This feature is still under development and may not work reliably in all cases.
        """
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
                ps.app.messageBox("Error - No image files found in the selected folder.")
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
                ps.app.messageBox("Warning - No AR camera data found in the JSON files.")
                return
            
            # Calculate and set proper region based on camera positions
            if camera_positions:
                print(f"Calculating region based on {len(camera_positions)} camera positions...")
                ps.app.update()
                
                # Trova i bounds delle posizioni delle camere
                min_x = min_y = min_z = float('inf')
                max_x = max_y = max_z = float('-inf')
                
                for pos in camera_positions:
                    min_x = min(min_x, pos.x)
                    max_x = max(max_x, pos.x)
                    min_y = min(min_y, pos.y)
                    max_y = max(max_y, pos.y)
                    min_z = min(min_z, pos.z)
                    max_z = max(max_z, pos.z)
                
                # Calcola centro e dimensioni
                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2
                center_z = (min_z + max_z) / 2
                
                size_x = max(abs(max_x - min_x), 1)
                size_y = max(abs(max_y - min_y), 1)
                size_z = max(abs(max_z - min_z), 1)
                
                # Aggiungi margine del 50%
                size_x *= 1.5
                size_y *= 1.5
                size_z *= 1.5
                
                region.center = ps.Vector([center_x, center_y, center_z])
                region.size = ps.Vector([size_x, size_y, size_z])
                chunk.region = region
                
                print(f"Region set: center={center_x:.2f},{center_y:.2f},{center_z:.2f}, size={size_x:.2f},{size_y:.2f},{size_z:.2f}")
            
            # Attempt to save the project
            save_path = None
            try:
                if self.doc.path:
                    save_path = self.doc.path
                    self.doc.save(save_path)
                    print(f"Project saved to {save_path}")
                else:
                    print("Warning: Document has no path. Please save manually.")
            except Exception as save_error:
                print(f"Error saving document: {str(save_error)}. Please save manually.")
            
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
            
            ps.app.messageBox(f"Success - Imported {len(image_files)} images with {cameras_with_data} AR camera positions.")
            
        except Exception as e:
            ps.app.update()
            print(f"Critical error: {str(e)}")
            ps.app.messageBox(f"Error: An error occurred: {str(e)}")
            
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
