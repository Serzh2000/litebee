/** A small authored mark: a quadcopter frame, four motors joined by the arms. */
export function Mark({ size = 26 }: { size?: number }) {
  return (
    <svg className="brand-mark" width={size} height={size} viewBox="0 0 26 26" aria-hidden="true">
      <g stroke="var(--ink)" strokeWidth="1.6" strokeLinecap="round">
        <path d="M6 6 20 20M20 6 6 20" />
      </g>
      <g fill="var(--sheet)" stroke="var(--ink)" strokeWidth="1.6">
        <circle cx="5" cy="5" r="3" />
        <circle cx="21" cy="5" r="3" />
        <circle cx="5" cy="21" r="3" />
        <circle cx="21" cy="21" r="3" />
      </g>
      <circle cx="13" cy="13" r="3" fill="var(--accent)" />
    </svg>
  )
}
