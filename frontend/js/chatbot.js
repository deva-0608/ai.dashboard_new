const API = "http://localhost:8000";

/* ================================
   READ URL PARAMS
================================ */
const params = new URLSearchParams(window.location.search);
const reportType = params.get("report_type");
const reportId   = params.get("report_id");

if (!reportType || !reportId) {
  alert("Missing report_type or report_id in URL");
}

/* ================================
   DOM ELEMENTS
================================ */
const input = document.getElementById("chat-input");
const chat  = document.getElementById("chat-messages");
const chartsContainer = document.getElementById("charts-container");
const kpiContainer = document.getElementById("kpi-container");

/* ================================
   CHAT INPUT
================================ */
input.addEventListener("keypress", e => {
  if (e.key === "Enter") send();
});

/* ================================
   SEND MESSAGE
================================ */
function send() {
  const text = input.value.trim();
  if (!text) return;

  append(text, "right");
  input.value = "";

  fetch(`${API}/reports/design/${reportType}/detail/${reportId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: text })
  })
    .then(res => {
      if (!res.ok) throw new Error("Chat API failed");
      return res.json();
    })
    .then(data => {
      append(data.summary || "No summary returned", "left");

      clearDashboard();

      if (Array.isArray(data.kpis)) {
        renderKPIs(data.kpis);
      }

      if (Array.isArray(data.charts)) {
        renderCharts(data.charts);
      }
    })
    .catch(err => {
      console.error(err);
      append("Error processing request", "left");
    });
}

/* ================================
   CHAT MESSAGE
================================ */
function append(msg, side) {
  const div = document.createElement("div");
  div.className = side;
  div.innerText = msg;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

/* ================================
   CLEAR DASHBOARD
================================ */
function clearDashboard() {
  // Dispose old charts safely
  chartsContainer.querySelectorAll(".chart-card").forEach(card => {
    const instance = echarts.getInstanceByDom(card);
    if (instance) instance.dispose();
  });

  chartsContainer.innerHTML = "";
  if (kpiContainer) kpiContainer.innerHTML = "";
}

/* ================================
   RENDER KPIs
================================ */
function renderKPIs(kpis) {
  if (!kpiContainer) return;

  kpis.forEach(kpi => {
    const div = document.createElement("div");
    div.className = "kpi-card";
    div.innerHTML = `
      <div class="kpi-name">${kpi.name}</div>
      <div class="kpi-value">${kpi.value}</div>
    `;
    kpiContainer.appendChild(div);
  });
}

/* ================================
   RENDER CHARTS (DYNAMIC)
================================ */
function renderCharts(charts) {
  if (!charts || charts.length === 0) return;

  charts.forEach(chartSpec => {
    if (!chartSpec.option) return;

    const card = document.createElement("div");
    card.className = "chart-card";
    chartsContainer.appendChild(card);

    const chart = echarts.init(card);
    chart.setOption(chartSpec.option, true);
  });
}
