let avatarModel;
let app;
let audioContext;
let audioSource;
let analyser;
let dataArray;
let animationFrame;

function setupLive2D() {
  app = new PIXI.Application({
    view: document.getElementById('live2d'),
    resizeTo: window, 
    transparent: true
  });  

  window.addEventListener('resize', () => {
    app.renderer.resize(window.innerWidth, window.innerHeight);
    if (avatarModel) {
      avatarModel.x = app.renderer.width / 2;
      avatarModel.y = app.renderer.height / 1.2;
    }
  });

  loadModel();
}

async function loadModel() {
  avatarModel = await PIXI.live2d.Live2DModel.from('assets/hiyori_free_en/runtime/hiyori_free_t08.model3.json');
  avatarModel.scale.set(0.3);
  avatarModel.x = app.renderer.width / 2;
  avatarModel.y = app.renderer.height / 1.2;
  avatarModel.anchor.set(0.5);
  app.stage.addChild(avatarModel);
}

function playMotion(name) {
  if (!avatarModel) return;
  avatarModel.motion(name);
}

function setupAudioAnalyzer(audioElement) {
  if (audioContext) {
    audioContext.close();
    cancelAnimationFrame(animationFrame);
  }

  audioContext = new AudioContext();
  audioSource = audioContext.createMediaElementSource(audioElement);
  analyser = audioContext.createAnalyser();
  analyser.fftSize = 2048;
  audioSource.connect(analyser);
  analyser.connect(audioContext.destination);
  dataArray = new Uint8Array(analyser.fftSize);

  animateMouth();
}

function animateMouth() {
  let mouthOpen = 0;

  function animate() {
    animationFrame = requestAnimationFrame(animate);
    analyser.getByteTimeDomainData(dataArray);

    let sum = dataArray.reduce((acc, val) => acc + ((val - 128) / 128) ** 2, 0);
    let volume = Math.sqrt(sum / dataArray.length);

    mouthOpen += (Math.min(volume * 5, 1) - mouthOpen) * 0.4;

    if (avatarModel && avatarModel.internalModel) {
      avatarModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', mouthOpen);
    }
  }

  animate();
}

setupLive2D();