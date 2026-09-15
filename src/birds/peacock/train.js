import * as T from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

// Separate train prototype. Coordinates are derived from the body bounds.
export async function createTrain(body) {
  const box = new T.Box3().setFromObject(body);
  const h = box.max.y - box.min.y;
  const root = new T.Group();
  root.name = 'peacock_train_prototype';
  root.position.set(box.min.x + (box.max.x-box.min.x)*0.50, box.min.y+h*0.46, (box.min.z+box.max.z)/2);
  root.rotation.y = -Math.PI/2; // The bird faces -X; feathers face the same way.
  const hinge = new T.Group(); root.add(hinge);
  const tex = await new T.TextureLoader().loadAsync(`${import.meta.env.BASE_URL}assets/peacock/feather-cutout.png`);
  tex.colorSpace = T.SRGBColorSpace;
  const material = new T.MeshStandardMaterial({map:tex,alphaTest:0.5,alphaToCoverage:true,side:T.DoubleSide,roughness:0.72,metalness:0.08});
  const fiberMaterial = new T.MeshStandardMaterial({vertexColors:true,roughness:.82,metalness:.05});
  const feathers=[];
  const rows=[{count:23,length:1.38,width:.38},{count:19,length:1.12,width:.33},{count:15,length:.86,width:.28}];
  rows.forEach((row,r)=>{
    for(let i=0;i<row.count;i++) {
      const t=i/(row.count-1), angle=(t-.5)*Math.PI*.94;
      const length=h*row.length*(1-.035*Math.cos(i*2.399+r));
      const geometry=new T.PlaneGeometry(h*row.width,length,12,40);
      geometry.translate(0,length/2,0);
      const pos=geometry.attributes.position;
      for(let v=0;v<pos.count;v++){
        const y=pos.getY(v)/length, cross=pos.getX(v)/(h*row.width/2);
        // Compress the narrow terminal spike and give its barbs room to spread.
        const tip=T.MathUtils.smoothstep(y,.70,.96);
        pos.setX(v,pos.getX(v)*(1+.65*tip));
        pos.setY(v,length*(y<=.76?y:.76+(y-.76)*.43));
        pos.setZ(v,-.025*h*y*y + .07*h*cross*cross*Math.sin(Math.PI*y));
      }
      geometry.computeVertexNormals();
      const pivot=new T.Group();pivot.position.set((t-.5)*h*.035,0,r*h*.014);
      const mesh=new T.Mesh(geometry,material);pivot.add(mesh);hinge.add(pivot);
      // Tapered, curved 3D filaments keep the fringe legible from oblique views.
      const fibers=[];
      const palette=['#e9d9bc','#efddda','#dce7e4','#e5dced'];
      for(let j=0;j<28;j++){
        const side=j%2?1:-1, u=Math.floor(j/2)/13;
        const reach=h*row.width*(.12+.34*u);
        const startY=length*(.69+.11*(1-u));
        const endY=length*(.875-.07*u+.008*Math.sin(j*2.399));
        const curve=new T.CubicBezierCurve3(
          new T.Vector3(side*h*row.width*.035,startY,-.02*h),
          new T.Vector3(side*reach*.25,length*(.89-.025*u),-.018*h),
          new T.Vector3(side*reach,endY+.055*length,-.012*h),
          new T.Vector3(side*reach*.90,endY,-.01*h));
        const tube=new T.TubeGeometry(curve,12,h*.0007,3,false);
        const fp=tube.attributes.position;
        for(let k=0;k<fp.count;k++){
          const q=Math.floor(k/4)/12, c=curve.getPointAt(q);
          const scale=1-.92*q*q;
          fp.setXYZ(k,c.x+(fp.getX(k)-c.x)*scale,c.y+(fp.getY(k)-c.y)*scale,c.z+(fp.getZ(k)-c.z)*scale);
        }
        tube.computeVertexNormals();
        const color=new T.Color(palette[j%palette.length]),colors=[];
        for(let k=0;k<fp.count;k++)colors.push(color.r,color.g,color.b);
        tube.setAttribute('color',new T.Float32BufferAttribute(colors,3));fibers.push(tube);
      }
      const fringe=new T.Mesh(mergeGeometries(fibers),fiberMaterial);
      mesh.add(fringe);fibers.forEach(g=>g.dispose());
      feathers.push({pivot,mesh,angle,phase:i*2.399+r,length,t});
    }
  });
  let openness=0;
  function update(value,time=0) {
    openness=T.MathUtils.clamp(value,0,1);
    // Raise first, then open. Closing gathers the feathers before lowering.
    const rise=T.MathUtils.smoothstep(openness,0,.65);
    const spread=T.MathUtils.smoothstep(openness,.22,1);
    hinge.rotation.x=T.MathUtils.lerp(-1.80,0,rise);
    for(const f of feathers){
      f.pivot.rotation.z=f.angle*T.MathUtils.lerp(.09,1,spread);
      f.mesh.rotation.y=(1-spread)*(f.t-.5)*2.5+.012*Math.sin(time*1.2+f.phase)*spread;
    }
  }
  update(0);
  return {root,update,featherCount:feathers.length,get openness(){return openness;}};
}
