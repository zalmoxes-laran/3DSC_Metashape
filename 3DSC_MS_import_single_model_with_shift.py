import Metashape as ps

def read_shift_parameters(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            first_line = file.readline()
            projection_coor, shift_coor_x, shift_coor_y, shift_coor_z = first_line.split()
            return ps.Vector([float(shift_coor_x), float(shift_coor_y), float(shift_coor_z)]), projection_coor
    except Exception as e:
        print(f"Errore nella lettura del file shift.txt: {e}")
        return None, None

doc = ps.app.document
print("Benvenuto nell'importer 3D di Metashape")

# Chiede all'utente di specificare un modello 3D
model_path = ps.app.getOpenFileName("Specify the 3D model file:")
if not model_path:
    print("Nessun file modello selezionato.")
    exit()

# Chiede all'utente di specificare un file shift (opzionale)
shift_path = ps.app.getOpenFileName("Specify the shift file (optional):")
shift_coor, projection_coor = None, None
if shift_path:
    shift_coor, projection_coor = read_shift_parameters(shift_path)

# Verifica se esiste un chunk attivo
if doc.chunk is None:
    print("Nessun chunk attivo trovato. Creazione di un nuovo chunk.")
    chunk = doc.addChunk()
else:
    chunk = doc.chunk
    print("Utilizzo del chunk attivo.")

# Importazione del modello
if shift_coor:
    chunk.importModel(path=model_path, shift=shift_coor, crs=ps.CoordinateSystem(projection_coor))
else:
    chunk.importModel(path=model_path)

print("Modello importato con successo nel chunk attivo.")
