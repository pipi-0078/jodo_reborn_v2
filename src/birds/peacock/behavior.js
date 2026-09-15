// Bounded ground behavior for a single bird in the preview arena.
// Navigation for the actual Pure Land layout is a later integration step.
export class PeacockBehavior {
  constructor(seed=916){
    this.seed=seed;this.position={x:0,z:0};this.heading=0;this.speed=0;
    this.energy=.8;this.curiosity=.5;this.time=0;this.elapsed=0;this.state='look';this.duration=3;
    this.mode='auto';this.openness=0;this.target={x:0,z:0};this.history=[];this.recent=[];
    this.lookYaw=0;this.lookTarget=0;this.lookTimer=0;this.radius=1.65;
  }
  random(){this.seed=(Math.imul(1664525,this.seed)+1013904223)>>>0;return this.seed/4294967296;}
  enter(state){
    this.state=state;this.elapsed=0;
    this.duration={look:4+this.random()*4,walk:12+this.random()*8,rest:9+this.random()*7,display:17+this.random()*5}[state];
    if(state==='walk'){
      for(let tries=0;tries<20;tries++){
        const angle=this.random()*Math.PI*2,r=.4+this.random()*1.15;
        const target={x:Math.cos(angle)*r,z:Math.sin(angle)*r};
        if(Math.hypot(target.x-this.position.x,target.z-this.position.z)>.65){this.target=target;break;}
      }
    }
    this.history.push({time:this.time,state});if(this.history.length>80)this.history.shift();
    this.recent.push(state);if(this.recent.length>3)this.recent.shift();
  }
  command(mode){
    this.mode=mode;
    if(mode==='auto'){this.enter('look');return;}
    // Closing the train precedes walking, even on a manual request.
    this.enter(mode);
  }
  choose(){
    if(this.energy<.32)return 'rest';
    const weights={walk:.3+this.curiosity*.7,look:.2,rest:.10+(1-this.energy)*.3,display:.28};
    weights[this.state]=0;
    if(this.recent.includes('display'))weights.display*=.35;
    let roll=this.random()*Object.values(weights).reduce((a,b)=>a+b,0);
    for(const [state,w]of Object.entries(weights)){roll-=w;if(roll<=0)return state;}
    return 'look';
  }
  update(dt){
    this.time+=dt;this.elapsed+=dt;
    const wantsOpen=this.state==='display'&&this.elapsed<this.duration-5;
    const openTarget=wantsOpen?1:0;
    this.openness+=Math.sign(openTarget-this.openness)*Math.min(Math.abs(openTarget-this.openness),dt/5);
    let distance=0,turnDistance=0;
    const dx=this.target.x-this.position.x,dz=this.target.z-this.position.z,len=Math.hypot(dx,dz);
    const walking=this.state==='walk'&&this.openness<.001&&len>.07;
    if(walking){
      const desired=Math.atan2(dz,-dx);
      const diff=Math.atan2(Math.sin(desired-this.heading),Math.cos(desired-this.heading));
      const turn=Math.max(-.7*dt,Math.min(.7*dt,diff));
      this.heading+=turn;turnDistance=Math.abs(turn)*.075;
      const targetSpeed=Math.abs(diff)>.35?0:Math.min(.11,len*.22);
      this.speed+=(targetSpeed-this.speed)*(1-Math.exp(-dt*5));
      distance=this.speed*dt;
      const nx=this.position.x-Math.cos(this.heading)*distance,nz=this.position.z+Math.sin(this.heading)*distance;
      if(Math.hypot(nx,nz)<this.radius){this.position.x=nx;this.position.z=nz;}else{distance=0;this.enter('look');}
      this.energy=Math.max(0,this.energy-dt*.018);this.curiosity=Math.max(0,this.curiosity-dt*.025);
    }else this.speed=0;
    if(this.state==='rest'){this.energy=Math.min(1,this.energy+dt*.045);this.curiosity=Math.min(1,this.curiosity+dt*.028);}
    else if(this.state!=='walk')this.curiosity=Math.min(1,this.curiosity+dt*.016);
    this.lookTimer-=dt;
    if(this.lookTimer<=0){this.lookTimer=2+this.random()*3;this.lookTarget=(this.random()-.5)*(this.state==='rest'?.25:.9);}
    this.lookYaw+=(this.lookTarget-this.lookYaw)*(1-Math.exp(-dt*2));
    if(this.elapsed>this.duration||(this.state==='walk'&&len<.07&&this.elapsed>3)){
      if(this.mode==='auto')this.enter(this.choose());
      else if(this.mode==='walk')this.enter('walk');
      else if(this.mode==='display')this.enter('display');
      else this.elapsed=0;
    }
    return {distance:distance+turnDistance,moving:distance+turnDistance>.00001,lookYaw:this.lookYaw,resting:this.state==='rest',time:this.time};
  }
}
