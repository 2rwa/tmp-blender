from __future__ import annotations
import json, math, os
from pathlib import Path
import bpy
from mathutils import Vector

OUT=Path.cwd()/"output"; OUT.mkdir(parents=True,exist_ok=True)
BLEND=OUT/"geometry-nodes-volume-flame.blend"
REPORT=OUT/"geometry-nodes-volume-flame-report.json"
START,END,FPS=1,96,24
W,H,SAMPLES=480,360,16
N,R=420,0.72
PREP=os.environ.get("BLENDER_PREPARE_ONLY")=="1"

def inp(node,name):
    s=node.inputs.get(name)
    if s is None: raise KeyError(f"missing {name}: {[x.name for x in node.inputs]}")
    return s

def mathn(nodes,op,b=None):
    n=nodes.new("ShaderNodeMath"); n.operation=op
    if b is not None: n.inputs[1].default_value=b
    return n

def link(links,a,b): links.new(a,b)

def look(obj,target=(0,0,1.6)):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

def clear():
    bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)

def flame_material():
    m=bpy.data.materials.new("FlameVolume"); m.use_nodes=True
    ns=m.node_tree.nodes; ns.clear()
    out=ns.new("ShaderNodeOutputMaterial"); vol=ns.new("ShaderNodeVolumePrincipled")
    vals={"Density":1.15,"Density Attribute":"density","Emission Strength":5.0,
          "Emission Color":(1.0,0.055,0.004,1.0),"Blackbody Intensity":1.6,
          "Temperature":1450.0,"Blackbody Tint":(1.0,0.28,0.02,1.0)}
    applied=[]
    for k,v in vals.items():
        s=vol.inputs.get(k)
        if s is not None: s.default_value=v; applied.append(k)
    m.node_tree.links.new(vol.outputs["Volume"],out.inputs["Volume"])
    return m,applied

def ground_material():
    m=bpy.data.materials.new("Ground"); m.use_nodes=True
    b=m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value=(0.018,0.022,0.030,1)
    b.inputs["Roughness"].default_value=0.75; b.inputs["Metallic"].default_value=0.1
    return m

def seed_points():
    ga=math.pi*(3-math.sqrt(5)); pts=[]
    for i in range(N):
        r=R*math.sqrt((i+0.5)/N); a=i*ga
        pts.append((r*math.cos(a),r*math.sin(a),0))
    return pts

def build_nodes(obj,mat):
    g=bpy.data.node_groups.new("GN_VolumeFlame","GeometryNodeTree")
    g.interface.new_socket(name="Geometry",in_out="INPUT",socket_type="NodeSocketGeometry")
    g.interface.new_socket(name="Geometry",in_out="OUTPUT",socket_type="NodeSocketGeometry")
    n,l=g.nodes,g.links
    gi=n.new("NodeGroupInput"); pos=n.new("GeometryNodeInputPosition"); sep=n.new("ShaderNodeSeparateXYZ")
    idx=n.new("GeometryNodeInputIndex"); tm=n.new("GeometryNodeInputSceneTime")
    link(l,pos.outputs["Position"],sep.inputs["Vector"])
    iph=mathn(n,"MULTIPLY",0.61803398875); link(l,idx.outputs["Index"],iph.inputs[0])
    ts=mathn(n,"MULTIPLY",0.86); link(l,tm.outputs["Seconds"],ts.inputs[0])
    add=mathn(n,"ADD"); link(l,iph.outputs[0],add.inputs[0]); link(l,ts.outputs[0],add.inputs[1])
    age=mathn(n,"FRACT"); link(l,add.outputs[0],age.inputs[0])
    tmul=mathn(n,"MULTIPLY",-0.78); link(l,age.outputs[0],tmul.inputs[0])
    taper=mathn(n,"ADD",1.0); link(l,tmul.outputs[0],taper.inputs[0])
    xs=mathn(n,"MULTIPLY"); ys=mathn(n,"MULTIPLY")
    link(l,sep.outputs["X"],xs.inputs[0]); link(l,taper.outputs[0],xs.inputs[1])
    link(l,sep.outputs["Y"],ys.inputs[0]); link(l,taper.outputs[0],ys.inputs[1])
    ap=mathn(n,"MULTIPLY",10.0); ip=mathn(n,"MULTIPLY",0.37)
    link(l,age.outputs[0],ap.inputs[0]); link(l,idx.outputs["Index"],ip.inputs[0])
    ph=mathn(n,"ADD"); link(l,ap.outputs[0],ph.inputs[0]); link(l,ip.outputs[0],ph.inputs[1])
    sn=mathn(n,"SINE"); cp=mathn(n,"MULTIPLY",1.27); cs=mathn(n,"COSINE")
    link(l,ph.outputs[0],sn.inputs[0]); link(l,ph.outputs[0],cp.inputs[0]); link(l,cp.outputs[0],cs.inputs[0])
    am=mathn(n,"MULTIPLY",0.28); link(l,age.outputs[0],am.inputs[0])
    amp=mathn(n,"ADD",0.08); link(l,am.outputs[0],amp.inputs[0])
    xw=mathn(n,"MULTIPLY"); yw=mathn(n,"MULTIPLY")
    link(l,sn.outputs[0],xw.inputs[0]); link(l,amp.outputs[0],xw.inputs[1])
    link(l,cs.outputs[0],yw.inputs[0]); link(l,amp.outputs[0],yw.inputs[1])
    xf=mathn(n,"ADD"); yf=mathn(n,"ADD")
    link(l,xs.outputs[0],xf.inputs[0]); link(l,xw.outputs[0],xf.inputs[1])
    link(l,ys.outputs[0],yf.inputs[0]); link(l,yw.outputs[0],yf.inputs[1])
    zm=mathn(n,"MULTIPLY",4.6); zf=mathn(n,"ADD",-0.15)
    link(l,age.outputs[0],zm.inputs[0]); link(l,zm.outputs[0],zf.inputs[0])
    comb=n.new("ShaderNodeCombineXYZ")
    link(l,xf.outputs[0],comb.inputs["X"]); link(l,yf.outputs[0],comb.inputs["Y"]); link(l,zf.outputs[0],comb.inputs["Z"])
    sp=n.new("GeometryNodeSetPosition"); link(l,gi.outputs["Geometry"],sp.inputs["Geometry"]); link(l,comb.outputs["Vector"],sp.inputs["Position"])
    rm=mathn(n,"MULTIPLY",-0.24); rad=mathn(n,"ADD",0.34)
    link(l,age.outputs[0],rm.inputs[0]); link(l,rm.outputs[0],rad.inputs[0])
    mtp=n.new("GeometryNodeMeshToPoints"); mtp.mode="VERTICES"; link(l,sp.outputs["Geometry"],mtp.inputs["Mesh"])
    pv=n.new("GeometryNodePointsToVolume"); pv.resolution_mode="VOXEL_SIZE"
    inp(pv,"Density").default_value=2.2; inp(pv,"Voxel Size").default_value=0.11
    link(l,mtp.outputs["Points"],inp(pv,"Points")); link(l,rad.outputs[0],inp(pv,"Radius"))
    sm=n.new("GeometryNodeSetMaterial"); sm.inputs["Material"].default_value=mat; link(l,pv.outputs["Volume"],sm.inputs["Geometry"])
    go=n.new("NodeGroupOutput"); go.is_active_output=True; link(l,sm.outputs["Geometry"],go.inputs["Geometry"])
    mod=obj.modifiers.new(name="GeometryNodes",type="NODES"); mod.node_group=g
    return g

