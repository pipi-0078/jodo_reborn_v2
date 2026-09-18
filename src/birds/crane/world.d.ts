import type {Scene,Vector3,Object3D} from 'three';
export function createWorldCrane(scene:Scene,sunDirection:Vector3):Promise<{bird:Object3D;update(dt:number):void}>;
