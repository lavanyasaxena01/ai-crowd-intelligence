import { useRef, useState } from 'react'
import { analyzeVisionImage, fetchVisionStatus } from '../api/visionApi'

export default function VisionIntelligence({ online }) {
  const inputRef = useRef(null)
  const [preview, setPreview] = useState(null)
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [status, setStatus] = useState(null)

  async function refreshStatus() {
    try {
      const s = await fetchVisionStatus()
      setStatus(s)
    } catch (err) {
      setStatus({ configured: false, message: err.message })
    }
  }

  function onPick(e) {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setResult(null)
    setError('')
    const url = URL.createObjectURL(f)
    setPreview(url)
    refreshStatus()
  }

  async function onAnalyze() {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const data = await analyzeVisionImage(file)
      setResult(data)
    } catch (err) {
      setError(err.message || 'Vision analysis failed')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="glass-panel vision-panel" aria-label="Hugging Face vision intelligence">
      <div className="panel-head">
        <h2>Hugging Face Vision Intelligence</h2>
        <button type="button" className="ghost-btn" onClick={refreshStatus} disabled={!online}>
          Check HF Status
        </button>
      </div>
      <p className="panel-sub">
        Upload a venue/CCTV still. Detection runs on Hugging Face Hub
        ({status?.model || 'facebook/detr-resnet-50'}) — no fabricated counts.
      </p>

      {status && (
        <div className={`hf-status ${status.configured ? 'on' : 'off'}`}>
          {status.configured
            ? `● HF configured · ${status.model}`
            : `○ ${status.message || 'HF_TOKEN not configured'}`}
        </div>
      )}

      <div className="vision-grid">
        <div>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            onChange={onPick}
            aria-label="Upload crowd image"
          />
          <button
            type="button"
            className="run-btn compact"
            disabled={!file || loading || !online}
            onClick={onAnalyze}
          >
            {loading ? 'ANALYZING…' : 'ANALYZE WITH HUGGING FACE'}
          </button>
          {error && <div className="empty-state compact warn" style={{ marginTop: 10 }}><strong>{error}</strong></div>}
        </div>
        <div className="vision-preview">
          {preview ? (
            <div className="vision-canvas-wrap">
              <img src={preview} alt="Uploaded crowd scene" />
              {result?.detections?.length > 0 && (
                <svg className="bbox-layer" viewBox={`0 0 ${result.image_size?.width || 1} ${result.image_size?.height || 1}`} preserveAspectRatio="none">
                  {result.detections.map((d, i) => {
                    if (!d.box) return null
                    const w = d.box.xmax - d.box.xmin
                    const h = d.box.ymax - d.box.ymin
                    return (
                      <rect
                        key={`b-${i}`}
                        x={d.box.xmin}
                        y={d.box.ymin}
                        width={w}
                        height={h}
                        fill="none"
                        stroke="#38bdf8"
                        strokeWidth={Math.max(2, (result.image_size?.width || 800) / 400)}
                      />
                    )
                  })}
                </svg>
              )}
            </div>
          ) : (
            <div className="empty-state compact">
              <div className="empty-icon">◌</div>
              <strong>NO IMAGE SELECTED</strong>
              <p>Upload a crowd/venue image to run Hub object detection.</p>
            </div>
          )}
        </div>
        <div>
          {!result ? (
            <div className="empty-state compact">
              <div className="empty-icon">◌</div>
              <strong>WAITING FOR ANALYSIS</strong>
              <p>Results appear only after a successful Hugging Face inference call.</p>
            </div>
          ) : (
            <>
              <div className="section-label">Vision Analysis</div>
              <div className="kv"><span>People Detected</span><span>{result.people_detected}</span></div>
              <div className="kv"><span>Model</span><span>{result.model}</span></div>
              <div className="kv"><span>Source</span><span>{result.source}</span></div>
              {Object.entries(result.label_counts || {}).map(([label, count]) => (
                <div className="kv" key={label}><span>{label}</span><span>{count}</span></div>
              ))}
              <p className="reason">{result.observation}</p>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
