/** OCR Form Fill — UI Behaviors */

document.addEventListener('DOMContentLoaded', function() {
  // Drag-and-drop upload
  const dropzone = document.querySelector('.dropzone');
  if (dropzone) {
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        document.querySelector('input[type="file"]').files = files;
        updateDropzoneText(files[0].name);
      }
    });
  }

  // SSE progress stream
  const sessionId = document.querySelector('[data-session-id]');
  if (sessionId) {
    subscribeToProgress(sessionId.dataset.sessionId);
  }

  // Confidence coloring
  document.querySelectorAll('[data-confidence]').forEach(el => {
    const conf = parseFloat(el.dataset.confidence);
    if (conf >= 0.9) el.classList.add('conf-high');
    else if (conf >= 0.7) el.classList.add('conf-medium');
    else el.classList.add('conf-low');
  });
});

function updateDropzoneText(filename) {
  const dz = document.querySelector('.dropzone');
  if (dz) dz.innerHTML = `<p><strong>${filename}</strong></p><p class="text-sm text-gray-500">Click or drag to replace</p>`;
}

function subscribeToProgress(sessionId) {
  const evtSource = new EventSource(`/api/v1/sessions/${sessionId}/events`);
  evtSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      updateStepper(data);
    } catch (e) { /* ignore parse errors */ }
  };
  evtSource.onerror = () => {
    // SSE connection closed — session likely complete
    evtSource.close();
  };
}

function updateStepper(data) {
  const stepper = document.querySelector('.stepper');
  if (!stepper) return;
  const steps = stepper.querySelectorAll('.step');
  steps.forEach(step => {
    if (step.dataset.node === data.node) {
      step.classList.remove('active');
      step.classList.add(data.status === 'running' ? 'active' : 'completed');
    }
  });
}