def add_point(name,loc,energy,color,size):
    d=bpy.data.lights.new(name=name,type="POINT"); d.energy=energy; d.color=color; d.shadow_soft_size=size
    o=bpy.data.objects.new(name,d); bpy.context.collection.objects.link(o); o.location=loc

def main():
    clear(); sc=bpy.context.scene
    engine="BLENDER_WORKBENCH"
    for e in ("BLENDER_EEVEE_NEXT","BLENDER_EEVEE"):
        try: sc.render.engine=e; engine=e; break
        except TypeError: pass
    eff=None; ev=getattr(sc,"eevee",None)
    if ev is not None:
        if hasattr(ev,"taa_render_samples"): ev.taa_render_samples=SAMPLES; eff=int(ev.taa_render_samples)
        if hasattr(ev,"volumetric_samples"): ev.volumetric_samples=16
        if hasattr(ev,"volumetric_tile_size"): ev.volumetric_tile_size="8"
    sc.frame_start=START; sc.frame_end=END; sc.frame_current=START; sc.render.fps=FPS
    sc.render.resolution_x=W; sc.render.resolution_y=H; sc.render.resolution_percentage=100
    sc.render.image_settings.file_format="PNG"; sc.render.image_settings.color_mode="RGB"
    sc.world.use_nodes=True; bg=sc.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value=(0.0015,0.002,0.0035,1); bg.inputs["Strength"].default_value=0.08
    fm,applied=flame_material(); gm=ground_material()
    me=bpy.data.meshes.new("FlameSeedPoints"); me.from_pydata(seed_points(),[],[]); me.update()
    host=bpy.data.objects.new("GeometryNodesVolumeFlame",me); bpy.context.collection.objects.link(host); host.data.materials.append(fm)
    group=build_nodes(host,fm)
    bpy.ops.mesh.primitive_plane_add(size=16,location=(0,0,-0.35)); bpy.context.object.data.materials.append(gm)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=0.82,depth=0.38,location=(0,0,-0.18)); bpy.context.object.data.materials.append(gm)
    cd=bpy.data.cameras.new("Camera"); cam=bpy.data.objects.new("Camera",cd); bpy.context.collection.objects.link(cam); sc.camera=cam
    cam.location=(5.6,-7.4,3.7); cd.lens=58; look(cam)
    add_point("FireLight",(0,0,1.2),650,(1,0.18,0.025),2.4); add_point("Fill",(-3,-3,3.5),90,(0.1,0.18,0.4),3)
    report={"object":host.name,"modifier":"GeometryNodes","node_group":group.name,"node_count":len(group.nodes),
      "node_types":[x.bl_idname for x in group.nodes],"material_node_types":[x.bl_idname for x in fm.node_tree.nodes],
      "material_inputs_applied":applied,"seed_point_count":N,"frame_start":START,"frame_end":END,"fps":FPS,
      "resolution_x":W,"resolution_y":H,"requested_render_samples":SAMPLES,"effective_render_samples":eff,
      "points_to_volume_resolution_mode":"VOXEL_SIZE","points_to_volume_voxel_size":0.11}
    REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    print(f"BLENDER_ENGINE={engine}\nGN_NODE_COUNT={len(group.nodes)}\nGN_SEED_POINTS={N}\nRENDER_RESOLUTION={W}x{H}\nBLEND_PATH={BLEND}")
    if PREP: print("BLENDER_PREPARE_ONLY=1"); return
    sc.frame_set(48); sc.render.filepath=str(OUT/"preview.png"); bpy.ops.render.render(write_still=True)

if __name__=="__main__": main()
