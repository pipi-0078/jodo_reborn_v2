export class ParrotBehavior {
  constructor(seed=918){this.seed=seed;this.state='look';this.time=0;this.elapsed=0;this.duration=7;this.mode='auto';this.yaw=0;this.tilt=0;this.rest=0;this.targetYaw=.25;this.lookTimer=3;this.history=['look'];}
  random(){this.seed=(1664525*this.seed+1013904223)>>>0;return this.seed/4294967296;}
  enter(state){this.state=state;this.elapsed=0;this.duration=state==='rest'?12+this.random()*6:6+this.random()*5;this.history.push(state);if(this.history.length>100)this.history.shift();}
  command(mode){this.mode=mode;this.enter(mode==='auto'?'look':mode);}
  update(dt){
    this.time+=dt;this.elapsed+=dt;this.lookTimer-=dt;
    if(this.lookTimer<=0){this.targetYaw=(this.random()-.5)*.84;this.lookTimer=2.5+this.random()*3;}
    if(this.elapsed>=this.duration){
      if(this.mode==='auto'){const candidates=['look','curious','rest'].filter(s=>s!==this.state);this.enter(candidates[Math.floor(this.random()*candidates.length)]);}else this.elapsed=0;
    }
    const rest=this.state==='rest'?1:0;
    const yaw=rest?this.targetYaw*.2:this.targetYaw;
    const tilt=this.state==='curious'?.2*Math.sin(this.elapsed*.7):0;
    const blend=1-Math.exp(-dt*2);
    this.yaw+=(yaw-this.yaw)*blend;this.tilt+=(tilt-this.tilt)*blend;this.rest+=(rest-this.rest)*blend;
    return {yaw:this.yaw,tilt:this.tilt,rest:this.rest};
  }
}
