/* ==========================================================================
   Mosquito Breeding Risk Detection System - Main Controller JS
   ========================================================================== */

let currentRiskLevel = 'LOW';
let previousScore = 0;
let pollInterval = null;

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initClock();
  initCharts();
  
  // Initial data fetch
  fetchLatestReading();
  fetchHistoryData();
  updateAnalyticsCharts();

  // Poll for live sensor updates every 3.5 seconds
  pollInterval = setInterval(fetchLatestReading, 3500);

  // Setup form submit handlers
  setupConfigModal();
  setupOperations();

  // Scroll listener for Project Documentation Reading Progress & Active TOC Link
  window.addEventListener('scroll', handleDocScroll);
});

/* Tab Navigation */
function initNavigation() {
  const navBtns = document.querySelectorAll('.nav-btn');
  const pages = document.querySelectorAll('.tab-page');

  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      switchTab(targetTab);
    });
  });
}

function switchTab(targetTab) {
  const navBtns = document.querySelectorAll('.nav-btn');
  const pages = document.querySelectorAll('.tab-page');

  navBtns.forEach(b => {
    if (b.getAttribute('data-tab') === targetTab) {
      b.classList.add('active');
    } else {
      b.classList.remove('active');
    }
  });

  pages.forEach(p => p.classList.remove('active'));

  const targetPage = document.getElementById(`${targetTab}-page`);
  if (targetPage) targetPage.classList.add('active');

  if (targetTab === 'analytics') {
    updateAnalyticsCharts();
  } else if (targetTab === 'map') {
    refreshMapNodes();
  } else if (targetTab === 'history') {
    fetchHistoryData();
  } else if (targetTab === 'operations') {
    loadOperations();
  } else if (targetTab === 'project') {
    handleDocScroll();
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* The selected profile is included in future simulator readings. Hardware
   readings retain their reported species so historical results stay accurate. */
function switchSpeciesProfile(species) {
  localStorage.setItem('mosquitoSpeciesProfile', species);
  const selected = document.querySelector(`#speciesSwitcher option[value="${species}"]`);
  if (selected) {
    showToast(`Simulation profile set to ${selected.textContent}.`);
  }
}

function showToast(message) {
  let toast = document.getElementById('appToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'appToast';
    toast.setAttribute('role', 'status');
    toast.style.cssText = 'position:fixed;right:1rem;bottom:1rem;z-index:9999;padding:.8rem 1rem;border-radius:.65rem;background:#0f766e;color:#fff;box-shadow:0 10px 28px rgba(0,0,0,.28);font-size:.85rem;opacity:0;transform:translateY(10px);transition:all .2s ease';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  requestAnimationFrame(() => { toast.style.opacity = '1'; toast.style.transform = 'translateY(0)'; });
  clearTimeout(showToast.timeout);
  showToast.timeout = setTimeout(() => { toast.style.opacity = '0'; toast.style.transform = 'translateY(10px)'; }, 2800);
}

function getUserRole() {
  return localStorage.getItem('mosquitoUserRole') || 'Administrator';
}

function canAccessRole(targetRole) {
  const currentRole = getUserRole();
  if (!targetRole) return true;
  return targetRole.split(',').map(role => role.trim()).includes(currentRole);
}

function applyRolePermissions() {
  const role = getUserRole();
  const roleSpecificElements = document.querySelectorAll('[data-role]');
  roleSpecificElements.forEach(element => {
    const allowedRoles = (element.dataset.role || '').split(',').map(item => item.trim()).filter(Boolean);
    const allowed = allowedRoles.length === 0 || allowedRoles.includes(role);
    if (element instanceof HTMLButtonElement || element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement || element instanceof HTMLFormElement) {
      element.disabled = !allowed;
      element.style.opacity = allowed ? '1' : '0.5';
      element.style.cursor = allowed ? '' : 'not-allowed';
    }
  });

  const configBtn = document.getElementById('btnOpenConfig');
  if (configBtn) {
    configBtn.disabled = !canAccessRole('Administrator');
    configBtn.style.opacity = canAccessRole('Administrator') ? '1' : '0.5';
    configBtn.style.cursor = canAccessRole('Administrator') ? '' : 'not-allowed';
  }
}

/* Print Project Documentation */
function printDocumentation() {
  window.print();
}

/* Handle Documentation Reading Progress & TOC Active Highlighting */
function handleDocScroll() {
  const projectPage = document.getElementById('project-page');
  if (!projectPage || !projectPage.classList.contains('active')) return;

  const progressBar = document.getElementById('docProgressBar');
  const docContainer = document.getElementById('docBodyContainer');
  if (!docContainer) return;

  // Calculate scroll progress percentage
  const totalHeight = docContainer.scrollHeight - window.innerHeight;
  const currentScroll = window.scrollY - docContainer.offsetTop;
  
  if (totalHeight > 0 && progressBar) {
    const progress = Math.min(Math.max((currentScroll / totalHeight) * 100, 0), 100);
    progressBar.style.width = `${progress}%`;
  }

  // Active TOC Section Highlighting
  const sections = document.querySelectorAll('.doc-card');
  const tocLinks = document.querySelectorAll('.toc-link');

  let currentSecId = '';
  sections.forEach(sec => {
    const secTop = sec.offsetTop - 150;
    if (window.scrollY >= secTop) {
      currentSecId = sec.getAttribute('id');
    }
  });

  tocLinks.forEach(link => {
    if (link.getAttribute('href') === `#${currentSecId}`) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });
}

/* Date & Time Live Clock */
function initClock() {
  const clockElem = document.getElementById('liveClock');
  const dateElem = document.getElementById('liveDate');

  function update() {
    const now = new Date();
    if (clockElem) clockElem.textContent = now.toLocaleTimeString();
    if (dateElem) dateElem.textContent = now.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  }

  update();
  setInterval(update, 1000);
}

/* Fetch Latest Sensor Reading & Update Dashboard UI */
async function fetchLatestReading() {
  try {
    const res = await fetch('/api/latest?allow_empty=1');
    const json = await res.json();

    if (json.status === 'success' && json.data) {
      updateDashboardUI(json.data, json.is_hardware_connected);
    } else if (json.status === 'success' && json.data === null) {
      showWaitingForSensorData();
    } else if (res.status === 404) {
      showWaitingForSensorData();
    }
  } catch (err) {
    console.error('Error fetching latest sensor reading:', err);
    updateConnectionStatus('OFFLINE');
  }
}

function showWaitingForSensorData() {
  updateConnectionStatus('WAITING');
  document.getElementById('valTemp').textContent = '--°C';
  document.getElementById('valHumidity').textContent = '--%';
  document.getElementById('lastUpdate').textContent = 'Waiting for sensor data';
  document.getElementById('valWater').textContent = 'WAITING';
  document.getElementById('valWater').style.color = 'var(--text-muted)';
  document.getElementById('waterRippleWrapper').classList.remove('active');
  document.getElementById('riskBadge').textContent = 'NO DATA';
  document.getElementById('riskBadge').className = 'risk-badge UNKNOWN';
  document.getElementById('gaugeScore').textContent = '--';
  document.getElementById('riskReasonText').textContent = 'Waiting for sensor readings from NODE-01.';
  document.getElementById('hwRssi').textContent = '-- dBm';
  document.getElementById('hwBattery').textContent = '--%';
}

/* Update Dashboard Components */
function updateDashboardUI(reading, isHardwareConnected) {
  updateConnectionStatus(isHardwareConnected ? 'ONLINE' : 'WAITING');

  // 1. Temperature & Humidity Values (with smooth count up)
  const tempElem = document.getElementById('valTemp');
  const humElem = document.getElementById('valHumidity');
  const lastUpdateElem = document.getElementById('lastUpdate');

  if (tempElem) animateValue(tempElem, parseFloat(tempElem.textContent) || 0, reading.temperature, 800, '°C');
  if (humElem) animateValue(humElem, parseFloat(humElem.textContent) || 0, reading.humidity, 800, '%');
  if (lastUpdateElem) lastUpdateElem.textContent = reading.timestamp;

  // 2. Water Status Indicator & Ripple Animation
  const waterElem = document.getElementById('valWater');
  const waterIconWrapper = document.getElementById('waterRippleWrapper');

  if (waterElem) {
    if (reading.water_detected) {
      waterElem.textContent = 'DETECTED';
      waterElem.style.color = '#ef4444';
      if (waterIconWrapper) waterIconWrapper.classList.add('active');
    } else {
      waterElem.textContent = 'NOT DETECTED';
      waterElem.style.color = '#10b981';
      if (waterIconWrapper) waterIconWrapper.classList.remove('active');
    }
  }

  // 3. Risk Gauge Update
  updateRiskGauge(reading.risk_score, reading.risk_level, reading.risk_reason);

  // 4. Warning Alert Banner Trigger
  const alertBanner = document.getElementById('alertBanner');
  const alertMsg = document.getElementById('alertMsg');

  if (reading.risk_level === 'HIGH' || reading.water_detected) {
    if (alertBanner && !alertBanner.classList.contains('manually-closed')) {
      alertBanner.classList.add('active');
      if (alertMsg) {
        if (reading.risk_level === 'HIGH') {
          alertMsg.textContent = `CRITICAL ALERT: HIGH Mosquito Breeding Risk (${reading.risk_score}%) detected! Standing water & temperature optimal for larvae multiplication.`;
        } else {
          alertMsg.textContent = `WARNING: Stagnant Water Detected at sensor site. Environmental vector risk monitoring active.`;
        }
      }
    }
  } else {
    if (alertBanner) alertBanner.classList.remove('active');
  }
}

/* Risk Gauge & Score Animation */
function updateRiskGauge(score, level, reason) {
  const gaugeProgress = document.getElementById('gaugeProgress');
  const gaugeScore = document.getElementById('gaugeScore');
  const riskBadge = document.getElementById('riskBadge');
  const reasonText = document.getElementById('riskReasonText');

  // Gauge circumference = 2 * PI * r = 2 * 3.14159 * 90 = 565.48
  const maxDash = 565;
  const offset = maxDash - (score / 100) * maxDash;

  if (gaugeProgress) {
    gaugeProgress.style.strokeDashoffset = offset;

    // Color transition
    if (level === 'LOW') {
      gaugeProgress.style.stroke = 'var(--risk-low)';
    } else if (level === 'MODERATE') {
      gaugeProgress.style.stroke = 'var(--risk-mod)';
    } else {
      gaugeProgress.style.stroke = 'var(--risk-high)';
    }
  }

  if (gaugeScore) {
    animateValue(gaugeScore, previousScore, score, 1000, '%');
    previousScore = score;
  }

  if (riskBadge) {
    riskBadge.textContent = `${level} RISK`;
    riskBadge.className = `risk-badge ${level}`;
  }

  if (reasonText) {
    reasonText.textContent = reason || 'Environmental conditions normal.';
  }

  currentRiskLevel = level;
}

/* Smooth Value Counter Animation */
function animateValue(elem, start, end, duration, suffix = '') {
  if (isNaN(start)) start = 0;
  if (isNaN(end)) end = 0;
  if (start === end) {
    elem.textContent = `${end}${suffix}`;
    return;
  }

  const range = end - start;
  let current = start;
  const increment = end > start ? 0.4 : -0.4;
  const stepTime = Math.abs(Math.floor(duration / (range / increment)));
  
  const startTime = performance.now();

  function step(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const val = (start + range * progress).toFixed(1);
    elem.textContent = `${val}${suffix}`;

    if (progress < 1) {
      requestAnimationFrame(step);
    } else {
      elem.textContent = `${end}${suffix}`;
    }
  }

  requestAnimationFrame(step);
}

/* Connection Status Indicator */
function updateConnectionStatus(state) {
  const statusPill = document.getElementById('connectionPill');
  const statusText = document.getElementById('connectionText');

  if (state === 'ONLINE' || state === true) {
    if (statusPill) {
      statusPill.style.borderColor = 'rgba(16, 185, 129, 0.4)';
      statusPill.style.background = 'rgba(16, 185, 129, 0.1)';
    }
    if (statusText) {
      statusText.textContent = 'ESP8266 ONLINE';
      statusText.style.color = 'var(--risk-low)';
    }
  } else if (state === 'WAITING') {
    if (statusPill) {
      statusPill.style.borderColor = 'rgba(245, 158, 11, 0.4)';
      statusPill.style.background = 'rgba(245, 158, 11, 0.1)';
    }
    if (statusText) {
      statusText.textContent = 'WAITING FOR HARDWARE';
      statusText.style.color = 'var(--risk-mod)';
    }
  } else {
    if (statusPill) {
      statusPill.style.borderColor = 'rgba(239, 68, 68, 0.4)';
      statusPill.style.background = 'rgba(239, 68, 68, 0.1)';
    }
    if (statusText) {
      statusText.textContent = 'SERVER DISCONNECTED';
      statusText.style.color = 'var(--risk-high)';
    }
  }
}

/* Close Alert Banner */
function closeAlertBanner() {
  const alertBanner = document.getElementById('alertBanner');
  if (alertBanner) {
    alertBanner.classList.remove('active');
    alertBanner.classList.add('manually-closed');
  }
}

/* Simulation Controls */
async function triggerSimulation(mode) {
  try {
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: mode,
        species: localStorage.getItem('mosquitoSpeciesProfile') || 'aedes'
      })
    });
    const json = await res.json();
    if (json.status === 'success') {
      // Re-enable alert banner if high risk requested
      const alertBanner = document.getElementById('alertBanner');
      if (alertBanner) alertBanner.classList.remove('manually-closed');

      updateDashboardUI(json.data);
      updateAnalyticsCharts();
    }
  } catch (err) {
    console.error('Simulation trigger failed:', err);
  }
}

