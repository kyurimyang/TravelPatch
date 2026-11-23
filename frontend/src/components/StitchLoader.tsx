import { useEffect, useId, useState } from 'react'
import './StitchLoader.css'

type Props = {
  /** Lines shown one after another while waiting (the last one stays). */
  steps: string[]
  /** Fill the screen area (page loading) or sit inline (inside a card). */
  size?: 'page' | 'inline'
}

// The patch: an airplane cut from cloth (2026-11-24: it was a square; a plane says "travel").
// Seen from above, nose up; the whole drawing is turned so it flies up and to the right.
// pathLength=100 lets the CSS animate the stitching in percent whatever the real length is.
const PLANE =
  'M60 8 C65 12 67 22 67 38 L110 62 L110 72 L67 62 L65 92 L84 104 L84 111 L60 105 L36 111 L36 104 L55 92 L53 62 L10 72 L10 62 L53 38 C53 22 55 12 60 8 Z'
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
            <path className="stitch-loader__reveal" d={PLANE} pathLength={100} />
          </mask>
          {/* Gingham cloth, same colours as the app's fabric tokens. */}
          <pattern id={`cloth-${uid}`} width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(-38)">
            <rect className="stitch-loader__cloth-base" width="10" height="10" />
            <rect className="stitch-loader__cloth-band" width="5" height="10" />
            <rect className="stitch-loader__cloth-band" width="10" height="5" />
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
          <path className="stitch-loader__holes" d={PLANE} pathLength={100} />
          <path className="stitch-loader__thread" d={PLANE} pathLength={100} mask={`url(#reveal-${uid})`} />
          <g className="stitch-loader__needle" style={{ offsetPath: `path('${PLANE}')` }}>
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
