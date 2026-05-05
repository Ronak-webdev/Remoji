import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactDOM from 'react-dom';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, Download, X, Settings, Sparkles, ArrowLeft, Sun, Moon } from 'lucide-react';
import styled from 'styled-components';
import Loader from './Loader';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5999';
const POLL_INTERVAL = 1500;

// ========== FULLSCREEN ZOOM VIEWER ==========
const ZoomViewer = ({ imageUrl, onClose, onDownload }) => {
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef(null);
  const imageRef = useRef(null);

  // Clamp position to keep image visible
  const clampPosition = useCallback((newPos, currentScale) => {
    if (!containerRef.current) return newPos;

    const rect = containerRef.current.getBoundingClientRect();
    const scaledWidth = rect.width * currentScale;
    const scaledHeight = rect.height * currentScale;

    const maxX = Math.max(0, (scaledWidth - rect.width) / 2);
    const maxY = Math.max(0, (scaledHeight - rect.height) / 2);

    return {
      x: Math.max(-maxX, Math.min(maxX, newPos.x)),
      y: Math.max(-maxY, Math.min(maxY, newPos.y))
    };
  }, []);

  // Handle mouse wheel zoom (centered on cursor)
  const handleWheel = useCallback((e) => {
    e.preventDefault();
    if (!containerRef.current) return;

    const delta = e.deltaY > 0 ? 0.92 : 1.08; // smoother zoom steps
    const rect = containerRef.current.getBoundingClientRect();

    // Mouse position relative to container center
    const mouseX = e.clientX - rect.left - rect.width / 2;
    const mouseY = e.clientY - rect.top - rect.height / 2;

    setScale(prevScale => {
      const newScale = Math.max(0.5, Math.min(25, prevScale * delta));

      // Calculate new position to keep mouse point fixed
      const scaleChange = newScale / prevScale;
      const newPos = {
        x: mouseX - (mouseX - position.x) * scaleChange,
        y: mouseY - (mouseY - position.y) * scaleChange
      };

      const clampedPos = clampPosition(newPos, newScale);
      
      setPosition(clampedPos);
      return newScale;
    });
  }, [position, clampPosition]);

  // Drag handlers
  const handleMouseDown = (e) => {
    if (scale <= 1) return;
    e.stopPropagation();
    setDragging(true);
    setDragStart({
      x: e.clientX - position.x,
      y: e.clientY - position.y
    });
  };

  const handleMouseMove = useCallback((e) => {
    if (!dragging) return;

    const newPos = {
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y
    };

    const clampedPos = clampPosition(newPos, scale);
    setPosition(clampedPos);
  }, [dragging, dragStart, scale, clampPosition]);

  const handleMouseUp = () => {
    setDragging(false);
  };

  // Double click to reset
  const handleDoubleClick = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  // Keyboard support
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === '+' || e.key === '=') {
        setScale(s => Math.min(25, s * 1.2));
      }
      if (e.key === '-') {
        setScale(s => Math.max(0.5, s / 1.2));
      }
      if (e.key === '0') {
        setScale(1);
        setPosition({ x: 0, y: 0 });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Event listeners
  useEffect(() => {
    window.addEventListener('wheel', handleWheel, { passive: false });
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('wheel', handleWheel);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleWheel, handleMouseMove]);

  return ReactDOM.createPortal(
    <motion.div 
      className="fullscreen-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <button
        className="back-expanded"
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
      >
        <ArrowLeft size={18} />
        Back
      </button>

      <button
        className="download-expanded-btn"
        onClick={(e) => {
          e.stopPropagation();
          onDownload();
        }}
        title="Download Masterpiece"
      >
        <Download size={22} />
      </button>

      <div 
        className="expanded-stage"
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onDoubleClick={handleDoubleClick}
        style={{ 
          cursor: scale > 1 ? (dragging ? 'grabbing' : 'grab') : 'default' 
        }}
      >
        <div
          className="zoom-target-wrapper"
          style={{
            transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
            transformOrigin: 'center center',
            transition: dragging ? 'none' : 'transform 0.12s cubic-bezier(0.23, 1, 0.32, 1)'
          }}
        >
          <img
            ref={imageRef}
            src={imageUrl}
            alt="Full Resolution"
            className="zoom-image-core"
            draggable={false}
          />
        </div>

        {/* Zoom Level Indicator */}
        <div className="zoom-indicator">
          {Math.round(scale * 100)}%
        </div>
      </div>

      {/* Close Button */}
      <button className="close-expanded" onClick={onClose}>
        <X size={36} />
      </button>
    </motion.div>,
    document.body
  );
};