function openWiringDiagram() {
  const modal = document.getElementById('wiringModal');
  if (modal) modal.classList.add('active');
}

function exportPDFReport() {
  switchTab('project');
  window.setTimeout(() => window.print(), 120);
}

let gisMap = null;
let gisMarkers = [];
let userLocationMarker = null;
let userLocationRadius = null;
let exampleNodeMode = false;
let exampleNodes = [];
let currentSiteLocation = null;
window.exampleNodes = exampleNodes;

function persistExampleNodeState() {
  try {
    localStorage.setItem('mosquitoExampleNodes', JSON.stringify(exampleNodes));
  } catch (error) {
    console.warn('Unable to save example nodes:', error);
  }
}

function loadExampleNodeState() {
  try {
    const savedNodes = JSON.parse(localStorage.getItem('mosquitoExampleNodes') || '[]');
    exampleNodes = Array.isArray(savedNodes) ? savedNodes.filter(node =>
      typeof node.node_id === 'string' && node.node_id.startsWith('EXAMPLE-') &&
      typeof node.name === 'string' && Number.isFinite(node.lat) && Number.isFinite(node.lng) &&
      Number.isFinite(node.temperature) && Number.isFinite(node.humidity) &&
      typeof node.water_detected === 'boolean' && ['LOW', 'MODERATE', 'HIGH'].includes(node.risk_level) &&
      Number.isFinite(node.risk_score)
    ) : [];
  } catch (error) {
    exampleNodes = [];
  }
  window.exampleNodes = exampleNodes;
  syncNodeSelectors();
}

