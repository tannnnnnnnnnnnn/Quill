import {
  DEFAULT_SERVER_URL,
  SITE_DEFINITIONS,
  getSettings,
  saveSettings
} from "./src/config.js";

const form = document.querySelector("#settingsForm");
const serverUrl = document.querySelector("#serverUrl");
const autoPrompt = document.querySelector("#autoPrompt");
const siteList = document.querySelector("#siteList");
const saveStatus = document.querySelector("#saveStatus");
const siteInputs = new Map();

function addSiteToggle(key, label) {
  const row = document.createElement("label");
  row.className = "toggle-row";
  const copy = document.createElement("span");
  const name = document.createElement("strong");
  name.textContent = label;
  copy.append(name);
  const input = document.createElement("input");
  input.type = "checkbox";
  input.name = key;
  row.append(copy, input);
  siteList.append(row);
  siteInputs.set(key, input);
}

for (const [key, site] of Object.entries(SITE_DEFINITIONS)) {
  addSiteToggle(key, site.label);
}

const settings = await getSettings();
serverUrl.value = settings.serverUrl || DEFAULT_SERVER_URL;
autoPrompt.checked = settings.autoPrompt;
for (const [key, input] of siteInputs) input.checked = settings.sites[key];

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;

  const sites = Object.fromEntries(
    [...siteInputs].map(([key, input]) => [key, input.checked])
  );
  await saveSettings({
    serverUrl: serverUrl.value,
    autoPrompt: autoPrompt.checked,
    sites
  });
  saveStatus.textContent = "Saved";
  setTimeout(() => {
    saveStatus.textContent = "";
  }, 1800);
});
