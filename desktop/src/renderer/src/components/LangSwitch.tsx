import { getLang, setLang, type Lang } from '@core/i18n'
import './LangSwitch.css'

const LANGS: [Lang, string, string][] = [
  ['ru', 'RU', 'Русский'],
  ['en', 'EN', 'English'],
]

/** Two small toggles: the language of the interface. The names stay in their own language. */
export function LangSwitch() {
  const now = getLang()
  return (
    <div className="lang" role="group" aria-label="Language / Язык">
      {LANGS.map(([id, short, name]) => (
        <button key={id} type="button" aria-pressed={now === id} title={name} onClick={() => setLang(id)}>
          {short}
        </button>
      ))}
    </div>
  )
}
