document.addEventListener('DOMContentLoaded', () => {
    // State management
    const state = {
        currentModel: 'llama3',
        currentTone: 'Formal',
        currentLength: 'Medium',
        currentSubject: '',
        currentBody: '',
        attachmentFile: null,
        ocrExtractedText: '',
        useRag: true
    };

    // UI Elements - Navigation & Tabs
    const menuItems = document.querySelectorAll('.sidebar-menu .menu-item');
    const tabContents = document.querySelectorAll('.tab-content');
    const btnNewEmail = document.getElementById('btn-new-email-action');

    // UI Elements - Mobile Sidebar Responsive Selectors
    const appSidebar = document.getElementById('app-sidebar');

    // UI Elements - Generator Dashboard
    const promptInput = document.getElementById('prompt-input');
    const btnGenerate = document.getElementById('btn-generate-email');
    const btnClearChat = document.getElementById('btn-clear-chat');
    const fileAttachInput = document.getElementById('file-attach-input');
    const attachmentBar = document.getElementById('attachment-preview-bar');
    const attachmentFileName = document.getElementById('attachment-file-name');
    const btnRemoveAttachment = document.getElementById('btn-remove-attachment');
    
    // Output Card Elements
    const outputSubject = document.getElementById('output-subject');
    const outputBody = document.getElementById('output-body');
    const statusTag = document.getElementById('status-tag');
    const toneSelect = document.getElementById('tone-select');
    const lengthSelect = document.getElementById('length-select');
    
    // Action Buttons
    const btnCopyEmail = document.getElementById('btn-copy-email');
    const btnRegenerate = document.getElementById('btn-regenerate');
    const btnSave = document.getElementById('btn-action-save');
    const btnGmail = document.getElementById('btn-action-gmail');
    const btnExportPdf = document.getElementById('btn-action-pdf');
    const btnExportDocx = document.getElementById('btn-action-docx');
    
    // Status Badge Elements
    const statusDot = document.getElementById('status-dot');
    const statusModelName = document.getElementById('status-model-name');
    const statusModeLabel = document.getElementById('status-mode-label');
    const toast = document.getElementById('toast-notification');

    // --- Toast Notification Helper ---
    function showToast(message, duration = 3000) {
        toast.textContent = message;
        toast.classList.remove('hidden');
        setTimeout(() => {
            toast.classList.add('hidden');
        }, duration);
    }



    // --- Tab Navigation Switcher ---
    function switchTab(tabId) {
        menuItems.forEach(item => {
            if (item.dataset.tab === tabId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        tabContents.forEach(tab => {
            if (tab.id === tabId) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // Trigger view specific reloads
        if (tabId === 'tab-history') loadHistory();
        if (tabId === 'tab-saved') loadSavedEmails();
        if (tabId === 'tab-templates') loadTemplates();
        if (tabId === 'tab-rag') loadRagDocuments();
        if (tabId === 'tab-analytics') loadAnalytics();
    }

    menuItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = item.dataset.tab;
            if (tabId) switchTab(tabId);
        });
    });

    btnNewEmail.addEventListener('click', () => {
        switchTab('tab-dashboard');
        promptInput.value = '';
        promptInput.focus();
    });

    // --- Ollama Connection Check & Models ---
    async function checkOllamaStatus() {
        try {
            const res = await fetch('/api/ollama/models');
            const data = await res.json();
            
            const modelDropdown = document.getElementById('model-select-dropdown');
            if (modelDropdown && data.models && data.models.length > 0) {
                modelDropdown.innerHTML = '';
                data.models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m;
                    opt.textContent = m;
                    modelDropdown.appendChild(opt);
                });
            }

            if (data.online) {
                statusDot.className = 'status-indicator online';
                statusModelName.textContent = data.models[0] || 'Ollama LLM';
                statusModeLabel.textContent = 'Ollama Connected (Live)';
                state.currentModel = data.models[0] || 'llama3';
            } else {
                statusDot.className = 'status-indicator';
                statusModelName.textContent = 'Llama3 / Ollama';
                statusModeLabel.textContent = 'Smart Offline Mode Active';
            }
        } catch (e) {
            statusDot.className = 'status-indicator';
            statusModelName.textContent = 'Offline AI Engine';
            statusModeLabel.textContent = 'Offline Fallback Active';
        }
    }

    // --- Generate Email Function ---
    async function generateEmail() {
        const promptText = promptInput.value.trim();
        if (!promptText) {
            showToast('Please enter a prompt first.');
            return;
        }

        // UI Loading State
        btnGenerate.disabled = true;
        btnGenerate.textContent = '...';
        statusTag.textContent = 'Generating...';
        statusTag.style.backgroundColor = '#FEF08A';
        statusTag.style.color = '#854D0E';
        outputSubject.textContent = 'Generating Subject...';
        outputBody.textContent = 'Drafting your email using Ollama AI models... Please wait.';

        try {
            const payload = {
                prompt: promptText,
                model: state.currentModel,
                tone: toneSelect.value,
                length: lengthSelect.value,
                use_rag: state.useRag,
                ocr_text: state.ocrExtractedText
            };

            const res = await fetch('/api/generate-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();

            if (res.ok) {
                state.currentSubject = data.subject || 'Generated Email Subject';
                state.currentBody = data.body || '';

                outputSubject.textContent = state.currentSubject;
                outputBody.textContent = state.currentBody;

                statusTag.textContent = 'Ready';
                statusTag.style.backgroundColor = '#DCFCE7';
                statusTag.style.color = '#15803D';
                
                showToast('Email draft generated successfully!');
            } else {
                showToast(data.error || 'Failed to generate email.');
                statusTag.textContent = 'Error';
            }
        } catch (e) {
            console.error(e);
            showToast('Network error during generation.');
            statusTag.textContent = 'Error';
        } finally {
            btnGenerate.disabled = false;
            btnGenerate.textContent = '➔';
        }
    }

    btnGenerate.addEventListener('click', generateEmail);

    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            generateEmail();
        }
    });

    btnClearChat.addEventListener('click', () => {
        promptInput.value = '';
        outputSubject.textContent = '(Generated Email Subject)';
        outputBody.textContent = 'Your generated email draft will appear here when you enter a prompt and click send.';
        state.currentSubject = '';
        state.currentBody = '';
        removeAttachment();
        showToast('Chat cleared.');
    });

    // --- Render Attachment Thumbnail Preview ---
    function renderAttachmentThumbnail(file) {
        const container = document.getElementById('attachment-thumbnail-container');
        if (!container) return;
        container.innerHTML = ''; // Clear previous

        const fileType = file.type || '';
        const fileExtension = file.name.split('.').pop().toLowerCase();

        if (fileType.startsWith('image/') || ['png', 'jpg', 'jpeg', 'bmp', 'webp', 'gif'].includes(fileExtension)) {
            const img = document.createElement('img');
            img.src = URL.createObjectURL(file);
            img.onload = () => URL.revokeObjectURL(img.src);
            container.appendChild(img);
        } else if (fileType.startsWith('video/') || ['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(fileExtension)) {
            // Renders standard video placeholder thumbnail frame
            const video = document.createElement('video');
            video.src = URL.createObjectURL(file);
            video.muted = true;
            video.playsInline = true;
            video.style.objectFit = 'cover';
            video.style.width = '100%';
            video.style.height = '100%';
            video.currentTime = 1; // Seek to 1s to capture frame
            video.onloadeddata = () => URL.revokeObjectURL(video.src);
            container.appendChild(video);
        } else {
            const span = document.createElement('span');
            span.className = 'file-icon';
            span.textContent = fileExtension === 'pdf' ? '📄' : (fileExtension === 'docx' || fileExtension === 'doc' ? '📝' : '📎');
            container.appendChild(span);
        }
    }

    // --- Attachment & OCR Handler ---
    fileAttachInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        state.attachmentFile = file;
        attachmentFileName.textContent = file.name;
        attachmentBar.classList.remove('hidden');
        renderAttachmentThumbnail(file);

        const fileExtension = file.name.split('.').pop().toLowerCase();
        const isVideo = ['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(fileExtension);
        const label = isVideo ? 'Video Transcribing' : 'Text Extraction';
        
        ocrBadgeTag.textContent = isVideo ? 'Video Transcribing...' : 'OCR Extracted';

        showToast(`${label} in progress for ${file.name}...`);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/ocr', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (res.ok && data.extracted_text) {
                state.ocrExtractedText = data.extracted_text;
                ocrBadgeTag.textContent = isVideo ? 'Video Transcription Ready' : 'OCR Text Extracted';
                showToast(isVideo ? 'Video speech transcription linked to context!' : 'OCR Text extracted and attached to prompt context!');
            }
        } catch (err) {
            showToast('File uploaded.');
        }
    });

    function removeAttachment() {
        state.attachmentFile = null;
        state.ocrExtractedText = '';
        fileAttachInput.value = '';
        if (pdfAttachInput) pdfAttachInput.value = '';
        if (imageAttachInput) imageAttachInput.value = '';
        if (typeof videoAttachInput !== 'undefined' && videoAttachInput) videoAttachInput.value = '';
        if (docxAttachInput) docxAttachInput.value = '';
        if (txtAttachInput) txtAttachInput.value = '';
        attachmentBar.classList.add('hidden');
        const container = document.getElementById('attachment-thumbnail-container');
        if (container) container.innerHTML = '';
    }

    btnRemoveAttachment.addEventListener('click', removeAttachment);

    // --- Format Pill Event Listeners & File Picker Triggers ---
    const pillEmail = document.getElementById('pill-email');
    const pillPdf = document.getElementById('pill-pdf');
    const pillImage = document.getElementById('pill-image');
    const pillVideo = document.getElementById('pill-video');
    const pillDocx = document.getElementById('pill-docx');
    const pillMore = document.getElementById('pill-more');
    const moreMenu = document.getElementById('more-dropdown-menu');

    const pdfAttachInput = document.getElementById('pdf-attach-input');
    const imageAttachInput = document.getElementById('image-attach-input');
    const videoAttachInput = document.getElementById('video-attach-input');
    const docxAttachInput = document.getElementById('docx-attach-input');
    const txtAttachInput = document.getElementById('txt-attach-input');
    const ocrBadgeTag = document.getElementById('ocr-badge-tag');

    function setActivePill(activePill) {
        document.querySelectorAll('.format-pills-row .pill-btn').forEach(btn => btn.classList.remove('active'));
        if (activePill) activePill.classList.add('active');
        if (moreMenu) moreMenu.classList.add('hidden');
    }

    if (pillEmail) {
        pillEmail.addEventListener('click', () => {
            setActivePill(pillEmail);
            showToast('Format set to Email Text Prompt');
        });
    }

    // PDF Pill -> Browses .pdf files
    if (pillPdf) {
        pillPdf.addEventListener('click', () => {
            setActivePill(pillPdf);
            pdfAttachInput.click();
        });
    }

    // Image Pill -> Browses image files (.png, .jpg, .bmp, .webp)
    if (pillImage) {
        pillImage.addEventListener('click', () => {
            setActivePill(pillImage);
            imageAttachInput.click();
        });
    }

    // Video Pill -> Browses video files (.mp4, .mov, .avi, .mkv, .webm)
    if (pillVideo) {
        pillVideo.addEventListener('click', () => {
            setActivePill(pillVideo);
            if (videoAttachInput) videoAttachInput.click();
        });
    }

    // DOCX Pill -> Browses .docx files
    if (pillDocx) {
        pillDocx.addEventListener('click', () => {
            setActivePill(pillDocx);
            docxAttachInput.click();
        });
    }

    // More Dropdown Toggle
    if (pillMore) {
        pillMore.addEventListener('click', (e) => {
            e.stopPropagation();
            moreMenu.classList.toggle('hidden');
        });
    }

    document.addEventListener('click', () => {
        if (moreMenu && !moreMenu.classList.contains('hidden')) {
            moreMenu.classList.add('hidden');
        }
    });

    const menuOptDocx = document.getElementById('menu-opt-docx');
    if (menuOptDocx) {
        menuOptDocx.addEventListener('click', () => {
            setActivePill(pillMore);
            docxAttachInput.click();
        });
    }

    // --- Example Prompt Buttons (Event Delegation) ---
    document.addEventListener('click', (e) => {
        const exampleBtn = e.target.closest('.example-pill-btn');
        if (exampleBtn) {
            const promptText = exampleBtn.dataset.prompt || exampleBtn.textContent.trim();
            promptInput.value = promptText;
            showToast('Loaded example prompt!');
            generateEmail();
        }
    });

    const menuOptTxt = document.getElementById('menu-opt-txt');
    if (menuOptTxt) {
        menuOptTxt.addEventListener('click', () => {
            setActivePill(pillMore);
            txtAttachInput.click();
        });
    }

    const menuOptCsv = document.getElementById('menu-opt-csv');
    if (menuOptCsv) {
        menuOptCsv.addEventListener('click', () => {
            setActivePill(pillMore);
            txtAttachInput.click();
        });
    }

    // Process File Selection & Extraction helper
    async function processSelectedFile(file, formatLabel) {
        if (!file) return;

        state.attachmentFile = file;
        attachmentFileName.textContent = file.name;
        attachmentBar.classList.remove('hidden');
        renderAttachmentThumbnail(file);

        const fileExtension = file.name.split('.').pop().toLowerCase();
        const isVideo = ['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(fileExtension);
        const label = isVideo ? 'Video Transcribing' : 'Text Extraction';
        
        ocrBadgeTag.textContent = isVideo ? 'Video Transcribing...' : `${formatLabel} Attached`;

        showToast(`${label} in progress for ${file.name}...`);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/ocr', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (res.ok && data.extracted_text) {
                state.ocrExtractedText = data.extracted_text;
                ocrBadgeTag.textContent = isVideo ? 'Video Transcription Ready' : 'OCR Text Extracted';
                showToast(isVideo ? 'Video speech transcription linked to context!' : `${formatLabel} file attached and text extracted!`);
            }
        } catch (err) {
            showToast(`${formatLabel} file attached.`);
        }
    }

    if (pdfAttachInput) {
        pdfAttachInput.addEventListener('change', (e) => processSelectedFile(e.target.files[0], 'PDF'));
    }
    if (imageAttachInput) {
        imageAttachInput.addEventListener('change', (e) => processSelectedFile(e.target.files[0], 'Image OCR'));
    }
    if (videoAttachInput) {
        videoAttachInput.addEventListener('change', (e) => processSelectedFile(e.target.files[0], 'Video'));
    }
    if (docxAttachInput) {
        docxAttachInput.addEventListener('change', (e) => processSelectedFile(e.target.files[0], 'DOCX'));
    }
    if (txtAttachInput) {
        txtAttachInput.addEventListener('change', (e) => processSelectedFile(e.target.files[0], 'Document'));
    }

    // --- Action Buttons ---
    btnCopyEmail.addEventListener('click', () => {
        if (!state.currentBody) {
            showToast('No email content to copy.');
            return;
        }
        const fullText = `Subject: ${state.currentSubject}\n\n${state.currentBody}`;
        navigator.clipboard.writeText(fullText).then(() => {
            showToast('Email copied to clipboard!');
        });
    });

    btnRegenerate.addEventListener('click', generateEmail);

    btnSave.addEventListener('click', async () => {
        if (!state.currentBody) {
            showToast('Generate an email first to save.');
            return;
        }
        try {
            const res = await fetch('/api/saved-emails', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    subject: state.currentSubject,
                    body: state.currentBody,
                    tone: toneSelect.value
                })
            });
            if (res.ok) {
                showToast('Email draft saved to Saved Emails!');
            }
        } catch (e) {
            showToast('Error saving email draft.');
        }
    });

    btnGmail.addEventListener('click', () => {
        if (!state.currentBody) {
            showToast('Generate an email draft first.');
            return;
        }
        const subject = encodeURIComponent(state.currentSubject || 'Generated Email');
        const body = encodeURIComponent(state.currentBody);
        
        // Direct Web Gmail Compose URL
        const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&tf=1&su=${subject}&body=${body}`;
        window.open(gmailUrl, '_blank');
        showToast('Opening Gmail Draft Compose...');
    });

    btnExportPdf.addEventListener('click', async () => {
        if (!state.currentBody) {
            showToast('Generate an email draft first.');
            return;
        }
        showToast('Generating PDF document...');
        const res = await fetch('/api/export/pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subject: state.currentSubject, body: state.currentBody })
        });
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${state.currentSubject.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.pdf`;
        a.click();
    });

    btnExportDocx.addEventListener('click', async () => {
        if (!state.currentBody) {
            showToast('Generate an email draft first.');
            return;
        }
        showToast('Generating DOCX document...');
        const res = await fetch('/api/export/docx', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subject: state.currentSubject, body: state.currentBody })
        });
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${state.currentSubject.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.docx`;
        a.click();
    });

    // Tone / Length changes
    toneSelect.addEventListener('change', () => {
        if (state.currentBody) generateEmail();
    });
    lengthSelect.addEventListener('change', () => {
        if (state.currentBody) generateEmail();
    });

    // --- View Loaders ---
    async function loadHistory() {
        const container = document.getElementById('history-list-container');
        try {
            const res = await fetch('/api/history');
            const data = await res.json();
            if (data.length === 0) {
                container.innerHTML = '<p class="empty-state">No chat history found.</p>';
                return;
            }
            container.innerHTML = data.map(item => `
                <div class="history-card">
                    <div class="history-card-header">
                        <strong>Subject: ${item.subject || 'Untitled'}</strong>
                        <small>${item.created_at}</small>
                    </div>
                    <p style="margin-bottom:8px; color:var(--text-secondary);">Prompt: "${item.prompt}"</p>
                    <div style="background:#F8FAFC; padding:12px; border-radius:8px; white-space:pre-wrap; font-size:0.9rem;">${item.body}</div>
                </div>
            `).join('');
        } catch (e) {
            container.innerHTML = '<p class="empty-state">Error loading history.</p>';
        }
    }

    async function loadSavedEmails() {
        const container = document.getElementById('saved-list-container');
        try {
            const res = await fetch('/api/saved-emails');
            const data = await res.json();
            if (data.length === 0) {
                container.innerHTML = '<p class="empty-state">No saved emails yet.</p>';
                return;
            }
            container.innerHTML = data.map(item => `
                <div class="saved-card">
                    <div class="saved-card-header">
                        <strong>${item.subject}</strong>
                        <button class="btn-ghost" onclick="deleteSavedEmail(${item.id})">Delete</button>
                    </div>
                    <div style="background:#F8FAFC; padding:12px; border-radius:8px; white-space:pre-wrap; font-size:0.9rem;">${item.body}</div>
                </div>
            `).join('');
        } catch (e) {
            container.innerHTML = '<p class="empty-state">Error loading saved emails.</p>';
        }
    }

    async function loadTemplates() {
        const container = document.getElementById('templates-grid-container');
        try {
            const res = await fetch('/api/templates');
            const data = await res.json();
            container.innerHTML = data.map(tpl => `
                <div class="template-card" onclick="useTemplate('${encodeURIComponent(tpl.prompt)}')">
                    <span class="template-category">${tpl.category}</span>
                    <h4>${tpl.title}</h4>
                    <p style="font-size:0.88rem; color:var(--text-secondary);">${tpl.prompt}</p>
                </div>
            `).join('');
        } catch (e) {
            container.innerHTML = '<p>Error loading templates.</p>';
        }
    }

    window.useTemplate = (encodedPrompt) => {
        const prompt = decodeURIComponent(encodedPrompt);
        switchTab('tab-dashboard');
        promptInput.value = prompt;
        generateEmail();
    };

    window.deleteSavedEmail = async (id) => {
        await fetch(`/api/saved-emails?id=${id}`, { method: 'DELETE' });
        loadSavedEmails();
        showToast('Saved email deleted.');
    };

    async function loadRagDocuments() {
        const container = document.getElementById('rag-docs-list');
        try {
            const res = await fetch('/api/rag/documents');
            const data = await res.json();
            if (data.length === 0) {
                container.innerHTML = '<p class="empty-state">No documents indexed in knowledge base.</p>';
                return;
            }
            container.innerHTML = `
                <table style="width:100%; border-collapse:collapse;">
                    <thead>
                        <tr style="text-align:left; border-bottom:1px solid var(--border-color);">
                            <th style="padding:10px;">Filename</th>
                            <th style="padding:10px;">Type</th>
                            <th style="padding:10px;">Chunks</th>
                            <th style="padding:10px;">Date</th>
                            <th style="padding:10px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.map(doc => `
                            <tr style="border-bottom:1px solid var(--border-light);">
                                <td style="padding:10px; font-weight:600;">${doc.filename}</td>
                                <td style="padding:10px;">${doc.file_type}</td>
                                <td style="padding:10px;">${doc.chunk_count}</td>
                                <td style="padding:10px; font-size:0.85rem;">${doc.created_at}</td>
                                <td style="padding:10px;"><button class="btn-ghost" onclick="deleteRagDoc(${doc.id})">Delete</button></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } catch (e) {
            container.innerHTML = '<p>Error loading RAG documents.</p>';
        }
    }

    window.deleteRagDoc = async (id) => {
        await fetch(`/api/rag/documents?id=${id}`, { method: 'DELETE' });
        loadRagDocuments();
        showToast('Document deleted from knowledge base.');
    };

    // RAG File Upload
    const ragFileInput = document.getElementById('rag-file-input');
    if (ragFileInput) {
        ragFileInput.addEventListener('change', async (e) => {
            const files = e.target.files;
            if (!files.length) return;
            for (let i = 0; i < files.length; i++) {
                const formData = new FormData();
                formData.append('file', files[i]);
                showToast(`Indexing ${files[i].name} into knowledge base...`);
                await fetch('/api/rag/upload', { method: 'POST', body: formData });
            }
            showToast('Documents indexed for RAG!');
            loadRagDocuments();
        });
    }

    // Drag and Drop support for RAG Document Uploads
    const ragDropzone = document.getElementById('rag-dropzone');
    if (ragDropzone && ragFileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            ragDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            ragDropzone.addEventListener(eventName, () => {
                ragDropzone.style.borderColor = 'var(--primary-coral)';
                ragDropzone.style.backgroundColor = 'rgba(37, 99, 235, 0.08)';
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            ragDropzone.addEventListener(eventName, () => {
                ragDropzone.style.borderColor = 'var(--primary-coral-border)';
                ragDropzone.style.backgroundColor = 'var(--primary-coral-light)';
            }, false);
        });

        ragDropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files.length > 0) {
                // Read files array to input
                const dataTransfer = new DataTransfer();
                for (let i = 0; i < files.length; i++) {
                    dataTransfer.items.add(files[i]);
                }
                ragFileInput.files = dataTransfer.files;
                ragFileInput.dispatchEvent(new Event('change'));
            }
        }, false);
    }



    let dailyChartInstance = null;
    let monthlyChartInstance = null;
    let timeChartInstance = null;

    async function loadAnalytics() {
        try {
            const res = await fetch('/api/analytics');
            const data = await res.json();
            
            document.getElementById('stat-generated').textContent = data.total_generated;
            document.getElementById('stat-time-saved').textContent = `${data.time_saved_hours} hrs`;
            document.getElementById('stat-saved').textContent = data.total_saved;
            document.getElementById('stat-tone').textContent = data.top_tone;
            document.getElementById('time-saved-min-tag').textContent = `${data.time_saved_minutes} mins`;

            // 1. Render Daily Usage Chart
            const dailyCtx = document.getElementById('dailyUsageChart').getContext('2d');
            const dailyLabels = Object.keys(data.daily_usage).length > 0 ? 
                Object.keys(data.daily_usage).reverse() : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
            const dailyData = Object.values(data.daily_usage).length > 0 ? 
                Object.values(data.daily_usage).reverse() : [3, 5, 2, 8, 6, 4, data.total_generated || 9];

            if (dailyChartInstance) dailyChartInstance.destroy();
            dailyChartInstance = new Chart(dailyCtx, {
                type: 'line',
                data: {
                    labels: dailyLabels,
                    datasets: [{
                        label: 'Emails Generated',
                        data: dailyData,
                        borderColor: '#FF4D36',
                        backgroundColor: 'rgba(255, 77, 54, 0.15)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 5,
                        pointHoverRadius: 7,
                        pointBackgroundColor: '#FF4D36'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#F1F5F9' } },
                        x: { grid: { display: false } }
                    }
                }
            });

            // 2. Render Monthly Usage Chart
            const monthlyCtx = document.getElementById('monthlyUsageChart').getContext('2d');
            const monthlyLabels = Object.keys(data.monthly_usage).length > 0 ? 
                Object.keys(data.monthly_usage).reverse() : ['Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'];
            const monthlyData = Object.values(data.monthly_usage).length > 0 ? 
                Object.values(data.monthly_usage).reverse() : [12, 19, 25, 32, 28, data.total_generated || 45];

            if (monthlyChartInstance) monthlyChartInstance.destroy();
            monthlyChartInstance = new Chart(monthlyCtx, {
                type: 'bar',
                data: {
                    labels: monthlyLabels,
                    datasets: [{
                        label: 'Monthly Volume',
                        data: monthlyData,
                        backgroundColor: '#1E293B',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#F1F5F9' } },
                        x: { grid: { display: false } }
                    }
                }
            });

            // 3. Render Time Management & Efficiency Doughnut Chart
            const timeCtx = document.getElementById('timeMgmtChart').getContext('2d');
            const timeSavedMins = data.time_saved_minutes || (data.total_generated * 5.5) || 50;
            const timeSpentMins = Math.round(data.total_generated * 0.5) || 5;

            if (timeChartInstance) timeChartInstance.destroy();
            timeChartInstance = new Chart(timeCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Time Saved with AI (mins)', 'AI Processing Time (mins)'],
                    datasets: [{
                        data: [timeSavedMins, timeSpentMins],
                        backgroundColor: ['#FF4D36', '#E2E8F0'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { boxWidth: 12, font: { family: 'Outfit' } } }
                    },
                    cutout: '70%'
                }
            });

        } catch (e) {
            console.error('Error loading analytics graphs:', e);
        }
    }

    // --- Settings Sub-navigation Tabs Handler ---
    const settingsNavBtns = document.querySelectorAll('.settings-nav-btn');
    settingsNavBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active from all btns
            settingsNavBtns.forEach(b => b.classList.remove('active'));
            // Add active to clicked
            btn.classList.add('active');
            
            // Hide all sections
            const targetSectionId = btn.dataset.section;
            document.querySelectorAll('.settings-section').forEach(sec => {
                sec.classList.remove('active');
            });
            // Show target section
            const targetSec = document.getElementById(targetSectionId);
            if (targetSec) targetSec.classList.add('active');
        });
    });

    // --- Profile Picture Uploader Handler ---
    const profilePicInput = document.getElementById('profile-pic-upload-input');
    const settingsProfilePreview = document.getElementById('settings-profile-pic-preview');
    const headerProfilePic = document.getElementById('header-profile-pic');

    if (profilePicInput) {
        profilePicInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            showToast('Uploading profile picture...');
            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/api/user/upload-profile-pic', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (res.ok && data.profile_picture) {
                    const cacheBustedUrl = `${data.profile_picture}&t=${new Date().getTime()}`;
                    if (settingsProfilePreview) settingsProfilePreview.src = cacheBustedUrl;
                    if (headerProfilePic) headerProfilePic.src = cacheBustedUrl;
                    showToast('Profile picture updated!');
                } else {
                    showToast(data.error || 'Failed to upload image.');
                }
            } catch (err) {
                console.error(err);
                showToast('Error uploading photo.');
            }
        });
    }

    // --- Save All Settings ---
    const btnSaveAllSettings = document.getElementById('btn-save-all-settings');
    if (btnSaveAllSettings) {
        btnSaveAllSettings.addEventListener('click', async () => {
            const senderName = document.getElementById('username-display-input').value.trim();
            const ollamaUrl = document.getElementById('ollama-url-input').value.trim();
            const defaultModel = document.getElementById('model-select-dropdown').value.trim();
            const senderEmail = document.getElementById('sender-email-input').value.trim();
            const receiverName = document.getElementById('receiver-name-input').value.trim();
            const receiverEmail = document.getElementById('receiver-email-input').value.trim();
            const defaultSignature = document.getElementById('signature-input').value;
            
            const smtpServer = document.getElementById('smtp-server-input').value.trim();
            const smtpPort = document.getElementById('smtp-port-input').value.trim();
            const smtpUser = document.getElementById('smtp-user-input').value.trim();
            const smtpPass = document.getElementById('smtp-pass-input').value.trim();
            
            const defaultTone = document.getElementById('setting-default-tone').value;

            showToast('Saving settings...');

            try {
                const res = await fetch('/api/ollama/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sender_name: senderName,
                        ollama_url: ollamaUrl,
                        default_model: defaultModel,
                        sender_email: senderEmail,
                        receiver_name: receiverName,
                        receiver_email: receiverEmail,
                        smtp_server: smtpServer,
                        smtp_port: smtpPort,
                        smtp_user: smtpUser,
                        smtp_pass: smtpPass
                    })
                });
                
                if (res.ok) {
                    showToast('All settings saved successfully!');
                    
                    // Update header display info dynamically
                    const emailTag = document.getElementById('user-email-tag');
                    if (emailTag) {
                        const emailAddress = senderEmail || emailTag.textContent.split('(').pop().replace(')', '').trim();
                        emailTag.textContent = senderName ? `${senderName} (${emailAddress})` : emailAddress;
                    }
                    
                    checkOllamaStatus();
                } else {
                    showToast('Failed to save settings.');
                }
            } catch (err) {
                console.error(err);
                showToast('Error saving settings.');
            }
        });
    }

    // --- Load Settings into Inputs ---
    async function loadSettings() {
        try {
            const res = await fetch('/api/ollama/settings');
            const data = await res.json();
            
            // Inputs
            if (data.sender_name) {
                const usernameInput = document.getElementById('username-display-input');
                if (usernameInput) usernameInput.value = data.sender_name;
                
                // Update header display tag
                const emailTag = document.getElementById('user-email-tag');
                if (emailTag) {
                    const emailAddress = data.sender_email || emailTag.textContent.split('(').pop().replace(')', '').trim();
                    emailTag.textContent = `${data.sender_name} (${emailAddress})`;
                }
            }
            
            if (data.sender_email) document.getElementById('sender-email-input').value = data.sender_email;
            if (data.receiver_name) document.getElementById('receiver-name-input').value = data.receiver_name;
            if (data.receiver_email) document.getElementById('receiver-email-input').value = data.receiver_email;
            if (data.default_signature) document.getElementById('signature-input').value = data.default_signature;
            
            if (data.ollama_url) document.getElementById('ollama-url-input').value = data.ollama_url;
            if (data.default_model) document.getElementById('model-select-dropdown').value = data.default_model;
            
            if (data.smtp_server) document.getElementById('smtp-server-input').value = data.smtp_server;
            if (data.smtp_port) document.getElementById('smtp-port-input').value = data.smtp_port;
            if (data.smtp_user) document.getElementById('smtp-user-input').value = data.smtp_user;
            if (data.smtp_pass) document.getElementById('smtp-pass-input').value = data.smtp_pass;
            
            // Set dynamic preview images on load
            const cacheBustedUrl = `/api/user/profile-pic?t=${new Date().getTime()}`;
            if (settingsProfilePreview) settingsProfilePreview.src = cacheBustedUrl;
            if (headerProfilePic) headerProfilePic.src = cacheBustedUrl;

        } catch (e) {
            console.error('Error loading settings:', e);
        }
    }

    // Load on init
    loadSettings();

    const btnTestConn = document.getElementById('btn-test-ollama-conn');
    if (btnTestConn) {
        btnTestConn.addEventListener('click', () => {
            const ollamaUrl = document.getElementById('ollama-url-input').value.trim();
            checkOllamaStatus(ollamaUrl);
            showToast('Checked Ollama connection status.');
        });
    }

    // Init status on load
    checkOllamaStatus();
});
