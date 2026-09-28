from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy

def read_frame(path: Path):
    r=vtk.vtkPolyDataReader()
    r.SetFileName(str(path))
    r.ReadAllScalarsOn()
    r.ReadAllVectorsOn()
    r.Update()
    p=r.GetOutput()
    pts=vtk_to_numpy(p.GetPoints().GetData()).astype(np.float32,copy=False)
    pd=p.GetPointData()
    disp=pd.GetArray("Displacement")
    phi=pd.GetArray("Phasefield")
    if disp is None or phi is None:
        names=[pd.GetArrayName(i) for i in range(pd.GetNumberOfArrays())]
        raise RuntimeError(f"required fields missing in {path}: {names}")
    disp=vtk_to_numpy(disp).astype(np.float32,copy=False)
    phi=vtk_to_numpy(phi).astype(np.float32,copy=False).reshape(-1)
    if disp.ndim!=2 or disp.shape[1]!=3:
        raise RuntimeError(f"unexpected Displacement shape {disp.shape}")
    return pts,disp,phi

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("vtk_dir",type=Path)
    ap.add_argument("output",type=Path)
    ap.add_argument("--case",required=True)
    ap.add_argument("--max-frames",type=int,default=24)
    ap.add_argument("--grid-step",type=int,default=4)
    ap.add_argument("--fps",type=int,default=8)
    a=ap.parse_args()

    files=sorted(a.vtk_dir.rglob("*.vtk"))
    if not files:
        raise SystemExit("no VTK files")
    a.output.mkdir(parents=True,exist_ok=True)

    stride=max(1,math.ceil(len(files)/a.max_frames))
    selected=files[::stride]
    if selected[-1]!=files[-1]:
        selected.append(files[-1])

    pts0,disp0,phi0=read_frame(selected[0])
    ux=np.unique(np.round(pts0[:,0],9))
    uz=np.unique(np.round(pts0[:,2],9))
    nx,nz=len(ux),len(uz)
    if nx*nz!=len(pts0):
        raise RuntimeError(f"mapped grid is not rectangular: {nx}x{nz}!={len(pts0)}")
    order=np.lexsort((pts0[:,0],pts0[:,2]))
    grid=order.reshape(nz,nx)
    sampled=grid[::a.grid_step,::a.grid_step]
    snz,snx=sampled.shape
    sel=sampled.reshape(-1)
    center=np.array([(float(ux.min())+float(ux.max()))/2.0,
                     float(np.median(pts0[:,1])),
                     (float(uz.min())+float(uz.max()))/2.0],dtype=np.float32)

    recs=[]
    gmin=1.0
    gmax=0.0
    max_disp=0.0
    for seq,path in enumerate(selected,1):
        pts,disp,phi=read_frame(path)
        if len(pts)!=len(pts0):
            raise RuntimeError("particle count changed")
        deformed=pts+disp
        q=deformed[sel]
        qp=phi[sel]
        qd=disp[sel]
        gmin=min(gmin,float(np.nanmin(qp)))
        gmax=max(gmax,float(np.nanmax(qp)))
        max_disp=max(max_disp,float(np.linalg.norm(qd,axis=1).max()))
        fn=f"frame_{seq:04d}.npz"
        np.savez_compressed(a.output/fn,points=q,phasefield=qp)
        recs.append({
            "frame":seq,
            "file":fn,
            "source":path.name,
            "phasefield_min":float(qp.min()),
            "phasefield_max":float(qp.max())
        })

    manifest={
        "case":a.case,
        "source_vtk_files":len(files),
        "frames":len(recs),
        "fps":a.fps,
        "source_grid":{"nx":nx,"nz":nz,"particles":len(pts0)},
        "sampled_grid":{"nx":snx,"nz":snz,"vertices":int(snx*snz),"grid_step":a.grid_step},
        "center":center.tolist(),
        "phasefield_min":gmin,
        "phasefield_max":gmax,
        "max_displacement_m":max_disp,
        "note":"Source benchmark is a 2D mapped x-z grid. Blender adds only visual thickness; deformation uses position + Displacement.",
        "frames_data":recs
    }
    (a.output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))

if __name__=="__main__":
    main()
