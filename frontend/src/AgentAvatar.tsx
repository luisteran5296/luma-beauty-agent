import {Blobatar} from '@blobatar/react';
import {useGaze} from '@blobatar/react/gaze';
import {idle, thinking} from 'blobatar/expression';
import 'blobatar/motion.css';
import 'blobatar/gaze.css';

export function AgentAvatar({busy=false, size=160}: {busy?:boolean; size?:number}) {
  const {ref} = useGaze({travel:2.5, lookAt:'pointer'});
  return <div className={`agent-orb ${busy?'is-thinking':''}`} aria-hidden="true">
    <div className="orb-halo"/><div className="orb-ring"/>
    <Blobatar ref={ref} name="Luma Clementine" size={size} background={false} hue={35}
      traits={{shape:.95,'eye.ratio':.12}} animate="always" expression={busy?thinking:idle}/>
  </div>;
}
