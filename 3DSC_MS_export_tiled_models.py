import os
import Metashape as ps

# Funzione per leggere il file shift.txt
def read_shift(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        first_line = f.readline()
    projection_coor = str(first_line.split(' ')[0])
    shift_coor_x = float(first_line.split(' ')[1])
    shift_coor_y = float(first_line.split(' ')[2])
    shift_coor_z = float(first_line.split(' ')[3])
    shift_coor = ps.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
    return shift_coor

# Ottieni la cartella di esportazione dall'utente
export_folder = ps.app.getExistingDirectory("Specify destination folder for 3D models: ")
export_folder += "/"

# Ottieni il file shift.txt dall'utente
shift_file = ps.app.getOpenFileName("Select the shift.txt file")

if not export_folder:
    raise Exception("No export folder selected.")
if not shift_file:
    raise Exception("No shift.txt file selected.")

# Leggi i valori di shift
shift = read_shift(shift_file)

# Ottieni il chunk attivo
doc = ps.app.document
chunk = doc.chunk

# Imposta i parametri di esportazione
tile_format = ps.TileFormat.TileFormatOBJ  # Formato OBJ
texture_format = ps.ImageFormat.ImageFormatPNG  # Formato PNG

# Ottieni il modello a piastrelle
tiled_model = chunk.tiled_model

# Verifica che esista un modello a piastrelle
if not tiled_model:
    raise Exception("No tiled model found in the active chunk.")

# Crea la cartella di esportazione se non esiste
if not os.path.exists(export_folder):
    os.makedirs(export_folder)

# Esporta le singole tile in formato OBJ e le texture in PNG
for tile_index in range(len(tiled_model.tiles)):
    # Definisce il nome del file per ogni tile
    tile_name = f"tile_{tile_index:04d}"
    obj_path = os.path.join(export_folder, f"{tile_name}.obj")
    png_path = os.path.join(export_folder, f"{tile_name}.png")
    
    # Esporta la tile con lo shift
    tiled_model.exportTile(tile_index, obj_path, tile_format, translation=shift)
    
    # Esporta la texture
    tiled_model.exportTileTexture(tile_index, png_path, texture_format)

print("Esportazione completata.")
