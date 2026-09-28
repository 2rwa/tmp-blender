from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

SCALE=20.0

def parse_args():
    argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p=argparse.ArgumentParser()
    p.add_argument("--cache",type=Path,required=True)
    p.add_argument("--case",required=True)
    p.add_argument("--output",type=Path,required=True)
    return p.parse_args(argv)

def look_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

def phase_to_rgba(phi):
    d=np.clip(1.0-phi,0.0,1.0)
    rgba=np.empty((len(phi),4),dtype=np.float32)
    rgba[:,0]=0.12+0.88*d
    rgba[:,1]=0.42*(1.0-d)+0.07*d
    rgba[:,2]=0.90*(1.0-d)+0.03*d
    rgba[:,3]=1.0
    return rgba

def make_faces(nx,nz):
    f=[]
    for z in range(nz-1):
        row=z*nx
        nxt=(z+1)*nx
        for x in range(nx-1):
            a=row+x
            b=a+1
            c=nxt+x+1
            d=nxt+x
            f.append((a,b,c,d))
    return f

def load_frame(cache,rec,center):
    dat=np.load(cache/rec["file"])
    pts=(dat["points"].astype(np.float32)-center[None,:])*SCALE
    phi=dat["phasefield"].astype(np.float32)
    return pts,phi

def main():
    a=parse_args()
    cache=a.cache.resolve()
    out=a.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((cache/"manifest.json").read_text())
    center=np.asarray(manifest["center"],dtype=np.float32)
    nx=int(manifest["sampled_grid"]["nx"])
    nz=int(manifest["sampled_grid"]["nz"])
    frames=manifest["frames_data"]

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    p0,phi0=load_frame(cache,frames[0],center)
    mesh=bpy.data.meshes.new("FractureSurface")
    mesh.from_pydata(p0.tolist(),[],make_faces(nx,nz))
    mesh.update()

    color=mesh.color_attributes.new(name="fracture_color",type="FLOAT_COLOR",domain="POINT")
    color.data.foreach_set("color",phase_to_rgba(phi0).ravel())

    obj=bpy.data.objects.new("FractureSurface",mesh)
    bpy.context.collection.objects.link(obj)

    mat=bpy.data.materials.new("FractureMaterial")
    mat.use_nodes=True
    nt=mat.node_tree
    bsdf=nt.nodes.get("Principled BSDF")
    vc=nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name="fracture_color"
    nt.links.new(vc.outputs["Color"],bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value=0.10
    bsdf.inputs["Roughness"].default_value=0.34
    em=bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
    if em is not None:
        nt.links.new(vc.outputs["Color"],em)
    es=bsdf.inputs.get("Emission Strength")
    if es is not None:
        es.default_value=0.06
    obj.data.materials.append(mat)

    solid=obj.modifiers.new("Visual thickness only","SOLIDIFY")
    solid.thickness=0.025
    solid.offset=0.0
    bevel=obj.modifiers.new("Soft edges","BEVEL")
    bevel.width=0.004
    bevel.segments=2

    scene=bpy.context.scene
    scene.frame_start=1
    scene.frame_end=len(frames)
    scene.render.fps=int(manifest["fps"])
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value=(0.006,0.009,0.018,1)
    bg.inputs["Strength"].default_value=0.18

    floor_mat=bpy.data.materials.new("Floor")
    floor_mat.use_nodes=True
    fbs=floor_mat.node_tree.nodes.get("Principled BSDF")
    fbs.inputs["Base Color"].default_value=(0.018,0.025,0.04,1)
    fbs.inputs["Roughness"].default_value=0.72
    bpy.ops.mesh.primitive_plane_add(size=8,location=(0,0,-1.08))
    floor=bpy.context.object
    floor.data.materials.append(floor_mat)

    for name,loc,energy,size,colorv in (
        ("Key",(3.6,-4.2,4.0),900,3.0,(1.0,0.78,0.58)),
        ("Fill",(-3.2,-2.0,2.5),520,2.5,(0.38,0.62,1.0)),
        ("Rim",(0.5,2.5,4.5),720,2.8,(0.45,0.80,1.0))
    ):
        ld=bpy.data.lights.new(name,"AREA")
        ld.energy=energy
        ld.shape="DISK"
        ld.size=size
        ld.color=colorv
        lo=bpy.data.objects.new(name,ld)
        bpy.context.collection.objects.link(lo)
        lo.location=loc
        look_at(lo,(0,0,0))

    camd=bpy.data.cameras.new("Camera")
    cam=bpy.data.objects.new("Camera",camd)
    bpy.context.collection.objects.link(cam)
    scene.camera=cam
    cam.location=(3.1,-4.4,2.45)
    camd.lens=52
    look_at(cam,(0,0,0))

    for engine in ("BLENDER_EEVEE_NEXT","BLENDER_EEVEE","BLENDER_WORKBENCH"):
        try:
            scene.render.engine=engine
            break
        except Exception:
            pass
    scene.render.resolution_x=640
    scene.render.resolution_y=360
    scene.render.resolution_percentage=100

    state={"frame":None}
    def update_frame(scene, depsgraph=None):
        idx=max(0,min(len(frames)-1,scene.frame_current-1))
        if state["frame"]==idx:
            return
        pts,phi=load_frame(cache,frames[idx],center)
        mesh.vertices.foreach_set("co",pts.ravel())
        mesh.color_attributes["fracture_color"].data.foreach_set("color",phase_to_rgba(phi).ravel())
        mesh.update()
        state["frame"]=idx

    bpy.app.handlers.frame_change_pre.append(update_frame)

    scene.frame_set(len(frames))
    update_frame(scene)
    scene.render.image_settings.file_format="PNG"
    preview=out/"preview.png"
    scene.render.filepath=str(preview)
    bpy.ops.render.render(write_still=True)

    scene.frame_set(1)
    scene.render.image_settings.file_format="FFMPEG"
    scene.render.ffmpeg.format="MPEG4"
    scene.render.ffmpeg.codec="H264"
    scene.render.ffmpeg.constant_rate_factor="MEDIUM"
    video=out/"media.mp4"
    scene.render.filepath=str(video)
    t=time.perf_counter()
    bpy.ops.render.render(animation=True)
    render_seconds=time.perf_counter()-t

    blend=out/f"sph-fracture-3d-{a.case}.blend"
    scene.frame_set(len(frames))
    update_frame(scene)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))

    val={
      "case":a.case,
      "representation":"Blender 3D displaced phase-field surface",
      "source_physics":"2D mapped Kalthoff-Winkler phase-field fracture benchmark",
      "visual_thickness_only":True,
      "deformed_position":"initial mapped position + Displacement",
      "phasefield_color":"1=intact blue, 0=fractured red",
      "frames":len(frames),
      "fps":manifest["fps"],
      "source_particles":manifest["source_grid"]["particles"],
      "render_vertices":manifest["sampled_grid"]["vertices"],
      "render_faces":int((nx-1)*(nz-1)),
      "max_displacement_m":manifest["max_displacement_m"],
      "phasefield_min":manifest["phasefield_min"],
      "phasefield_max":manifest["phasefield_max"],
      "render_seconds":render_seconds,
      "preview_bytes":preview.stat().st_size,
      "video_bytes":video.stat().st_size,
      "blend_bytes":blend.stat().st_size,
      "errors":[]
    }
    (out/"validation-3d.json").write_text(json.dumps(val,indent=2)+"\n")
    print(json.dumps(val,indent=2))

if __name__=="__main__":
    main()
