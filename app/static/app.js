const uploadForm = document.querySelector("#upload-form");
const fileInput = document.querySelector("#pdf-file");
const dropZone = document.querySelector("#drop-zone");
const selectedFile = document.querySelector("#selected-file");
const uploadButton = document.querySelector("#upload-button");
const uploadStatus = document.querySelector("#upload-status");
const uploadReceipt = document.querySelector("#upload-receipt");
const receiptFilename = document.querySelector("#receipt-filename");
const receiptDocumentId = document.querySelector("#receipt-document-id");
const receiptChunkCount = document.querySelector("#receipt-chunk-count");

const searchForm = document.querySelector("#search-form");
const searchQuery = document.querySelector("#search-query");
const topK = document.querySelector("#top-k");
const searchButton = document.querySelector("#search-button");
const searchStatus = document.querySelector("#search-status");
const promptButtons = document.querySelectorAll("[data-prompt]");
const resultsSummary = document.querySelector("#results-summary");
const results = document.querySelector("#results");
const embeddingModeLabel = document.querySelector("#embedding-mode-label");
const embeddingModeHelper = document.querySelector("#embedding-mode-helper");
let answerInFlight = false;

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

function renderEmptyState(message, hideSummary = true) {
  results.replaceChildren();
  resultsSummary.hidden = hideSummary;
  const empty = document.createElement("div");
  empty.className = "empty-state";
  const copy = document.createElement("p");
  copy.textContent = message;
  empty.append(copy);
  results.append(empty);
}

