# Script from Emanuel Demetrescu emanuel.demetrescu@gmail.com CC-BY

import os
import Metashape as ps

doc = ps.app.document

x_res_a_terra = 1.26
tex = 4096
ratio = 0.6

print("Starting texturize script")
ps.app.update()

def tex_num_from_area(area,x_res_a_terra,tex,ratio):
    numtex = pow((10000 / x_res_a_terra), 2) / (tex*tex*ratio)
    #print(str(numtex))
    numtex_x_area = (numtex*area)/100
    #print(str(numtex_x_area))
    numtex_round = round(numtex_x_area,0)
    #print(str(numtex_round))
    if numtex_round == 0:
        texnum_def = 1
    else:
        texnum_def = numtex_round
    return texnum_def

def tex_num_calc(x_res_a_terra,tex,ratio):
    #x_res_a_terra = 12
    #tex = 4096
    #ratio = 0.6
    numtex = pow((10000 / x_res_a_terra), 2) / (tex*tex*ratio) #10066329.6
    print(str(numtex))
    numtex_round = round(numtex,0)
    print(str(numtex_round))
    if numtex_round == 0:
        fact = 1/numtex
        texnum_def = 1
    else:
        fact = numtex/numtex_round
        texnum_def = numtex_round
    print(str(fact))
    mq_corretto = round(100*fact,1)
    print("Alla risoluzione di "+str(x_res_a_terra)+" px/mm, servono "+str(texnum_def)+" texture "+str(tex)+" pxs. per "+str(mq_corretto)+" m2")
    return texnum_def, mq_corretto

#tex_num_calc(1.26,4096,0.6)

for chunk in doc.chunks:
    if not chunk.model:
        pass
        #raise Exception("No model!")
    else:
        current_model = chunk.model
        area_model = 0.0
        area_model = current_model.area()
        if area_model == 0.0:
            print(chunk.label+" has no area. Maybe the model isn't metric. It means that there aren't GCP or GPS information in the chunk.")
            pass
        else:
            tex_num = tex_num_from_area(area_model,x_res_a_terra,tex,ratio)
            print(chunk.label+" has an area of "+str(area_model)+" mq and needs "+str(int(tex_num))+" textures.")
            chunk.buildUV(mapping_mode=ps.GenericMapping, page_count=tex_num, texture_size=tex)
            chunk.buildTexture(blending_mode = ps.MosaicBlending, texture_size=tex, fill_holes=True, ghosting_filter=True)

ps.app.update()
print("step finished")
