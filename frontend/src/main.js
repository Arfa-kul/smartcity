import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import "./style.css";

// ============================================================
// SCENE SETUP
// ============================================================

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x06101f);

const camera = new THREE.PerspectiveCamera(
  60,
  window.innerWidth / window.innerHeight,
  0.1,
  1000
);

camera.position.set(70, 70, 90);

const renderer = new THREE.WebGLRenderer({
  antialias: true
});

renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

document.body.appendChild(renderer.domElement);

// ============================================================
// CAMERA CONTROLS
// ============================================================

const controls = new OrbitControls(camera, renderer.domElement);

controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.minDistance = 20;
controls.maxDistance = 220;
controls.maxPolarAngle = Math.PI / 2.05;

// ============================================================
// LIGHTING
// ============================================================

const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
scene.add(ambientLight);

const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2);
directionalLight.position.set(50, 100, 50);
scene.add(directionalLight);

// ============================================================
// GROUND
// ============================================================

const groundGeometry = new THREE.PlaneGeometry(180, 180);

const groundMaterial = new THREE.MeshStandardMaterial({
  color: 0x111a29,
  roughness: 0.9,
  metalness: 0.1
});

const ground = new THREE.Mesh(
  groundGeometry,
  groundMaterial
);

ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.05;

scene.add(ground);

// ============================================================
// GRID
// ============================================================

const grid = new THREE.GridHelper(
  180,
  36,
  0x1d3857,
  0x16243a
);

grid.position.y = 0.02;

scene.add(grid);

// ============================================================
// ROADS
// ============================================================

function createRoad(x, z, width, depth) {
  const geometry = new THREE.BoxGeometry(
    width,
    0.15,
    depth
  );

  const material = new THREE.MeshStandardMaterial({
    color: 0x3d4656
  });

  const road = new THREE.Mesh(
    geometry,
    material
  );

  road.position.set(x, 0.08, z);

  scene.add(road);

  return road;
}

createRoad(0, 0, 150, 12);
createRoad(0, 25, 150, 10);
createRoad(0, -25, 150, 10);

createRoad(0, 0, 12, 150);
createRoad(30, 0, 10, 150);
createRoad(-35, 0, 10, 150);

// ============================================================
// BUILDINGS
// ============================================================

function createBuilding(x, z, width, depth, height) {
  const geometry = new THREE.BoxGeometry(
    width,
    height,
    depth
  );

  const material = new THREE.MeshStandardMaterial({
    color: 0x2859c7,
    roughness: 0.7,
    metalness: 0.1
  });

  const building = new THREE.Mesh(
    geometry,
    material
  );

  building.position.set(
    x,
    height / 2,
    z
  );

  scene.add(building);

  return building;
}

createBuilding(-50, -40, 18, 22, 42);
createBuilding(-25, -42, 20, 18, 55);
createBuilding(5, -42, 22, 20, 48);

createBuilding(45, -40, 20, 24, 50);

createBuilding(-55, 35, 22, 20, 46);
createBuilding(-25, 38, 18, 22, 60);
createBuilding(5, 38, 20, 20, 52);

createBuilding(45, 38, 22, 22, 58);

// ============================================================
// POLLUTION HOTSPOTS
// ============================================================

const hotspots = [];

function createHotspot(x, z, radius) {
  const hotspotGeometry = new THREE.CylinderGeometry(
    radius,
    radius,
    0.8,
    64,
    1,
    false
  );

  const hotspotMaterial = new THREE.MeshBasicMaterial({
    color: 0x00ff66,
    transparent: true,
    opacity: 0.35
  });

  const hotspot = new THREE.Mesh(
    hotspotGeometry,
    hotspotMaterial
  );

  hotspot.position.set(x, 0.5, z);

  scene.add(hotspot);

  // Glow cylinder
  const glowGeometry = new THREE.CylinderGeometry(
    radius * 0.7,
    radius * 0.7,
    1.5,
    64
  );

  const glowMaterial = new THREE.MeshBasicMaterial({
    color: 0x00ff66,
    transparent: true,
    opacity: 0.18
  });

  const glow = new THREE.Mesh(
    glowGeometry,
    glowMaterial
  );

  glow.position.set(x, 0.9, z);

  scene.add(glow);

  hotspots.push({
    hotspot,
    glow,
    radius
  });
}

