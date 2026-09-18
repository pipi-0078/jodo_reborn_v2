import {Vector3} from 'three/webgpu';
import { sin, time, smoothstep, uniform } from 'three/tsl';
import { POND_OUTER, BANK_INNER, WATER_LEVEL, POND_DEPTH } from './layout';
// Share displacement between the pond and foot ripples; fade waves near the shore.
export function pondWave(p: any) {
 const edge=POND_OUTER-(-WATER_LEVEL)*(POND_OUTER-BANK_INNER)/-POND_DEPTH;
 return sin(p.x.mul(.24).add(time.mul(.7))).mul(sin(p.z.mul(.21).add(time.mul(.55)))).mul(.16)
 .add(sin(p.x.mul(.9).add(p.z.mul(.75)).add(time.mul(1.2))).mul(.045))
 .mul(smoothstep(0,2,p.xz.length().negate().add(edge)));
}

export const craneWaterFocus = uniform(new Vector3(100000,0,100000));
