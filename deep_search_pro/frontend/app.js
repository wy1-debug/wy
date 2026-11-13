const API_BASE = "";

let currentThreadId = null;
let websocket = null;
let heartbeatTimer = null;
let uploadedFiles = [];
let isProcessing = false;
let requestController = null;
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = new Set(['txt', 'md', 'csv', 'json', 'yml', 'yaml', 'docx', 'pdf', 'xlsx', 'xls']);

const chatArea = document.getElementById("chatArea");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const stopBtn = document.getElementById("stopBtn");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const uploadPreview = document.getElementById("uploadPreview");
const refreshFilesBtn = document.getElementById("refreshFilesBtn");
const newChatBtn = document.getElementById("newChatBtn");
const fileList = document.getElementById("fileList");
const connStatus = document.getElementById("connStatus");
const threadIdDisplay = document.getElementById("threadIdDisplay");
const progressPanel = document.getElementById("progressPanel");
const progressText = document.getElementById("progressText");
const progressSteps = document.getElementById("progressSteps");
const toastContainer = document.getElementById("toastContainer");

document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    loadFileList();
});

function bindEvents() {
    sendBtn.addEventListener("click", sendMessage);
    stopBtn.addEventListener("click", stopGeneration);
    newChatBtn.addEventListener("click", startNewChat);
    uploadBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", handleFileSelect);
    refreshFilesBtn.addEventListener("click", () => {
        loadFileList();
        showToast("文件列表已刷新", "success");
    });

    messageInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    });
    messageInput.addEventListener("input", autoResize);

    bindSuggestionButtons();
}

function bindSuggestionButtons() {
    document.querySelectorAll(".suggestion-btn").forEach((button) => {
        button.addEventListener("click", () => {
            messageInput.value = button.dataset.query || "";
            autoResize();
            sendMessage();
        });
    });
}

