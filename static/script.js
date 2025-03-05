const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const progressContainer = document.getElementById('progress-container');
const progress = document.getElementById('progress-bar-inner');
const progressText = document.getElementById('progress-text');
const result = document.getElementById('result');
let fileToUpload = null;

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    showUploadOptions(e.dataTransfer.files[0]);
});

fileInput.addEventListener('change', (e) => {
    showUploadOptions(e.target.files[0]);
});

function copyToClipboard(button) {
    const input = button.parentElement.querySelector('.link-input');
    input.select();
    document.execCommand('copy');
    window.getSelection().removeAllRanges();
    button.innerHTML = '✅ copied link!';
    setTimeout(() => {
        button.innerHTML = '📋 copy link';
    }, 2000);
}

function showUploadOptions(file) {
    fileToUpload = file;
    document.getElementById('options').style.display = 'flex';
}

function cancelUpload() {
    fileToUpload = null;
    document.getElementById('options').style.display = 'none';
}

function confirmUpload() {
    const expirationDays = document.getElementById('expiration-days').value;
    const maxDownloads = document.getElementById('max-downloads').value;
    const password = document.getElementById('file-password').value;
    
    uploadFile(fileToUpload, {
        expirationDays,
        maxDownloads: maxDownloads || null,
        password: password || null
    });
    
    document.getElementById('options').style.display = 'none';
}

function uploadFile(file, options) {
    if (file.size > 500 * 1024 * 1024) {
        result.innerHTML = '<p style="color: #e74c3c;">❌ file size exceeds 512mb limit!</p>';
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('options', JSON.stringify(options));
    progressContainer.style.display = 'block';
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload', true);
    xhr.upload.onprogress = (e) => {
        const percentComplete = (e.loaded / e.total) * 100;
        progress.style.width = percentComplete + '%';
        progressText.textContent = Math.round(percentComplete) + '%';
    };
    xhr.onload = function() {
        if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            const fullUrl = window.location.origin + response.download_url;
            result.innerHTML = `
                <p style="color: #2ecc71;">✨ file uploaded successfully!</p>
                <p style="color: #e7dc3c;">🔑 deletion key (save it somewhere): <span class="key">${response.deletion_key}</span></p>
                <div class="link-container">
                    <input type="text" class="link-input" value="${fullUrl}" readonly>
                    <a class="button" onclick="copyToClipboard(this)">📋 copy link</a>
                </div>
            `;
        } else {
            result.innerHTML = '<p style="color: #e74c3c;">❌ file upload failed!</p>';
        }
    };
    xhr.send(formData);
}

function checkPassword() {
    const password = document.getElementById('access-password').value;
    const fileId = window.location.pathname.split('/').pop();
    fetch('/check-password/' + fileId, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ password: password })
    })
    .then(response => response.json())
    .then(data => {
        if (data.valid) {
            document.getElementById('password-prompt').style.display = 'none';
            document.getElementById('file-content').style.display = 'block';
            
            // Dynamically load preview after password authentication
            const previewContainer = document.getElementById('preview-container');
            if (previewContainer && previewContainer.dataset.previewType) {
                const previewType = previewContainer.dataset.previewType;
                const previewSrc = `/get/${fileId}?password=${password}`;
                
                if (previewType === 'image') {
                    const img = document.createElement('img');
                    img.src = previewSrc;
                    img.classList.add('media-preview');
                    previewContainer.innerHTML = '';
                    previewContainer.appendChild(img);
                } else if (previewType === 'video') {
                    const video = document.createElement('video');
                    video.controls = true;
                    video.classList.add('media-preview');
                    const source = document.createElement('source');
                    source.src = previewSrc;
                    source.type = `video/${previewContainer.dataset.fileExtension}`;
                    video.appendChild(source);
                    previewContainer.innerHTML = '';
                    previewContainer.appendChild(video);
                } else if (previewType === 'audio') {
                    const audio = document.createElement('audio');
                    audio.controls = true;
                    audio.classList.add('media-preview');
                    const source = document.createElement('source');
                    source.src = previewSrc;
                    source.type = `audio/${previewContainer.dataset.fileExtension}`;
                    audio.appendChild(source);
                    previewContainer.innerHTML = '';
                    previewContainer.appendChild(audio);
                }
            }

            const downloadButton = document.getElementById('download-button');
            if (downloadButton)
                downloadButton.href = `/get/${fileId}?password=${password}`;
        } else {
            alert('incorrect password');
        }
    });
}
function reportFile(fileId) {
    const reason = prompt("provide the reason you're reporting this file.");
    if (reason) {
        fetch('/report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ fileId: fileId, reason: reason }),
        })
        .then(response => {
            if (response.ok) {
                alert("thank you for your report!");
            } else {
                alert("error reporting the file.");
            }
        });
    }
}

function deleteFile(fileId) {
    const key = prompt("provide the 6-digit deletion key.");
    if (key) {
        fetch('/delete/' + fileId, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ key: key })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert("file deleted successfully!");
                window.location.href = '/';
            } else {
                alert("error deleting the file.");
            }
        });
    }
}