window.addEventListener('DOMContentLoaded', () => {
  loadExampleNodeState();
});

function setCurrentLocationMarker(latitude, longitude) {
  if (!gisMap) return;

  currentSiteLocation = { lat: latitude, lng: longitude };
  const latLng = [latitude, longitude];
  const popupHtml = '<div class="map-popup"><h4>Current site</h4><p>Node 01</p></div>';

  if (!userLocationMarker) {
    userLocationRadius = L.circle(latLng, {
      radius: 120,
      color: '#38bdf8',
      fillColor: '#38bdf8',
      fillOpacity: 0.12,
      weight: 1
    }).addTo(gisMap);

    userLocationMarker = L.circleMarker(latLng, {
      radius: 9,
      color: '#38bdf8',
      fillColor: '#38bdf8',
      fillOpacity: 1,
      weight: 2
    }).addTo(gisMap).bindPopup(popupHtml);
  } else {
    userLocationRadius.setLatLng(latLng);
    userLocationMarker.setLatLng(latLng).bindPopup(popupHtml);
  }

  gisMap.flyTo(latLng, 14, { animate: true, duration: 1.2 });

  if (typeof loadOperations === 'function') {
    loadOperations();
  }
}

function requestCurrentLocation() {
  if (!('geolocation' in navigator)) {
    showToast('Geolocation is not supported in this browser.');
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (position) => {
      setCurrentLocationMarker(position.coords.latitude, position.coords.longitude);
      showToast('Current location added to the GIS map.');
    },
    (error) => {
      console.warn('Current location unavailable:', error.message || error);
      showToast('Unable to access your current location.');
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
  );
}

function toggleExampleNodePlacement() {
  exampleNodeMode = !exampleNodeMode;
  const button = Array.from(document.querySelectorAll('button')).find(btn => btn.textContent.includes('Add Example Node'));
  if (button) {
    button.classList.toggle('btn-primary', exampleNodeMode);
    button.classList.toggle('btn-secondary', !exampleNodeMode);
    button.innerHTML = exampleNodeMode ? '<i class="fa-solid fa-map-pin"></i> Click map to place node' : '<i class="fa-solid fa-map-pin"></i> Add Example Node';
  }
  showToast(exampleNodeMode ? 'Click anywhere on the map to place an example node.' : 'Example node placement mode off.');
}

function addExampleNodeAt(latlng) {
  let exampleNumber = 1;
  while (exampleNodes.some(node => node.node_id === `EXAMPLE-${exampleNumber}`)) exampleNumber++;
  const nodeId = `EXAMPLE-${exampleNumber}`;
  const riskLevel = ['LOW', 'MODERATE', 'HIGH'][Math.floor(Math.random() * 3)];
  const sampleNode = {
    node_id: nodeId,
    name: `Example Node ${exampleNumber}`,
    lat: latlng.lat,
    lng: latlng.lng,
    temperature: 26 + Math.random() * 10,
    humidity: 45 + Math.random() * 35,
    water_detected: Math.random() > 0.4,
    risk_level: riskLevel,
    risk_score: 35 + Math.random() * 55,
    is_example: true,
    has_reading: true
  };

  exampleNodes.push(sampleNode);
  window.exampleNodes = exampleNodes;
  persistExampleNodeState();
  syncNodeSelectors();
  showToast(`${sampleNode.name} added at the selected map point.`);
  refreshMapNodes();
  if (typeof loadOperations === 'function') {
    loadOperations();
  }
}

function removeExampleNode(nodeId) {
  const index = exampleNodes.findIndex(node => node.node_id === nodeId);
  if (index === -1) return;

  exampleNodes.splice(index, 1);
  window.exampleNodes = exampleNodes;
  persistExampleNodeState();
  syncNodeSelectors();
  showToast(`Removed ${nodeId}.`);
  refreshMapNodes();
  if (typeof loadOperations === 'function') {
    loadOperations();
  }
}

function syncNodeSelectors() {
  const nodes = [
    { node_id: 'NODE-01', name: 'Current Site' },
    ...(window.exampleNodes || [])
  ];

  document.querySelectorAll('#inspectionForm select[name="node_id"], #calibrationForm select[name="node_id"]').forEach(select => {
    const selectedNodeId = select.value;
    select.replaceChildren(...nodes.map(node => new Option(`${node.node_id} · ${node.name}`, node.node_id)));
    select.value = nodes.some(node => node.node_id === selectedNodeId) ? selectedNodeId : 'NODE-01';
  });
}

async function refreshMapNodes() {
  const mapElement = document.getElementById('gisMap');
  const panel = document.getElementById('nodePanelList');
  if (!mapElement || !panel) return;
  try {
    const response = await fetch('/api/nodes');
    const payload = await response.json();
    if (payload.status !== 'success') throw new Error('Node status unavailable');
    const nodes = payload.data || [];
    exampleNodes = window.exampleNodes || exampleNodes;
    window.exampleNodes = exampleNodes;

    const geoNodes = nodes.map(node => {
      if (node.node_id === 'NODE-01' && currentSiteLocation) {
        return { ...node, lat: currentSiteLocation.lat, lng: currentSiteLocation.lng, name: 'Current Site', location: 'Current site' };
      }
      return node;
    });

    let combinedNodes = [...geoNodes, ...exampleNodes];

    if (window.L && !gisMap) {
      gisMap = L.map('gisMap').setView([12.9716, 77.5946], 14);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
      }).addTo(gisMap);

      gisMap.on('click', (event) => {
        if (!exampleNodeMode) return;
        addExampleNodeAt(event.latlng);
        exampleNodeMode = false;
        const button = Array.from(document.querySelectorAll('button')).find(btn => btn.textContent.includes('Click map to place node'));
        if (button) {
          button.classList.remove('btn-primary');
          button.classList.add('btn-secondary');
          button.innerHTML = '<i class="fa-solid fa-map-pin"></i> Add Example Node';
        }
      });
    }
    if (gisMap) {
      if (!userLocationMarker) requestCurrentLocation();
      gisMarkers.forEach(marker => marker.remove());
      gisMarkers = [];

      combinedNodes.forEach(node => {
        const colors = { LOW: '#10b981', MODERATE: '#f59e0b', HIGH: '#ef4444' };
        const color = colors[node.risk_level] || '#64748b';
        const heatHalo = L.circle([node.lat, node.lng], { radius: Math.max(40, (node.risk_score || 0) * 5), color, weight: 1, fillColor: color, fillOpacity: .12 }).addTo(gisMap);
        const popupContent = !node.is_example && !node.has_reading
          ? `<div class="map-popup"><h4>${node.name}</h4><p>Waiting for sensor data.</p></div>`
          : node.is_example
          ? `<div class="map-popup"><h4>${node.name}</h4><p>${node.temperature}°C · ${node.humidity}% humidity</p><p>Water: ${node.water_detected ? 'Detected' : 'Clear'} · <b>${node.risk_level}</b></p><button class="btn-secondary remove-example-node-btn" data-node-id="${node.node_id}" style="margin-top:0.5rem; width:100%;">Remove example node</button></div>`
          : `<div class="map-popup"><h4>${node.name}</h4><p>${node.temperature}°C · ${node.humidity}% humidity</p><p>Water: ${node.water_detected ? 'Detected' : 'Clear'} · <b>${node.risk_level}</b></p></div>`;

        const marker = L.circleMarker([node.lat, node.lng], {
          radius: node.is_example ? 11 : 10,
          color,
          fillOpacity: .85
        }).addTo(gisMap).bindPopup(popupContent);

        if (node.is_example) {
          marker.on('popupopen', () => {
            const deleteButton = document.querySelector(`.remove-example-node-btn[data-node-id="${node.node_id}"]`);
            if (deleteButton) {
              deleteButton.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                removeExampleNode(node.node_id);
              });
            }
          });
        }

        gisMarkers.push(marker, heatHalo);
      });
      gisMap.invalidateSize();
    }
    panel.innerHTML = combinedNodes.map(node => `<div class="node-status-card"><div class="node-status-header"><span class="node-id-badge">${node.node_id}</span><span class="risk-badge ${node.risk_level}">${node.has_reading ? node.risk_level : 'NO DATA'}</span></div><div class="node-name">${node.name}</div><div class="node-meta">${node.has_reading || node.is_example ? `<span>${node.temperature}°C</span><span>${node.humidity}% RH</span><span>${node.water_detected ? 'Water detected' : 'Water clear'}</span>` : '<span>Waiting for sensor data</span>'}</div></div>`).join('');
  } catch (error) {
    console.error('Failed to refresh map nodes:', error);
    panel.innerHTML = '<div style="color:var(--text-muted);padding:1rem;text-align:center">Unable to load node data.</div>';
  }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const rawText = await response.text();
  let payload = {};

  if (rawText) {
    try {
      payload = JSON.parse(rawText);
    } catch (error) {
      payload = { status: 'error', message: rawText.trim().startsWith('<') ? 'The backend returned an HTML error page. Check the server configuration.' : rawText };
    }
  }

  if (!response.ok || payload.status !== 'success') throw new Error(payload.message || 'Request failed');
  return payload.data;
}