const StyledUploadWrapper = styled.div`
  .container {
    --transition: 350ms;
    --folder-W: 120px;
    --folder-H: 80px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    padding: 10px;
    background: linear-gradient(135deg, #f162ba, #ed45ae);
    border-radius: 15px;
    box-shadow: 0 15px 30px rgba(147, 51, 234, 0.4), 0 5px 15px rgba(237, 69, 174, 0.3);
    height: calc(var(--folder-H) * 1.7);
    position: relative;
    width: 100%;
    max-width: 200px;
    margin: 20px auto;
  }

  .folder {
    position: absolute;
    top: -20px;
    left: calc(50% - 60px);
    animation: float 2.5s infinite ease-in-out;
    transition: transform var(--transition) ease;
  }

  .folder:hover {
    transform: scale(1.05);
  }

  .folder .front-side,
  .folder .back-side {
    position: absolute;
    transition: transform var(--transition);
    transform-origin: bottom center;
  }

  .folder .back-side::before,
  .folder .back-side::after {
    content: "";
    display: block;
    background-color: white;
    opacity: 0.5;
    z-index: 0;
    width: var(--folder-W);
    height: var(--folder-H);
    position: absolute;
    transform-origin: bottom center;
    border-radius: 15px;
    transition: transform 350ms;
    z-index: 0;
  }

  .container:hover .back-side::before {
    transform: rotateX(-5deg) skewX(5deg);
  }
  .container:hover .back-side::after {
    transform: rotateX(-10deg) skewX(10deg);
  }

  .folder .front-side {
    z-index: 2;
  }

  .container:hover .front-side {
    transform: rotateX(-40deg) skewX(15deg);
  }

  .folder .tip {
    background: linear-gradient(135deg, #ff9a56, #ff6f56);
    width: 80px;
    height: 20px;
    border-radius: 12px 12px 0 0;
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
    position: absolute;
    top: -10px;
    z-index: 2;
  }

  .folder .cover {
    background: linear-gradient(135deg, #ffe563, #ffc663);
    width: var(--folder-W);
    height: var(--folder-H);
    box-shadow: 0 15px 30px rgba(0, 0, 0, 0.3);
    border-radius: 10px;
  }

  .custom-file-upload {
    font-size: 1.1em;
    color: #ffffff;
    text-align: center;
    background: rgba(255, 255, 255, 0.2);
    border: none;
    border-radius: 10px;
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
    cursor: pointer;
    transition: background var(--transition) ease;
    display: inline-block;
    width: 100%;
    padding: 10px 35px;
    position: relative;
    z-index: 5;
  }

  .custom-file-upload:hover {
    background: rgba(255, 255, 255, 0.4);
  }

  .custom-file-upload input[type="file"] {
    display: none;
  }

  @keyframes float {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-20px); }
    100% { transform: translateY(0px); }
  }

  @media (max-width: 600px) {
    .container {
      --folder-W: 90px;
      --folder-H: 60px;
      height: calc(var(--folder-H) * 1.8);
      max-width: 160px;
    }
    .folder {
      left: calc(50% - 45px);
    }
    .tip {
      width: 60px !important;
      height: 15px !important;
    }
    .custom-file-upload {
      font-size: 0.9em;
      padding: 8px 20px;
    }
  }
`;

const FolderUpload = ({ onChange }) => {
  return (
    <StyledUploadWrapper>
      <div className="container">
        <div className="folder">
          <div className="front-side">
            <div className="tip" />
            <div className="cover" />
          </div>
          <div className="back-side cover" />
        </div>
        <label className="custom-file-upload">
          <input className="title" type="file" onChange={onChange} accept="image/*" />
          Upload Image
        </label>
      </div>
    </StyledUploadWrapper>
  );
};

