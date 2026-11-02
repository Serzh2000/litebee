import type { CatalogItem } from '@core/catalog'
import type { ShowData } from '@core/show'
import catalog from './catalog.json'
import quarterLadder from '../../../../shows/quarter_ladder.json'
import quarterFrame from '../../../../shows/quarter_frame.json'
import quarterSpiral from '../../../../shows/quarter_spiral.json'
import quarterBaton from '../../../../shows/quarter_baton.json'
import quarterShuttle from '../../../../shows/quarter_shuttle.json'
import quarterTriangle from '../../../../shows/quarter_triangle.json'
import quarterHops from '../../../../shows/quarter_hops.json'
import myDream from '../../../../shows/my_dream.json'
import myPeople from '../../../../shows/my_people_my_country_5.json'
import fullCorners from '../../../../shows/full_corners.json'
import fullMarch from '../../../../shows/full_march.json'
import fullRainbow from '../../../../shows/full_rainbow.json'
import fullRings from '../../../../shows/full_rings.json'
import fullWave from '../../../../shows/full_wave.json'
import quarterCircleData from '../../../../shows/quarter_circle.json'
import quarterExpand from '../../../../shows/quarter_expand.json'
import quarterSquareData from '../../../../shows/quarter_square.json'
import quarterSwap from '../../../../shows/quarter_swap.json'
import quarterTraffic from '../../../../shows/quarter_traffic.json'
import quarterTwin from '../../../../shows/quarter_twin.json'
import quarterWaveData from '../../../../shows/quarter_wave.json'
import quarterLadderSource from '../../../../../shows/quarter_ladder.py?raw'
import quarterFrameSource from '../../../../../shows/quarter_frame.py?raw'
import quarterSpiralSource from '../../../../../shows/quarter_spiral.py?raw'
import quarterBatonSource from '../../../../../shows/quarter_baton.py?raw'
import quarterShuttleSource from '../../../../../shows/quarter_shuttle.py?raw'
import quarterTriangleSource from '../../../../../shows/quarter_triangle.py?raw'
import quarterHopsSource from '../../../../../shows/quarter_hops.py?raw'
import myDreamSource from '../../../../../shows/my_dream.py?raw'
import myPeopleSource from '../../../../../shows/my_people_my_country_5.py?raw'
import fullCornersSource from '../../../../../shows/full_corners.py?raw'
import fullMarchSource from '../../../../../shows/full_march.py?raw'
import fullRainbowSource from '../../../../../shows/full_rainbow.py?raw'
import fullRingsSource from '../../../../../shows/full_rings.py?raw'
import fullWaveSource from '../../../../../shows/full_wave.py?raw'
import quarterCircleSource from '../../../../../shows/quarter_circle.py?raw'
import quarterExpandSource from '../../../../../shows/quarter_expand.py?raw'
import quarterSquareSource from '../../../../../shows/quarter_square.py?raw'
import quarterSwapSource from '../../../../../shows/quarter_swap.py?raw'
import quarterTrafficSource from '../../../../../shows/quarter_traffic.py?raw'
import quarterTwinSource from '../../../../../shows/quarter_twin.py?raw'
import quarterWaveSource from '../../../../../shows/quarter_wave.py?raw'
import quarterPairCross from '../../../../shows/quarter_pair_cross.json'
import quarterPairCrossSource from '../../../../../shows/quarter_pair_cross.py?raw'
import quarterPairMirror from '../../../../shows/quarter_pair_mirror.json'
import quarterPairMirrorSource from '../../../../../shows/quarter_pair_mirror.py?raw'
import quarterPairFollow from '../../../../shows/quarter_pair_follow.json'
import quarterPairFollowSource from '../../../../../shows/quarter_pair_follow.py?raw'
import quarterPairElevator from '../../../../shows/quarter_pair_elevator.json'
import quarterPairElevatorSource from '../../../../../shows/quarter_pair_elevator.py?raw'
import quarterPairOrbit from '../../../../shows/quarter_pair_orbit.json'
import quarterPairOrbitSource from '../../../../../shows/quarter_pair_orbit.py?raw'
import quarterPairZigzag from '../../../../shows/quarter_pair_zigzag.json'
import quarterPairZigzagSource from '../../../../../shows/quarter_pair_zigzag.py?raw'
import quarterPairDialog from '../../../../shows/quarter_pair_dialog.json'
import quarterPairDialogSource from '../../../../../shows/quarter_pair_dialog.py?raw'
import quarterPairLeapfrog from '../../../../shows/quarter_pair_leapfrog.json'
import quarterPairLeapfrogSource from '../../../../../shows/quarter_pair_leapfrog.py?raw'
import quarterFiveCross from '../../../../shows/quarter_five_cross.json'
import quarterFiveCrossSource from '../../../../../shows/quarter_five_cross.py?raw'
import quarterSixSwap from '../../../../shows/quarter_six_swap.json'
import quarterSixSwapSource from '../../../../../shows/quarter_six_swap.py?raw'
import quarterSixWave from '../../../../shows/quarter_six_wave.json'
import quarterSixWaveSource from '../../../../../shows/quarter_six_wave.py?raw'
import quarterSevenHex from '../../../../shows/quarter_seven_hex.json'
import quarterSevenHexSource from '../../../../../shows/quarter_seven_hex.py?raw'
import quarterEightCarousel from '../../../../shows/quarter_eight_carousel.json'
import quarterEightCarouselSource from '../../../../../shows/quarter_eight_carousel.py?raw'
import quarterEightPulse from '../../../../shows/quarter_eight_pulse.json'
import quarterEightPulseSource from '../../../../../shows/quarter_eight_pulse.py?raw'

