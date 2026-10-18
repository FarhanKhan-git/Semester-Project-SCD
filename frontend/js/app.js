/* =========================================================================
   app.js : small helper functions used by every page.
   - api()          sends a request to the Python server
   - requireLogin() sends the user to the login page if not logged in
   - buildSidebar() draws the left menu for the user's role
   ========================================================================= */

// ---------- Saving the login in the browser ----------
function saveLogin(data) {
  localStorage.setItem("vv_token", data.token);
  localStorage.setItem("vv_user", JSON.stringify(data.user));
}

function getUser() {
  const text = localStorage.getItem("vv_user");
  return text ? JSON.parse(text) : null;
}

function logout() {
  localStorage.removeItem("vv_token");
  localStorage.removeItem("vv_user");
  window.location.href = "login.html";
}

// Each role has its own home page
function homePage(role) {
  if (role === "examiner") return "examiner-dashboard.html";
  if (role === "admin") return "admin.html";
  return "student-dashboard.html";
}

// ---------- Talking to the server ----------
// Example: const exams = await api("/api/exams");
// Example: await api("/api/login", { method: "POST", body: { email, password } });
async function api(path, options = {}) {
  const settings = { method: options.method || "GET", headers: {} };
  const token = localStorage.getItem("vv_token");
  if (token) settings.headers["Authorization"] = "Bearer " + token;

  if (options.form) {
    settings.body = options.form;                 // FormData (file uploads)
  } else if (options.body) {
    settings.headers["Content-Type"] = "application/json";
    settings.body = JSON.stringify(options.body);
  }

  const response = await fetch(path, settings);
  if (response.status === 401 && !path.includes("/login")) {
    logout();
    return;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Something went wrong. Please try again.");
  return data;
}

// ---------- Page protection ----------
function requireLogin(role) {
  const user = getUser();
  if (!user) {
    window.location.href = "login.html";
    return null;
  }
  if (role && user.role !== role) {
    window.location.href = homePage(user.role);
    return null;
  }
  return user;
}

// ---------- Left menu ----------
function buildSidebar(activePage) {
  const user = getUser();
  const menus = {
    examiner: [["examiner-dashboard.html", "Dashboard"], ["create-exam.html", "Create Exam"]],
    student: [["student-dashboard.html", "Dashboard"], ["practice.html", "Practice Mode"]],
    admin: [["admin.html", "Admin Panel"]],
  };
  const links = menus[user.role]
    .map(([page, label]) => `<a href="${page}" class="${page === activePage ? "active" : ""}">${label}</a>`)
    .join("");

  document.getElementById("sidebar").innerHTML = `
    <a class="logo" href="${homePage(user.role)}">
      <div class="wave"><span></span><span></span><span></span><span></span><span></span></div>VivaVoice
    </a>
    <div class="menu">
      <div class="menu-title">Menu</div>
      ${links}
    </div>
    <div class="user-box">
      <div class="name">${escapeHtml(user.name)}</div>
      <div class="role">${user.role}</div>
      <button class="btn btn-sm" onclick="logout()">Log out</button>
    </div>`;
}

// ---------- Small display helpers ----------
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

function formatDate(isoText) {
  const d = new Date(isoText + (isoText.endsWith("Z") ? "" : "Z"));
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) +
    ", " + d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function badge(text) {
  const colours = {
    "Active": "green", "Completed": "green", "Correct": "green", "Published": "green",
    "In Progress": "amber", "Partially Correct": "amber", "Awaiting Results": "amber", "Medium": "amber",
    "Closed": "grey", "Easy": "green", "Hard": "red", "Incorrect": "red",
  };
  return `<span class="badge badge-${colours[text] || "grey"}">${escapeHtml(text)}</span>`;
}

function percent(score, max) {
  return max ? Math.round((score / max) * 100) : 0;
}

function showMessage(elementId, text, type = "error") {
  const box = document.getElementById(elementId);
  box.className = "alert alert-" + type;
  box.textContent = text;
}

function copyCode(code) {
  navigator.clipboard.writeText(code);
  alert("Exam code " + code + " copied. Share it with your students.");
}
