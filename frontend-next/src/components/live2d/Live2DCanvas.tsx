"use client";

import { useRef, useEffect, useCallback, useImperativeHandle, forwardRef, useState } from "react";

const MODEL_PATH = "/assets/hiyori_free_en/runtime/hiyori_free_t08.model3.json";
const SPEAKING_MOTIONS = ["Tap", "Flick", "Tap@Body"];
const IDLE_MOTIONS = ["Idle", "Flick", "FlickDown"];

const SCRIPTS = [
  "https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js",
  "https://cdn.jsdelivr.net/gh/dylanNew/live2d/webgl/Live2D/lib/live2d.min.js",
  "https://cdn.jsdelivr.net/npm/pixi.js@6.5.2/dist/browser/pixi.min.js",
  "https://cdn.jsdelivr.net/npm/pixi-live2d-display/dist/index.min.js",
];

let _scriptsLoaded = false;
let _scriptsLoading: Promise<void> | null = null;

function loadScriptsSequentially(): Promise<void> {
  if (_scriptsLoaded) return Promise.resolve();
  if (_scriptsLoading) return _scriptsLoading;

  _scriptsLoading = (async () => {
    for (const src of SCRIPTS) {
      // Skip if already loaded (e.g. by another instance of this component)
      if (document.querySelector(`script[src="${src}"]`)) continue;
      await new Promise<void>((resolve, reject) => {
        const script = document.createElement("script");
        script.src = src;
        script.async = false;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error(`Failed to load: ${src}`));
        document.head.appendChild(script);
      });
    }
    _scriptsLoaded = true;
  })();

  return _scriptsLoading;
}

export interface Live2DHandle {
  playMotion: (name: string) => void;
  startLipSync: (audioElement: HTMLAudioElement) => void;
  stopLipSync: () => void;
  setSpeaking: (speaking: boolean) => void;
  setLipSyncValue: (value: number) => void;
}

interface Props {
  className?: string;
}