createHotspot(-20, 0, 7);
createHotspot(25, 20, 6);
createHotspot(-35, -20, 5);

function updateHotspots(congestion) {
  const level = Math.max(
    0,
    Math.min(1, Number(congestion) || 0)
  );

  const hue = 0.33 - level * 0.33;

  const color = new THREE.Color();
  color.setHSL(hue, 1, 0.5);

  hotspots.forEach((item, index) => {
    const pulse =
      1 +
      Math.sin(performance.now() * 0.002 + index) *
      0.08;

    item.hotspot.scale.set(
      pulse,
      1,
      pulse
    );

    item.glow.scale.set(
      pulse,
      1,
      pulse
    );

    item.hotspot.material.color.copy(color);
    item.glow.material.color.copy(color);

    item.hotspot.material.opacity =
      0.25 + level * 0.35;

    item.glow.material.opacity =
      0.12 + level * 0.2;
  });
}

// ============================================================
// SENSORS
// ============================================================

const sensors = [];

function createSensor(
  name,
  x,
  z
) {
  const sensorGroup = new THREE.Group();

  // Sensor pole
  const poleGeometry = new THREE.CylinderGeometry(
    0.15,
    0.15,
    2.5,
    16
  );

  const poleMaterial = new THREE.MeshStandardMaterial({
    color: 0x263238
  });

  const pole = new THREE.Mesh(
    poleGeometry,
    poleMaterial
  );

  pole.position.y = 1.25;

  sensorGroup.add(pole);

  // Sensor sphere
  const sensorGeometry = new THREE.SphereGeometry(
    1.2,
    24,
    24
  );

  const sensorMaterial = new THREE.MeshStandardMaterial({
    color: 0x00ff99,
    emissive: 0x00aa66,
    emissiveIntensity: 0.8
  });

  const sensor = new THREE.Mesh(
    sensorGeometry,
    sensorMaterial
  );

  sensor.position.y = 2.8;

  sensor.userData.sensorName = name;
  sensor.userData.sensorId = sensors.length;

  sensorGroup.add(sensor);

  sensorGroup.position.set(
    x,
    0,
    z
  );

  scene.add(sensorGroup);

  sensors.push({
    name,
    group: sensorGroup,
    mesh: sensor
  });

  return sensor;
}

// Six sensors
createSensor("ITPL Gate", -45, -20);
createSensor("Whitefield Main", -25, 0);
createSensor("Hope Farm", 0, 0);
createSensor("Channasandra Jn", 25, 0);
createSensor("Kundalahalli", 25, 20);
createSensor("Brookefield", 45, 20);

// ============================================================
// SENSOR LABELS
// ============================================================

function createSensorLabel(sensorName) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 128;

  const context = canvas.getContext("2d");

  context.clearRect(
    0,
    0,
    canvas.width,
    canvas.height
  );

  context.fillStyle = "rgba(5, 15, 30, 0.85)";
  context.roundRect(
    10,
    10,
    492,
    108,
    20
  );
  context.fill();

  context.fillStyle = "#ffffff";
  context.font = "bold 34px Arial";
  context.textAlign = "center";
  context.textBaseline = "middle";

  context.fillText(
    sensorName,
    256,
    64
  );

  const texture = new THREE.CanvasTexture(canvas);

  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true
  });

  const sprite = new THREE.Sprite(material);

  sprite.scale.set(8, 2, 1);

  return sprite;
}

// ============================================================
// SENSOR CLICK PANEL
// ============================================================

let latestState = null;

const sensorPanel = document.createElement("div");

