/**
 * The mark of Litebee: a honeycomb cell for the bee, two rotor rings for the drone, one dot for the LED. Drawn in the
 * product hue and nothing else.
 */
export function Mark({ size = 24 }: { size?: number }) {
  return (
    <svg className="brand-mark" width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <g stroke="var(--accent)" strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round">
        <path d="M12 7.5l4.9 2.8v5.4L12 18.5l-4.9-2.8v-5.4z" />
        <circle cx="4.6" cy="6.4" r="2.6" />
        <circle cx="19.4" cy="6.4" r="2.6" />
        <path d="M6.5 8.2l1 1.2M17.5 8.2l-1 1.2" />
      </g>
      <circle cx="12" cy="13" r="1.9" fill="var(--accent)" />
    </svg>
  )
}