function setupOperations() {
  const role = document.getElementById('roleSwitcher');
  if (role) {
    role.value = localStorage.getItem('mosquitoUserRole') || 'Administrator';
    role.addEventListener('change', () => {
      localStorage.setItem('mosquitoUserRole', role.value);
      applyRolePermissions();
      showToast(`Role changed to ${role.value}.`);
    });
  }
  applyRolePermissions();
  const inspectionForm = document.getElementById('inspectionForm');
  inspectionForm?.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      await requestJson('/api/inspections', { method: 'POST', body: new FormData(inspectionForm) });
      inspectionForm.reset(); showToast('Inspection added to the field queue.'); loadOperations();
    } catch (error) { showToast(error.message); }
  });
  const calibrationForm = document.getElementById('calibrationForm');
  calibrationForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const form = new FormData(calibrationForm);
    try {
      await requestJson('/api/calibrations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.fromEntries(form)) });
      calibrationForm.reset(); showToast('Calibration record saved.'); loadOperations();
    } catch (error) { showToast(error.message); }
  });
}

async function loadOperations() {
  try {
    const [alerts, devices, inspections, calibrations, forecast, summary, recommendations] = await Promise.all([
      requestJson('/api/alerts'), requestJson('/api/devices'), requestJson('/api/inspections'),
      requestJson('/api/calibrations'), requestJson('/api/forecast?hours=24'),
      requestJson('/api/summary'), requestJson('/api/recommendations')
    ]);

    const exampleDevices = (window.exampleNodes || []).map(node => ({
      node_id: node.node_id,
      name: node.name,
      temperature: node.temperature,
      humidity: node.humidity,
      water_detected: Boolean(node.water_detected),
      risk_level: node.risk_level || 'LOW',
      risk_score: node.risk_score || 0,
      last_sync: 'Example node',
      rssi: -60,
      battery_level: 100,
      is_example: true,
      has_reading: true
    }));

    const allDevices = [...(Array.isArray(devices) ? devices : []), ...exampleDevices];
    renderOperations({ alerts, devices: allDevices, inspections, calibrations, forecast, summary, recommendations });
  } catch (error) {
    console.error('Failed to load operations:', error);
    showToast('Could not load the operations centre.');
  }
}