export interface ShowEntry {
  id: string
  title: string
  file: string
  source: string
  /** the show as the Python simulator computed it, shown until the editor has run the source itself */
  data?: ShowData
  /** one line in the examples menu */
  note: string
  /** which part of the mat the show is written for */
  kind: 'quarter' | 'full'
  /** how many drones the show uses, counted from its data */
  drones: number
  /** seconds, themes and tags that the wizard filters by (see tools/gen_gallery.py) */
  seconds: number
  themes: string[]
  tags: string[]
  /** true for the shows of the generated gallery: their data comes from running the source */
  gallery: boolean
}

const data = (d: unknown) => d as ShowData

/** Shows that ship with the app: the Python files of ../shows and what the Python simulator made of them. */
const ENTRIES: Omit<ShowEntry, 'drones' | 'seconds' | 'themes' | 'tags' | 'gallery'>[] = [
  // five to eight drones, one quarter of the mat
  { id: 'quarter_five_cross', title: 'Пятёрка: хоровод', file: 'quarter_five_cross.py', source: quarterFiveCrossSource, data: data(quarterFiveCross), note: '5 дронов, обход квадрата и центр', kind: 'quarter' },
  { id: 'quarter_six_swap', title: 'Шестёрка: ряды меняются', file: 'quarter_six_swap.py', source: quarterSixSwapSource, data: data(quarterSixSwap), note: '6 дронов, два ряда', kind: 'quarter' },
  { id: 'quarter_six_wave', title: 'Шестёрка: волна', file: 'quarter_six_wave.py', source: quarterSixWaveSource, data: data(quarterSixWave), note: '6 дронов, бегущая волна высоты', kind: 'quarter' },
  { id: 'quarter_seven_hex', title: 'Семёрка: шестиугольник', file: 'quarter_seven_hex.py', source: quarterSevenHexSource, data: data(quarterSevenHex), note: '7 дронов, кольцо и центр', kind: 'quarter' },
  { id: 'quarter_eight_carousel', title: 'Восьмёрка: карусель', file: 'quarter_eight_carousel.py', source: quarterEightCarouselSource, data: data(quarterEightCarousel), note: '8 дронов, бегущие цвета', kind: 'quarter' },
  { id: 'quarter_eight_pulse', title: 'Восьмёрка: пульс', file: 'quarter_eight_pulse.py', source: quarterEightPulseSource, data: data(quarterEightPulse), note: '8 дронов, сжатие и разжатие', kind: 'quarter' },
  // two drones, one quarter of the mat
  { id: 'quarter_pair_cross', title: 'Разминуться', file: 'quarter_pair_cross.py', source: quarterPairCrossSource, data: data(quarterPairCross), note: '2 дрона, по диагоналям на разной высоте', kind: 'quarter' },
  { id: 'quarter_pair_mirror', title: 'Зеркало', file: 'quarter_pair_mirror.py', source: quarterPairMirrorSource, data: data(quarterPairMirror), note: '2 дрона, противоположные углы', kind: 'quarter' },
  { id: 'quarter_pair_follow', title: 'Догонялки', file: 'quarter_pair_follow.py', source: quarterPairFollowSource, data: data(quarterPairFollow), note: '2 дрона, один за другим', kind: 'quarter' },
  { id: 'quarter_pair_elevator', title: 'Лифт', file: 'quarter_pair_elevator.py', source: quarterPairElevatorSource, data: data(quarterPairElevator), note: '2 дрона, высота в противофазе, только свет и высота', kind: 'quarter' },
  { id: 'quarter_pair_orbit', title: 'Облёт', file: 'quarter_pair_orbit.py', source: quarterPairOrbitSource, data: data(quarterPairOrbit), note: '2 дрона, кольцо вокруг зависшего', kind: 'quarter' },
  { id: 'quarter_pair_zigzag', title: 'Зигзаг', file: 'quarter_pair_zigzag.py', source: quarterPairZigzagSource, data: data(quarterPairZigzag), note: '2 дрона, две половины коврика', kind: 'quarter' },
  { id: 'quarter_pair_dialog', title: 'Диалог света', file: 'quarter_pair_dialog.py', source: quarterPairDialogSource, data: data(quarterPairDialog), note: '2 дрона, только свет', kind: 'quarter' },
  { id: 'quarter_pair_leapfrog', title: 'Чехарда', file: 'quarter_pair_leapfrog.py', source: quarterPairLeapfrogSource, data: data(quarterPairLeapfrog), note: '2 дрона, по очереди над друг другом', kind: 'quarter' },
  // one quarter of the mat, 6 x 6 cells
  { id: 'quarter_traffic', title: 'Светофор', file: 'quarter_traffic.py', source: quarterTrafficSource, data: data(quarterTraffic), note: '3 дрона, только свет', kind: 'quarter' },
  { id: 'quarter_square', title: 'Квадрат', file: 'quarter_square.py', source: quarterSquareSource, data: data(quarterSquareData), note: '4 дрона, по углам', kind: 'quarter' },
  { id: 'quarter_expand', title: 'Раскрытие', file: 'quarter_expand.py', source: quarterExpandSource, data: data(quarterExpand), note: '4 дрона, в углы и назад', kind: 'quarter' },
  { id: 'quarter_swap', title: 'Обмен местами', file: 'quarter_swap.py', source: quarterSwapSource, data: data(quarterSwap), note: '4 дрона, разная высота', kind: 'quarter' },
  { id: 'quarter_wave', title: 'Волна высоты', file: 'quarter_wave.py', source: quarterWaveSource, data: data(quarterWaveData), note: '4 дрона', kind: 'quarter' },
  { id: 'quarter_circle', title: 'Круг', file: 'quarter_circle.py', source: quarterCircleSource, data: data(quarterCircleData), note: '4 дрона, circle', kind: 'quarter' },
  { id: 'quarter_twin', title: 'Двойная звезда', file: 'quarter_twin.py', source: quarterTwinSource, data: data(quarterTwin), note: '2 дрона, circle в обе стороны', kind: 'quarter' },
  { id: 'quarter_ladder', title: 'Лесенка', file: 'quarter_ladder.py', source: quarterLadderSource, data: data(quarterLadder), note: '3 дрона, высота 80–140', kind: 'quarter' },
  { id: 'quarter_frame', title: 'Строй по рамке', file: 'quarter_frame.py', source: quarterFrameSource, data: data(quarterFrame), note: '3 дрона, строем', kind: 'quarter' },
  { id: 'quarter_spiral', title: 'Спираль', file: 'quarter_spiral.py', source: quarterSpiralSource, data: data(quarterSpiral), note: '2 дрона, вверх по кругу', kind: 'quarter' },
  { id: 'quarter_baton', title: 'Эстафета света', file: 'quarter_baton.py', source: quarterBatonSource, data: data(quarterBaton), note: '4 дрона, свет и высота', kind: 'quarter' },
  { id: 'quarter_shuttle', title: 'Челнок', file: 'quarter_shuttle.py', source: quarterShuttleSource, data: data(quarterShuttle), note: '3 дрона, от края до края', kind: 'quarter' },
  { id: 'quarter_triangle', title: 'Треугольник', file: 'quarter_triangle.py', source: quarterTriangleSource, data: data(quarterTriangle), note: '3 дрона, по вершинам', kind: 'quarter' },
  { id: 'quarter_hops', title: 'Прыжки по очереди', file: 'quarter_hops.py', source: quarterHopsSource, data: data(quarterHops), note: '4 дрона', kind: 'quarter' },
  // the whole mat, 12 x 12 cells
  { id: 'full_rainbow', title: 'Радуга', file: 'full_rainbow.py', source: fullRainbowSource, data: data(fullRainbow), note: '6 дронов, только свет', kind: 'full' },
  { id: 'full_corners', title: 'Углы к центру', file: 'full_corners.py', source: fullCornersSource, data: data(fullCorners), note: '4 дрона', kind: 'full' },
  { id: 'full_march', title: 'Марш двух рядов', file: 'full_march.py', source: fullMarchSource, data: data(fullMarch), note: '10 дронов', kind: 'full' },
  { id: 'full_wave', title: 'Волна по коврику', file: 'full_wave.py', source: fullWaveSource, data: data(fullWave), note: '10 дронов', kind: 'full' },
  { id: 'full_rings', title: 'Два кольца', file: 'full_rings.py', source: fullRingsSource, data: data(fullRings), note: '8 дронов, circle', kind: 'full' },
  { id: 'my_dream', title: 'My Dream', file: 'my_dream.py', source: myDreamSource, data: data(myDream), note: 'ваше шоу, 10 дронов', kind: 'full' },
  {
    id: 'my_people_my_country_5',
    title: 'My People, My Country (5)',
    file: 'my_people_my_country_5.py',
    source: myPeopleSource,
    data: data(myPeople),
    note: 'ваше шоу, 10 дронов',
    kind: 'full',
  },
]

