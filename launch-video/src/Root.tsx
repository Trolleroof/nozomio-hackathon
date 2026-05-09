import "./index.css";
import { Composition } from "remotion";
import { CrucibleLaunch, FPS, DURATION_IN_FRAMES } from "./Composition";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="CrucibleLaunch"
        component={CrucibleLaunch}
        durationInFrames={DURATION_IN_FRAMES}
        fps={FPS}
        width={1920}
        height={1080}
      />
    </>
  );
};