sensorPanel.style.position = "fixed";
sensorPanel.style.top = "28px";
sensorPanel.style.right = "28px";
sensorPanel.style.width = "290px";
sensorPanel.style.padding = "20px";
sensorPanel.style.background = "rgba(7, 20, 39, 0.96)";
sensorPanel.style.border = "1px solid rgba(0,255,153,0.35)";
sensorPanel.style.borderRadius = "16px";
sensorPanel.style.color = "#ffffff";
sensorPanel.style.fontFamily = "Arial, sans-serif";
sensorPanel.style.boxShadow =
  "0 20px 50px rgba(0,0,0,0.45)";
sensorPanel.style.backdropFilter = "blur(12px)";
sensorPanel.style.zIndex = "1000";
sensorPanel.style.display = "none";

document.body.appendChild(sensorPanel);

function formatValue(value, digits = 1) {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(Number(value))
  ) {
    return "N/A";
  }

  return Number(value).toFixed(digits);
}

function getStatusColor(status) {
  if (status === "NORMAL") {
    return "#00ff99";
  }

  if (status === "WARNING") {
    return "#ffd166";
  }

  return "#ff5c7a";
}

function showSensorPanel(sensorInfo) {
  const state = latestState;

  if (!state) {
    sensorPanel.innerHTML = `
      <div style="font-size:16px;font-weight:bold;">
        Sensor Data
      </div>
      <div style="margin-top:10px;color:#9aa8bb;">
        Waiting for live data...
      </div>
    `;

    sensorPanel.style.display = "block";
    return;
  }

  const now = state.now || {};
  const anomaly = state.anomaly || {};

  const status =
    anomaly.status ||
    "NORMAL";

  const statusColor =
    getStatusColor(status);

  const time =
    state.time ||
    "Unknown";

  sensorPanel.innerHTML = `
    <div style="
      display:flex;
      justify-content:space-between;
      align-items:center;
      margin-bottom:18px;
    ">
      <div>
        <div style="
          font-size:11px;
          letter-spacing:1.5px;
          color:#00ff99;
          font-weight:bold;
        ">
          SMARTCITY SENSOR
        </div>

        <div style="
          font-size:20px;
          font-weight:700;
          margin-top:4px;
        ">
          ${sensorInfo.name}
        </div>
      </div>

      <button
        id="closeSensorPanel"
        style="
          border:none;
          background:rgba(255,255,255,0.08);
          color:white;
          width:32px;
          height:32px;
          border-radius:8px;
          cursor:pointer;
          font-size:18px;
        "
      >
        ×
      </button>
    </div>

    <div style="
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:10px;
    ">

      <div style="
        background:rgba(255,255,255,0.06);
        padding:12px;
        border-radius:10px;
      ">
        <div style="
          font-size:10px;
          color:#8fa1b7;
          text-transform:uppercase;
        ">
          CO₂
        </div>

        <div style="
          margin-top:5px;
          font-size:18px;
          font-weight:bold;
        ">
          ${formatValue(now.co2)}
        </div>

        <div style="
          font-size:10px;
          color:#7d8da2;
        ">
          ppm
        </div>
      </div>

      <div style="
        background:rgba(255,255,255,0.06);
        padding:12px;
        border-radius:10px;
      ">
        <div style="
          font-size:10px;
          color:#8fa1b7;
          text-transform:uppercase;
        ">
          Noise
        </div>

        <div style="
          margin-top:5px;
          font-size:18px;
          font-weight:bold;
        ">
          ${formatValue(now.noise_db)}
        </div>

        <div style="
          font-size:10px;
          color:#7d8da2;
        ">
          dB(A)
        </div>
      </div>

      <div style="
        background:rgba(255,255,255,0.06);
        padding:12px;
        border-radius:10px;
      ">
        <div style="
          font-size:10px;
          color:#8fa1b7;
          text-transform:uppercase;
        ">
          Congestion
        </div>

        <div style="
          margin-top:5px;
          font-size:18px;
          font-weight:bold;
        ">
          ${formatValue(now.congestion, 2)}
        </div>

        <div style="
          font-size:10px;
          color:#7d8da2;
        ">
          index
        </div>
      </div>

      <div style="
        background:rgba(255,255,255,0.06);
        padding:12px;
        border-radius:10px;
      ">
        <div style="
          font-size:10px;
          color:#8fa1b7;
          text-transform:uppercase;
        ">
          Vehicles
        </div>

        <div style="
          margin-top:5px;
          font-size:18px;
          font-weight:bold;
        ">
          ${formatValue(now.vehicle_count, 0)}
        </div>

        <div style="
          font-size:10px;
          color:#7d8da2;
        ">
          vehicles
        </div>
      </div>

      <div style="
        background:rgba(255,255,255,0.06);
        padding:12px;
        border-radius:10px;
      ">
        <div style="
          font-size:10px;
          color:#8fa1b7;
          text-transform:uppercase;
        ">
          Traffic
        </div>

        <div style="
          margin-top:5px;
          font-size:18px;
          font-weight:bold;
        ">
          ${formatValue(now.traffic_speed)}
        </div>

        <div style="
          font-size:10px;
          color:#7d8da2;
        ">
          km/h
        </div>
      </div>

      <div style="
        background:rgba(255,255,255,0.06);
        padding:12px;
        border-radius:10px;
      ">
        <div style="
          font-size:10px;
          color:#8fa1b7;
          text-transform:uppercase;
        ">
          Temperature
        </div>

        <div style="
          margin-top:5px;
          font-size:18px;
          font-weight:bold;
        ">
          ${formatValue(now.temperature)}
        </div>

        <div style="
          font-size:10px;
          color:#7d8da2;
        ">
          °C
        </div>
      </div>

    </div>

    <div style="
      margin-top:14px;
      padding:12px;
      border-radius:10px;
      background:rgba(255,255,255,0.05);
    ">
      <div style="
        font-size:10px;
        color:#8fa1b7;
        text-transform:uppercase;
        margin-bottom:5px;
      ">
        Replay Time
      </div>

      <div style="
        font-size:13px;
        font-weight:600;
      ">
        ${time}
      </div>
    </div>

    <div style="
      margin-top:10px;
      padding:11px 12px;
      border-radius:10px;
      background:${statusColor}15;
      border:1px solid ${statusColor}55;
      display:flex;
      justify-content:space-between;
      align-items:center;
    ">
      <span style="
        font-size:10px;
        color:#8fa1b7;
        text-transform:uppercase;
      ">
        Anomaly Status
      </span>

      <span style="
        color:${statusColor};
        font-weight:bold;
        font-size:12px;
      ">
        ${status}
      </span>
    </div>
  `;

  sensorPanel.style.display = "block";

  const closeButton =
    document.getElementById(
      "closeSensorPanel"
    );

  if (closeButton) {
    closeButton.onclick = () => {
      sensorPanel.style.display = "none";
    };
  }
}

