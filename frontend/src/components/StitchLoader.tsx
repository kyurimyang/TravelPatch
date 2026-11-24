import { useEffect, useId, useState } from 'react'
import './StitchLoader.css'

type Props = {
  /** Lines shown one after another while waiting (the last one stays). */
  steps: string[]
  /** Fill the screen area (page loading) or sit inline (inside a card). */
  size?: 'page' | 'inline'
}

// The patch: an airplane cut from denim and sewn round in cream, like the logo's ticket and the
// app icon's plane (2026-11-24: it was a square, then gingham).
// Seen from above, nose up; the whole drawing is turned so it flies up and to the right.
// pathLength=100 lets the CSS animate the stitching in percent whatever the real length is.
const PLANE =
  'M60 8 C65 12 67 22 67 38 L110 62 L110 72 L67 62 L65 92 L84 104 L84 111 L60 105 L36 111 L36 104 L55 92 L53 62 L10 72 L10 62 L53 38 C53 22 55 12 60 8 Z'
// The running stitch: the same distance (4.2) inside the edge all the way round, worked out from
// PLANE, so the thread never rides on the cut edge.
const STITCH =
  'M60.02 15.54 L59.84 15.75 L59.18 17.60 L58.30 21.25 L57.96 23.50 L57.49 28.60 L57.16 38.05 L56.78 39.80 L56.07 40.84 L55.40 41.44 L54.50 42.03 L14.65 64.27 L14.37 64.49 L14.22 64.81 L14.22 66.43 L14.37 66.64 L14.65 66.66 L52.60 57.88 L53.35 57.90 L54.80 58.24 L55.70 58.85 L56.47 59.70 L56.87 60.50 L57.26 62.85 L59.17 91.55 L58.85 93.60 L58.60 94.15 L58.15 94.75 L57.00 95.73 L42.21 105.15 L57.85 101.26 L59.90 100.85 L62.20 101.26 L77.76 105.12 L63.00 95.73 L61.85 94.75 L61.40 94.15 L61.15 93.60 L60.83 91.55 L62.79 62.25 L63.13 60.50 L63.34 60.00 L64.02 59.11 L64.90 58.40 L65.45 58.15 L66.65 57.90 L67.65 57.93 L105.25 66.64 L105.59 66.66 L105.78 66.43 L105.78 64.81 L105.40 64.30 L65.50 42.03 L64.60 41.44 L63.93 40.84 L63.22 39.80 L62.84 38.05 L62.51 28.60 L62.00 23.20 L61.63 20.85 L61.14 18.75 L60.64 17.05 Z'
const STEP_MS = 1600

// "Stitching" loader: a needle runs round an airplane patch and leaves stitches behind it, while
// a dashed contrail of running stitch trails behind. With reduced motion, the finished stitching
// is shown still.
export function StitchLoader({ steps, size = 'page' }: Props) {
  const [step, setStep] = useState(0)
  // Unique per loader: two loaders on one page must not share mask/pattern ids.
  const uid = useId().replace(/:/g, '')

  useEffect(() => {
    if (steps.length < 2) return
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, steps.length - 1)), STEP_MS)
    return () => clearInterval(timer)
  }, [steps.length])

  return (
    <div className={`stitch-loader stitch-loader--${size}`} role="status" aria-live="polite">
      <svg className="stitch-loader__art" viewBox="0 0 120 120" aria-hidden="true">
        <defs>
          {/* The reveal: a solid stroke that grows along the outline and uncovers the stitches. */}
          <mask id={`reveal-${uid}`} maskUnits="userSpaceOnUse">
            <path className="stitch-loader__reveal" d={STITCH} pathLength={100} />
          </mask>
          {/* Denim twill, the logo's ticket cloth (2026-11-24): indigo warp, paler weft on the diagonal. */}
          <pattern id={`cloth-${uid}`} width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect className="stitch-loader__cloth-base" width="3" height="3" />
            <rect className="stitch-loader__cloth-band" width="3" height="0.9" />
            <rect className="stitch-loader__cloth-shade" y="1.8" width="3" height="0.5" />
          </pattern>
        </defs>
        {/* Contrail: two runs of stitches behind the tail, drawn in a loop. */}
        <g className="stitch-loader__trail">
          {/* from the wing tips, backwards along the plane's line (it flies 38° right of up) */}
          <path d="M13 40 L-7 66" />
          <path d="M91 101 L71 127" />
        </g>
        <g transform="rotate(38 60 60)">
          <path className="stitch-loader__cloth" d={PLANE} fill={`url(#cloth-${uid})`} />
          {/* A patch on the patch: the cabin windows, sewn as a row of small stitches. */}
          <path className="stitch-loader__windows" d="M60 22 L60 58" />
          <path className="stitch-loader__holes" d={STITCH} pathLength={100} />
          <path className="stitch-loader__thread" d={STITCH} pathLength={100} mask={`url(#reveal-${uid})`} />
          <g className="stitch-loader__needle" style={{ offsetPath: `path('${STITCH}')` }}>
            {/* thread trailing from the eye, then the needle pointing the way it travels */}
            <path className="stitch-loader__tail" d="M-11 0 q-7 7 -16 5" />
            <line x1="-14" y1="0" x2="11" y2="0" />
            <ellipse cx="-10" cy="0" rx="2.4" ry="1.3" />
          </g>
        </g>
      </svg>
      <p className="stitch-loader__text">{steps[step]}</p>
    </div>
  )
}
