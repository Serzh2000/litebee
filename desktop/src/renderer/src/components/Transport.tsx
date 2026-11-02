import { Pause, Play } from 'lucide-react'
import { SPEEDS } from '../state/usePlayback'
import { seconds } from '../lib/color'
import './Transport.css'
import { tr } from '@core/i18n'

interface Props {
  t: number
  duration: number
  playing: boolean
  speed: number
  onToggle: () => void
  onSpeed: (s: number) => void
  onSeek: (t: number) => void
}

/** Play, speed, the scrubber and the count: the show time, shared by the chart and the count sheet. */
export function Transport({ t, duration, playing, speed, onToggle, onSpeed, onSeek }: Props) {
  return (
    <div className="transport">
      <button type="button" className="play" onClick={onToggle} aria-label={playing ? tr('Пауза') : tr('Играть')}>
        {playing ? <Pause size={16} strokeWidth={2} aria-hidden="true" /> : <Play size={16} strokeWidth={2} aria-hidden="true" />}
        {playing ? tr('Пауза') : tr('Играть')}
      </button>
      <div className="speeds" role="group" aria-label={tr('Скорость симуляции')}>
        {SPEEDS.map((s) => (
          <button key={s} type="button" aria-pressed={speed === s} onClick={() => onSpeed(s)}>
            {s}×
          </button>
        ))}
      </div>
      <p className="count" aria-live="off">
        <strong>{seconds(t)}</strong> / {seconds(duration)} {tr('с')}
      </p>
      <input
        className="scrub"
        type="range"
        min={0}
        max={duration}
        step={0.1}
        value={t}
        aria-label={tr('Время шоу')}
        onChange={(e) => onSeek(Number(e.target.value))}
        style={{ ['--at' as string]: `${duration > 0 ? (t / duration) * 100 : 0}%` }}
      />
    </div>
  )
}