// ========== SETTINGS PANEL ==========
const SettingsPanel = ({ quality, emojiSize, onQualityChange, onEmojiSizeChange, onClose, theme, onThemeToggle }) => {
  const [contrast, setContrast] = useState(1.1);
  const [saturation, setSaturation] = useState(1);

  return (
    <>
      {/* Backdrop - closes settings on click */}
      <motion.div 
        className="settings-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div 
        className="settings-sidebar"
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'tween', ease: 'circOut' }}
      >
        <div className="sidebar-header">
          <h3>⚙️ Optimization</h3>
          <div className="header-controls">
            <button 
              className="theme-toggle-settings"
              onClick={onThemeToggle}
              title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
            >
              {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
            </button>
            <button className="close-btn" onClick={onClose}>
              <X size={24} />
            </button>
          </div>
        </div>

        <div className="controls-grid">
          {/* Quality Control */}
          <div className="control-group">
            <label>Fidelity: {quality}</label>
            <div className="slider-container">
              <input
                type="range"
                min="1"
                max="10"
                value={quality}
                onChange={(e) => onQualityChange(parseInt(e.target.value))}
                className="slider"
                style={{
                  background: `linear-gradient(to right, var(--primary) 0%, var(--primary) ${((quality - 1) / 9) * 100}%, var(--glass-border) ${((quality - 1) / 9) * 100}%, var(--glass-border) 100%)`
                }}
              />
            </div>
            <small>1 = High Detail | 10 = Extreme Masterpiece</small>
          </div>

          {/* Emoji Size Control */}
          <div className="control-group">
            <label>Scale: {emojiSize}px</label>
            <div className="slider-container">
              <input
                type="range"
                min="8"
                max="32"
                value={emojiSize}
                onChange={(e) => onEmojiSizeChange(parseInt(e.target.value))}
                className="slider"
                style={{
                  background: `linear-gradient(to right, var(--primary) 0%, var(--primary) ${((emojiSize - 8) / 24) * 100}%, var(--glass-border) ${((emojiSize - 8) / 24) * 100}%, var(--glass-border) 100%)`
                }}
              />
            </div>
            <small>8px = Small | 32px = Large</small>
          </div>

          {/* Contrast Control */}
          <div className="control-group">
            <label>Contrast: {contrast.toFixed(1)}x</label>
            <div className="slider-container">
              <input
                type="range"
                min="0.5"
                max="2"
                step="0.1"
                value={contrast}
                onChange={(e) => setContrast(parseFloat(e.target.value))}
                className="slider"
                style={{
                  background: `linear-gradient(to right, var(--primary) 0%, var(--primary) ${((contrast - 0.5) / 1.5) * 100}%, var(--glass-border) ${((contrast - 0.5) / 1.5) * 100}%, var(--glass-border) 100%)`
                }}
              />
            </div>
            <small>0.5x = Low | 2x = High</small>
          </div>

          {/* Saturation Control */}
          <div className="control-group">
            <label>Saturation: {saturation.toFixed(1)}x</label>
            <div className="slider-container">
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={saturation}
                onChange={(e) => setSaturation(parseFloat(e.target.value))}
                className="slider"
                style={{
                  background: `linear-gradient(to right, var(--primary) 0%, var(--primary) ${(saturation / 2) * 100}%, var(--glass-border) ${(saturation / 2) * 100}%, var(--glass-border) 100%)`
                }}
              />
            </div>
            <small>0 = B&W | 2x = Vivid</small>
          </div>
        </div>

        <div className="settings-footer">
          <Sparkles size={18} />
          <p>Adjust before processing for best results</p>
        </div>
      </motion.div>
    </>
  );
};

// ========== PREVIEW CARD COMPONENT ==========
const PreviewCard = ({ isLoading, imageSrc, label, onClick, isInput = false, onFileDrop }) => {
  const [dragOver, setDragOver] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!dragOver) setDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    if (onFileDrop) onFileDrop(e);
  };

  return (
    <motion.div
      className="preview-card"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, y: -100, transition: { duration: 0.4 } }}
      onClick={onClick}
    >
      {isLoading ? (
        <div className="loader-wrapper large-loader">
          <Loader />
          <p style={{ color: '#ffaa00', fontWeight: 800, marginTop: '2rem' }}>
            GENESIS IN PROGRESS...
          </p>
        </div>
      ) : imageSrc ? (
        <div 
          className={`img-wrapper ${dragOver ? 'drag-over' : ''}`}
          onDragOver={isInput ? handleDragOver : undefined}
          onDragEnter={isInput ? handleDragOver : undefined}
          onDragLeave={isInput ? handleDragLeave : undefined}
          onDrop={isInput ? handleDrop : undefined}
        >
          <img src={imageSrc} alt={label} className="preview-img" />
          <div className="label">{label}</div>
        </div>
      ) : isInput ? (
        <div
          className={`upload-placeholder ${dragOver ? 'drag-over' : ''}`}
          onDragOver={handleDragOver}
          onDragEnter={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <FolderUpload onChange={onFileDrop} />
          <p style={{ marginTop: '0.5rem', fontWeight: 500, fontSize: '0.9rem' }}>
            or drag an image here
          </p>
          <small style={{ color: 'var(--text-dim)', marginTop: '0.2rem' }}>
            PNG / JPG / WEBP — up to 10MB
          </small>
        </div>
      ) : (
        <div className="upload-placeholder">
          <div className="upload-icon-glow">
            <Upload size={64} color="var(--primary)" />
          </div>
          <p style={{ marginTop: '1rem', fontWeight: 700 }}>Waiting...</p>
        </div>
      )}
    </motion.div>
  );
};