// ============================================================
// RAYCASTER FOR SENSOR CLICKING
// ============================================================

const raycaster = new THREE.Raycaster();

const mouse = new THREE.Vector2();

let pointerDownX = 0;
let pointerDownY = 0;

renderer.domElement.addEventListener(
  "pointerdown",
  (event) => {
    pointerDownX = event.clientX;
    pointerDownY = event.clientY;
  }
);

renderer.domElement.addEventListener(
  "pointerup",
  (event) => {
    const distanceMoved = Math.sqrt(
      Math.pow(event.clientX - pointerDownX, 2) +
      Math.pow(event.clientY - pointerDownY, 2)
    );

    // If the mouse moved significantly,
    // it was probably camera orbiting rather than clicking.
    if (distanceMoved > 8) {
      return;
    }

    const rect =
      renderer.domElement.getBoundingClientRect();

    mouse.x =
      ((event.clientX - rect.left) /
        rect.width) *
        2 -
      1;

    mouse.y =
      -(
        (event.clientY - rect.top) /
        rect.height
      ) *
        2 +
      1;

    raycaster.setFromCamera(
      mouse,
      camera
    );

    const sensorMeshes =
      sensors.map(
        (sensorInfo) =>
          sensorInfo.mesh
      );

    const intersections =
      raycaster.intersectObjects(
        sensorMeshes,
        true
      );

    if (intersections.length > 0) {
      const clickedMesh =
        intersections[0].object;

      const sensorInfo =
        sensors.find(
          (sensor) =>
            sensor.mesh === clickedMesh
        );

      if (sensorInfo) {
        showSensorPanel(sensorInfo);
      }
    }
  }
);

