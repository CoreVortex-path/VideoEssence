/** Minimal inline SVG icons for the PDF workspace (14px, stroke = currentColor). */

interface IconProps {
  className?: string
  filled?: boolean
}

function base(props: IconProps) {
  return {
    className: props.className ?? 'h-3.5 w-3.5',
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  }
}

export function BackIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M15 6l-6 6 6 6" />
    </svg>
  )
}

export function StarIcon(props: IconProps) {
  return (
    <svg {...base(props)} fill={props.filled ? 'currentColor' : 'none'}>
      <path d="M12 3.5l2.7 5.4 6 .9-4.3 4.2 1 5.9-5.4-2.8-5.4 2.8 1-5.9L3.3 9.8l6-.9L12 3.5z" />
    </svg>
  )
}

export function ChevronLeftIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M14 6l-6 6 6 6" />
    </svg>
  )
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M10 6l6 6-6 6" />
    </svg>
  )
}

export function ZoomInIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="11" cy="11" r="7" />
      <path d="M11 8v6M8 11h6M21 21l-4.5-4.5" />
    </svg>
  )
}

export function ZoomOutIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="11" cy="11" r="7" />
      <path d="M8 11h6M21 21l-4.5-4.5" />
    </svg>
  )
}

export function FitIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
    </svg>
  )
}

export function SearchIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.5-4.5" />
    </svg>
  )
}

export function InfoIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </svg>
  )
}

export function DownloadIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 4v11M7 11l5 5 5-5M4 20h16" />
    </svg>
  )
}

export function DotsIcon(props: IconProps) {
  return (
    <svg {...base(props)} fill="currentColor" stroke="none">
      <circle cx="12" cy="5" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="12" cy="19" r="1.6" />
    </svg>
  )
}

export function SelectIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M5 3l7 18 2.5-7.5L22 11 5 3z" />
    </svg>
  )
}

export function HandIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M8 11V5.5a1.5 1.5 0 013 0V10m0-5.5v-1a1.5 1.5 0 013 0V10m0-4.5a1.5 1.5 0 013 0V12m0-3a1.5 1.5 0 013 0v4a7 7 0 01-7 7h-1c-2.5 0-4-1-5.5-3.5L3.6 12a1.5 1.5 0 012.4-1.7l2 2.3" />
    </svg>
  )
}

export function HighlightIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 20h8M6 16l8.5-8.5a2.1 2.1 0 013 3L9 19l-4 1 1-4z" />
    </svg>
  )
}

export function UnderlineIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M6 4v6a6 6 0 0012 0V4M5 20h14" />
    </svg>
  )
}

export function PenIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M17 3l4 4L8 20l-5 1 1-5L17 3z" />
    </svg>
  )
}

export function RectIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="4" y="6" width="16" height="12" rx="1" />
    </svg>
  )
}

export function NoteIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M21 12a8 8 0 01-8 8H4l2-3a8 8 0 1115-5z" />
    </svg>
  )
}

export function EraserIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M5 15l8-8a2 2 0 013 0l3 3a2 2 0 010 3l-5 5H9l-4-3zM8 21h13" />
    </svg>
  )
}

export function CloseIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  )
}

export function RotateIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M20 8A8 8 0 105 9M4 4v5h5" />
    </svg>
  )
}

export function FullscreenIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
    </svg>
  )
}

export function AiIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" />
      <path d="M19 16l.9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9L19 16z" />
    </svg>
  )
}

export function CopyIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V6a2 2 0 012-2h9" />
    </svg>
  )
}

export function PanelRightIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M15 4v16" />
    </svg>
  )
}
