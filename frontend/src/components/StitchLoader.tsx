import { useEffect, useId, useState } from 'react'
import './StitchLoader.css'

type Props = {
  /** Lines shown one after another while waiting (the last one stays). */
  steps: string[]
  /** Fill the screen area (page loading) or sit inline (inside a card). */
  size?: 'page' | 'inline'
}

// The patch outline: a slightly wobbly square, like a hand-cut piece of cloth. pathLength=100 lets
// the CSS animate it in percent whatever the real length is.
const PATCH = 'M14 16 L106 12 L108 104 L12 108 Z'
const STEP_MS = 1600

// "Stitching" loader: a needle runs round a fabric patch and leaves stitches behind it.
// With reduced motion, the finished stitching is shown still.
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
            <path className="stitch-loader__reveal" d={PATCH} pathLength={100} />
          </mask>
          {/* Gingham cloth, same colours as the app's fabric tokens. */}
          <pattern id={`cloth-${uid}`} width="10" height="10" patternUnits="userSpaceOnUse">
            <rect className="stitch-loader__cloth-base" width="10" height="10" />
            <rect className="stitch-loader__cloth-band" width="5" height="10" />
            <rect className="stitch-loader__cloth-band" width="10" height="5" />
          </pattern>
        </defs>
        <path className="stitch-loader__cloth" d={PATCH} fill={`url(#cloth-${uid})`} />
        <path className="stitch-loader__holes" d={PATCH} pathLength={100} />
        <path className="stitch-loader__thread" d={PATCH} pathLength={100} mask={`url(#reveal-${uid})`} />
        <g className="stitch-loader__needle">
          {/* thread trailing from the eye, then the needle pointing the way it travels */}
          <path className="stitch-loader__tail" d="M-11 0 q-7 7 -16 5" />
          <line x1="-14" y1="0" x2="11" y2="0" />
          <ellipse cx="-10" cy="0" rx="2.4" ry="1.3" />
        </g>
      </svg>
      <p className="stitch-loader__text">{steps[step]}</p>
    </div>
  )
}