// ============================================================
// HIGHLIGHT SENSOR ON HOVER
// ============================================================

renderer.domElement.addEventListener(
  "pointermove",
  (event) => {
    const rect =
      renderer.domElement.getBoundingClientRect();

    mouse.x =
      ((event.clientX - rect.left) /
        rect.width) *
        2 -
      1;

    mouse.y =
      -(
        (event.clientY - rect.top) /
        rect.height
      ) *
        2 +
      1;

    raycaster.setFromCamera(
      mouse,
      camera
    );

    const sensorMeshes =
      sensors.map(
        (sensorInfo) =>
          sensorInfo.mesh
      );

    const intersections =
      raycaster.intersectObjects(
        sensorMeshes,
        true
      );

    if (intersections.length > 0) {
      renderer.domElement.style.cursor =
        "pointer";
    } else {
      renderer.domElement.style.cursor =
        "default";
    }
  }
);

// ============================================================
// MOPSO ROUTE
// ============================================================

const routePoints = [
  new THREE.Vector3(-45, 0.6, -20),
  new THREE.Vector3(-25, 0.6, -20),
  new THREE.Vector3(-25, 0.6, 0),
  new THREE.Vector3(0, 0.6, 0),
  new THREE.Vector3(25, 0.6, 0),
  new THREE.Vector3(25, 0.6, 20),
  new THREE.Vector3(45, 0.6, 20)
];

const routeCurve =
  new THREE.CatmullRomCurve3(
    routePoints
  );

const routeGeometry =
  new THREE.BufferGeometry().setFromPoints(
    routeCurve.getPoints(100)
  );

const routeMaterial =
  new THREE.LineBasicMaterial({
    color: 0x00ff99
  });

const routeLine =
  new THREE.Line(
    routeGeometry,
    routeMaterial
  );

scene.add(routeLine);

// ============================================================
// VEHICLES
// ============================================================

const vehicles = [];

let targetVehicleCount = 10;
let targetTrafficSpeed = 40;

function createVehicle() {
  const vehicleGroup =
    new THREE.Group();

  // Body
  const bodyGeometry =
    new THREE.BoxGeometry(
      3.2,
      0.8,
      1.6
    );

  const bodyMaterial =
    new THREE.MeshStandardMaterial({
      color: 0x27a9e1
    });

  const body =
    new THREE.Mesh(
      bodyGeometry,
      bodyMaterial
    );

  body.position.y = 0.5;

  vehicleGroup.add(body);

  // Roof
  const roofGeometry =
    new THREE.BoxGeometry(
      1.6,
      0.65,
      1.3
    );

  const roofMaterial =
    new THREE.MeshStandardMaterial({
      color: 0x071321
    });

  const roof =
    new THREE.Mesh(
      roofGeometry,
      roofMaterial
    );

  roof.position.y = 1.15;

  vehicleGroup.add(roof);

  const startProgress =
    Math.random();

  const startPoint =
    routeCurve.getPointAt(
      startProgress
    );

  vehicleGroup.position.copy(
    startPoint
  );

  vehicleGroup.position.y =
    0.2;

  scene.add(vehicleGroup);

  vehicles.push({
    mesh: vehicleGroup,
    progress: startProgress,
    speedMultiplier:
      0.8 + Math.random() * 0.4
  });
}

for (let i = 0; i < 15; i++) {
  createVehicle();
}

