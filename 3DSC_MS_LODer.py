import Metashape
import math


def create_sub_bboxes(original_bbox, sub_bbox_size):
    center = original_bbox.center
    size = original_bbox.size
    min_point = Metashape.Vector([center.x - size.x / 2, center.y - size.y / 2, center.z - size.z / 2])
    max_point = Metashape.Vector([center.x + size.x / 2, center.y + size.y / 2, center.z + size.z / 2])

    sub_bboxes = []
    # Calcola il numero di bounding box per ciascuna direzione
    # Resto del codice...
    
    # Calcola il numero di bounding box per ciascuna direzione
    x_steps = int(math.ceil((max_point.x - min_point.x) / sub_bbox_size.x))
    y_steps = int(math.ceil((max_point.y - min_point.y) / sub_bbox_size.y))
    z_steps = int(math.ceil((max_point.z - min_point.z) / sub_bbox_size.z))

    # Crea i bounding box più piccoli
    for x in range(x_steps):
        for y in range(y_steps):
            for z in range(z_steps):
                min_sub = Metashape.Vector([min_point.x + x * sub_bbox_size.x,
                                            min_point.y + y * sub_bbox_size.y,
                                            min_point.z + z * sub_bbox_size.z])
                max_sub = min_sub + sub_bbox_size
                # Assicurati che il bounding box non ecceda le dimensioni originali
                max_sub = Metashape.Vector([min(max_sub.x, max_point.x),
                                            min(max_sub.y, max_point.y),
                                            min(max_sub.z, max_point.z)])

                sub_bbox = Metashape.Region(min_sub, max_sub)
                sub_bboxes.append(sub_bbox)

    return sub_bboxes

def duplicate_mesh(chunk):
    original_model = chunk.model
    if original_model is None:
        print("Nessun modello trovato nel chunk.")
        return None

    # La copia diretta dei dati della mesh può non essere supportata.
    # Potresti dover esportare e reimportare la mesh o utilizzare altre strategie.
    # ...

    return duplicated_mesh


def export_and_remove_polys(chunk, sub_bbox, duplicated_mesh, export_path):
    # Imposta il bounding box del chunk per l'esportazione
    chunk.region = sub_bbox

    # Esporta la mesh
    chunk.exportModel(export_path, binary=True, format=Metashape.ModelFormat.ModelFormatOBJ)
        
doc = Metashape.app.document
chunk = doc.chunk
original_bbox = chunk.region
sub_bbox_size = Metashape.Vector([10, 10, 10])  # Dimensioni dei bbox più piccoli
sub_bboxes = create_sub_bboxes(original_bbox, sub_bbox_size)

# Duplica la mesh originale
original_mesh = chunk.model
if original_mesh is not None:
    duplicated_mesh = duplicate_mesh(original_mesh)

    # Esporta e rimuovi i poligoni per ogni sub_bbox
    for index, sub_bbox in enumerate(sub_bboxes):
        export_path = f"mesh_part_{index}.obj"  # Percorso di esportazione
        export_and_remove_polys(chunk, sub_bbox, duplicated_mesh, export_path)
else:
    print("Nessuna mesh trovata nel chunk corrente.")
