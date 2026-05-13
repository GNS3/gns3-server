import RFB from './novnc/core/rfb.js';

(function () {
  'use strict';

  // Parse URL parameters
  const params = new URLSearchParams(window.location.search);
  const wsUrl = params.get('ws_url');
  const nodeName = params.get('node_name') || 'VNC';
  const autoconnect = params.get('autoconnect') !== '0';

  // DOM elements
  const container = document.getElementById('vnc-container');
  const statusBar = document.getElementById('status-bar');
  const errorDialog = document.getElementById('error-dialog');
  const errorTitle = document.getElementById('error-title');
  const errorMessage = document.getElementById('error-message');
  const loadingIndicator = document.getElementById('loading');
  const toolbar = document.getElementById('vnc-toolbar');
  const toolbarToggle = document.getElementById('toolbar-toggle');
  const connectionStatus = document.getElementById('connection-status');
  const clipboardModal = document.getElementById('clipboard-modal');
  const modalOverlay = document.getElementById('modal-overlay');
  const clipboardText = document.getElementById('clipboard-text');

  // State
  let rfb = null;
  let connectionTimeout = null;
  let scale = 1.0;
  let isConnected = false;
  let toolbarVisible = false;
  let mediaRecorder = null;
  let recordedChunks = [];
  let isRecording = false;
  let isPaused = false;
  let recordingStartTime = null;
  let pausedStartTime = null;
  let totalPausedTime = 0;
  let recordingTimer = null;
  let recordingAnimationFrame = null;
  let canvasOverlay = null;
  let overlayContext = null;

  // Click effect for recording
  let clickEffects = []; // Array of {x, y, startTime}
  let currentMousePos = null; // Current mouse position for cursor rendering
  let drawAnimationFrame = null; // Animation frame ID for continuous drawing
  let audioStream = null; // Audio stream for microphone
  let cameraStream = null; // Camera stream for video recording
  let cameraVideo = null; // Video element for camera preview
  let recordingMode = 'vnc'; // Current recording mode: 'vnc', 'vnc-camera', 'camera'
  let isMuted = false; // Microphone muted state

  // Debug mode - set to false in production
  const DEBUG = false;

  // Logging utility
  function log(message, level = 'info') {
    if (!DEBUG && level !== 'error') return; // Only log errors in production

    const prefix = '[VNC Console]';
    const timestamp = new Date().toISOString();
    const logMessage = `${timestamp} ${prefix} ${level.toUpperCase()}: ${message}`;

    if (level === 'error') {
      console.error(logMessage);
    } else if (level === 'warn') {
      console.warn(logMessage);
    } else {
      console.log(logMessage);
    }
  }

  // Update status display
  function updateStatus(message, type = 'info') {
    log(message, type);
    statusBar.textContent = message;
    statusBar.className = type;
    statusBar.style.opacity = '1';

    // Auto-hide success messages after 3 seconds
    if (type === 'success') {
      setTimeout(() => {
        statusBar.style.opacity = '0';
      }, 3000);
    }
  }

  // Show error dialog
  function showError(title, message) {
    log(`${title}: ${message}`, 'error');

    errorTitle.textContent = title;
    errorMessage.textContent = message;
    errorDialog.style.display = 'block';
    statusBar.style.display = 'none';

    if (loadingIndicator) {
      loadingIndicator.style.display = 'none';
    }
  }

  // Hide loading indicator
  function hideLoading() {
    if (loadingIndicator) {
      loadingIndicator.style.display = 'none';
    }
  }

  // Validate required parameters
  if (!wsUrl) {
    showError(
      'Missing Parameter',
      'WebSocket URL (ws_url) is required. Please close this window and try opening the console again.'
    );
    return;
  }

  // Set page title
  document.title = `VNC Console - ${nodeName}`;
  log(`Opening VNC console for node: ${nodeName}`);

  // ===== Toolbar Functions =====

  // Attach RFB event listeners
  function attachRfbEventListeners(rfbInstance) {
    // Event: Connecting
    rfbInstance.addEventListener('connecting', () => {
      log('Connecting to VNC server...');
      updateStatus('Connecting...');
      updateConnectionStatus('Connecting...', '#ffa500');
    });

    // Event: Connected
    rfbInstance.addEventListener('connect', () => {
      clearTimeout(connectionTimeout);
      hideLoading();
      isConnected = true;
      updateStatus('Connected', 'success');
      updateConnectionStatus('Connected', '#4caf50');
      log('Successfully connected to VNC server');

      // Force initial scale
      setTimeout(() => {
        if (rfbInstance) {
          rfbInstance.scaleViewport = true;
          if (typeof rfbInstance.sendScaleConfig === 'function') {
            rfbInstance.sendScaleConfig();
            log('VNC display scaled to fit viewport');
          }
        }
      }, 500);
    });

    // Event: Disconnect
    rfbInstance.addEventListener('disconnect', (e) => {
      clearTimeout(connectionTimeout);
      hideLoading();
      isConnected = false;

      // Note: Do NOT stop recording on disconnect
      // Recording continues locally, even if VNC connection is lost
      // This allows users to get a complete video with possible black screen periods

      const clean = e.detail && e.detail.clean;

      if (clean) {
        // Normal disconnect
        log('Disconnected from VNC server (clean)');
        updateStatus('Disconnected', 'warning');
        updateConnectionStatus('Disconnected', '#ff9800');
      } else {
        // Abnormal disconnect
        const reason = e.detail ? e.detail.reason : 'Unknown error';
        log(`Connection lost: ${reason}`, 'error');
        updateConnectionStatus('Disconnected', '#f44336');
        showError(
          'Connection Lost',
          `The VNC connection was closed unexpectedly.\n\nReason: ${reason}\n\n` +
            'Please check if the node is still running and try again.'
        );
      }
    });

    // Event: Credentials required
    rfbInstance.addEventListener('credentialsrequired', () => {
      log('VNC server requires authentication');
      const password = prompt('Enter VNC password:');

      if (password) {
        log('Sending VNC credentials');
        rfbInstance.sendCredentials({ password: password });
      } else {
        showError(
          'Authentication Required',
          'This VNC server requires a password. Please close this window and try again with the correct credentials.'
        );
        rfbInstance.disconnect();
      }
    });

    // Event: Security failure
    rfbInstance.addEventListener('securityfailure', () => {
      clearTimeout(connectionTimeout);
      log('Security negotiation failed', 'error');
      showError(
        'Security Error',
        'Security negotiation with the VNC server failed. This could be due to:\n\n' +
          '• Unsupported security type\n' +
          '• TLS/SSL configuration mismatch\n' +
          '• Protocol version incompatibility\n\n' +
          'Please check the server configuration and try again.'
      );
    });

    // Event: Clipboard
    rfbInstance.addEventListener('clipboard', (e) => {
      if (e.detail && e.detail.text) {
        log('Clipboard data received from server');
        // Clipboard handling could be added here if needed
      }
    });

    log('RFB event listeners attached');
  }

  // Toggle toolbar visibility
  function toggleToolbar() {
    toolbarVisible = !toolbarVisible;
    if (toolbarVisible) {
      toolbar.classList.remove('hidden');
      toolbarToggle.classList.add('active');
      container.classList.add('with-toolbar');
    } else {
      toolbar.classList.add('hidden');
      toolbarToggle.classList.remove('active');
      container.classList.remove('with-toolbar');
    }
    updateContainerPadding();
    log(`Toolbar ${toolbarVisible ? 'shown' : 'hidden'}`);
  }

  // Update container padding based on toolbar and recording state
  function updateContainerPadding() {
    // Remove all padding classes first
    container.classList.remove('with-toolbar', 'with-recording');

    // Add toolbar padding if visible
    if (toolbarVisible) {
      container.classList.add('with-toolbar');
    }

    // Add recording padding if recording
    if (isRecording) {
      container.classList.add('with-recording');
    }
  }

  // Create recording overlay canvas
  function createRecordingOverlay() {
    // Get VNC canvas
    let vncCanvas = null;
    if (typeof rfb.get_canvas === 'function') {
      vncCanvas = rfb.get_canvas();
    } else if (rfb.canvas) {
      vncCanvas = rfb.canvas;
    } else {
      vncCanvas = container.querySelector('canvas');
    }

    if (!vncCanvas) {
      log('Cannot find VNC canvas for overlay', 'error');
      return false;
    }

    // Create overlay canvas
    canvasOverlay = document.createElement('canvas');
    canvasOverlay.style.position = 'absolute';
    canvasOverlay.style.top = '0';
    canvasOverlay.style.left = '0';
    canvasOverlay.style.pointerEvents = 'none'; // Let clicks pass through
    canvasOverlay.style.zIndex = '100';
    canvasOverlay.width = vncCanvas.width;
    canvasOverlay.height = vncCanvas.height;

    // Add to container (before the loading element)
    container.insertBefore(canvasOverlay, container.firstChild);

    overlayContext = canvasOverlay.getContext('2d');
    log('Recording overlay created');

    return true;
  }

  // Destroy recording overlay canvas
  function destroyRecordingOverlay() {
    if (canvasOverlay && canvasOverlay.parentNode) {
      canvasOverlay.parentNode.removeChild(canvasOverlay);
      canvasOverlay = null;
      overlayContext = null;
      log('Recording overlay destroyed');
    }
  }

  // Draw recording timestamp on overlay
  function drawRecordingTimestamp() {
    if (!overlayContext || !canvasOverlay || !recordingStartTime) {
      return;
    }

    // Clear overlay
    overlayContext.clearRect(0, 0, canvasOverlay.width, canvasOverlay.height);

    // Calculate elapsed time
    let elapsed = Date.now() - recordingStartTime - totalPausedTime;
    if (isPaused && pausedStartTime) {
      elapsed -= Date.now() - pausedStartTime;
    }

    const seconds = Math.floor(elapsed / 1000);
    const minutes = Math.floor(seconds / 60)
      .toString()
      .padStart(2, '0');
    const secs = (seconds % 60).toString().padStart(2, '0');
    const timestamp = `${minutes}:${secs}`;

    // Draw timestamp text at top center (no background)
    overlayContext.font = 'bold 32px monospace';
    overlayContext.fillStyle = isPaused ? '#ff9800' : '#f44336';
    overlayContext.textAlign = 'center';
    overlayContext.textBaseline = 'top';
    overlayContext.textShadow = '2px 2px 4px rgba(0, 0, 0, 0.8)';
    overlayContext.fillText(`⏺ ${timestamp}`, canvasOverlay.width / 2, 20);

    // Request next frame
    if (isRecording) {
      recordingAnimationFrame = requestAnimationFrame(drawRecordingTimestamp);
    }
  }

  // Start recording overlay animation
  function startRecordingOverlay() {
    if (createRecordingOverlay()) {
      drawRecordingTimestamp();
    }
  }

  // Stop recording overlay animation
  function stopRecordingOverlay() {
    if (recordingAnimationFrame) {
      cancelAnimationFrame(recordingAnimationFrame);
      recordingAnimationFrame = null;
    }
    destroyRecordingOverlay();
  }

  // Toggle fullscreen
  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch((err) => {
        log(`Failed to enter fullscreen: ${err.message}`, 'error');
      });
    } else {
      document.exitFullscreen();
    }
  }

  // Send Ctrl+Alt+Del
  function sendCtrlAltDel() {
    if (rfb && isConnected) {
      log('Sending Ctrl+Alt+Del');
      rfb.sendCtrlAltDel();
    }
  }

  // Send Ctrl+Alt+Backspace
  function sendCtrlAltBackspace() {
    if (rfb && isConnected) {
      log('Sending Ctrl+Alt+Backspace');
      // Send key sequence: Ctrl down, Alt down, Backspace down/up, Alt up, Ctrl up
      rfb.sendKey(0xffe3, 'ControlLeft', true); // Ctrl down
      rfb.sendKey(0xffe9, 'AltLeft', true); // Alt down
      rfb.sendKey(0xff08, 'BackSpace', true); // Backspace down
      rfb.sendKey(0xff08, 'BackSpace', false); // Backspace up
      rfb.sendKey(0xffe9, 'AltLeft', false); // Alt up
      rfb.sendKey(0xffe3, 'ControlLeft', false); // Ctrl up
    }
  }

  // Send Tab
  function sendTab() {
    if (rfb && isConnected) {
      log('Sending Tab');
      rfb.sendKey(0xff09, 'Tab');
    }
  }

  // Send Escape
  function sendEsc() {
    if (rfb && isConnected) {
      log('Sending Esc');
      rfb.sendKey(0xff1b, 'Escape');
    }
  }

  // Get selected modifiers
  function getSelectedModifiers() {
    const modifiers = [];
    const ctrlAltCheckbox = document.getElementById('mod-ctrl-alt');

    // Special case: Ctrl+Alt checkbox overrides individual ones
    if (ctrlAltCheckbox && ctrlAltCheckbox.checked) {
      return ['ctrl', 'alt'];
    }

    if (document.getElementById('mod-ctrl').checked) {
      modifiers.push('ctrl');
    }
    if (document.getElementById('mod-alt').checked) {
      modifiers.push('alt');
    }
    if (document.getElementById('mod-shift').checked) {
      modifiers.push('shift');
    }

    return modifiers;
  }

  // Send key combination with modifiers
  function sendKeyCombination(fNum) {
    if (rfb && isConnected) {
      const modifiers = getSelectedModifiers();
      const keysym = 0xffbe + fNum - 1; // F1-F12 keysyms

      // Build description
      const modDesc = modifiers.length > 0 ? modifiers.join('+').toUpperCase() + '+' : '';
      log(`Sending ${modDesc}F${fNum}`);

      // Send modifiers (key down)
      const modifierKeys = {
        ctrl: { code: 0xffe3, name: 'ControlLeft' },
        alt: { code: 0xffe9, name: 'AltLeft' },
        shift: { code: 0xffe1, name: 'ShiftLeft' },
      };

      modifiers.forEach((mod) => {
        rfb.sendKey(modifierKeys[mod].code, modifierKeys[mod].name, true);
      });

      // Send function key
      rfb.sendKey(keysym, `F${fNum}`, true);
      rfb.sendKey(keysym, `F${fNum}`, false);

      // Release modifiers (key up)
      modifiers.reverse().forEach((mod) => {
        rfb.sendKey(modifierKeys[mod].code, modifierKeys[mod].name, false);
      });
    }
  }

  // Send Print Screen
  function sendPrintScreen() {
    if (rfb && isConnected) {
      log('Sending Print Screen');
      rfb.sendKey(0xff15, 'Print');
    }
  }

  // Toggle microphone mute
  function toggleMute() {
    isMuted = !isMuted;

    const muteBtn = document.getElementById('btn-mute');
    if (muteBtn) {
      muteBtn.textContent = isMuted ? '🔇 Muted' : '🔊 Mic';
      muteBtn.classList.toggle('recording', isMuted);
    }

    // If recording is active, toggle audio track
    if (audioStream) {
      audioStream.getAudioTracks().forEach((track) => {
        track.enabled = !isMuted;
      });
      log(isMuted ? 'Microphone muted' : 'Microphone unmuted');
    } else {
      log(isMuted ? 'Will mute microphone when recording starts' : 'Microphone will be enabled when recording');
    }
  }

  // Take screenshot and download
  function takeScreenshot() {
    if (!rfb || !isConnected) {
      log('Cannot take screenshot: not connected', 'error');
      return;
    }

    try {
      // Get the VNC canvas - try different methods
      let canvas = null;

      // Method 1: Try rfb.get_canvas()
      if (typeof rfb.get_canvas === 'function') {
        canvas = rfb.get_canvas();
      }

      // Method 2: Try rfb.canvas
      if (!canvas && rfb.canvas) {
        canvas = rfb.canvas;
      }

      // Method 3: Query canvas from container
      if (!canvas) {
        canvas = container.querySelector('canvas');
      }

      if (!canvas) {
        log('Cannot get VNC canvas - tried all methods', 'error');
        return;
      }

      log(`Got canvas: ${canvas.width}x${canvas.height}`);

      // Convert canvas to data URL first (more compatible)
      const dataUrl = canvas.toDataURL('image/png');

      // Create download link
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `vnc-screenshot-${timestamp}.png`;

      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = filename;
      a.style.display = 'none';
      document.body.appendChild(a);

      // Trigger download
      a.click();

      // Cleanup
      setTimeout(() => {
        document.body.removeChild(a);
        log(`Screenshot saved: ${filename}`);
        updateStatus('Screenshot saved', 'success');
      }, 100);
    } catch (error) {
      log(`Screenshot error: ${error.message}`, 'error');
      log(error.stack, 'error');
    }
  }

  // Toggle recording (start/pause/resume)
  function toggleRecording() {
    if (!rfb || !isConnected) {
      log('Cannot record: not connected', 'error');
      return;
    }

    if (!isRecording) {
      // Start new recording
      startRecording();
    } else if (!isPaused) {
      // Pause recording
      pauseRecording();
    } else {
      // Resume recording
      resumeRecording();
    }
  }

  // Start recording
  async function startRecording() {
    try {
      // Get recording mode from select
      const modeSelect = document.getElementById('record-mode');
      recordingMode = modeSelect ? modeSelect.value : 'vnc';
      log(`Starting recording in mode: ${recordingMode}`);

      let vncCanvas = null;
      let recordingCanvas, recordingCtx;

      // Create camera video element for camera modes
      if (recordingMode === 'vnc-camera' || recordingMode === 'camera') {
        try {
          cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 320, height: 240 },
            audio: false,
          });

          // Use existing preview video element from DOM
          const previewVideo = document.getElementById('camera-preview');
          if (previewVideo) {
            previewVideo.srcObject = cameraStream;
            previewVideo.style.display = 'inline-block';
            cameraVideo = previewVideo;
          } else {
            // Create video element for camera if preview not found
            cameraVideo = document.createElement('video');
            cameraVideo.srcObject = cameraStream;
            cameraVideo.muted = true;
            cameraVideo.autoplay = true;
          }
          await cameraVideo.play();
          log('Camera initialized for recording');
        } catch (err) {
          log(`Camera not available: ${err.message}`, 'warn');
          // Fall back to VNC only mode
          recordingMode = 'vnc';
          cameraStream = null;
          cameraVideo = null;
        }
      }

      if (recordingMode === 'vnc' || recordingMode === 'vnc-camera') {
        // Get the VNC canvas
        if (typeof rfb.get_canvas === 'function') {
          vncCanvas = rfb.get_canvas();
        } else if (rfb.canvas) {
          vncCanvas = rfb.canvas;
        } else {
          vncCanvas = container.querySelector('canvas');
        }

        if (!vncCanvas) {
          log('Cannot find VNC canvas for recording', 'error');
          updateStatus('Recording failed: Cannot find VNC canvas', 'error');
          return;
        }

        log(`Got canvas: ${vncCanvas.width}x${vncCanvas.height}`);

        // Create a recording canvas
        recordingCanvas = document.createElement('canvas');
        recordingCanvas.width = vncCanvas.width;
        recordingCanvas.height = vncCanvas.height;
        recordingCtx = recordingCanvas.getContext('2d', { willReadFrequently: true });
      } else {
        // Pure camera mode - create canvas based on camera resolution
        const camWidth = cameraVideo.videoWidth || 640;
        const camHeight = cameraVideo.videoHeight || 480;

        recordingCanvas = document.createElement('canvas');
        recordingCanvas.width = camWidth;
        recordingCanvas.height = camHeight;
        recordingCtx = recordingCanvas.getContext('2d', { willReadFrequently: true });
      }

      // Capture stream from the recording canvas
      const refreshRate = window.screen.refreshRate || 30;
      log(`Display refresh rate: ${refreshRate}Hz, using ${Math.min(refreshRate, 60)}Hz for recording`);

      let videoStream;
      if (recordingCanvas) {
        videoStream = recordingCanvas.captureStream(Math.min(refreshRate, 60));
      } else {
        // Pure camera mode - use camera stream directly
        videoStream = cameraStream;
      }

      // Get microphone audio
      let combinedStream = videoStream;
      try {
        audioStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        // Apply mute state
        audioStream.getAudioTracks().forEach((track) => {
          track.enabled = !isMuted;
          combinedStream.addTrack(track);
        });
        log(isMuted ? 'Microphone added but muted' : 'Microphone audio added to recording');
      } catch (err) {
        log(`Microphone not available: ${err.message}`, 'warn');
        audioStream = null;
      }

      // Create MediaRecorder
      const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9') ? 'video/webm;codecs=vp9' : 'video/webm';

      mediaRecorder = new MediaRecorder(combinedStream, { mimeType });
      recordedChunks = [];

      // Continuous draw function to ensure video has actual duration
      // Handle camera mode switching during recording
      async function handleCameraModeSwitch(newMode) {
        // Only process if mode changed and recording is active
        if (newMode === recordingMode || !isRecording) return;

        const oldMode = recordingMode;
        recordingMode = newMode;
        log(`Switching recording mode from ${oldMode} to ${newMode}`);

        // Show/hide camera preview based on mode
        const previewVideo = document.getElementById('camera-preview');

        // Need camera for vnc-camera or camera mode
        if (newMode === 'vnc-camera' || newMode === 'camera') {
          if (!cameraStream) {
            try {
              cameraStream = await navigator.mediaDevices.getUserMedia({
                video: { width: 320, height: 240 },
                audio: false,
              });

              // Use existing preview video element from DOM
              if (previewVideo) {
                previewVideo.srcObject = cameraStream;
                previewVideo.style.display = 'inline-block';
                cameraVideo = previewVideo;
              } else {
                cameraVideo = document.createElement('video');
                cameraVideo.srcObject = cameraStream;
                cameraVideo.muted = true;
                cameraVideo.autoplay = true;
              }
              await cameraVideo.play();
              log('Camera initialized after mode switch');
            } catch (err) {
              log(`Camera not available after mode switch: ${err.message}`, 'warn');
              recordingMode = 'vnc'; // Fall back to VNC only
              // Show warning to user
              const modeSelect = document.getElementById('record-mode');
              if (modeSelect) modeSelect.value = 'vnc';
            }
          } else {
            // Camera stream exists, just show preview
            if (previewVideo) {
              previewVideo.style.display = 'inline-block';
              cameraVideo = previewVideo;
            }
          }
        }

        // If switching to VNC only, hide camera preview but keep stream
        if (newMode === 'vnc' && cameraStream) {
          if (previewVideo) {
            previewVideo.style.display = 'none';
          }
          log('Switched to VNC only mode, camera hidden but available');
        }
      }

      function continuousDraw() {
        // Always keep drawing, but only record when not paused
        // This ensures the animation loop continues for when we resume

        // Dynamically get recording mode from select (allows switching during recording)
        const modeSelect = document.getElementById('record-mode');
        const currentMode = modeSelect ? modeSelect.value : 'vnc';

        // Handle camera mode switching during recording
        if (isRecording) {
          handleCameraModeSwitch(currentMode);
        }

        if (currentMode === 'vnc-camera' && vncCanvas && recordingCtx) {
          // Draw VNC canvas
          recordingCtx.drawImage(vncCanvas, 0, 0);

          // Draw camera in corner (picture-in-picture)
          if (cameraVideo) {
            const pipWidth = 200;
            const pipHeight = 150;
            const pipX = recordingCanvas.width - pipWidth - 10;
            const pipY = recordingCanvas.height - pipHeight - 10;

            // Draw semi-transparent background
            recordingCtx.fillStyle = 'rgba(0, 0, 0, 0.3)';
            recordingCtx.fillRect(pipX - 2, pipY - 2, pipWidth + 4, pipHeight + 4);

            // Draw camera feed
            recordingCtx.drawImage(cameraVideo, pipX, pipY, pipWidth, pipHeight);
          }
        } else if (currentMode === 'vnc' && vncCanvas && recordingCtx) {
          // VNC only mode
          recordingCtx.drawImage(vncCanvas, 0, 0);
        } else if (currentMode === 'camera' && cameraVideo) {
          // Camera only mode
          recordingCtx.drawImage(cameraVideo, 0, 0, recordingCanvas.width, recordingCanvas.height);
        }

        // Draw recording timestamp on the recording canvas
        if (recordingStartTime) {
          // Calculate elapsed time
          let elapsed = Date.now() - recordingStartTime - totalPausedTime;

          const seconds = Math.floor(elapsed / 1000);
          const minutes = Math.floor(seconds / 60)
            .toString()
            .padStart(2, '0');
          const secs = (seconds % 60).toString().padStart(2, '0');
          const timestamp = `${minutes}:${secs}`;

          // Draw timestamp at top center (no background)
          recordingCtx.font = 'bold 32px monospace';
          recordingCtx.fillStyle = '#f44336';
          recordingCtx.textAlign = 'center';
          recordingCtx.textBaseline = 'top';
          recordingCtx.textShadow = '2px 2px 4px rgba(0, 0, 0, 0.8)';
          recordingCtx.fillText(`⏺ ${timestamp}`, recordingCanvas.width / 2, 20);
        }

        // Draw GNS3 watermark at bottom right (artistic style)
        recordingCtx.save();
        recordingCtx.font = 'bold italic 40px serif';
        recordingCtx.textAlign = 'right';
        recordingCtx.textBaseline = 'bottom';

        // Add shadow for depth effect
        recordingCtx.shadowColor = 'rgba(0, 0, 0, 0.5)';
        recordingCtx.shadowBlur = 4;
        recordingCtx.shadowOffsetX = 2;
        recordingCtx.shadowOffsetY = 2;

        // Draw with gradient-like effect using two overlapping texts
        recordingCtx.fillStyle = 'rgba(255, 255, 255, 0.12)';
        recordingCtx.fillText('GNS3', recordingCanvas.width - 22, recordingCanvas.height - 22);
        recordingCtx.fillStyle = 'rgba(255, 255, 255, 0.2)';
        recordingCtx.fillText('GNS3', recordingCanvas.width - 20, recordingCanvas.height - 20);
        recordingCtx.restore();

        // Steganography watermark - embed GNS3 in pixel data (for verification)
        // Embed with multiple positions and redundancy for robustness
        const frameCount = Math.floor(((Date.now() - recordingStartTime) / 1000) * 60);
        if (frameCount % 30 === 0) {
          // Every ~0.5 seconds
          const watermarkText = 'GNS3';

          // Multiple embedding positions for redundancy
          const positions = [
            { x: recordingCanvas.width - 100, y: recordingCanvas.height - 40 },
            { x: recordingCanvas.width - 180, y: recordingCanvas.height - 30 },
            { x: recordingCanvas.width - 60, y: recordingCanvas.height - 60 },
          ];

          positions.forEach((pos, posIdx) => {
            // Get image data from watermark area
            const imageData = recordingCtx.getImageData(pos.x, pos.y, 40, 30);
            const data = imageData.data;

            // Embed watermark 3 times with offset for redundancy
            for (let copy = 0; copy < 3; copy++) {
              const offset = copy * 10;

              for (let i = 0; i < watermarkText.length; i++) {
                const charCode = watermarkText.charCodeAt(i);
                for (let bit = 0; bit < 8; bit++) {
                  const pixelIdx = ((i + offset) * 8 + bit) * 4;
                  if (pixelIdx < data.length) {
                    const bitValue = (charCode >> bit) & 1;
                    // Modify blue channel's 2nd bit (more robust than LSB)
                    data[pixelIdx + 2] = (data[pixelIdx + 2] & 0xfd) | (bitValue << 1);
                  }
                }
              }
            }

            // Put modified data back
            recordingCtx.putImageData(imageData, pos.x, pos.y);
          });
        }

        // Draw mouse cursor
        if (currentMousePos) {
          recordingCtx.save();
          // Draw arrow cursor
          recordingCtx.beginPath();
          recordingCtx.moveTo(currentMousePos.x, currentMousePos.y);
          recordingCtx.lineTo(currentMousePos.x, currentMousePos.y + 18);
          recordingCtx.lineTo(currentMousePos.x + 5, currentMousePos.y + 14);
          recordingCtx.lineTo(currentMousePos.x + 10, currentMousePos.y + 14);
          recordingCtx.closePath();
          recordingCtx.fillStyle = '#fff';
          recordingCtx.fill();
          recordingCtx.strokeStyle = '#000';
          recordingCtx.lineWidth = 1;
          recordingCtx.stroke();
          recordingCtx.restore();
        }

        // Draw click effects (ripples)
        const currentTime = Date.now();

        clickEffects = clickEffects.filter((effect) => {
          const age = currentTime - effect.startTime;
          if (age > 600) {
            // Remove effects older than 600ms
            return false;
          }

          // Calculate ripple animation
          const progress = age / 600; // 0 to 1
          const maxRadius = 40;
          const currentRadius = progress * maxRadius;
          const alpha = 1 - progress; // Fade out

          // Save context state
          recordingCtx.save();

          // Draw expanding ripple
          recordingCtx.beginPath();
          recordingCtx.arc(effect.x, effect.y, currentRadius, 0, Math.PI * 2);
          recordingCtx.strokeStyle = `rgba(244, 67, 54, ${alpha})`; // Red
          recordingCtx.lineWidth = 3;
          recordingCtx.stroke();

          // Draw outer ripple (slightly delayed)
          if (progress > 0.2) {
            const outerProgress = (progress - 0.2) / 0.8;
            const outerRadius = outerProgress * maxRadius * 1.5;
            const outerAlpha = (1 - outerProgress) * 0.5;
            recordingCtx.beginPath();
            recordingCtx.arc(effect.x, effect.y, outerRadius, 0, Math.PI * 2);
            recordingCtx.strokeStyle = `rgba(244, 67, 54, ${outerAlpha})`;
            recordingCtx.lineWidth = 2;
            recordingCtx.stroke();
          }

          // Draw center dot
          recordingCtx.beginPath();
          recordingCtx.arc(effect.x, effect.y, 6, 0, Math.PI * 2);
          recordingCtx.fillStyle = `rgba(244, 67, 54, ${alpha})`;
          recordingCtx.fill();

          // Restore context state
          recordingCtx.restore();

          return true;
        });

        // Request next frame to ensure continuous recording
        drawAnimationFrame = requestAnimationFrame(continuousDraw);
      }

      // Handle data available
      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          recordedChunks.push(event.data);
        }
      };

      // Handle recording stop
      mediaRecorder.onstop = () => {
        // Stop continuous drawing
        if (drawAnimationFrame) {
          cancelAnimationFrame(drawAnimationFrame);
          drawAnimationFrame = null;
        }

        // Clear click effects
        clickEffects = [];
        currentMousePos = null;

        // Stop and clear audio stream
        if (audioStream) {
          audioStream.getTracks().forEach((track) => track.stop());
          audioStream = null;
        }

        // Stop and clear camera stream
        if (cameraStream) {
          cameraStream.getTracks().forEach((track) => track.stop());
          cameraStream = null;
        }
        cameraVideo = null;

        // Hide camera preview
        const previewVideo = document.getElementById('camera-preview');
        if (previewVideo) {
          previewVideo.style.display = 'none';
          previewVideo.srcObject = null;
        }

        const blob = new Blob(recordedChunks, { type: 'video/webm' });
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `vnc-recording-${timestamp}.webm`;
        const url = URL.createObjectURL(blob);

        // Auto-download
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();

        setTimeout(() => {
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        }, 100);

        log(`Recording saved: ${filename}`);
        updateStatus('Recording saved', 'success');

        // Update container padding after stop
        updateContainerPadding();
      };

      // Start recording
      mediaRecorder.start();
      isRecording = true;
      isPaused = false;
      recordingStartTime = Date.now();
      totalPausedTime = 0;

      // Start continuous drawing
      continuousDraw();

      // Update container padding
      updateContainerPadding();

      // Update UI
      updateRecordingUI();

      // Reset time display
      const timeDisplay = document.getElementById('recording-time');
      if (timeDisplay) {
        timeDisplay.textContent = '00:00';
        log('Time display initialized');
      } else {
        log('WARNING: recording-time element not found!', 'error');
      }

      // Start timer
      updateRecordingTimer();
      recordingTimer = setInterval(updateRecordingTimer, 1000);

      log('Recording started (canvas capture mode)');
    } catch (error) {
      log(`Recording error: ${error.message}`, 'error');
      log(error.stack, 'error');
      updateStatus('Recording failed: ' + error.message, 'error');
    }
  }

  // Pause recording
  function pauseRecording() {
    if (mediaRecorder && isRecording && !isPaused) {
      mediaRecorder.pause();
      isPaused = true;
      pausedStartTime = Date.now();

      // Note: We don't stop continuousDrawing anymore - it keeps running
      // so it will be ready when we resume

      // Stop updating overlay (freeze the timestamp display)
      if (recordingAnimationFrame) {
        cancelAnimationFrame(recordingAnimationFrame);
        recordingAnimationFrame = null;
      }

      // Update UI
      updateRecordingUI();

      log('Recording paused');
    }
  }

  // Resume recording
  function resumeRecording() {
    if (mediaRecorder && isRecording && isPaused) {
      mediaRecorder.resume();
      isPaused = false;

      // Add paused time to total
      if (pausedStartTime) {
        totalPausedTime += Date.now() - pausedStartTime;
        pausedStartTime = null;
      }

      // Note: continuousDrawing is already running, no need to restart

      // Resume overlay animation
      drawRecordingTimestamp();

      // Update UI
      updateRecordingUI();

      log('Recording resumed');
    }
  }

  // Stop recording
  function stopRecording() {
    if (mediaRecorder && isRecording) {
      log('Stopping recording...');

      // If paused, resume first to properly finalize
      if (isPaused) {
        log('Resuming paused recording before stopping...');
        mediaRecorder.resume();
        isPaused = false;
        if (pausedStartTime) {
          totalPausedTime += Date.now() - pausedStartTime;
          pausedStartTime = null;
        }
      }

      // Stop the recorder
      mediaRecorder.stop();
      isRecording = false;
      isPaused = false;

      // Update UI to reset state
      const recordBtn = document.getElementById('btn-record-pause');
      const stopBtn = document.getElementById('btn-record-stop');
      const indicator = document.getElementById('recording-indicator');

      if (recordBtn) {
        recordBtn.textContent = '⏺ Record';
        recordBtn.classList.remove('recording');
        recordBtn.style.display = 'inline-flex';
      }

      if (stopBtn) {
        stopBtn.style.display = 'none';
      }

      if (indicator) {
        indicator.classList.remove('show');
        indicator.style.background = 'rgba(244, 67, 54, 0.95)';
      }

      // Reset timer display
      const timeDisplay = document.getElementById('recording-time');
      if (timeDisplay) {
        timeDisplay.textContent = '00:00';
      }

      // Stop timer
      if (recordingTimer) {
        clearInterval(recordingTimer);
        recordingTimer = null;
      }

      // Reset state variables
      recordingStartTime = null;
      pausedStartTime = null;
      totalPausedTime = 0;

      // Reset mute state
      isMuted = false;
      const muteBtn = document.getElementById('btn-mute');
      if (muteBtn) {
        muteBtn.textContent = '🔊 Mic';
        muteBtn.classList.remove('recording');
      }

      // Stop recording overlay
      stopRecordingOverlay();

      // Update container padding (remove recording padding)
      updateContainerPadding();

      log('Recording stopped and UI reset');
    }
  }

  // Update recording UI based on state
  function updateRecordingUI() {
    const recordBtn = document.getElementById('btn-record-pause');
    const stopBtn = document.getElementById('btn-record-stop');
    const indicator = document.getElementById('recording-indicator');

    if (!recordBtn || !stopBtn || !indicator) {
      log('Missing recording UI elements', 'warn');
      log(`recordBtn: ${!!recordBtn}, stopBtn: ${!!stopBtn}, indicator: ${!!indicator}`, 'warn');
      return;
    }

    if (!isRecording) {
      // Not recording
      recordBtn.textContent = '⏺ Record';
      recordBtn.classList.remove('recording');
      recordBtn.style.display = 'inline-flex';
      stopBtn.style.display = 'none';
      indicator.classList.remove('show');
      indicator.style.background = 'rgba(244, 67, 54, 0.95)';
      log('UI: Not recording state');
    } else if (isPaused) {
      // Paused
      recordBtn.textContent = '▶ Resume';
      recordBtn.classList.add('recording');
      recordBtn.style.display = 'inline-flex';
      stopBtn.style.display = 'inline-flex';
      indicator.classList.add('show');
      indicator.style.background = 'rgba(255, 152, 0, 0.95)'; // Orange
      log('UI: Paused state');
    } else {
      // Recording
      recordBtn.textContent = '⏸ Pause';
      recordBtn.classList.add('recording');
      recordBtn.style.display = 'inline-flex';
      stopBtn.style.display = 'inline-flex';
      indicator.classList.add('show');
      indicator.style.background = 'rgba(244, 67, 54, 0.95)'; // Red
      log('UI: Recording state');
    }

    // Force browser reflow
    if (indicator.classList.contains('show')) {
      indicator.offsetHeight; // Trigger reflow
    }
  }

  // Update recording timer display
  function updateRecordingTimer() {
    if (!recordingStartTime) return;

    let elapsed = Date.now() - recordingStartTime - totalPausedTime;

    // If currently paused, don't count the paused time
    if (isPaused && pausedStartTime) {
      elapsed -= Date.now() - pausedStartTime;
    }

    const seconds = Math.floor(elapsed / 1000);
    const minutes = Math.floor(seconds / 60)
      .toString()
      .padStart(2, '0');
    const secs = (seconds % 60).toString().padStart(2, '0');

    const timeDisplay = document.getElementById('recording-time');
    if (timeDisplay) {
      timeDisplay.textContent = `${minutes}:${secs}`;
    }
  }

  // Toggle dropdown menu
  function toggleDropdown(dropdownId, menuId) {
    const dropdown = document.getElementById(dropdownId);
    const menu = document.getElementById(menuId);

    if (dropdown && menu) {
      const isOpen = menu.classList.contains('show');

      // Close all other dropdowns first
      document.querySelectorAll('.dropdown-menu').forEach((m) => {
        m.classList.remove('show');
      });
      document.querySelectorAll('.dropdown').forEach((d) => {
        d.classList.remove('active');
      });

      // Toggle current dropdown
      if (!isOpen) {
        menu.classList.add('show');
        dropdown.classList.add('active');
        log(`Dropdown ${dropdownId} opened`);
      } else {
        log(`Dropdown ${dropdownId} closed`);
      }
    }
  }

  // Close dropdown when clicking outside
  function handleClickOutside(event) {
    const dropdowns = document.querySelectorAll('.dropdown');
    dropdowns.forEach((dropdown) => {
      const menu = dropdown.querySelector('.dropdown-menu');
      if (menu && menu.classList.contains('show')) {
        if (!dropdown.contains(event.target)) {
          menu.classList.remove('show');
          dropdown.classList.remove('active');
          log('Dropdown closed (clicked outside)');
        }
      }
    });
  }

  // Scale up
  function scaleUp() {
    if (rfb && isConnected) {
      scale = Math.min(scale + 0.1, 3.0);
      rfb.scaleViewport = false;
      rfb.scale = scale;
      if (typeof rfb.sendScaleConfig === 'function') {
        rfb.sendScaleConfig();
      }
      log(`Scale up to ${scale.toFixed(1)}x`);
    }
  }

  // Scale down
  function scaleDown() {
    if (rfb && isConnected) {
      scale = Math.max(scale - 0.1, 0.3);
      rfb.scaleViewport = false;
      rfb.scale = scale;
      if (typeof rfb.sendScaleConfig === 'function') {
        rfb.sendScaleConfig();
      }
      log(`Scale down to ${scale.toFixed(1)}x`);
    }
  }

  // Scale to fit
  function scaleToFit() {
    if (rfb && isConnected) {
      scale = 1.0;
      rfb.scaleViewport = true;
      if (typeof rfb.sendScaleConfig === 'function') {
        rfb.sendScaleConfig();
      }
      log('Scale to fit viewport');
    }
  }

  // Connect/Reconnect
  function connect() {
    if (rfb) {
      // Check if already connected
      if (rfb._rfb_connection_state === 'connected') {
        log('Already connected');
        return;
      }

      // If disconnected, we need to recreate the RFB object
      log('Reconnecting...');

      // Clean up old RFB object
      try {
        if (rfb._rfb_connection_state !== 'disconnected') {
          rfb.disconnect();
        }
      } catch (e) {
        log(`Error during disconnect: ${e.message}`, 'warn');
      }

      // Remove old RAF (resize animation frame) if any
      container.innerHTML = '';

      // Create new RFB instance
      rfb = new RFB(container, wsUrl, {
        resizeSession: false,
        scaleViewport: true,
      });

      // Re-attach all event listeners
      attachRfbEventListeners(rfb);

      // Connect
      rfb.connect();

      log('RFB reconnection initiated');
    } else {
      log('RFB object not initialized, cannot connect', 'error');
    }
  }

  // Disconnect
  function disconnect() {
    if (rfb && isConnected) {
      log('Disconnecting...');
      rfb.disconnect();
      isConnected = false;
      updateConnectionStatus('Disconnected', '#ff9800');
    }
  }

  // Update connection status display
  function updateConnectionStatus(status, color = '#fff') {
    connectionStatus.textContent = `● ${status}`;
    connectionStatus.style.color = color;
  }

  // Open clipboard modal
  function openClipboard() {
    clipboardModal.style.display = 'block';
    modalOverlay.style.display = 'block';
    clipboardText.value = '';
    clipboardText.focus();
    log('Clipboard modal opened');
  }

  // Close clipboard modal
  function closeClipboard() {
    clipboardModal.style.display = 'none';
    modalOverlay.style.display = 'none';
    log('Clipboard modal closed');
  }

  // Send clipboard text to remote
  function sendClipboard() {
    const text = clipboardText.value;
    if (rfb && isConnected && text) {
      rfb.clipboardPasteFrom(text);
      log(`Sent clipboard text (${text.length} chars)`);
      closeClipboard();
      updateStatus('Clipboard sent', 'success');
    }
  }

  // Setup modifier checkbox interactions
  function setupModifierCheckboxes() {
    const ctrlAltCheckbox = document.getElementById('mod-ctrl-alt');
    const ctrlCheckbox = document.getElementById('mod-ctrl');
    const altCheckbox = document.getElementById('mod-alt');
    const shiftCheckbox = document.getElementById('mod-shift');

    // Ctrl+Alt checkbox logic
    if (ctrlAltCheckbox) {
      ctrlAltCheckbox.addEventListener('change', () => {
        if (ctrlAltCheckbox.checked) {
          // Uncheck individual Ctrl and Alt
          ctrlCheckbox.checked = false;
          altCheckbox.checked = false;
          updateCheckboxVisual(ctrlCheckbox);
          updateCheckboxVisual(altCheckbox);
        }
        updateCheckboxVisual(ctrlAltCheckbox);
      });
    }

    // Individual Ctrl checkbox
    if (ctrlCheckbox) {
      ctrlCheckbox.addEventListener('change', () => {
        if (ctrlCheckbox.checked && ctrlAltCheckbox.checked) {
          ctrlAltCheckbox.checked = false;
          updateCheckboxVisual(ctrlAltCheckbox);
        }
        updateCheckboxVisual(ctrlCheckbox);
      });
    }

    // Individual Alt checkbox
    if (altCheckbox) {
      altCheckbox.addEventListener('change', () => {
        if (altCheckbox.checked && ctrlAltCheckbox.checked) {
          ctrlAltCheckbox.checked = false;
          updateCheckboxVisual(ctrlAltCheckbox);
        }
        updateCheckboxVisual(altCheckbox);
      });
    }

    // Shift checkbox
    if (shiftCheckbox) {
      shiftCheckbox.addEventListener('change', () => {
        updateCheckboxVisual(shiftCheckbox);
      });
    }

    log('Modifier checkbox interactions setup');
  }

  // Update checkbox visual state
  function updateCheckboxVisual(checkbox) {
    const parent = checkbox.closest('.modifier-checkbox');
    if (checkbox.checked) {
      parent.classList.add('active');
    } else {
      parent.classList.remove('active');
    }
  }

  // Setup toolbar event listeners
  function setupToolbarListeners() {
    // Toolbar toggle
    toolbarToggle.addEventListener('click', toggleToolbar);

    // Connection controls
    document.getElementById('btn-fullscreen').addEventListener('click', toggleFullscreen);
    document.getElementById('btn-connect').addEventListener('click', connect);
    document.getElementById('btn-disconnect').addEventListener('click', disconnect);

    // Dropdown toggle
    document.getElementById('send-keys-toggle').addEventListener('click', (e) => {
      e.stopPropagation();
      toggleDropdown('send-keys-dropdown', 'send-keys-menu');
    });

    // Prevent dropdown from closing when clicking inside
    document.getElementById('send-keys-menu').addEventListener('click', (e) => {
      e.stopPropagation();
    });

    // Setup modifier checkbox interactions
    setupModifierCheckboxes();

    // Function Keys (F1-F12)
    for (let i = 1; i <= 12; i++) {
      const btn = document.getElementById(`btn-f${i}`);
      if (btn) {
        btn.addEventListener('click', () => sendKeyCombination(i));
      }
    }

    // Quick Actions
    document.getElementById('btn-ctrlaltdel').addEventListener('click', sendCtrlAltDel);
    document.getElementById('btn-ctrlaltbs').addEventListener('click', sendCtrlAltBackspace);
    document.getElementById('btn-tab').addEventListener('click', sendTab);
    document.getElementById('btn-esc').addEventListener('click', sendEsc);
    document.getElementById('btn-print').addEventListener('click', sendPrintScreen);

    // Scale controls
    document.getElementById('btn-scale-up').addEventListener('click', scaleUp);
    document.getElementById('btn-scale-down').addEventListener('click', scaleDown);
    document.getElementById('btn-scale-fit').addEventListener('click', scaleToFit);

    // Screen capture
    document.getElementById('btn-screenshot').addEventListener('click', takeScreenshot);
    document.getElementById('btn-mute').addEventListener('click', toggleMute);
    document.getElementById('btn-record-pause').addEventListener('click', toggleRecording);
    document.getElementById('btn-record-stop').addEventListener('click', stopRecording);

    // Clipboard
    document.getElementById('btn-clipboard').addEventListener('click', openClipboard);
    document.getElementById('btn-clipboard-send').addEventListener('click', sendClipboard);
    document.getElementById('btn-clipboard-cancel').addEventListener('click', closeClipboard);
    modalOverlay.addEventListener('click', closeClipboard);

    // Close dropdowns when clicking outside
    document.addEventListener('click', handleClickOutside);

    log('Toolbar event listeners setup');
  }

  // Initialize toolbar
  setupToolbarListeners();

  // Connection timeout handler
  if (autoconnect) {
    connectionTimeout = setTimeout(() => {
      if (rfb && rfb._rfb_connection_state !== 'connected') {
        showError(
          'Connection Timeout',
          'Could not connect to the VNC server. Please verify:\n\n' +
            '• The node is started\n' +
            '• The console type is set to VNC\n' +
            '• Your network connection is stable\n' +
            '• No firewall is blocking the connection'
        );
        if (rfb) {
          rfb.disconnect();
        }
      }
    }, 15000); // 15 second timeout
  }

  // Initialize noVNC
  try {
    log('Initializing noVNC RFB connection...');
    log(`WebSocket URL: ${wsUrl.replace(/ticket=[^&]+/, 'ticket=***')}`); // Hide token in logs

    // Create RFB instance
    rfb = new RFB(container, wsUrl, {
      resizeSession: false, // Don't resize the remote session
      scaleViewport: true, // Scale the display to fit the container
      // Additional noVNC options can be added here
    });

    // Attach event listeners using the extracted function
    attachRfbEventListeners(rfb);

    // Focus management
    container.addEventListener('click', () => {
      if (rfb) {
        rfb.focus();
        log('VNC canvas focused');
      }
    });

    // Mouse click tracking for recording effects
    // Use document-level listener to capture all clicks, even if noVNC intercepts them
    document.addEventListener(
      'mousedown',
      (e) => {
        log(`Document MouseDown detected: recording=${isRecording}, paused=${isPaused}`);

        if (!isRecording || isPaused) {
          return;
        }

        // Check if click is within VNC container
        const containerRect = container.getBoundingClientRect();
        if (
          e.clientX < containerRect.left ||
          e.clientX > containerRect.right ||
          e.clientY < containerRect.top ||
          e.clientY > containerRect.bottom
        ) {
          log('Click outside VNC container, ignoring');
          return;
        }

        log('Click inside VNC container, processing...');

        // Get VNC canvas to calculate coordinates
        let vncCanvas = null;
        if (typeof rfb.get_canvas === 'function') {
          vncCanvas = rfb.get_canvas();
        } else if (rfb.canvas) {
          vncCanvas = rfb.canvas;
        } else {
          vncCanvas = container.querySelector('canvas');
        }

        if (!vncCanvas) {
          log('Cannot find VNC canvas for click tracking');
          return;
        }

        log(`VNC Canvas: ${vncCanvas.width}x${vncCanvas.height}`);

        // Get canvas position and dimensions
        const rect = vncCanvas.getBoundingClientRect();
        log(`Canvas rect: left=${rect.left}, top=${rect.top}, width=${rect.width}, height=${rect.height}`);
        log(`Mouse client: x=${e.clientX}, y=${e.clientY}`);

        // Calculate click position relative to canvas
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Scale coordinates to match canvas internal resolution
        const scaleX = vncCanvas.width / rect.width;
        const scaleY = vncCanvas.height / rect.height;
        const canvasX = x * scaleX;
        const canvasY = y * scaleY;

        log(
          `Click position: relative=(${x.toFixed(0)}, ${y.toFixed(0)}), scaled=(${canvasX.toFixed(
            0
          )}, ${canvasY.toFixed(0)})`
        );

        // Add click effect
        const effect = {
          x: canvasX,
          y: canvasY,
          startTime: Date.now(),
        };
        clickEffects.push(effect);

        log(`✓ Click effect added! Total effects: ${clickEffects.length}`);
      },
      true
    ); // Use capture phase to catch events before noVNC

    // Track mouse position for cursor rendering in recording
    document.addEventListener(
      'mousemove',
      (e) => {
        // Only track when recording
        if (!isRecording) {
          currentMousePos = null;
          return;
        }

        // Get VNC canvas
        let vncCanvas = null;
        if (typeof rfb.get_canvas === 'function') {
          vncCanvas = rfb.get_canvas();
        } else if (rfb.canvas) {
          vncCanvas = rfb.canvas;
        } else {
          vncCanvas = container.querySelector('canvas');
        }

        if (!vncCanvas) {
          return;
        }

        // Get canvas position and dimensions
        const rect = vncCanvas.getBoundingClientRect();

        // Check if mouse is within canvas
        if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
          // Calculate position relative to canvas
          const x = e.clientX - rect.left;
          const y = e.clientY - rect.top;

          // Scale to canvas resolution
          const scaleX = vncCanvas.width / rect.width;
          const scaleY = vncCanvas.height / rect.height;
          currentMousePos = {
            x: x * scaleX,
            y: y * scaleY,
          };
        } else {
          currentMousePos = null;
        }
      },
      true
    );

    // Keyboard shortcuts (as alternative to toolbar buttons)
    document.addEventListener('keydown', (e) => {
      // Ctrl+Alt+Del
      if (e.ctrlKey && e.altKey && e.key === 'Delete') {
        e.preventDefault();
        sendCtrlAltDel();
      }

      // Ctrl+Alt+Backspace
      if (e.ctrlKey && e.altKey && e.key === 'Backspace') {
        e.preventDefault();
        sendCtrlAltBackspace();
      }

      // Tab handling for browser shortcuts
      if (e.ctrlKey && e.shiftKey && e.key === 'Tab') {
        log('Ctrl+Shift+Tab pressed (allowing browser default)');
      }

      // F5 and F11 - allow browser defaults for refresh and fullscreen
      if (e.key === 'F5' || e.key === 'F11') {
        log(`Function key ${e.key} pressed (allowing browser default)`);
        return;
      }

      // Prevent some browser shortcuts that interfere with VNC
      if (e.ctrlKey && e.key === 's') {
        e.preventDefault(); // Prevent save
        log('Prevented Ctrl+S (save)');
      }

      if (e.ctrlKey && e.key === 'p') {
        e.preventDefault(); // Prevent print
        log('Prevented Ctrl+P (print)');
      }

      // F11 is handled by browser for fullscreen, no need to prevent
    });

    // Window resize handling
    window.addEventListener('resize', () => {
      if (rfb && rfb._rfb_connection_state === 'connected') {
        // Re-apply scaling after resize
        rfb.scaleViewport = true;
        if (typeof rfb.sendScaleConfig === 'function') {
          rfb.sendScaleConfig();
        }
        log('Window resized, VNC display rescaled');
      }
    });

    // Cleanup on page unload
    window.addEventListener('beforeunload', (e) => {
      if (rfb) {
        log('Page unloading, disconnecting VNC...');
        rfb.disconnect();
      }
    });

    // Handle visibility change (pause/resume)
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        log('Page hidden (VNC connection paused)');
      } else {
        log('Page visible (VNC connection active)');
        if (rfb) {
          rfb.focus();
        }
      }
    });

    log('noVNC RFB initialized successfully');
  } catch (error) {
    clearTimeout(connectionTimeout);
    hideLoading();
    showError(
      'Initialization Error',
      `Failed to initialize VNC console:\n\n${error.message}\n\n` +
        'Please ensure you are using a modern browser with WebSocket support.'
    );
    log(`Initialization error: ${error.message}`, 'error');
    log(error.stack, 'error');
  }
})();
