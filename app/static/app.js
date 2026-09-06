const uploadForm = document.querySelector("#upload-form");
const fileInput = document.querySelector("#pdf-file");
const dropZone = document.querySelector("#drop-zone");
const selectedFile = document.querySelector("#selected-file");
const uploadButton = document.querySelector("#upload-button");
const uploadStatus = document.querySelector("#upload-status");
const uploadReceipt = document.querySelector("#upload-receipt");
const receiptDocumentId = document.querySelector("#receipt-document-id");
const receiptChunkCount = document.querySelector("#receipt-chunk-count");

const searchForm = document.querySelector("#search-form");
const searchQuery = document.querySelector("#search-query");
const topK = document.querySelector("#top-k");
const searchButton = document.querySelector("#search-button");
const searchStatus = document.querySelector("#search-status");
const resultsHeading = document.querySelector("#results-heading");
const results = document.querySelector("#results");
let searchInFlight = false;

function updateStatus(element, state, message) {
  element.dataset.state = state;
  element.querySelector(".status-text").textContent = message;
}

function describeApiError(payload, fallback) {
  if (!payload) {
    return fallback;
  }
  if (typeof payload.detail === "string") {
    return payload.detail;
  }
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join("; ") || fallback;
  }
  return fallback;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // A useful HTTP fallback is shown below when a response has no JSON body.
  }
  if (!response.ok) {
    throw new Error(describeApiError(payload, `Request failed with HTTP ${response.status}.`));
  }
  return payload;
}

function isPdf(file) {
  return file && file.name.toLowerCase().endsWith(".pdf");
}

function setSelectedFile(file) {
  uploadReceipt.hidden = true;
  if (!file) {
    selectedFile.textContent = "SELECT PDF";
    uploadButton.disabled = true;
    updateStatus(uploadStatus, "idle", "AWAITING SOURCE DOCUMENT");
    return;
  }

  selectedFile.textContent = file.name;
  if (!isPdf(file)) {
    uploadButton.disabled = true;
    updateStatus(uploadStatus, "error", "UNSUPPORTED FILE — SELECT A PDF");
    return;
  }
  if (file.size === 0) {
    uploadButton.disabled = true;
    updateStatus(uploadStatus, "error", "EMPTY FILE — SELECT A NON-EMPTY PDF");
    return;
  }

  uploadButton.disabled = false;
  updateStatus(uploadStatus, "idle", `${file.name} READY FOR INGESTION`);
}

fileInput.addEventListener("change", () => {
  setSelectedFile(fileInput.files[0]);
});

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.dataset.dragging = "true";
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    delete dropZone.dataset.dragging;
  });
});

dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (!file) {
    return;
  }
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  setSelectedFile(file);
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file || !isPdf(file) || file.size === 0) {
    setSelectedFile(file);
    return;
  }

  uploadButton.disabled = true;
  fileInput.disabled = true;
  dropZone.dataset.disabled = "true";
  uploadButton.querySelector("span:first-child").textContent = "INGESTING";
  uploadForm.setAttribute("aria-busy", "true");
  uploadReceipt.hidden = true;
  updateStatus(uploadStatus, "loading", "EXTRACTING, EMBEDDING, AND STORING CHUNKS");

  try {
    const formData = new FormData();
    formData.append("file", file);
    const payload = await requestJson("/upload", { method: "POST", body: formData });

    receiptDocumentId.textContent = payload.document_id;
    receiptChunkCount.textContent = String(payload.chunk_count);
    uploadReceipt.hidden = false;
    updateStatus(
      uploadStatus,
      "success",
      `INGESTION COMPLETE — ${payload.chunk_count} CHUNK${payload.chunk_count === 1 ? "" : "S"} STORED`,
    );
    searchQuery.focus();
  } catch (error) {
    updateStatus(uploadStatus, "error", `INGESTION FAILED — ${error.message}`);
  } finally {
    fileInput.disabled = false;
    delete dropZone.dataset.disabled;
    uploadForm.removeAttribute("aria-busy");
    uploadButton.querySelector("span:first-child").textContent = "INGEST DOCUMENT";
    uploadButton.disabled = !isPdf(file) || file.size === 0;
  }
});

function metadataRow(label, value, className = "") {
  const row = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = value;
  if (className) {
    description.className = className;
  }
  row.append(term, description);
  return row;
}

function renderResults(items) {
  results.replaceChildren();
  resultsHeading.textContent = `${items.length} RETRIEVED CHUNK${items.length === 1 ? "" : "S"}`;

  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const message = document.createElement("p");
    message.textContent = "No chunks are stored yet. Ingest a text-based PDF and search again.";
    empty.append(message);
    results.append(empty);
    return;
  }

  items.forEach((item, index) => {
    const article = document.createElement("article");
    article.className = "result-item";

    const evidence = document.createElement("div");
    const rank = document.createElement("p");
    rank.className = "result-rank";
    rank.textContent = `RESULT / ${String(index + 1).padStart(2, "0")}`;
    const source = document.createElement("h3");
    source.className = "result-source";
    source.textContent = item.source_filename;
    const metadata = document.createElement("dl");
    metadata.className = "result-metadata";
    metadata.append(
      metadataRow("PAGE", String(item.page)),
      metadataRow("CHUNK INDEX", String(item.chunk_index)),
      metadataRow("L2 DISTANCE", Number(item.l2_distance).toFixed(6), "result-distance"),
      metadataRow("DOCUMENT ID", item.document_id),
      metadataRow("CHUNK ID", item.chunk_id),
    );
    evidence.append(rank, source, metadata);

    const content = document.createElement("div");
    content.className = "result-content";
    const contentLabel = document.createElement("p");
    contentLabel.className = "result-content-label";
    contentLabel.textContent = "RETRIEVED TEXT";
    const text = document.createElement("p");
    text.className = "result-text";
    text.textContent = item.text;
    content.append(contentLabel, text);

    article.append(evidence, content);
    results.append(article);
  });
}

function updateSearchButton() {
  const topKValue = Number(topK.value);
  searchButton.disabled = (
    searchInFlight || !searchQuery.value.trim() || topKValue < 1 || topKValue > 50
  );
}

searchQuery.addEventListener("input", updateSearchButton);
topK.addEventListener("input", updateSearchButton);

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = searchQuery.value.trim();
  const topKValue = Number(topK.value);
  if (!query || topKValue < 1 || topKValue > 50) {
    updateStatus(searchStatus, "error", "ENTER A QUERY AND A TOP K VALUE FROM 1 TO 50");
    updateSearchButton();
    return;
  }

  searchButton.disabled = true;
  searchInFlight = true;
  searchQuery.disabled = true;
  topK.disabled = true;
  searchButton.querySelector("span:first-child").textContent = "SEARCHING";
  searchForm.setAttribute("aria-busy", "true");
  updateStatus(searchStatus, "loading", "EMBEDDING QUERY AND RANKING STORED CHUNKS");

  try {
    const payload = await requestJson("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: topKValue }),
    });
    renderResults(payload.results);
    updateStatus(
      searchStatus,
      "success",
      `SEARCH COMPLETE — ${payload.count} RESULT${payload.count === 1 ? "" : "S"} RETURNED`,
    );
    document.querySelector(".results-section").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    updateStatus(searchStatus, "error", `SEARCH FAILED — ${error.message}`);
  } finally {
    searchInFlight = false;
    searchQuery.disabled = false;
    topK.disabled = false;
    searchForm.removeAttribute("aria-busy");
    searchButton.querySelector("span:first-child").textContent = "EXECUTE SEARCH";
    updateSearchButton();
  }
});
