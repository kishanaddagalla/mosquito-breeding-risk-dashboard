/* ==========================================================================
   Chart.js Analytics Initialization & Dynamic Data Synchronization
   ========================================================================== */

let tempChart = null;
let humChart = null;
let riskChart = null;
let riskPieChart = null;
let nodeCompareChart = null;

function initCharts() {
  const chartOptionsBase = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color: '#78716c',
          font: { family: "'Outfit', 'Inter', sans-serif", size: 12 }
        }
      },
      tooltip: {
        backgroundColor: '#1e293b',
        titleColor: '#f8fafc',
        bodyColor: '#cbd5e1',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(128, 128, 128, 0.18)' },
        ticks: { color: '#78716c', font: { size: 11 } }
      },
      y: {
        grid: { color: 'rgba(128, 128, 128, 0.18)' },
        ticks: { color: '#78716c', font: { size: 11 } }
      }
    }
  };

  // 1. Temperature Chart
  const ctxTemp = document.getElementById('tempChart');
  if (ctxTemp) {
    tempChart = new Chart(ctxTemp, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Temperature (°C)',
          data: [],
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.12)',
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          pointRadius: 3,
          pointHoverRadius: 6
        }]
      },
      options: chartOptionsBase
    });
  }

  // 2. Humidity Chart
  const ctxHum = document.getElementById('humidityChart');
  if (ctxHum) {
    humChart = new Chart(ctxHum, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Humidity (%)',
          data: [],
          borderColor: '#06b6d4',
          backgroundColor: 'rgba(6, 182, 212, 0.12)',
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          pointRadius: 3,
          pointHoverRadius: 6
        }]
      },
      options: chartOptionsBase
    });
  }

  // 3. Risk Score Timeline Chart
  const ctxRisk = document.getElementById('riskChart');
  if (ctxRisk) {
    riskChart = new Chart(ctxRisk, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Risk Index Score (0-100)',
          data: [],
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245, 158, 11, 0.15)',
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          pointRadius: 3,
          pointHoverRadius: 6
        }]
      },
      options: {
        ...chartOptionsBase,
        scales: {
          ...chartOptionsBase.scales,
          y: {
            ...chartOptionsBase.scales.y,
            min: 0,
            max: 100
          }
        }
      }
    });
  }

  // 4. Risk Level Distribution Pie Chart
  const ctxPie = document.getElementById('riskPieChart');
  if (ctxPie) {
    riskPieChart = new Chart(ctxPie, {
      type: 'doughnut',
      data: {
        labels: ['LOW Risk', 'MODERATE Risk', 'HIGH Risk'],
        datasets: [{
          data: [0, 0, 0],
          backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
          borderColor: '#090d16',
          borderWidth: 3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: '#94a3b8', font: { family: "'Outfit', sans-serif", size: 12 } }
          }
        }
      }
    });
  }

  // 5. Node Comparison Chart
  const ctxNode = document.getElementById('nodeCompareChart');
  if (ctxNode) {
    nodeCompareChart = new Chart(ctxNode, {
      type: 'bar',
      data: {
        labels: ['Temperature (°C)', 'Humidity (%)', 'Risk Score (%)'],
        datasets: [{
          label: 'NODE-01',
          data: [0, 0, 0],
          backgroundColor: 'rgba(6, 182, 212, 0.7)',
          borderColor: '#06b6d4',
          borderWidth: 2,
          borderRadius: 6
        }]
      },
      options: {
        ...chartOptionsBase,
        plugins: {
          ...chartOptionsBase.plugins,
          legend: {
            labels: { color: '#78716c', font: { family: "'Outfit', sans-serif", size: 12 } }
          }
        }
      }
    });
  }
}

async function updateAnalyticsCharts() {
  try {
    const response = await fetch('/api/analytics');
    const result = await response.json();
    if (result.status !== 'success' || !result.data) return;

    const data = result.data;
    
    // Format timestamp labels (e.g., "HH:MM")
    const formattedLabels = data.timestamps.map(ts => {
      const parts = ts.split(' ');
      return parts.length > 1 ? parts[1].substring(0, 5) : ts;
    });

    // Update Temperature Chart
    if (tempChart) {
      tempChart.data.labels = formattedLabels;
      tempChart.data.datasets[0].data = data.temperatures;
      tempChart.update();
    }

    // Update Humidity Chart
    if (humChart) {
      humChart.data.labels = formattedLabels;
      humChart.data.datasets[0].data = data.humidities;
      humChart.update();
    }

    // Update Risk Timeline Chart
    if (riskChart) {
      riskChart.data.labels = formattedLabels;
      riskChart.data.datasets[0].data = data.scores;
      riskChart.update();
    }

    // Update Risk Distribution Pie Chart
    if (riskPieChart && data.risk_counts) {
      riskPieChart.data.datasets[0].data = [
        data.risk_counts.LOW || 0,
        data.risk_counts.MODERATE || 0,
        data.risk_counts.HIGH || 0
      ];
      riskPieChart.update();
    }

    // Update Node Comparison Chart
    if (nodeCompareChart) {
      const latest = await fetch('/api/latest?allow_empty=1').then(r => r.json()).catch(() => null);
      if (latest && latest.status === 'success' && latest.data) {
        nodeCompareChart.data.datasets[0].data = [
          latest.data.temperature || 0,
          latest.data.humidity || 0,
          latest.data.risk_score || 0
        ];
        nodeCompareChart.update();
      }
    }

  } catch (error) {
    console.error('Failed to load analytics chart data:', error);
  }
}