// ========== MAIN COMPONENT ==========
const EmojiMosaic = () => {
  // State Management
  const [theme, setTheme] = useState('light');
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [outputUrl, setOutputUrl] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [quality, setQuality] = useState(3);
  const [emojiSize, setEmojiSize] = useState(12);
  const [error, setError] = useState(null);
  const [contrast, setContrast] = useState(1.1);
  const [saturation, setSaturation] = useState(1);
  const [exportFormat, setExportFormat] = useState('png');
  const [exportQuality, setExportQuality] = useState('original');
  const [showDownloadPanel, setShowDownloadPanel] = useState(false);

  // Theme Sync
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(prev => prev === 'light' ? 'dark' : 'light');

  // Refs
  const fileInputRef = useRef(null);

  // Lock body scroll when expanded
  useEffect(() => {
    document.body.style.overflow = isExpanded ? 'hidden' : 'auto';
    return () => {
      document.body.style.overflow = 'auto';
    };
  }, [isExpanded]);

  // File Selection Handler
  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setOutputUrl(null);
    setTaskId(null);
    setIsExpanded(false);
    setError(null);
  };

  // Drag/drop file handler
  const handleFileDrop = (e) => {
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setOutputUrl(null);
    setTaskId(null);
    setIsExpanded(false);
    setError(null);
  };

  // Upload and Process Handler
  const handleProcess = async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('image', selectedFile);
    formData.append('quality', quality);
    formData.append('emoji_size', emojiSize);

    try {
      // Upload image
      const uploadRes = await axios.post(`${API_BASE_URL}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      const taskId = uploadRes.data.id;
      setTaskId(taskId);

      // Poll for completion
      const pollStatus = async () => {
        try {
          const statusRes = await axios.get(`${API_BASE_URL}/status/${taskId}`);
          const { status, output_url } = statusRes.data;

          if (status === 'completed') {
            setOutputUrl(`${API_BASE_URL}${output_url}?t=${Date.now()}`);
            setIsLoading(false);
          } else if (status.startsWith('error')) {
            throw new Error(status);
          } else {
            setTimeout(pollStatus, POLL_INTERVAL);
          }
        } catch (err) {
          setError(err.message);
          setIsLoading(false);
        }
      };

      pollStatus();
    } catch (err) {
      console.error('Process error:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Check backend connection';
      setError(`⚠️ ${errorMsg}`);
      setIsLoading(false);
    }
  };

  // Download Handler
  const handleDownload = async () => {
    if (!taskId) return;
    try {
      const response = await axios.get(
        `${API_BASE_URL}/export/${taskId}?format=${exportFormat}&quality_mode=${exportQuality}`,
        { responseType: 'blob' }
      );

      const blobUrl = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = `emoji-masterpiece-${exportQuality}.${exportFormat}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      setError('Export failed. Try again.');
    }
  };

  // ========== LEFT SLIDE-OUT DOWNLOAD PANEL ==========
  const SlideOutDownload = ({ open, onClose }) => {
    return (
      <>
        <motion.div
          className="slide-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        />

        <motion.div
          className="slide-download-panel"
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'tween', ease: 'circOut' }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="slide-header">
            <h3>Download</h3>
            <button className="close-btn" onClick={onClose}><X size={18} /></button>
          </div>

          <div className="slide-body">
            <div className="export-option-group">
              <button
                className={`export-chip ${exportQuality === 'low' ? 'active' : ''}`}
                onClick={() => setExportQuality('low')}
              >
                Low Quality
              </button>
              <button
                className={`export-chip ${exportQuality === 'original' ? 'active' : ''}`}
                onClick={() => setExportQuality('original')}
              >
                Original Quality
              </button>
            </div>

            <div className="export-option-grid">
              {['png', 'jpg', 'webp'].map((format) => (
                <button
                  key={format}
                  className={`export-format ${exportFormat === format ? 'active' : ''}`}
                  onClick={() => setExportFormat(format)}
                >
                  {format.toUpperCase()}
                </button>
              ))}
            </div>

            <div style={{ marginTop: '1rem' }}>
              <button
                className="export-download-btn"
                onClick={async () => {
                  await handleDownload();
                  onClose();
                }}
              >
                <Download size={16} />
                Download {exportFormat.toUpperCase()}
              </button>
            </div>
          </div>
        </motion.div>
      </>
    );
  };

  return (
    <div className={`app-container ${previewUrl ? 'has-image' : ''}`}>
      {/* Header */}
      <AnimatePresence>
        {!previewUrl && !isExpanded && (
          <motion.header
            initial={{ opacity: 0, y: 0 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -100 }}
            transition={{ duration: 0.5, ease: "circOut" }}
          >
            <motion.div
              initial={{ y: -20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.1 }}
            >
              <h1>✨ Emoji Masterpiece</h1>
              <p>The Ultimate High-Fidelity Art Engine</p>
            </motion.div>
          </motion.header>
        )}
      </AnimatePresence>

      {/* Settings Toggle */}
      <div className="floating-controls">
        {!isExpanded && (
          <button
            className="settings-toggle"
            onClick={() => setShowSettings(!showSettings)}
            title="Settings"
          >
            <Settings size={28} />
          </button>
        )}

        {/* Download toggle visible in both normal and expanded views */}
        {outputUrl && !isLoading && (
          <button
            className="download-toggle"
            onClick={(e) => {
              e.stopPropagation();
              setShowDownloadPanel(true);
            }}
            title="Download options"
          >
            <Download size={20} />
          </button>
        )}

        {/* export-panel removed - using slide-out download panel instead */}
      </div>

      {/* Slide-out Download Panel */}
      <AnimatePresence>
        {showDownloadPanel && (
          <SlideOutDownload open={showDownloadPanel} onClose={() => setShowDownloadPanel(false)} />
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main className="main-stage">
        <div className={`preview-container ${outputUrl || isLoading ? 'split-view' : 'centered-view'} ${!previewUrl ? 'hero-state' : ''}`}>
          <AnimatePresence mode="wait">
            {!isExpanded && (
              <PreviewCard
                key={previewUrl ? 'input-image' : 'input-placeholder'}
                isInput
                imageSrc={previewUrl}
                label="Source Photo"
                onClick={() => fileInputRef.current?.click()}
                onFileDrop={handleFileDrop}
              />
            )}
          </AnimatePresence>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          <AnimatePresence mode="wait">
            {(outputUrl || isLoading) && !isExpanded && (
              <PreviewCard
                key={isLoading ? 'loading' : 'output'}
                isLoading={isLoading}
                imageSrc={outputUrl}
                label="View Masterpiece"
                onClick={() => outputUrl && setIsExpanded(true)}
              />
            )}
          </AnimatePresence>
        </div>

        {/* Action Buttons */}
        {!isExpanded && (outputUrl || previewUrl) && (
          <motion.div
            className="action-buttons"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
          >
            {previewUrl && !outputUrl && (
              <button className="btn btn-primary" onClick={handleProcess} disabled={isLoading}>
                <Sparkles size={20} />
                {isLoading ? 'Processing...' : 'Create Masterpiece'}
              </button>
            )}
            {outputUrl && (
              <>
                <button className="btn btn-primary" onClick={handleProcess} disabled={isLoading}>
                  <Sparkles size={20} />
                  {isLoading ? 'Processing...' : 'Regenerate'}
                </button>
              </>
            )}
          </motion.div>
        )}

        {/* Error Message */}
        <AnimatePresence>
          {error && (
            <motion.div
              className="error-message"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              ⚠️ {error}
              <button onClick={() => setError(null)}>×</button>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Zoom Viewer */}
      <AnimatePresence>
        {isExpanded && outputUrl && (
          <ZoomViewer 
            imageUrl={outputUrl} 
            onClose={() => setIsExpanded(false)} 
            onDownload={handleDownload}
          />
        )}
      </AnimatePresence>

      {/* Settings Panel */}
      <AnimatePresence>
        {showSettings && !isExpanded && (
          <SettingsPanel
            quality={quality}
            emojiSize={emojiSize}
            onQualityChange={setQuality}
            onEmojiSizeChange={setEmojiSize}
            onClose={() => setShowSettings(false)}
            theme={theme}
            onThemeToggle={toggleTheme}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default EmojiMosaic;
