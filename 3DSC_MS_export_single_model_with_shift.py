import Metashape as ps
import os

def read_shift_parameters(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            first_line = file.readline()
            projection_coor, shift_coor_x, shift_coor_y, shift_coor_z = first_line.split()
            return ps.CoordinateSystem(projection_coor), ps.Vector([float(shift_coor_x), float(shift_coor_y), float(shift_coor_z)])
    except Exception as e:
        print(f"Errore nella lettura del file shift.txt: {e}")
        return None, None

doc = ps.app.document
print("Benvenuto nell'esportatore 3D di Metashape")

# Verifica se esiste un chunk attivo
if doc.chunk is None:
    print("Nessun chunk attivo trovato.")
    exit()
else:
    chunk = doc.chunk
    print("Utilizzo del chunk attivo.")

# Chiede all'utente di specificare un file shift (opzionale)
shift_path = ps.app.getOpenFileName("Specify the shift file (optional):")
crs, shift_coor = None, None
if shift_path:
    crs, shift_coor = read_shift_parameters(shift_path)

# Chiede all'utente di specificare la cartella di destinazione e il nome del file
save_folder = ps.app.getExistingDirectory("Specify the folder to save the OBJ file:")
if not save_folder:
    print("Nessuna cartella selezionata.")
    exit()

file_name = ps.app.getString("Enter the name of the OBJ file:", chunk.label)
if not file_name:
    file_name = chunk.label

save_path = os.path.join(save_folder, file_name + ".obj")

# Esportazione del modello
chunk.exportModel(path=save_path, format=ps.ModelFormat.ModelFormatOBJ, crs=crs, shift=shift_coor)

print(f"Modello esportato con successo in {save_path}.")