function renderOperations({ alerts, devices, inspections, calibrations, forecast, summary, recommendations }) {
  applyRolePermissions();
  document.getElementById('opsAlertCount').textContent = alerts.filter(alert => !alert.acknowledged).length;
  document.getElementById('opsInspectionCount').textContent = inspections.filter(item => item.status !== 'RESOLVED').length;
  document.getElementById('opsDeviceCount').textContent = devices.length;
  document.getElementById('opsForecast').textContent = forecast.risk_score == null ? 'NO DATA' : `${forecast.risk_level} · ${forecast.risk_score}%`;
  document.getElementById('opsForecastText').textContent = forecast.summary;

  const siteHealthScore = document.getElementById('siteHealthScore');
  const siteHealthStatus = document.getElementById('siteHealthStatus');
  const siteHealthText = document.getElementById('siteHealthText');
  if (siteHealthScore) {
    siteHealthScore.textContent = summary.overall_risk == null ? '--' : `${summary.overall_risk}%`;
  }
  if (siteHealthStatus) {
    siteHealthStatus.textContent = summary.site_health;
    siteHealthStatus.className = `summary-status ${summary.site_health.toLowerCase()}`;
  }
  if (siteHealthText) {
    siteHealthText.textContent = `${summary.summary} Highest risk site: ${summary.highest_risk_node || 'N/A'}.`;
  }

  const recommendationList = document.getElementById('recommendationList');
  if (recommendationList) {
    const actions = recommendations.actions || [];
    recommendationList.innerHTML = actions.length
      ? actions.map(action => `<div class="ops-row ${action.priority.toLowerCase()}"><i class="fa-solid fa-clipboard-list"></i><div><b>${escapeHtml(action.title)}</b><small>${escapeHtml(action.detail)}</small><small>${escapeHtml(action.category)} · ${escapeHtml(action.node_id)}</small></div><span class="status-chip ${action.priority}">${action.priority}</span></div>`).join('')
      : '<div class="empty-state">No action required.</div>';
  }

  const compareList = document.getElementById('compareList');
  if (compareList) {
    const comparisonEntries = Array.isArray(summary.comparison) ? summary.comparison : [];
    const exampleEntries = (devices || []).filter(device => device.is_example).map(node => ({
      node_id: node.node_id,
      location: node.name,
      temperature: node.temperature,
      humidity: node.humidity,
      water_detected: node.water_detected,
      risk_level: node.risk_level
    }));
    const compareData = [...comparisonEntries, ...exampleEntries].slice(0, 4);

    compareList.innerHTML = compareData.length
      ? compareData.map(node => `
        <div class="ops-row ${node.risk_level.toLowerCase()}">
          <i class="fa-solid fa-location-dot"></i>
          <div>
            <b>${escapeHtml(node.node_id)} · ${escapeHtml(node.location)}</b>
            <small>${node.temperature}°C · ${node.humidity}% RH · ${node.water_detected ? 'Water detected' : 'Water clear'}</small>
          </div>
          <span class="risk-badge ${node.risk_level}">${node.risk_level}</span>
        </div>
      `).join('')
      : '<div class="empty-state">No node comparison data yet.</div>';
  }

  const alertList = document.getElementById('alertList');
  const canAcknowledge = canAccessRole('Administrator');
  alertList.innerHTML = alerts.length ? alerts.map(alert => `<div class="ops-row ${alert.severity.toLowerCase()}"><i class="fa-solid fa-bell"></i><div><b>${escapeHtml(alert.node_id)} · ${escapeHtml(alert.severity)} risk</b><small>${escapeHtml(alert.message)}</small><small>${escapeHtml(alert.created_at)}</small></div>${alert.acknowledged ? '<span class="status-chip RESOLVED">ACKNOWLEDGED</span>' : (canAcknowledge ? `<button class="btn-secondary" onclick="acknowledgeAlert(${alert.id})">Acknowledge</button>` : '<span class="status-chip OPEN">PENDING</span>')}</div>`).join('') : '<div class="empty-state">No active alerts.</div>';
  const deviceList = document.getElementById('deviceList');
  deviceList.innerHTML = devices.map(device => `<div class="ops-row ${device.risk_level.toLowerCase()}"><i class="fa-solid fa-microchip"></i><div><b>${escapeHtml(device.node_id)} · ${escapeHtml(device.name)}</b>${device.has_reading ? `<small>${device.temperature}°C · ${device.humidity}% RH · ${device.water_detected ? 'Water detected' : 'Water clear'}</small><small>RSSI ${device.rssi} dBm · battery ${device.battery_level}% · ${escapeHtml(device.last_sync)}</small>` : '<small>Waiting for sensor data</small>'}</div><span class="risk-badge ${device.risk_level}">${device.has_reading ? device.risk_level : 'NO DATA'}</span></div>`).join('');
  const inspectionList = document.getElementById('inspectionList');
  const canResolveInspection = canAccessRole('Administrator,Field worker');
  inspectionList.innerHTML = inspections.length ? inspections.map(item => `<div class="ops-row"><i class="fa-solid fa-location-dot"></i><div><b>${escapeHtml(item.site_name)} <span class="status-chip ${item.status}">${item.status}</span></b><small>${escapeHtml(item.node_id)} · ${escapeHtml(item.notes || 'No notes supplied')}</small>${item.photo_path ? `<a class="evidence-link" target="_blank" href="/static/${encodeURI(item.photo_path)}">View photo evidence</a>` : ''}</div>${item.status !== 'RESOLVED' && canResolveInspection ? `<button class="btn-secondary" onclick="resolveInspection(${item.id})">Resolve</button>` : ''}</div>`).join('') : '<div class="empty-state">No inspections yet. Create one after reviewing a risk alert.</div>';
  const calibrationList = document.getElementById('calibrationList');
  calibrationList.innerHTML = calibrations.length ? calibrations.map(item => `<div class="ops-row"><i class="fa-solid fa-ruler-combined"></i><div><b>${escapeHtml(item.sensor_name)} · ${escapeHtml(item.node_id)}</b><small>Offset: ${item.offset_value} · next due ${escapeHtml(item.next_due)}</small><small>${escapeHtml(item.notes || 'No calibration notes')}</small></div></div>`).join('') : '<div class="empty-state">No calibration records yet.</div>';
}