function autoResize() {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 120)}px`;
}

function startNewChat() {
    if (isProcessing) {
        showToast("请先停止当前任务，再开始新对话", "warning");
        return;
    }
    closeWebSocket();
    currentThreadId = null;
    uploadedFiles = [];
    isProcessing = false;
    window.sessionOutputPath = null;

    chatArea.innerHTML = getWelcomeMarkup();
    bindSuggestionButtons();
    renderUploadPreview();

    threadIdDisplay.textContent = "";
    progressPanel.classList.add("hidden");
    resetProcessingState();
    updateConnectionStatus(false);
    loadFileList();
    showToast("已开始新对话", "success");
}

async function stopGeneration() {
    if (requestController) requestController.abort();
    requestController = null;
    if (currentThreadId) {
        try {
            await fetch(`${API_BASE}/api/task/${encodeURIComponent(currentThreadId)}/cancel`, {
                method: "POST",
            });
        } catch (error) {
            console.warn("取消任务失败:", error);
        }
    }

    closeWebSocket();
    hideProgress(0);
    resetProcessingState();
    removeTypingIndicator();
    addAssistantMessage("任务已停止。");
    showToast("已请求停止任务", "warning");
}

function handleFileSelect(event) {
    if (isProcessing) return;
    const files = Array.from(event.target.files || []);
    for (const file of files) {
        const extension = file.name.split('.').pop().toLowerCase();
        if (!SUPPORTED_EXTENSIONS.has(extension)) {
            showToast(`不支持的文件类型: ${file.name}`, "error");
        } else if (file.size === 0 || file.size > MAX_UPLOAD_BYTES) {
            showToast(`${file.name}: 文件不能为空或超过 50 MB`, "error");
        } else if (uploadedFiles.length >= 20) {
            showToast("每次最多上传 20 个文件", "warning");
            break;
        } else if (!uploadedFiles.some(item => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) {
            uploadedFiles.push(file);
        }
    }
    renderUploadPreview();
    fileInput.value = "";
}

function renderUploadPreview() {
    if (uploadedFiles.length === 0) {
        uploadPreview.classList.add("hidden");
        uploadPreview.innerHTML = "";
        return;
    }

    uploadPreview.classList.remove("hidden");
    uploadPreview.innerHTML = uploadedFiles
        .map((file, index) => `
            <div class="upload-tag">
                <span>${getFileIcon(file.name)} ${escapeHtml(file.name)}</span>
                <button class="remove-btn" type="button" data-index="${index}" title="移除文件">×</button>
            </div>
        `)
        .join("");

    uploadPreview.querySelectorAll(".remove-btn").forEach((button) => {
        button.addEventListener("click", () => {
            if (isProcessing) return;
            uploadedFiles.splice(Number(button.dataset.index), 1);
            renderUploadPreview();
        });
    });
}

async function sendMessage() {
    let query = messageInput.value.trim();
    if (isProcessing || (!query && uploadedFiles.length === 0)) return;
    if (!query) query = "请读取并总结我上传的文件。";

    if (!currentThreadId) {
        currentThreadId = generateUUID();
    }

    isProcessing = true;
    const threadId = currentThreadId;
    const batch = uploadedFiles.slice();
    const controller = new AbortController();
    requestController = controller;
    uploadBtn.disabled = true;
    fileInput.disabled = true;
    newChatBtn.disabled = true;
    sendBtn.classList.add("hidden");
    stopBtn.classList.remove("hidden");

    addUserMessage(query + (batch.length ? `\n附件: ${batch.map(file => file.name).join('、')}` : ""));
    messageInput.value = "";
    messageInput.style.height = "auto";
    showTypingIndicator();
    showProgress("正在处理您的请求...");
    threadIdDisplay.textContent = `Session: ${currentThreadId.slice(0, 8)}...`;

    try {
        await ensureWebSocket(threadId);
        if (controller.signal.aborted) return;

        if (batch.length > 0) {
            showToast("正在上传文件...", "info");
            await uploadFiles(threadId, batch, controller.signal);
            if (controller.signal.aborted) return;
            uploadedFiles = uploadedFiles.filter(file => !batch.includes(file));
            renderUploadPreview();
        }

        const response = await fetch(`${API_BASE}/api/task`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query, thread_id: threadId }),
            signal: controller.signal,
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || `服务端返回 ${response.status}`);
        }

        if (data.status !== "started") {
            throw new Error(data.message || "任务启动失败");
        }
    } catch (error) {
        if (controller.signal.aborted || requestController !== controller) return;
        messageInput.value = query;
        autoResize();
        removeTypingIndicator();
        hideProgress(0);
        addAssistantMessage(`请求失败: ${error.message}`);
        showToast(error.message, "error");
        resetProcessingState();
    }
}

async function uploadFiles(threadId, files, signal) {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    formData.append("thread_id", threadId);

    const response = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body: formData,
        signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.status !== "uploaded") {
        throw new Error(data.detail || "文件上传失败");
    }

    showToast(`已上传 ${data.files.length} 个文件`, "success");
    return data;
}

function ensureWebSocket(threadId) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            closeWebSocket();
            reject(new Error("实时连接超时，请重试"));
        }, 10000);
        connectWebSocket(threadId, (error) => {
            clearTimeout(timer);
            if (error) reject(error);
            else resolve();
        });
    });
}

function connectWebSocket(threadId, onReady) {
    closeWebSocket();

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/${threadId}`;
    websocket = new WebSocket(wsUrl);
    const socket = websocket;

    websocket.onopen = () => {
        if (websocket !== socket) return;
        updateConnectionStatus(true);
        if (typeof onReady === "function") onReady();
        heartbeatTimer = setInterval(() => {
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send("ping");
            }
        }, 25000);
    };

    websocket.onmessage = (event) => {
        if (websocket !== socket) return;
        try {
            handleWebSocketMessage(JSON.parse(event.data));
        } catch (error) {
            console.error("解析 WebSocket 消息失败:", error);
        }
    };

    websocket.onclose = () => {
        if (websocket !== socket) return;
        updateConnectionStatus(false);
        clearHeartbeat();
        if (typeof onReady === "function") onReady(new Error("实时连接已关闭，请重试"));
    };

    websocket.onerror = (error) => {
        if (websocket !== socket) return;
        console.error("WebSocket error:", error);
        updateConnectionStatus(false);
        clearHeartbeat();
        if (typeof onReady === "function") onReady(new Error("无法连接服务端，请确认后端已启动"));
    };
}

function closeWebSocket() {
    clearHeartbeat();
    if (websocket) {
        websocket.close();
        websocket = null;
    }
}

function clearHeartbeat() {
    if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = null;
    }
}