function updateVehicleCount(count) {
  const numericCount =
    Number(count) || 0;

  const desiredCount =
    Math.max(
      5,
      Math.min(
        35,
        Math.round(
          numericCount / 180
        )
      )
    );

  targetVehicleCount =
    desiredCount;

  while (
    vehicles.length <
    targetVehicleCount
  ) {
    createVehicle();
  }

  while (
    vehicles.length >
    targetVehicleCount
  ) {
    const vehicle =
      vehicles.pop();

    scene.remove(
      vehicle.mesh
    );
  }
}

function updateTrafficSpeed(speed) {
  const numericSpeed =
    Number(speed);

  if (
    Number.isFinite(
      numericSpeed
    )
  ) {
    targetTrafficSpeed =
      Math.max(
        5,
        Math.min(
          100,
          numericSpeed
        )
      );
  }
}

function animateVehicles(delta) {
  const baseSpeed =
    targetTrafficSpeed *
    0.00012;

  vehicles.forEach(
    (vehicle) => {
      vehicle.progress +=
        baseSpeed *
        vehicle.speedMultiplier *
        delta;

      if (
        vehicle.progress >= 1
      ) {
        vehicle.progress -= 1;
      }

      const currentPoint =
        routeCurve.getPointAt(
          vehicle.progress
        );

      const nextProgress =
        Math.min(
          0.999,
          vehicle.progress +
            0.002
        );

      const nextPoint =
        routeCurve.getPointAt(
          nextProgress
        );

      vehicle.mesh.position.set(
        currentPoint.x,
        0.2,
        currentPoint.z
      );

      const direction =
        new THREE.Vector3(
          nextPoint.x -
            currentPoint.x,
          0,
          nextPoint.z -
            currentPoint.z
        );

      vehicle.mesh.rotation.y =
        Math.atan2(
          direction.x,
          direction.z
        );
    }
  );
}

// ============================================================
// DASHBOARD OVERLAY
// ============================================================

const dashboard =
  document.createElement("div");

dashboard.innerHTML = `
  <div style="
    position:fixed;
    left:24px;
    top:20px;
    width:300px;
    padding:20px;
    background:rgba(7,20,39,0.94);
    border:1px solid rgba(255,255,255,0.08);
    border-radius:18px;
    color:white;
    font-family:Arial,sans-serif;
    z-index:500;
    box-shadow:0 20px 50px rgba(0,0,0,0.35);
    backdrop-filter:blur(10px);
  ">

    <div style="
      display:flex;
      justify-content:space-between;
      align-items:center;
    ">

      <div>
        <div style="
          font-size:21px;
          font-weight:800;
          letter-spacing:0.5px;
        ">
          SMARTCITY<br>
          ITPL
        </div>

        <div style="
          margin-top:5px;
          color:#8292a8;
          font-size:11px;
        ">
          AI-Powered Urban Digital Twin
        </div>
      </div>

      <div style="
        color:#00ff99;
        font-size:10px;
      ">
        ● SYSTEM ONLINE
      </div>

    </div>

    <div id="metrics" style="
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:8px;
      margin-top:20px;
    ">

      <div style="
        background:rgba(255,255,255,0.06);
        padding:12px;
        border-radius:10px;
        text-align:center;
      ">
        <div style="
          font-size:9px;
          color:#8292a8;
        ">
          CO₂
        </div>

        <div id="co2Value" style="
          font-size:18px;
          font-weight:bold;
          margin-top:5px;
        ">
          --
        </div>

        <div style="
          font-size:8px;
          color:#68788e;
        ">
          ppm
        </div>
      </div>

      <div style="
        background:rgba(255,255,255,0.06);
        padding:12px;
        border-radius:10px;
        text-align:center;
      ">
        <div style="
          font-size:9px;
          color:#8292a8;
        ">
          NOISE
        </div>

        <div id="noiseValue" style="
          font-size:18px;
          font-weight:bold;
          margin-top:5px;
        ">
          --
        </div>

        <div style="
          font-size:8px;
          color:#68788e;
        ">
          dB(A)
        </div>
      </div>

      <div style="
        background:rgba(255,255,255,0.06);
        padding:12px;
        border-radius:10px;
        text-align:center;
      ">
        <div style="
          font-size:9px;
          color:#8292a8;
        ">
          CONGESTION
        </div>

        <div id="congestionValue" style="
          font-size:18px;
          font-weight:bold;
          margin-top:5px;
        ">
          --
        </div>

        <div style="
          font-size:8px;
          color:#68788e;
        ">
          index
        </div>
      </div>

    </div>

    <div style="
      margin-top:15px;
      padding:14px;
      background:rgba(255,255,255,0.045);
      border-radius:12px;
    ">

      <div style="
        font-size:11px;
        font-weight:bold;
        letter-spacing:1px;
        color:#aab8ca;
      ">
        3-HOUR FORECAST
      </div>

      <div id="forecastBox" style="
        margin-top:10px;
        font-size:10px;
        color:#c4cedc;
      ">
        Loading...
      </div>

    </div>

    <div style="
      margin-top:12px;
      padding:14px;
      background:rgba(255,255,255,0.045);
      border-radius:12px;
    ">

      <div style="
        font-size:11px;
        font-weight:bold;
        letter-spacing:1px;
        color:#aab8ca;
      ">
        MOPSO TRAFFIC OPTIMIZATION
      </div>

      <div id="mopsoBox" style="
        margin-top:10px;
      ">
        Loading...
      </div>

    </div>

    <div id="timeValue" style="
      margin-top:10px;
      color:#64748b;
      font-size:9px;
    ">
      Connecting to API...
    </div>

  </div>
`;

