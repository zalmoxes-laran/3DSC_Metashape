# Script from Emanuel Demetrescu emanuel.demetrescu@gmail.com CC-BY

import os
import Metashape as ps

chunk = doc.chunk

# get folder of 3d models
path_folder = ps.app.getExistingDirectory("Specify destination folder for 3D models: ")
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

# pass through the chunks
number = 0
for i in range(0, len(doc.chunks)):
    chunk = doc.chunks[i]
    if chunk.model:
        ob_fullpath = str(path_folder + chunk.label + "_mt.obj")
        if coord_shift is True:
           #doc.chunk.exportModel(path= ob_fullpath, format= ps.ModelFormat.ModelFormatOBJ,crs = ps.CoordinateSystem(projection_coor), shift = shift_coor)
           doc.chunks[i].exportModel(path= ob_fullpath, binary=True, precision=6, texture_format=ps.ImageFormatJPEG, save_texture=True, save_uv=True, save_normals=True, save_colors=True, save_cameras=False, save_markers=False, save_udim=False, save_alpha=False, strip_extensions=False, raster_transform=ps.RasterTransformNone, colors_rgb_8bit=True, format= ps.ModelFormat.ModelFormatOBJ,crs = ps.CoordinateSystem(projection_coor), shift = shift_coor)
        else:
            doc.chunks[i].exportModel(path= ob_fullpath, binary=True, precision=6, texture_format=ps.ImageFormatJPEG, save_texture=True, save_uv=True, save_normals=True, save_colors=True, save_cameras=False, save_markers=False, save_udim=False, save_alpha=False, strip_extensions=False, raster_transform=ps.RasterTransformNone, colors_rgb_8bit=True, format= ps.ModelFormat.ModelFormatOBJ)
    else:
        pass
    number += 1

ps.app.update()

print("step finished")
