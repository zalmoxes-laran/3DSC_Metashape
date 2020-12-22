# Script from Emanuel Demetrescu emanuel.demetrescu@gmail.com CC-BY

import os
import Metashape as ps

doc = ps.app.document
print("CIAO")
ps.app.update()

# get folder of 3d models
path_folder = ps.app.getExistingDirectory("Specify folder with 3D models: ")
path_folder += "/"

#print(path_folder)
file_list = os.listdir(path_folder)
coord_shift = False
for ob_txt in file_list:
    if ob_txt.rsplit(".",1)[1] == "txt":
        # QUI DEVO LEGGERE LE COORDINATE E LO SHIFT
        file_txt_fullpath = str(path_folder + ob_txt)
        print(file_txt_fullpath)
        f = open(file_txt_fullpath, 'r', encoding='utf-8')
#        f = os.open(file_txt_fullpath,”r”)
        first = f.readline()
        projection_coor = str(first.split(' ')[0])
        shift_coor_x = int(first.split(' ')[1])
        shift_coor_y = int(first.split(' ')[2])
        shift_coor_z = int(first.split(' ')[3])
        shift_coor = ps.Vector([shift_coor_x,shift_coor_y,shift_coor_z])
        coord_shift = True
        print(shift_coor_x)
        f.close()
    else:
        pass

obj_list = list()
chuncknumber = 1
for ob in file_list:
    if ob.rsplit(".",1)[1] in ["obj", "ply", "dae"]:
        format_file = str(ob.rsplit(".",1)[1])
        if format_file == "obj":
            format_file = "ModelFormatOBJ"
        ob_fullpath = str(path_folder + ob)
        obj_list.append(ob_fullpath)
        print(ob)
        doc.chunk = doc.chunks[0]
        chunk = doc.chunks[0].copy()
        doc.chunk = doc.chunks[chuncknumber]
        doc.chunk.label = ob
        if coord_shift is True:
           doc.chunk.importModel(path= ob_fullpath, format= ps.ModelFormat.ModelFormatOBJ,crs = ps.CoordinateSystem(projection_coor), shift = shift_coor)
        else:
            doc.chunk.importModel(path= ob_fullpath, format= format_file)
        chuncknumber +=1
    else:
        pass

print(obj_list)
ps.app.update()
print("step finished")