document.body.appendChild(
  dashboard
);

// ============================================================
// HELPERS
// ============================================================

function dashboardNumber(
  value,
  digits = 1
) {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(Number(value))
  ) {
    return "--";
  }

  return Number(value).toFixed(
    digits
  );
}

function updateDashboard(
  state,
  mopso
) {
  const now =
    state.now || {};

  document.getElementById(
    "co2Value"
  ).textContent =
    dashboardNumber(
      now.co2
    );

  document.getElementById(
    "noiseValue"
  ).textContent =
    dashboardNumber(
      now.noise_db
    );

  document.getElementById(
    "congestionValue"
  ).textContent =
    dashboardNumber(
      now.congestion,
      2
    );

  // Forecast
  const forecast =
    state.forecast || [];

  const forecastBox =
    document.getElementById(
      "forecastBox"
    );

  if (forecast.length > 0) {
    const co2Values =
      forecast
        .map(
          (item) =>
            dashboardNumber(
              item.co2
            )
        )
        .join(" → ");

    const noiseValues =
      forecast
        .map(
          (item) =>
            dashboardNumber(
              item.noise_db
            )
        )
        .join(" → ");

    const congestionValues =
      forecast
        .map(
          (item) =>
            dashboardNumber(
              item.congestion,
              2
            )
        )
        .join(" → ");

    forecastBox.innerHTML = `
      <div style="
        display:flex;
        justify-content:space-between;
        padding:7px 0;
        border-bottom:1px solid rgba(255,255,255,0.06);
      ">
        <span>CO₂</span>
        <span>${co2Values}</span>
      </div>

      <div style="
        display:flex;
        justify-content:space-between;
        padding:7px 0;
        border-bottom:1px solid rgba(255,255,255,0.06);
      ">
        <span>Noise</span>
        <span>${noiseValues}</span>
      </div>

      <div style="
        display:flex;
        justify-content:space-between;
        padding:7px 0;
      ">
        <span>Congestion</span>
        <span>${congestionValues}</span>
      </div>
    `;
  }

  // MOPSO
  if (
    mopso &&
    mopso.picks
  ) {
    const picks =
      mopso.picks;

    function pickCard(
      title,
      data,
      description
    ) {
      if (!data) {
        return "";
      }

      return `
        <div style="
          margin-top:8px;
          padding:10px;
          border-radius:9px;
          background:rgba(255,255,255,0.035);
          border:1px solid rgba(255,255,255,0.04);
        ">

          <div style="
            display:flex;
            justify-content:space-between;
          ">

            <span style="
              font-weight:bold;
              font-size:10px;
            ">
              ${title}
            </span>

            <span style="
              font-size:9px;
              color:#b6c3d4;
            ">
              Travel ${
                data.travel_change_pct >= 0
                  ? "+"
                  : ""
              }${dashboardNumber(
                data.travel_change_pct
              )}%
            </span>

          </div>

          <div style="
            margin-top:3px;
            font-size:8px;
            color:#74859b;
          ">
            ${description}
          </div>

          <div style="
            margin-top:3px;
            font-size:9px;
            color:#00ff99;
          ">
            CO₂ ${
              data.emissions_change_pct >= 0
                ? "+"
                : ""
            }${dashboardNumber(
              data.emissions_change_pct
            )}%
          </div>

        </div>
      `;
    }

    document.getElementById(
      "mopsoBox"
    ).innerHTML =

      pickCard(
        "BALANCED",
        picks.balanced,
        "Recommended operating point"
      ) +

      pickCard(
        "FASTEST",
        picks.fastest,
        "Minimum travel time"
      ) +

      pickCard(
        "CLEANEST",
        picks.cleanest,
        "Minimum emissions"
      );
  }

  document.getElementById(
    "timeValue"
  ).textContent =
    `Replay time: ${
      state.time || "--"
    }`;
}

