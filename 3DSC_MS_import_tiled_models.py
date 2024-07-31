import Metashape
import os

# Funzione per leggere il file shift.txt
def read_shift(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        first_line = f.readline()
    projection_coor = str(first_line.split(' ')[0])
    shift_coor_x = float(first_line.split(' ')[1])
    shift_coor_y = float(first_line.split(' ')[2])
    shift_coor_z = float(first_line.split(' ')[3])
    shift_coor = Metashape.Vector([shift_coor_x, shift_coor_y, shift_coor_z])
    return shift_coor

# Ottieni la cartella contenente le tile dall'utente
import_folder = Metashape.app.getExistingDirectory("Select the folder containing the exported tiles")

# Ottieni il file shift.txt dall'utente
shift_file = Metashape.app.getOpenFileName("Select the shift.txt file")

if not import_folder:
    raise Exception("No import folder selected.")
if not shift_file:
    raise Exception("No shift.txt file selected.")

# Leggi i valori di shift
shift = read_shift(shift_file)

# Ottieni il chunk attivo
doc = Metashape.app.document
chunk = doc.chunk

# Crea un nuovo chunk per il modello reimportato
new_chunk = doc.addChunk()
new_chunk.label = "Reimported_Tiles"

# Lista dei file OBJ da importare
obj_files = [f for f in os.listdir(import_folder) if f.endswith('.obj')]

# Importa ogni file OBJ come un modello separato
for obj_file in obj_files:
    obj_path = os.path.join(import_folder, obj_file)
    
    # Applica lo shift e importa il modello
    new_chunk.importModel(obj_path, Metashape.ModelFormat.ModelFormatOBJ, shift=shift)

# Creare una mesh unificata dalle tile importate
new_chunk.buildModel(surface_type=Metashape.Arbitrary, interpolation=Metashape.EnabledInterpolation)

# Genera la texture basata sui modelli importati
new_chunk.buildUV(mapping_mode=Metashape.GenericMapping)
new_chunk.buildTexture(blending_mode=Metashape.MosaicBlending)

# Costruisci un modello a piastrelle (tiled model) dal nuovo chunk
new_chunk.buildTiledModel()

print("Reimportazione delle tile e rigenerazione del modello a piastrelle completata con successo.")