function setSelectedFile(file) {
  uploadReceipt.hidden = true;
  if (!file) {
    selectedFile.textContent = "DROP OR SELECT A PDF";
    uploadButton.disabled = true;
    updateStatus(uploadStatus, "idle", "UPLOAD A REPORT TO BEGIN");
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
  updateStatus(uploadStatus, "idle", `${file.name} READY TO UPLOAD`);
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
  uploadButton.querySelector("span:first-child").textContent = "UPLOADING";
  uploadForm.setAttribute("aria-busy", "true");
  uploadReceipt.hidden = true;
  updateStatus(uploadStatus, "loading", "EXTRACTING AND EMBEDDING REPORT");

  try {
    const formData = new FormData();
    formData.append("file", file);
    const payload = await requestJson("/upload", { method: "POST", body: formData });

    receiptFilename.textContent = payload.source_filename;
    receiptDocumentId.textContent = payload.document_id;
    receiptChunkCount.textContent = (
      `${Number(payload.chunk_count).toLocaleString("en-US")} `
      + `passage${payload.chunk_count === 1 ? "" : "s"} indexed`
    );
    uploadReceipt.hidden = false;
    updateStatus(uploadStatus, "success", "REPORT READY");
    updateStatus(searchStatus, "success", "YOUR REPORT IS READY — ASK A QUESTION");
    renderEmptyState("Your report is ready. Ask a question to generate a grounded answer.");
    searchQuery.focus();
  } catch (error) {
    updateStatus(uploadStatus, "error", `INGESTION FAILED — ${error.message}`);
  } finally {
    fileInput.disabled = false;
    delete dropZone.dataset.disabled;
    uploadForm.removeAttribute("aria-busy");
    uploadButton.querySelector("span:first-child").textContent = "UPLOAD REPORT";
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

function buildPassage(item, index) {
  const article = document.createElement("article");
  article.className = "result-item";

  const evidence = document.createElement("div");
  const rank = document.createElement("p");
  rank.className = "result-rank";
  rank.textContent = `PASSAGE ${String(index + 1).padStart(2, "0")}`;
  const source = document.createElement("h3");
  source.className = "result-source";
  source.textContent = item.source_filename;
  const page = document.createElement("p");
  page.className = "result-page";
  page.textContent = `Page ${item.page}`;
  evidence.append(rank, source, page);

  const content = document.createElement("div");
  content.className = "result-content";
  const text = document.createElement("p");
  text.className = "result-text";
  text.textContent = item.text;

  const metadata = document.createElement("dl");
  metadata.className = "result-metadata";
  metadata.append(
    metadataRow("L2 DISTANCE", Number(item.l2_distance).toFixed(6), "result-distance"),
    metadataRow("CHUNK", String(item.chunk_index)),
  );

  const technicalDetails = document.createElement("details");
  technicalDetails.className = "technical-details result-technical-details";
  const detailsSummary = document.createElement("summary");
  detailsSummary.textContent = "TECHNICAL DETAILS";
  const technicalMetadata = document.createElement("dl");
  technicalMetadata.append(
    metadataRow("DOCUMENT ID", item.document_id),
    metadataRow("CHUNK ID", item.chunk_id),
  );
  technicalDetails.append(detailsSummary, technicalMetadata);
  content.append(text, metadata, technicalDetails);

  article.append(evidence, content);
  return article;
}

function buildCitation(citation, passages) {
  const item = document.createElement("li");
  item.className = "citation-item";
  const sourceLabel = document.createElement("p");
  sourceLabel.className = "citation-label";
  sourceLabel.textContent = `SOURCE ${String(citation.source_id).padStart(2, "0")}`;
  const filename = document.createElement("h4");
  filename.textContent = citation.source_filename;
  const location = document.createElement("p");
  location.textContent = `Page ${citation.page} · Chunk ${citation.chunk_index}`;

  const passage = passages[citation.source_id - 1];
  if (passage) {
    const distance = document.createElement("p");
    distance.className = "citation-distance";
    distance.textContent = `L2 ${Number(passage.l2_distance).toFixed(6)}`;
    item.append(sourceLabel, filename, location, distance);
  } else {
    item.append(sourceLabel, filename, location);
  }
  return item;
}

function renderAnswer(payload) {
  results.replaceChildren();
  resultsSummary.hidden = false;
  resultsSummary.textContent = (
    `${payload.citations.length} VERIFIED SOURCE${payload.citations.length === 1 ? "" : "S"}`
    + ` · ${payload.retrieved_passages.length} PASSAGES RETRIEVED`
  );

  const answer = document.createElement("article");
  answer.className = "answer-block";
  const answerLabel = document.createElement("p");
  answerLabel.className = "answer-label";
  answerLabel.textContent = payload.insufficient_evidence
    ? "INSUFFICIENT EVIDENCE"
    : "ANSWER";
  const answerText = document.createElement("p");
  answerText.className = "answer-text";
  answerText.textContent = payload.answer;
  answer.append(answerLabel, answerText);

  const sources = document.createElement("section");
  sources.className = "sources-block";
  const sourcesHeading = document.createElement("h3");
  sourcesHeading.textContent = "SOURCES";
  sources.append(sourcesHeading);
  if (payload.citations.length > 0) {
    const sourceList = document.createElement("ol");
    sourceList.className = "citation-list";
    payload.citations.forEach((citation) => {
      sourceList.append(buildCitation(citation, payload.retrieved_passages));
    });
    sources.append(sourceList);
  } else {
    const noSources = document.createElement("p");
    noSources.className = "no-sources";
    noSources.textContent = "No verified sources support an answer for this question.";
    sources.append(noSources);
  }

  const retrievalDetails = document.createElement("details");
  retrievalDetails.className = "retrieval-details";
  const retrievalSummary = document.createElement("summary");
  retrievalSummary.textContent = (
    `VIEW RETRIEVED PASSAGES · ${payload.retrieved_passages.length}`
  );
  const passageList = document.createElement("div");
  passageList.className = "retrieved-passages";
  if (payload.retrieved_passages.length === 0) {
    const empty = document.createElement("p");
    empty.className = "no-sources";
    empty.textContent = "No passages were retrieved.";
    passageList.append(empty);
  } else {
    payload.retrieved_passages.forEach((item, index) => {
      passageList.append(buildPassage(item, index));
    });
  }
  retrievalDetails.append(retrievalSummary, passageList);
  results.append(answer, sources, retrievalDetails);
}

function updateSearchButton() {
  const topKValue = Number(topK.value);
  searchButton.disabled = (
    answerInFlight || !searchQuery.value.trim() || topKValue < 1 || topKValue > 10
  );
}

searchQuery.addEventListener("input", updateSearchButton);
topK.addEventListener("input", updateSearchButton);
promptButtons.forEach((button) => {
  button.addEventListener("click", () => {
    searchQuery.value = button.dataset.prompt;
    updateSearchButton();
    searchQuery.focus();
  });
});

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = searchQuery.value.trim();
  const topKValue = Number(topK.value);
  if (!question || topKValue < 1 || topKValue > 10) {
    updateStatus(searchStatus, "error", "ENTER A QUESTION AND CHOOSE THE NUMBER OF PASSAGES");
    updateSearchButton();
    return;
  }

  searchButton.disabled = true;
  answerInFlight = true;
  searchQuery.disabled = true;
  topK.disabled = true;
  promptButtons.forEach((button) => { button.disabled = true; });
  searchButton.querySelector("span:first-child").textContent = "GENERATING";
  searchForm.setAttribute("aria-busy", "true");
  updateStatus(searchStatus, "loading", "RETRIEVING EVIDENCE + GENERATING ANSWER");

  try {
    const payload = await requestJson("/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: topKValue }),
    });
    renderAnswer(payload);
    updateStatus(
      searchStatus,
      "success",
      payload.insufficient_evidence
        ? "INSUFFICIENT RETRIEVED EVIDENCE"
        : `${payload.citations.length} VERIFIED SOURCE${payload.citations.length === 1 ? "" : "S"}`,
    );
    document.querySelector(".results-section").scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  } catch (error) {
    updateStatus(searchStatus, "error", `ANSWER FAILED — ${error.message}`);
  } finally {
    answerInFlight = false;
    searchQuery.disabled = false;
    topK.disabled = false;
    promptButtons.forEach((button) => { button.disabled = false; });
    searchForm.removeAttribute("aria-busy");
    searchButton.querySelector("span:first-child").textContent = "GENERATE GROUNDED ANSWER";
    updateSearchButton();
  }
});

async function updateProviderMode() {
  try {
    const health = await requestJson("/health");
    if (health.embedding_provider === "simulated") {
      embeddingModeLabel.textContent = "TEST MODE · SIMULATED EMBEDDINGS";
      embeddingModeHelper.textContent = (
        "Pipeline mechanics only. Simulated vectors do not provide semantic similarity."
      );
      return;
    }
    embeddingModeLabel.textContent = (
      `LOCAL EMBEDDINGS + ${health.answer_model} · ${health.answer_provider}`
    ).toUpperCase();
  } catch {
    embeddingModeLabel.textContent = "PROVIDER STATUS UNAVAILABLE";
    embeddingModeHelper.textContent = "Check the health endpoint for configuration status.";
  }
}

updateProviderMode();
