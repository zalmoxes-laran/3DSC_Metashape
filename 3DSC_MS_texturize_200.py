import os
import Metashape as ps

doc = ps.app.document

x_res_a_terra = 1.26
tex = 4096
ratio = 0.6
max_area = 200  # Massima area in metri quadri

print("Starting texturize script")
ps.app.update()

def tex_num_from_area(area, max_area, x_res_a_terra, tex, ratio):
    # Calcola il numero di texture in base all'area massima supportata
    max_tex = 12  # Numero massimo di texture per 200 mq
    if area > max_area:
        return max_tex
    else:
        numtex = pow((10000 / x_res_a_terra), 2) / (tex * tex * ratio)
        numtex_x_area = (numtex * area) / 100
        numtex_round = round(numtex_x_area, 0)
        return max(1, numtex_round)

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

# Numero totale di chunk
total_chunks = len(doc.chunks)
chunks_processed = 0

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
            tex_num = tex_num_from_area(area_model, max_area, x_res_a_terra, tex, ratio)
            print(chunk.label+" has an area of "+str(area_model)+" mq and needs "+str(int(tex_num))+" textures.")
            chunk.buildUV(mapping_mode=ps.GenericMapping, page_count=tex_num, texture_size=tex)
            chunk.buildTexture(blending_mode = ps.MosaicBlending, texture_size=tex, fill_holes=True, ghosting_filter=True)
            
            chunks_processed += 1
            progress = (chunks_processed / total_chunks) * 100
            print(f"Progress: {progress:.2f}% completed ({chunks_processed}/{total_chunks} chunks processed)")

ps.app.update()
print("Texturization completed for all chunks.")