const Live2DCanvas = forwardRef<Live2DHandle, Props>(function Live2DCanvasInner({ className }, ref) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const appRef = useRef<any>(null);
  const modelRef = useRef<any>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const speakingRef = useRef(false);
  const speakingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const idleIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  const [scriptsReady, setScriptsReady] = useState(_scriptsLoaded);

  // Load CDN scripts sequentially on mount
  useEffect(() => {
    if (scriptsReady) return;
    let cancelled = false;
    loadScriptsSequentially()
      .then(() => { if (!cancelled) setScriptsReady(true); })
      .catch((err) => console.error("Live2D script load error:", err));
    return () => { cancelled = true; };
  }, [scriptsReady]);

  // Initialize PIXI + Live2D after scripts are loaded
  useEffect(() => {
    if (!scriptsReady || !canvasRef.current) return;
    mountedRef.current = true;
    let destroyed = false;

    async function init() {
      if (destroyed || !canvasRef.current) return;

      const PIXI = (window as any).PIXI;
      if (!PIXI) { console.error("PIXI not found on window"); return; }

      const Live2DModel = PIXI.live2d?.Live2DModel;
      if (!Live2DModel) { console.error("pixi-live2d-display not loaded"); return; }

      const app = new PIXI.Application({
        view: canvasRef.current,
        resizeTo: canvasRef.current.parentElement || window,
        transparent: true,
        antialias: true,
      });
      appRef.current = app;

      try {
        const model = await Live2DModel.from(MODEL_PATH);
        if (destroyed) { model.destroy(); return; }
        modelRef.current = model;

        const resize = () => {
          if (!app.renderer || destroyed) return;
          app.renderer.resize(
            canvasRef.current!.parentElement!.clientWidth || window.innerWidth,
            canvasRef.current!.parentElement!.clientHeight || window.innerHeight,
          );
          const w = app.renderer.width;
          const h = app.renderer.height;
          // Legacy uses scale 0.3 at ~1080px height; scale proportionally
          model.scale.set(0.3 * (h / 1080));
          model.x = w / 2;
          model.y = h / 1.2;
          model.anchor.set(0.5);
        };
        resize();
        window.addEventListener("resize", resize);
        app.stage.addChild(model);

        // Random idle motions
        idleIntervalRef.current = setInterval(() => {
          if (!modelRef.current || speakingRef.current) return;
          const m = IDLE_MOTIONS[Math.floor(Math.random() * IDLE_MOTIONS.length)];
          try { modelRef.current.motion(m); } catch { /* ignore */ }
        }, 8000 + Math.random() * 5000);

      } catch (err) {
        console.error("Failed to load Live2D model:", err);
      }
    }

    init();

    return () => {
      destroyed = true;
      mountedRef.current = false;
      cancelAnimationFrame(animFrameRef.current);
      if (speakingIntervalRef.current) clearInterval(speakingIntervalRef.current);
      if (idleIntervalRef.current) clearInterval(idleIntervalRef.current);
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
      if (appRef.current) {
        try { appRef.current.destroy(true); } catch { /* ignore */ }
        appRef.current = null;
      }
      modelRef.current = null;
    };
  }, [scriptsReady]);

  const playMotion = useCallback((name: string) => {
    if (!modelRef.current) return;
    try { modelRef.current.motion(name); } catch { /* ignore */ }
  }, []);

  const startLipSync = useCallback((audioElement: HTMLAudioElement) => {
    cancelAnimationFrame(animFrameRef.current);
    if (audioCtxRef.current) audioCtxRef.current.close().catch(() => {});

    const ctx = new AudioContext();
    audioCtxRef.current = ctx;
    const source = ctx.createMediaElementSource(audioElement);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);
    analyser.connect(ctx.destination);
    analyserRef.current = analyser;
    const dataArray = new Uint8Array(analyser.fftSize);
    let mouthOpen = 0;

    function animate() {
      if (!mountedRef.current) return;
      animFrameRef.current = requestAnimationFrame(animate);
      analyser.getByteTimeDomainData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) sum += ((dataArray[i] - 128) / 128) ** 2;
      const volume = Math.sqrt(sum / dataArray.length);
      mouthOpen += (Math.min(volume * 5, 1) - mouthOpen) * 0.4;
      if (modelRef.current?.internalModel) {
        modelRef.current.internalModel.coreModel.setParameterValueById("ParamMouthOpenY", mouthOpen);
      }
    }
    animate();
  }, []);

  const stopLipSync = useCallback(() => {
    cancelAnimationFrame(animFrameRef.current);
    if (modelRef.current?.internalModel) {
      modelRef.current.internalModel.coreModel.setParameterValueById("ParamMouthOpenY", 0);
    }
  }, []);

  const setLipSyncValue = useCallback((value: number) => {
    if (modelRef.current?.internalModel) {
      modelRef.current.internalModel.coreModel.setParameterValueById("ParamMouthOpenY", value);
    }
  }, []);

  const setSpeaking = useCallback((speaking: boolean) => {
    speakingRef.current = speaking;
    if (speaking) {
      const m = SPEAKING_MOTIONS[Math.floor(Math.random() * SPEAKING_MOTIONS.length)];
      playMotion(m);
      speakingIntervalRef.current = setInterval(() => {
        if (!speakingRef.current) return;
        const m2 = SPEAKING_MOTIONS[Math.floor(Math.random() * SPEAKING_MOTIONS.length)];
        playMotion(m2);
      }, 4000);
    } else {
      if (speakingIntervalRef.current) {
        clearInterval(speakingIntervalRef.current);
        speakingIntervalRef.current = null;
      }
      setLipSyncValue(0);
    }
  }, [playMotion, setLipSyncValue]);

  useImperativeHandle(ref, () => ({
    playMotion,
    startLipSync,
    stopLipSync,
    setSpeaking,
    setLipSyncValue,
  }), [playMotion, startLipSync, stopLipSync, setSpeaking, setLipSyncValue]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ display: "block", width: "100%", height: "100%" }}
    />
  );
});

export default Live2DCanvas;