// ============================================================
// API CONNECTION
// ============================================================

async function updateSmartCityData() {
  try {
    const [
      stateResponse,
      mopsoResponse
    ] = await Promise.all([
      fetch(
        "http://127.0.0.1:8000/state"
      ),
      fetch(
        "http://127.0.0.1:8000/mopso?refresh=false"
      )
    ]);

    if (
      !stateResponse.ok ||
      !mopsoResponse.ok
    ) {
      throw new Error(
        "API request failed"
      );
    }

    const state =
      await stateResponse.json();

    const mopso =
      await mopsoResponse.json();

    // Save latest state
    latestState = state;

    // Update dashboard
    updateDashboard(
      state,
      mopso
    );

    // Update hotspot appearance
    updateHotspots(
      state.now?.congestion
    );

    // Update vehicle simulation
    updateVehicleCount(
      state.now?.vehicle_count
    );

    updateTrafficSpeed(
      state.now?.traffic_speed
    );

    // If sensor panel is already open,
    // refresh its values automatically.
    if (
      sensorPanel.style.display !==
      "none"
    ) {
      const visibleTitle =
        sensorPanel.querySelector(
          "div[style*='font-size:20px']"
        );

      if (visibleTitle) {
        const currentName =
          visibleTitle.textContent.trim();

        const selectedSensor =
          sensors.find(
            (sensor) =>
              sensor.name ===
              currentName
          );

        if (selectedSensor) {
          showSensorPanel(
            selectedSensor
          );
        }
      }
    }

    console.log(
      "SmartCity data updated:",
      state.time
    );

  } catch (error) {
    console.error(
      "SmartCity API connection failed:",
      error
    );

    document.getElementById(
      "timeValue"
    ).textContent =
      "API connection failed";
  }
}

updateSmartCityData();

setInterval(
  updateSmartCityData,
  5000
);

// ============================================================
// ANIMATION
// ============================================================

let previousTime =
  performance.now();

function animate() {
  requestAnimationFrame(
    animate
  );

  const currentTime =
    performance.now();

  const delta =
    Math.min(
      0.1,
      (currentTime -
        previousTime) /
        1000
    );

  previousTime =
    currentTime;

  controls.update();

  animateVehicles(
    delta
  );

  renderer.render(
    scene,
    camera
  );
}

animate();

// ============================================================
// RESPONSIVE RESIZE
// ============================================================

window.addEventListener(
  "resize",
  () => {
    camera.aspect =
      window.innerWidth /
      window.innerHeight;

    camera.updateProjectionMatrix();

    renderer.setSize(
      window.innerWidth,
      window.innerHeight
    );

    renderer.setPixelRatio(
      Math.min(
        window.devicePixelRatio,
        2
      )
    );
  }
);