function handleWebSocketMessage(payload) {
    if (payload.type === "pong") return;
    if (payload.type !== "monitor_event") return;

    const eventName = payload.event;
    const message = payload.message || "";
    const eventData = payload.data || {};

    switch (eventName) {
        case "session_created":
            removeTypingIndicator();
            addProgressStep("目录", message, "session");
            if (eventData.path) {
                window.sessionOutputPath = eventData.path;
            }
            break;
        case "tool_start":
            removeTypingIndicator();
            addProgressStep("工具", message, "tool");
            if (eventData.args && Object.keys(eventData.args).length > 0) {
                addProgressStep("参数", JSON.stringify(eventData.args), "tool");
            }
            break;
        case "assistant_call":
            removeTypingIndicator();
            addProgressStep("助手", message, "assistant");
            break;
        case "task_result":
            removeTypingIndicator();
            addProgressStep("完成", "任务完成", "result");
            hideProgress();
            if (eventData.result) {
                addAssistantMessage(eventData.result);
            }
            resetProcessingState();
            setTimeout(loadFileList, 500);
            showToast("任务执行完成", "success");
            break;
        case "cancelled":
            removeTypingIndicator();
            hideProgress(0);
            resetProcessingState();
            addAssistantMessage("任务已取消。");
            showToast("任务已取消", "warning");
            break;
        case "error":
            removeTypingIndicator();
            hideProgress(0);
            addAssistantMessage(`执行出错: ${message}`);
            showToast(message, "error");
            resetProcessingState();
            break;
        default:
            addProgressStep("状态", message || eventName, "tool");
    }
}

function showTypingIndicator() {
    removeTypingIndicator();
    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.id = "typingIndicator";
    typing.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="typing-dots">
            <span></span><span></span><span></span>
        </div>
    `;
    chatArea.appendChild(typing);
    scrollToBottom();
}

function removeTypingIndicator() {
    const typing = document.getElementById("typingIndicator");
    if (typing) typing.remove();
}

function resetProcessingState() {
    isProcessing = false;
    uploadBtn.disabled = false;
    fileInput.disabled = false;
    newChatBtn.disabled = false;
    sendBtn.disabled = false;
    sendBtn.classList.remove("hidden");
    stopBtn.classList.add("hidden");
}

function addUserMessage(text) {
    const welcome = chatArea.querySelector(".welcome-message");
    if (welcome) welcome.remove();

    const msg = document.createElement("div");
    msg.className = "message user";
    msg.innerHTML = `
        <div class="message-avatar">我</div>
        <div>
            <div class="message-bubble">${escapeHtml(text)}</div>
            <div class="message-time">${getCurrentTime()}</div>
        </div>
    `;
    chatArea.appendChild(msg);
    scrollToBottom();
}

function addAssistantMessage(text) {
    const msg = document.createElement("div");
    const messageId = `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    msg.className = "message assistant";
    msg.innerHTML = `
        <div class="message-avatar">AI</div>
        <div>
            <div class="message-bubble" id="${messageId}">${formatMessage(text)}</div>
            <div class="message-actions">
                <button class="action-btn" type="button" data-copy="${messageId}">复制</button>
            </div>
            <div class="message-time">${getCurrentTime()}</div>
        </div>
    `;
    chatArea.appendChild(msg);
    msg.querySelector("[data-copy]").addEventListener("click", () => copyMessage(messageId));
    scrollToBottom();
}

function copyMessage(messageId) {
    const element = document.getElementById(messageId);
    if (!element) return;

    navigator.clipboard.writeText(element.innerText)
        .then(() => showToast("已复制到剪贴板", "success"))
        .catch(() => showToast("复制失败", "error"));
}

function formatMessage(text) {
    let html = escapeHtml(String(text || ""));

    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, _lang, code) => {
        return `<pre><code>${code.replace(/<br>/g, "\n")}</code></pre>`;
    });
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
    html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/(?:^|\n)((?:- .+(?:\n|$))+)/g, (match) => {
        const items = match.trim().split("\n").map((line) => `<li>${line.replace(/^- /, "")}</li>`).join("");
        return `<ul>${items}</ul>`;
    });
    html = html.replace(/\n/g, "<br>");
    html = html.replace(/<pre><code>([\s\S]*?)<\/code><\/pre>/g, (_match, code) => {
        return `<pre><code>${code.replace(/<br>/g, "\n")}</code></pre>`;
    });
    return html;
}

