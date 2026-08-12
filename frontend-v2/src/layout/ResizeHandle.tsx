interface ResizeHandleProps {
  onMouseDown: (e: React.MouseEvent<HTMLDivElement>) => void
  title?: string
}

/** 4px разделитель между панелями, hover → accent (стили в index.css). */
export default function ResizeHandle({ onMouseDown, title }: ResizeHandleProps) {
  return <div className="resize-handle" onMouseDown={onMouseDown} title={title} />
}
