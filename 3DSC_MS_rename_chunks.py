
import Metashape

doc = Metashape.app.document
chunk = doc.chunk

number = 1
for i in range(1, len(doc.chunks)):
    chunk = doc.chunks[i]
    chunk.label = str(number)
    number += 1