const META = new Map(catalog.classic.map((c) => [c.id, c]))

const CLASSIC: ShowEntry[] = ENTRIES.map((e) => {
  const meta = META.get(e.id)
  return {
    ...e,
    drones: meta?.drones ?? Object.keys(e.data?.drones ?? {}).length,
    seconds: meta?.seconds ?? 0,
    themes: meta?.themes ?? [],
    tags: meta?.tags ?? [],
    gallery: false,
  }
})

// The generated gallery: only the Python sources are bundled; the app runs them like any file the person opens.
const GALLERY_SOURCES = import.meta.glob('../../../../../shows/gallery/*.py', { query: '?raw', import: 'default', eager: true }) as Record<string, string>
const sourceOf = (id: string) => Object.entries(GALLERY_SOURCES).find(([path]) => path.endsWith(`/${id}.py`))?.[1] ?? ''

const GALLERY: ShowEntry[] = catalog.gallery.map((g) => ({
  id: g.id,
  title: g.title,
  file: `${g.id}.py`,
  source: sourceOf(g.id),
  note: g.note,
  kind: g.area as 'quarter' | 'full',
  drones: g.drones,
  seconds: g.seconds,
  themes: g.themes,
  tags: g.tags,
  gallery: true,
}))

export const SHOWS: ShowEntry[] = [...CLASSIC, ...GALLERY]

/** Every example as the wizard sees it. */
export const CATALOG: CatalogItem[] = SHOWS.map((s) => ({
  id: s.id,
  title: s.title,
  note: s.note,
  area: s.kind,
  drones: s.drones,
  seconds: s.seconds,
  themes: s.themes,
  tags: s.tags,
}))