async function acknowledgeAlert(alertId) {
  if (!canAccessRole('Administrator')) {
    showToast('Only administrators can acknowledge alerts.');
    return;
  }
  try { await requestJson(`/api/alerts/${alertId}/acknowledge`, { method: 'POST' }); showToast('Alert acknowledged.'); loadOperations(); }
  catch (error) { showToast(error.message); }
}

async function resolveInspection(inspectionId) {
  if (!canAccessRole('Administrator,Field worker')) {
    showToast('Reviewers cannot resolve inspections.');
    return;
  }
  try { await requestJson(`/api/inspections/${inspectionId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'RESOLVED' }) }); showToast('Inspection marked resolved.'); loadOperations(); }
  catch (error) { showToast(error.message); }
}

/* Fetch History Data and Populate Table */
async function fetchHistoryData() {
  const startDate = document.getElementById('filterStartDate')?.value || '';
  const endDate = document.getElementById('filterEndDate')?.value || '';
  const riskLevel = document.getElementById('filterRiskLevel')?.value || 'ALL';

  let url = `/api/history?risk_level=${riskLevel}`;
  if (startDate) url += `&start_date=${startDate}`;
  if (endDate) url += `&end_date=${endDate}`;

  try {
    const res = await fetch(url);
    const json = await res.json();

    if (json.status === 'success') {
      renderHistoryTable(json.data);
    }
  } catch (err) {
    console.error('Failed to load history data:', err);
  }
}

function renderHistoryTable(data) {
  const tbody = document.getElementById('historyTableBody');
  if (!tbody) return;

  if (data.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 2rem; color: var(--text-muted);">No historical sensor records matching selected filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(row => {
    const parts = row.timestamp.split(' ');
    const dateStr = parts[0] || row.timestamp;
    const timeStr = parts[1] || '';

    const badgeClass = row.risk_level;
    const waterLabel = row.water_detected 
      ? '<span style="color:#ef4444; font-weight:700;"><i class="fa-solid fa-droplet"></i> DETECTED</span>' 
      : '<span style="color:#10b981;"><i class="fa-solid fa-check"></i> CLEAR</span>';

    return `
      <tr>
        <td><strong>${dateStr}</strong></td>
        <td>${timeStr}</td>
        <td>${row.node_id || 'NODE-01'}</td>
        <td>${row.temperature}°C</td>
        <td>${row.humidity}%</td>
        <td>${waterLabel}</td>
        <td><span class="risk-badge ${badgeClass}" style="font-size:0.75rem; padding: 0.2rem 0.6rem;">${row.risk_level}</span></td>
        <td><strong>${row.risk_score}%</strong></td>
      </tr>
    `;
  }).join('');
}

/* Export History Table to CSV */
function exportToCSV() {
  const table = document.getElementById('historyTable');
  if (!table) return;

  let csv = [];
  const rows = table.querySelectorAll('tr');

  for (let i = 0; i < rows.length; i++) {
    const row = [], cols = rows[i].querySelectorAll('td, th');
    for (let j = 0; j < cols.length; j++) {
      // Clean HTML tags from output
      let text = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, '').replace(/,/g, ';');
      row.push('"' + text + '"');
    }
    csv.push(row.join(','));
  }

  const csvFile = new Blob([csv.join('\n')], { type: 'text/csv' });
  const downloadLink = document.createElement('a');
  downloadLink.download = `mosquito_sensor_history_${new Date().toISOString().slice(0, 10)}.csv`;
  downloadLink.href = window.URL.createObjectURL(csvFile);
  downloadLink.style.display = 'none';
  document.body.appendChild(downloadLink);
  downloadLink.click();
  document.body.removeChild(downloadLink);
}

/* Configuration Modal Setup */
function setupConfigModal() {
  const modal = document.getElementById('configModal');
  const openBtn = document.getElementById('btnOpenConfig');
  const closeBtn = document.getElementById('btnCloseConfig');
  const form = document.getElementById('configForm');

  if (openBtn && modal) {
    openBtn.addEventListener('click', async () => {
      // Fetch current config
      try {
        const res = await fetch('/api/config');
        const json = await res.json();
        if (json.status === 'success') {
          const cfg = json.config;
          document.getElementById('cfgTempOptMin').value = cfg.temp_opt_min || 25.0;
          document.getElementById('cfgTempOptMax').value = cfg.temp_opt_max || 32.0;
          document.getElementById('cfgHumidityOpt').value = cfg.humidity_opt || 65.0;
          document.getElementById('cfgThreshHigh').value = cfg.thresh_high || 70;
          document.getElementById('cfgThreshMod').value = cfg.thresh_mod || 35;
        }
      } catch (err) {
        console.error('Failed to load config:', err);
      }
      modal.classList.add('active');
    });
  }

  if (closeBtn && modal) {
    closeBtn.addEventListener('click', () => modal.classList.remove('active'));
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const newCfg = {
        temp_opt_min: document.getElementById('cfgTempOptMin').value,
        temp_opt_max: document.getElementById('cfgTempOptMax').value,
        humidity_opt: document.getElementById('cfgHumidityOpt').value,
        thresh_high: document.getElementById('cfgThreshHigh').value,
        thresh_mod: document.getElementById('cfgThreshMod').value
      };

      try {
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newCfg)
        });
        const json = await res.json();
        if (json.status === 'success') {
          modal.classList.remove('active');
          fetchLatestReading(); // Recalculate with new rules
        }
      } catch (err) {
        console.error('Failed to save config:', err);
      }
    });
  }
}

/* Copy Code Snippet Helper */
function copyCodeSnippet() {
  const codeElem = document.getElementById('espCodeSnippet');
  if (!codeElem) return;

  const text = codeElem.innerText;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('btnCopyCode');
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
      setTimeout(() => btn.innerHTML = orig, 2000);
    }
  });
}