function showProgress(text) {
    progressText.textContent = text;
    progressSteps.innerHTML = "";
    progressPanel.classList.remove("hidden");
}

function hideProgress(delay = 1500) {
    setTimeout(() => progressPanel.classList.add("hidden"), delay);
}

function addProgressStep(label, text, type) {
    const step = document.createElement("div");
    step.className = `progress-step ${type}`;
    step.innerHTML = `<span class="step-icon">${escapeHtml(label)}</span><span>${escapeHtml(text)}</span>`;
    progressSteps.appendChild(step);
    progressSteps.scrollTop = progressSteps.scrollHeight;
}

function showToast(message, type = "info") {
    const labels = {
        success: "成功",
        error: "错误",
        warning: "提醒",
        info: "信息",
    };
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${labels[type] || labels.info}</span>
        <span>${escapeHtml(message)}</span>
    `;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("removing");
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

async function loadFileList() {
    try {
        const path = window.sessionOutputPath || "output";
        const response = await fetch(`${API_BASE}/api/files?path=${encodeURIComponent(path)}`);
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(data.detail || "加载文件列表失败");
        }

        if (!data.files || data.files.length === 0) {
            fileList.innerHTML = '<p class="empty-hint">暂无文件</p>';
            return;
        }

        fileList.innerHTML = data.files.map((file) => `
            <div class="file-item" data-path="${escapeHtml(file.path)}" title="${escapeHtml(file.name)}">
                <span class="file-icon">${getFileIcon(file.name)}</span>
                <span class="file-name">${escapeHtml(file.name)}</span>
                <span class="file-size">${formatSize(file.size)}</span>
            </div>
        `).join("");

        fileList.querySelectorAll(".file-item").forEach((item) => {
            item.addEventListener("click", () => downloadFile(item.dataset.path));
        });
    } catch (error) {
        fileList.innerHTML = `<p class="empty-hint">${escapeHtml(error.message || "加载失败")}</p>`;
    }
}

function downloadFile(filePath) {
    if (!filePath) return;
    window.open(`${API_BASE}/api/download?path=${encodeURIComponent(filePath)}`, "_blank");
}

function getFileIcon(filename) {
    const ext = String(filename || "").split(".").pop().toLowerCase();
    const icons = {
        md: "MD",
        pdf: "PDF",
        docx: "DOC",
        doc: "DOC",
        xlsx: "XLS",
        xls: "XLS",
        txt: "TXT",
        csv: "CSV",
        png: "IMG",
        jpg: "IMG",
        jpeg: "IMG",
    };
    return icons[ext] || "FILE";
}

function formatSize(bytes) {
    const size = Number(bytes) || 0;
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function updateConnectionStatus(connected) {
    const dot = connStatus.querySelector(".status-dot");
    const text = connStatus.querySelector(".status-text");
    dot.className = `status-dot ${connected ? "connected" : "disconnected"}`;
    text.textContent = connected ? "已连接" : "未连接";
}

function scrollToBottom() {
    chatArea.scrollTop = chatArea.scrollHeight;
}

function getCurrentTime() {
    return new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
}

function generateUUID() {
    if (window.crypto && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
        const random = Math.random() * 16 | 0;
        const value = char === "x" ? random : (random & 0x3 | 0x8);
        return value.toString(16);
    });
}

function getWelcomeMarkup() {
    return `
        <div class="welcome-message">
            <div class="welcome-icon">AI</div>
            <h3>欢迎使用 DeepSearch Pro</h3>
            <p>我可以协助查询药品信息、搜索公开资料、检索知识库、分析上传文件，并生成 Markdown 或 PDF 报告。</p>
            <div class="suggestions">
                <button class="suggestion-btn" data-query="查询所有药品信息，并生成一份 Markdown 报告">
                    查询药品信息并生成报告
                </button>
                <button class="suggestion-btn" data-query="搜索布洛芬的最新研究进展">
                    搜索布洛芬研究进展
                </button>
                <button class="suggestion-btn" data-query="查询销售记录最多的药品，并生成 PDF 报告">
                    生成销售数据分析报告
                </button>
            </div>
        </div>
    `;
}
