 import { useEffect, useRef } from 'react'
 import type { RefObject } from 'react'
 
 /**
  * Keyboard selection controller поверх pdf.js text layer (поведение как в
  * VS Code): Shift+←/→ по символам, Ctrl/Cmd+Shift+←/→ по словам,
  * Shift+↑/↓ по визуальным строкам, ShiftHome/End, Esc — снять выделение.
  *
  * Зачем свой контроллер: нативный Shift↑/↓ работает с DOM-текстом, а текст
  * pdf.js — множество абсолютно спозиционированных span, где одна визуальная
  * строка может состоять из нескольких span (и наоборот). Поэтому после
  * рендера text layer строим модель «страница → визуальные строки → span'ы»
  * и переводим DOM-selection в логическую позицию (строка, смещение).
  */
 
 interface SpanInfo {
   el: HTMLElement
   /** Смещение первого символа span в тексте строки. */
   start: number
   text: string
   left: number
 }
 
 interface LineInfo {
   top: number
   left: number
   right: number
   bottom: number
   column: number
   /** Смещение первого символа строки в тексте страницы (строки склеены '\n'). */
   start: number
   text: string
   spans: SpanInfo[]
 }
 
 export interface Model {
   lines: LineInfo[]
   text: string
   /** Контейнер text layer: координаты модели относительно него; нужен для
    *  перевода clientX/Y событий и live-измерений в координаты модели. */
   container: HTMLElement
   /** span element → координаты в модели. */
   index: Map<HTMLElement, { line: number; span: number }>
   /** Горизонтальные диапазоны колонок (client px), индекс = line.column. */
   columns: Array<{ left: number; right: number }>
   /** Границы графем (для Shift+←/→) и слов (для Ctrl+Shift+←/→). */
   charBounds: number[]
   wordBounds: number[]
 }
 
 export interface Pos {
   line: number
   offset: number
 }
 
 // В lib ES2020 (tsconfig) нет типов Intl.Segmenter — объявляем минимум сами.
 interface SegmentLike {
   segment: string
   index: number
   isWordLike?: boolean
 }
 interface SegmenterLike {
   segment(text: string): Iterable<SegmentLike>
 }
 const SegmenterCtor = (
   Intl as unknown as {
     Segmenter?: new (
       locales?: string,
       options?: { granularity: 'grapheme' | 'word' },
     ) => SegmenterLike
   }
 ).Segmenter
 
 const graphemeSegmenter = SegmenterCtor
   ? new SegmenterCtor(undefined, { granularity: 'grapheme' })
   : null
 const wordSegmenter = SegmenterCtor
   ? new SegmenterCtor(undefined, { granularity: 'word' })
   : null
 
 /** Переиспользуемый range для измерений — однопоточно, гонок нет. */
 const measureRange = document.createRange()
 
 function buildModel(container: HTMLElement): Model | null {
  // PDF.js может создавать marked-content обёртки вокруг настоящих span.
  // Берём только листовые текстовые span.
  const rawItems = Array.from(container.querySelectorAll('span'))
    .filter(
      (el) =>
        el.getAttribute('role') !== 'img' &&
        !el.classList.contains('endOfContent') &&
        !el.querySelector('span') &&
        (el.textContent ?? '').length > 0,
    )
    .map((el) => {
      const r = el.getBoundingClientRect()

      return {
        el,
        text: el.textContent ?? '',
        top: r.top,
        left: r.left,
        right: r.right,
        bottom: r.bottom,
        height: r.height,
        width: r.width,
      }
    })
    .filter((x) => x.width > 0 && x.height > 0)

  if (rawItems.length === 0) return null

  // Все координаты модели храним относительно text-layer.
  // Поэтому zoom/scroll не ломают модель: clientX/Y переводятся
  // относительно того же container.getBoundingClientRect().
  const containerRect = container.getBoundingClientRect()

  const items = rawItems.map((item) => ({
    ...item,
    top: item.top - containerRect.top,
    bottom: item.bottom - containerRect.top,
    left: item.left - containerRect.left,
    right: item.right - containerRect.left,
  }))

  /*
   * ---------------------------------------------------------------
   * 1. Сначала строим НАСТОЯЩИЕ визуальные строки.
   * ---------------------------------------------------------------
   *
   * Важный момент:
   *
   *   левая колонка:  ─────────────
   *   правая колонка: ─────────────
   *
   * имеют практически одинаковый top.
   *
   * Поэтому нельзя считать одинаковый top признаком одной строки
   * без учёта X.
   *
   * Здесь сначала группируем span'ы по вертикальному положению,
   * но пока не смешиваем их в один текст.
   */

  type RowItem = (typeof items)[number]

  interface VisualRow {
    top: number
    bottom: number
    height: number
    items: RowItem[]
  }

  const sortedByTop = [...items].sort(
    (a, b) => a.top - b.top || a.left - b.left,
  )

  const rows: VisualRow[] = []

  for (const item of sortedByTop) {
    let bestRow: VisualRow | null = null
    let bestScore = -Infinity

    for (const row of rows) {
      const overlap =
        Math.min(item.bottom, row.bottom) -
        Math.max(item.top, row.top)

      if (overlap <= 0) continue

      const minHeight = Math.max(1, Math.min(item.height, row.height))
      const verticalOverlap = overlap / minHeight

      if (verticalOverlap < 0.35) continue

      // Чем ближе вертикальные центры, тем лучше кандидат.
      const itemCenter = (item.top + item.bottom) / 2
      const rowCenter = (row.top + row.bottom) / 2
      const centerDistance = Math.abs(itemCenter - rowCenter)

      const score =
        verticalOverlap * 100 -
        centerDistance

      if (score > bestScore) {
        bestScore = score
        bestRow = row
      }
    }

    if (bestRow) {
      bestRow.items.push(item)
      bestRow.top = Math.min(bestRow.top, item.top)
      bestRow.bottom = Math.max(bestRow.bottom, item.bottom)
      bestRow.height = Math.max(bestRow.height, item.height)
    } else {
      rows.push({
        top: item.top,
        bottom: item.bottom,
        height: item.height,
        items: [item],
      })
    }
  }

  /*
   * ---------------------------------------------------------------
   * 1.5. Gutter-полосы между колонками.
   * ---------------------------------------------------------------
   *
   * У журнальных двух колонок gutter узкий (порядка 1.3 высоты
   * строки) — порог gap'а из шага 2 не отличает его от словесных
   * пробелов, и строки обеих колонок склеиваются в один fragment.
   * Поэтому gutter ищем как «долину» в x-проекции плотности текста:
   * полосу, (почти) пустую по всей высоте страницы. Долина устойчива
   * к рваным правым краям выключенных строк — в отличие от gap'ов.
   */

  const pageMedianHeight = (() => {
    const heights = items.map((x) => x.height).sort((a, b) => a - b)
    return heights[Math.floor(heights.length / 2)] ?? 10
  })()

  const itemsBlockLeft = Math.min(...items.map((x) => x.left))
  const itemsBlockRight = Math.max(...items.map((x) => x.right))
  const itemsBlockWidth = Math.max(1, itemsBlockRight - itemsBlockLeft)

  interface GutterBand {
    left: number
    right: number
  }

  const gutters: GutterBand[] = []

  {
    const binWidth = Math.max(1, pageMedianHeight / 6)
    const binCount = Math.ceil(itemsBlockWidth / binWidth)
    const coverage = new Array<number>(binCount).fill(0)

    for (const it of items) {
      const b0 = Math.max(
        0,
        Math.floor((it.left - itemsBlockLeft) / binWidth),
      )
      const b1 = Math.min(
        binCount - 1,
        Math.floor((it.right - itemsBlockLeft) / binWidth),
      )
      for (let b = b0; b <= b1; b++) coverage[b]++
    }

    const maxCoverage = Math.max(...coverage)
    // Gutter почти абсолютно пуст по высоте страницы (пересекают его
    // разве что заголовки/линейки): порог — малая доля максимума, а не
    // плато колонок — плато могут сильно различаться по плотности.
    const emptyLevel = Math.max(1, maxCoverage * 0.12)
    const minValleyWidth = pageMedianHeight * 0.6

    let runStart: number | null = null

    for (let b = 0; b <= binCount; b++) {
      const empty = b < binCount && coverage[b] <= emptyLevel

      if (empty && runStart === null) runStart = b

      if (!empty && runStart !== null) {
        const left = itemsBlockLeft + runStart * binWidth
        const right = itemsBlockLeft + b * binWidth
        const center = (left + right) / 2
        runStart = null

        if (right - left < minValleyWidth) continue

        // Полоса должна лежать в средней половине блока — отсекаем
        // поля страницы и отступы у краёв.
        if (
          center < itemsBlockLeft + itemsBlockWidth * 0.25 ||
          center > itemsBlockRight - itemsBlockWidth * 0.25
        ) {
          continue
        }

        gutters.push({ left, right })
      }
    }
  }

  const crossesGutter = (from: number, to: number): boolean =>
    gutters.some((g) => from < g.right && to > g.left)

  /*
   * ---------------------------------------------------------------
   * 2. Внутри каждой визуальной строки разделяем LEFT/RIGHT
   *    части по реальному горизонтальному разрыву.
   * ---------------------------------------------------------------
   *
   * Это принципиально отличается от старого алгоритма:
   *
   * старый:
   *
   *   span -> column
   *
   * новый:
   *
   *   span -> visual row -> horizontal fragments -> column
   *
   * Поэтому две колонки, находящиеся на одной высоте, больше
   * никогда не становятся одной строкой только потому, что
   * у них одинаковый top.
   */

  interface RowFragment {
    top: number
    bottom: number
    left: number
    right: number
    height: number
    items: RowItem[]
  }

  const fragments: RowFragment[] = []

  for (const row of rows) {
    const rowItems = [...row.items].sort(
      (a, b) => a.left - b.left,
    )

    if (rowItems.length === 0) continue

    /*
     * Обычный пробел между PDF.js span'ами обычно значительно
     * меньше межколоночного gutter.
     *
     * Порог масштабируется вместе с текстом, поэтому при 173%,
     * 200% и т.д. он не остаётся фиксированным CSS-пикселем.
     */
    const medianHeight = (() => {
      const heights = rowItems
        .map((x) => x.height)
        .sort((a, b) => a - b)

      return heights[Math.floor(heights.length / 2)] ?? row.height
    })()

    const gapThreshold = Math.max(
      12,
      medianHeight * 2.2,
    )

    let current: RowFragment | null = null

    for (const item of rowItems) {
      if (!current) {
        current = {
          top: item.top,
          bottom: item.bottom,
          left: item.left,
          right: item.right,
          height: item.height,
          items: [item],
        }
        continue
      }

      const gap = item.left - current.right

      /*
       * Небольшой gap = продолжение той же визуальной строки.
       *
       * Большой gap — или gap, пересекающий найденную gutter-полосу —
       * разрыв между колонками. Проверка полосы нужна, потому что
       * журнальный gutter может быть УЖЕ gapThreshold.
       */
      if (gap <= gapThreshold && !crossesGutter(current.right, item.left)) {
        current.items.push(item)
        current.left = Math.min(current.left, item.left)
        current.right = Math.max(current.right, item.right)
        current.top = Math.min(current.top, item.top)
        current.bottom = Math.max(current.bottom, item.bottom)
        current.height = Math.max(current.height, item.height)
      } else {
        fragments.push(current)

        current = {
          top: item.top,
          bottom: item.bottom,
          left: item.left,
          right: item.right,
          height: item.height,
          items: [item],
        }
      }
    }

    if (current) {
      fragments.push(current)
    }
  }

  if (fragments.length === 0) return null

  /*
   * ---------------------------------------------------------------
   * 3. Строим колонки из визуальных строк (fragments).
   * ---------------------------------------------------------------
   *
   * Если gutter-полосы найдены — детерминированный разрез блока по
   * полосам: fragment попадает в колонку, содержащую её центр (центр в
   * полосе — к ближайшей). Никакой жадной кластеризации: она каскадно
   * сливает колонки через широкие заголовки/подписи, перекрывающие
   * gutter (перекрытие по min-width у узкой строки внутри широкой
   * «колонки» равно 1, и вся страница становилась одной колонкой).
   *
   * Если полос нет (одноколоночная страница; sidebar-вёрстка, где
   * основной текст заходит под боковую колонку и пустой полосы нет) —
   * жадная кластеризация с защитами: широкие фрагменты не участвуют в
   * построении колонок, а центр фрагмента обязан лежать внутри колонки.
   */

  interface Column {
    left: number
    right: number
    fragments: RowFragment[]
  }

  const columns: Column[] = []

  const blockLeft = Math.min(...fragments.map((f) => f.left))
  const blockRight = Math.max(...fragments.map((f) => f.right))

  if (gutters.length > 0) {
    const ranges: Array<{ left: number; right: number }> = []
    let x0 = blockLeft

    for (const g of gutters) {
      ranges.push({ left: x0, right: g.left })
      x0 = g.right
    }
    ranges.push({ left: x0, right: blockRight })

    // Отбрасываем срезы-огрызки (уже трёх высот строки).
    const minColWidth = pageMedianHeight * 3
    let kept = ranges.filter((r) => r.right - r.left >= minColWidth)
    if (kept.length === 0) kept = ranges

    for (const r of kept) {
      columns.push({ left: r.left, right: r.right, fragments: [] })
    }

    for (const fragment of fragments) {
      const center = (fragment.left + fragment.right) / 2

      let best: Column | null = null
      let bestDist = Infinity

      for (const column of columns) {
        const inside = center >= column.left && center <= column.right
        const d = inside
          ? 0
          : Math.min(
              Math.abs(center - column.left),
              Math.abs(center - column.right),
            )

        if (d < bestDist) {
          bestDist = d
          best = column
        }
      }

      best!.fragments.push(fragment)
    }
  } else {
    /*
     * Фрагменты на (почти) всю ширину текстового блока — заголовки,
     * широкие формулы — не участвуют в построении колонок, иначе самый
     * широкий из них (обрабатывается первым) создаёт «колонку» от края
     * до края и поглощает обе настоящие.
     */
    const wideThreshold = Math.max(1, blockRight - blockLeft) * 0.6

    const narrowFragments = fragments.filter(
      (f) => f.right - f.left < wideThreshold,
    )
    const wideFragments = fragments.filter(
      (f) => f.right - f.left >= wideThreshold,
    )

    // Одноколоночная страница из сплошных полных строк: узких фрагментов
    // может не быть — тогда строим колонки из всего (старое поведение).
    const columnSource =
      narrowFragments.length > 0 ? narrowFragments : fragments

    // Сначала самые широкие fragments — они лучше определяют
    // реальный диапазон колонки.
    const sortedFragments = [...columnSource].sort((a, b) => {
      const widthA = a.right - a.left
      const widthB = b.right - b.left

      return (
        widthB - widthA ||
        a.left - b.left ||
        a.top - b.top
      )
    })

    for (const fragment of sortedFragments) {
      let best: Column | null = null
      let bestScore = -Infinity

      const fragmentWidth = Math.max(
        1,
        fragment.right - fragment.left,
      )

      const fragmentCenter =
        (fragment.left + fragment.right) / 2

      for (const column of columns) {
        /*
         * Центр фрагмента обязан лежать внутри колонки: центрированные
         * подписи/формулы, перекрывающие соседнюю колонку, иначе
         * каскадно склеивают колонки в одну.
         */
        if (
          fragmentCenter < column.left - 2 ||
          fragmentCenter > column.right + 2
        ) {
          continue
        }

        const overlap =
          Math.min(fragment.right, column.right) -
          Math.max(fragment.left, column.left)

        if (overlap <= 0) continue

        const columnWidth = Math.max(
          1,
          column.right - column.left,
        )

        const minWidth = Math.min(
          fragmentWidth,
          columnWidth,
        )

        const overlapRatio = overlap / minWidth

        /*
         * Требуем существенного пересечения.
         *
         * Маленькое касание границ или соседний gutter
         * не считается одной колонкой.
         */
        if (overlapRatio < 0.45) continue

        const columnCenter =
          (column.left + column.right) / 2

        const centerDistance =
          Math.abs(fragmentCenter - columnCenter)

        const score =
          overlapRatio * 100 -
          centerDistance * 0.05

        if (score > bestScore) {
          bestScore = score
          best = column
        }
      }

      if (!best) {
        best = {
          left: fragment.left,
          right: fragment.right,
          fragments: [],
        }

        columns.push(best)
      }

      best.fragments.push(fragment)

      best.left = Math.min(
        best.left,
        fragment.left,
      )

      best.right = Math.max(
        best.right,
        fragment.right,
      )
    }

    /*
     * Широкие фрагменты приписываем к уже построенным колонкам по
     * максимальному пересечению. Bounds колонки при этом РАСШИРЯЕМ:
     * диапазон колонки должен покрывать весь её текст, иначе
     * columnAtPoint будет роутить точки внутри текста в чужую колонку.
     * Слияние настоящих колонок это не возвращает — они построены выше
     * только из узких фрагментов.
     */
    if (columnSource !== fragments) {
      for (const fragment of wideFragments) {
        let best: Column | null = null
        let bestScore = -Infinity

        for (const column of columns) {
          const overlap =
            Math.min(fragment.right, column.right) -
            Math.max(fragment.left, column.left)

          const centerDistance = Math.abs(
            (fragment.left + fragment.right) / 2 -
              (column.left + column.right) / 2,
          )

          const score = overlap - centerDistance * 0.01

          if (score > bestScore) {
            bestScore = score
            best = column
          }
        }

        if (best) {
          best.fragments.push(fragment)
          best.left = Math.min(best.left, fragment.left)
          best.right = Math.max(best.right, fragment.right)
        } else {
          columns.push({
            left: fragment.left,
            right: fragment.right,
            fragments: [fragment],
          })
        }
      }
    }
  }

  /*
   * Колонки идут слева направо.
   *
   * column=0 -> левая
   * column=1 -> правая
   * и т.д.
   */
  columns.sort((a, b) => a.left - b.left)

  /*
   * ---------------------------------------------------------------
   * 4. Из каждой колонки строим LineInfo.
   * ---------------------------------------------------------------
   */

  const orderedLines: LineInfo[] = []

  columns.forEach((column, columnIndex) => {
    const columnFragments = [...column.fragments].sort(
      (a, b) =>
        a.top - b.top ||
        a.left - b.left,
    )

    for (const fragment of columnFragments) {
      const spanItems = [...fragment.items].sort(
        (a, b) => a.left - b.left,
      )

      if (spanItems.length === 0) continue

      const spans: SpanInfo[] = spanItems.map((item) => ({
        el: item.el,
        start: 0,
        text: item.text,
        left: item.left,
      }))

      orderedLines.push({
        top: fragment.top,
        left: fragment.left,
        right: fragment.right,
        bottom: fragment.bottom,
        column: columnIndex,
        start: 0,
        text: '',
        spans,
      })
    }
  })

  if (orderedLines.length === 0) return null

  /*
   * ---------------------------------------------------------------
   * 5. Индексы DOM -> logical position.
   * ---------------------------------------------------------------
   */

  const index = new Map<
    HTMLElement,
    { line: number; span: number }
  >()

  const parts: string[] = []

  let global = 0

  orderedLines.forEach((line, lineIndex) => {
    line.spans.sort(
      (a, b) => a.left - b.left,
    )

    line.start = global

    let offset = 0

    line.spans.forEach((span, spanIndex) => {
      span.start = offset

      offset += span.text.length

      index.set(span.el, {
        line: lineIndex,
        span: spanIndex,
      })
    })

    line.text = line.spans
      .map((span) => span.text)
      .join('')

    parts.push(line.text)

    global += line.text.length + 1
  })

  const text = parts.join('\n')

  /*
   * Важно:
   *
   * columns теперь соответствуют именно визуальным колонкам,
   * а не отдельным PDF.js span.
   */
  const columnRanges = columns.map((column) => ({
    left: column.left,
    right: column.right,
  }))

  return {
    lines: orderedLines,
    text,
    container,
    index,
    columns: columnRanges,
    charBounds: computeCharBounds(text),
    wordBounds: computeWordBounds(text),
  }
}
 
 function computeCharBounds(text: string): number[] {
   if (graphemeSegmenter) {
     const bounds = [0]
     for (const s of graphemeSegmenter.segment(text)) bounds.push(s.index + s.segment.length)
     return bounds
   }
   const bounds = [0]
   let i = 0
   while (i < text.length) {
     i += (text.codePointAt(i) ?? 0) > 0xffff ? 2 : 1
     bounds.push(i)
   }
   return bounds
 }
 
 function computeWordBounds(text: string): number[] {
   const bounds = new Set<number>([0, text.length])
   if (wordSegmenter) {
     for (const s of wordSegmenter.segment(text)) {
       if (s.isWordLike) {
         bounds.add(s.index)
         bounds.add(s.index + s.segment.length)
       }
     }
   } else {
     const re = /[\p{L}\p{N}_]+/gu
     let m: RegExpExecArray | null
     while ((m = re.exec(text))) {
       bounds.add(m.index)
       bounds.add(m.index + m[0].length)
     }
   }
   return [...bounds].sort((a, b) => a - b)
 }
 
 // --- Позиции: DOM <-> логика <-> глобальное смещение ---
 
 function spanOffsetToDom(span: HTMLElement, offset: number): { node: Text; offset: number } | null {
   const walker = document.createTreeWalker(span, NodeFilter.SHOW_TEXT)
   let acc = 0
   let node = walker.nextNode() as Text | null
   let last: Text | null = null
   while (node) {
     if (offset <= acc + node.data.length) return { node, offset: offset - acc }
     acc += node.data.length
     last = node
     node = walker.nextNode() as Text | null
   }
   return last ? { node: last, offset: last.data.length } : null
 }
 
 function domOffsetWithin(span: HTMLElement, node: Text, offset: number): number {
   const walker = document.createTreeWalker(span, NodeFilter.SHOW_TEXT)
   let acc = 0
   let cur = walker.nextNode()
   while (cur && cur !== node) {
     acc += (cur as Text).data.length
     cur = walker.nextNode()
   }
   return cur === node ? acc + offset : acc
 }
 
 function lineOffsetToDom(line: LineInfo, offset: number): { node: Text; offset: number } | null {
   const clamped = Math.max(0, Math.min(offset, line.text.length))
   for (const span of line.spans) {
     if (clamped <= span.start + span.text.length) {
       return spanOffsetToDom(span.el, clamped - span.start)
     }
   }
   const last = line.spans[line.spans.length - 1]
   return last ? spanOffsetToDom(last.el, last.text.length) : null
 }
 
 export function domToPos(model: Model, node: Node, offset: number): Pos | null {
   const el = node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement
   const spanEl = el?.closest('span') as HTMLElement | null
   if (!spanEl) return null
   const hit = model.index.get(spanEl)
   if (!hit) return null
   const span = model.lines[hit.line].spans[hit.span]
   const local =
     node.nodeType === Node.TEXT_NODE ? domOffsetWithin(span.el, node as Text, offset) : 0
   return { line: hit.line, offset: span.start + local }
 }
 
 function toGlobal(model: Model, pos: Pos): number {
   const line = model.lines[pos.line]
   return line.start + Math.min(pos.offset, line.text.length)
 }
 
 function toPos(model: Model, global: number): Pos {
   const g = Math.max(0, Math.min(global, model.text.length))
   let lo = 0
   let hi = model.lines.length - 1
   let line = 0
   while (lo <= hi) {
     const mid = (lo + hi) >> 1
     if (model.lines[mid].start <= g) {
       line = mid
       lo = mid + 1
     } else {
       hi = mid - 1
     }
   }
   const l = model.lines[line]
   return { line, offset: Math.min(g - l.start, l.text.length) }
 }
 
 function comparePos(a: Pos, b: Pos): number {
   return a.line - b.line || a.offset - b.offset
 }
 
 export interface LogicalSelection {
   text: string
   /** Прямоугольники в client coordinates — готовы для overlay. */
   clientRects: DOMRect[]
   anchor: Pos
   focus: Pos
 }
 
 /**
  * Читает текущий DOM-selection, но строит текст и подсветку по нашей модели
  * визуальных строк/колонок. Сам native selection остаётся только транспортом
  * для anchor/focus и ввода мышью/клавиатурой. Модель передаётся снаружи —
  * её строит useKeyboardSelection один раз на рендер text layer.
  */
function selectionLineRect(
  model: Model,
  line: LineInfo,
  from: number,
  to: number,
): DOMRect | null {
  if (to <= from) return null

  const left =
    from === 0
      ? line.left
      : caretX(model, line, from)

  const right =
    to === line.text.length
      ? line.right
      : caretX(model, line, to)

  const x0 = Math.min(left, right)
  const x1 = Math.max(left, right)

  if (x1 - x0 <= 1) return null

  const containerRect = model.container.getBoundingClientRect()

  return new DOMRect(
    containerRect.left + x0,
    containerRect.top + line.top,
    x1 - x0,
    line.bottom - line.top,
  )
}

function getColumnSelectionLines(
  model: Model,
  start: Pos,
  end: Pos,
): number[] {
  const startLine = model.lines[start.line]
  const endLine = model.lines[end.line]

  if (!startLine || !endLine) return []

  // Если anchor и focus находятся в одной колонке —
  // selection должна существовать только внутри этой колонки.
  if (startLine.column === endLine.column) {
    const column = startLine.column

    const indices = model.lines
      .map((line, index) => ({ line, index }))
      .filter(({ line }) => line.column === column)
      .map(({ index }) => index)

    const a = indices.indexOf(start.line)
    const b = indices.indexOf(end.line)

    if (a < 0 || b < 0) return []

    const lo = Math.min(a, b)
    const hi = Math.max(a, b)

    return indices.slice(lo, hi + 1)
  }

  // Разные колонки — это уже настоящий переход между колонками.
  // Для клавиатурного Shift+↑/↓ такого быть не должно,
  // но мышью его пока разрешаем.
  const result: number[] = []

  const lo = Math.min(start.line, end.line)
  const hi = Math.max(start.line, end.line)

  for (let i = lo; i <= hi; i += 1) {
    result.push(i)
  }

  return result
}

 export function getLogicalSelection(
  model: Model,
  container: HTMLElement,
): LogicalSelection | null {
  const sel = window.getSelection()

  if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
    return null
  }

  const {
    anchorNode,
    anchorOffset,
    focusNode,
    focusOffset,
  } = sel

  if (
    !anchorNode ||
    !focusNode ||
    !container.contains(anchorNode) ||
    !container.contains(focusNode)
  ) {
    return null
  }

  const anchor = domToPos(model, anchorNode, anchorOffset)
  const focus = domToPos(model, focusNode, focusOffset)

  if (!anchor || !focus) return null

  const forward = comparePos(anchor, focus) <= 0
  const start = forward ? anchor : focus
  const end = forward ? focus : anchor

  const lineIndices = getColumnSelectionLines(model, start, end)

  if (lineIndices.length === 0) return null

  const rects: DOMRect[] = []
  const parts: string[] = []

  for (const li of lineIndices) {
    const line = model.lines[li]

    const from =
      li === start.line
        ? start.offset
        : 0

    const to =
      li === end.line
        ? end.offset
        : line.text.length

    if (to <= from) continue

    const rect = selectionLineRect(model, line, from, to)

    if (rect) {
      rects.push(rect)
    }

    parts.push(line.text.slice(from, to))
  }

  if (rects.length === 0) return null

  return {
    text: parts.join('\n'),
    clientRects: rects,
    anchor,
    focus,
  }
}
 
/** Колонка для точки (x, y): все колонки, чей диапазон содержит x. Если их
 *  несколько (диапазоны перекрываются — напр., широкий заголовок расширил
 *  левую колонку, или основной текст заходит под sidebar), выбирается та,
 *  чья строка ближе к точке — lineDistance считается по границам самих
 *  строк, поэтому горизонтальный drag в соседнюю колонку по-прежнему
 *  работает. Если ни одна не содержит x — preferred (колонка anchor'а при
 *  drag), иначе ближайшая по X. */
function columnAtPoint(
  model: Model,
  x: number,
  y: number,
  preferredColumn?: number,
): number {
  const containing: number[] = []

  for (let i = 0; i < model.columns.length; i++) {
    const c = model.columns[i]
    if (x >= c.left && x <= c.right) containing.push(i)
  }

  if (containing.length === 1) return containing[0]

  if (containing.length > 1) {
    let best = containing[0]
    let bestDist = Infinity

    for (const ci of containing) {
      for (const line of model.lines) {
        if (line.column !== ci) continue

        const d = lineDistance(line, x, y)

        if (d < bestDist) {
          bestDist = d
          best = ci
        }
      }
    }

    return best
  }

  if (
    preferredColumn !== undefined &&
    preferredColumn >= 0 &&
    preferredColumn < model.columns.length
  ) {
    return preferredColumn
  }

  let best = 0
  let bestDist = Infinity

  for (let i = 0; i < model.columns.length; i++) {
    const c = model.columns[i]
    const d = x < c.left ? c.left - x : x - c.right

    if (d < bestDist) {
      bestDist = d
      best = i
    }
  }

  return best
}

/** Ближайшая логическая позиция к точке (clientX, clientY). */
export function posFromPoint(
  model: Model,
  clientX: number,
  clientY: number,
  preferredColumn?: number,
): Pos | null {
  if (model.lines.length === 0) return null

  const cr = model.container.getBoundingClientRect()
  const x = clientX - cr.left
  const y = clientY - cr.top

  /*
   * Ближайшая строка ищется только внутри колонки, определённой по
   * columnAtPoint. Старая эвристика «preferred-колонка, если она не
   * дальше соседней более чем на 12px» ломалась на коротких строках
   * (конец абзаца): у короткой строки right далеко левее курсора, и
   * ближайшей по lineDistance оказывалась строка соседней колонки —
   * выделение перескакивало.
   */
  const column = columnAtPoint(model, x, y, preferredColumn)
  const columnLines = model.lines.filter(
    (line) => line.column === column,
  )
  const candidates = columnLines.length > 0 ? columnLines : model.lines

  let bestLine: LineInfo | null = null
  let bestDistance = Infinity

  for (const line of candidates) {
    const distance = lineDistance(line, x, y)

    if (distance < bestDistance) {
      bestDistance = distance
      bestLine = line
    }
  }

  if (!bestLine) return null

  let lo = 0
  let hi = bestLine.text.length

  while (lo < hi) {
    const mid = (lo + hi) >> 1

    if (caretX(model, bestLine, mid) < x) {
      lo = mid + 1
    } else {
      hi = mid
    }
  }

  const candidatesOffsets = [
    Math.max(0, lo - 1),
    Math.min(bestLine.text.length, lo),
  ]

  let bestOffset = candidatesOffsets[0]
  let bestOffsetDistance = Infinity

  for (const offset of candidatesOffsets) {
    const distance = Math.abs(caretX(model, bestLine, offset) - x)

    if (distance < bestOffsetDistance) {
      bestOffsetDistance = distance
      bestOffset = offset
    }
  }

  const lineIndex = model.lines.indexOf(bestLine)

  return {
    line: lineIndex,
    offset: bestOffset,
  }
}

/** Устанавливает нативный Range по логическим позициям (без изменения модели). */
export function setLogicalSelection(model: Model, anchor: Pos, focus: Pos): void {
  const sel = window.getSelection()
  if (!sel) return
  const a = lineOffsetToDom(model.lines[anchor.line], anchor.offset)
  const f = lineOffsetToDom(model.lines[focus.line], focus.offset)
  if (!a || !f) return
  const range = document.createRange()
  if (comparePos(anchor, focus) <= 0) {
    range.setStart(a.node, a.offset)
    range.setEnd(f.node, f.offset)
  } else {
    range.setStart(f.node, f.offset)
    range.setEnd(a.node, a.offset)
  }
  sel.removeAllRanges()
  sel.addRange(range)
}
// --- Границы ---
 
 function nextBound(bounds: number[], pos: number): number {
   let lo = 0
   let hi = bounds.length - 1
   while (lo <= hi) {
     const mid = (lo + hi) >> 1
     if (bounds[mid] > pos) hi = mid - 1
     else lo = mid + 1
   }
   return lo < bounds.length ? bounds[lo] : pos
 }
 
 function prevBound(bounds: number[], pos: number): number {
   let lo = 0
   let hi = bounds.length - 1
   while (lo <= hi) {
     const mid = (lo + hi) >> 1
     if (bounds[mid] < pos) lo = mid + 1
     else hi = mid - 1
   }
   return hi >= 0 ? bounds[hi] : pos
 }

 function lineDistance(line: LineInfo, x: number, y: number): number {
  const vertical =
    y < line.top
      ? line.top - y
      : y > line.bottom
        ? y - line.bottom
        : 0

  const horizontal =
    x < line.left
      ? line.left - x
      : x > line.right
        ? x - line.right
        : 0

  return vertical * 4 + horizontal
}
 
 // --- Измерение x каретки (для Shift+↑/↓ и goal column) ---
 
 /** X-позиция каретки у заданного смещения строки, в координатах контейнера
  *  text layer (live-измерение минус текущий left контейнера — стабильно
  *  при скролле). */
export function caretX(model: Model, line: LineInfo, offset: number): number {
  const clamped = Math.max(0, Math.min(offset, line.text.length))
  const dom = lineOffsetToDom(line, clamped)

  if (!dom) {
    return clamped === 0 ? line.left : line.right
  }

  measureRange.setStart(dom.node, dom.offset)
  measureRange.collapse(true)

  const rect = measureRange.getBoundingClientRect()
  const containerRect = model.container.getBoundingClientRect()

  if (Number.isFinite(rect.left) && rect.width >= 0) {
    return rect.left - containerRect.left
  }

  return clamped === 0 ? line.left : line.right
}

/** Прямоугольник каретки (координаты контейнера text layer) для собственного
 *  caret'а: нативный caret в не-editable text layer браузер не рисует.
 *  Высота — по live-замеру collapsed range в самой позиции, а не по bounds
 *  строки: bounds строки — объединение rect'ов всех её span'ов, и один
 *  высокий span (inline-формула, надстрочный индекс) раздувал каретку до
 *  нескольких строк. Bounds строки — только fallback. */
export function caretRect(
  model: Model,
  pos: Pos,
): { x: number; top: number; height: number } | null {
  const line = model.lines[pos.line]
  if (!line) return null

  const clamped = Math.max(0, Math.min(pos.offset, line.text.length))
  const dom = lineOffsetToDom(line, clamped)

  if (dom) {
    measureRange.setStart(dom.node, dom.offset)
    measureRange.collapse(true)

    const rect = measureRange.getBoundingClientRect()
    const containerRect = model.container.getBoundingClientRect()

    if (Number.isFinite(rect.left) && rect.height > 1) {
      return {
        x: rect.left - containerRect.left,
        top: rect.top - containerRect.top,
        height: rect.height,
      }
    }
  }

  return {
    x: caretX(model, line, pos.offset),
    top: line.top,
    height: line.bottom - line.top,
  }
}
 
 // --- Хук ---
 
 interface UseKeyboardSelectionOptions {
   containerRef: RefObject<HTMLDivElement | null>
   tool: string
   /** Увеличивается после каждого завершённого рендера text layer. */
   renderVersion: number
   /** Модель строк/колонок — хук заполняет, вызывающий код читает
    *  (getLogicalSelection). Общая модель гарантирует, что клавиатура и
    *  мышь работают с одной и той же геометрией. */
   modelRef: { current: Model | null }
   /** Вызывается после изменения выделения клавиатурой. */
   onSelectionChange?: () => void
   /** Вызывается при снятии выделения (Esc). */
   onSelectionCleared?: () => void
  /** Вызывается при отпускании кнопки мыши после drag. */
  onMouseUp?: () => void
 }
 
 export function useKeyboardSelection({
   containerRef,
   tool,
   renderVersion,
   modelRef,
   onSelectionChange,
   onSelectionCleared,
  onMouseUp,
 }: UseKeyboardSelectionOptions): void {
   // Желаемая x-позиция каретки при повторных ↑/↓ (как в VS Code): сбрасывается
   // любой другой клавишей или кликом.
   const goalXRef = useRef<number | null>(null)
  const callbacksRef = useRef({ onSelectionChange, onSelectionCleared, onMouseUp })
  callbacksRef.current = { onSelectionChange, onSelectionCleared, onMouseUp }
  const mouseRef = useRef<{ anchor: Pos | null; dragging: boolean }>({
    anchor: null,
    dragging: false,
  })
 
   // Перестройка модели строк после каждого рендера text layer.
   useEffect(() => {
     const container = containerRef.current
     modelRef.current = container ? buildModel(container) : null
     goalXRef.current = null
    mouseRef.current = { anchor: null, dragging: false }
   }, [containerRef, modelRef, renderVersion])
 
   useEffect(() => {
     const container = containerRef.current
     if (!container || tool !== 'select') return
 
    const onMouseDown = (e: MouseEvent) => {
      if (e.button !== 0) return
      const model = modelRef.current
      if (!model) return
      const pos = posFromPoint(model, e.clientX, e.clientY)
      if (!pos) return
      // Нативный drag отключаем полностью: браузер расширяет Range по
      // DOM-порядку спанов pdf.js (поток контента, не визуальный порядок)
      // и на каждом mousemove дерётся с нашим контроллером за selection.
      e.preventDefault()
      mouseRef.current = { anchor: pos, dragging: true }
      if (e.detail === 2) {
        // Двойной клик: слово (preventDefault выше отключил нативный dblclick).
        const g = toGlobal(model, pos)
        const ws = toPos(model, prevBound(model.wordBounds, g))
        const we = toPos(model, nextBound(model.wordBounds, g))
        mouseRef.current.anchor = ws
        setLogicalSelection(model, ws, we)
      } else {
        setLogicalSelection(model, pos, pos)
      }
       goalXRef.current = null

       container.focus({ preventScroll: true })
      callbacksRef.current.onSelectionChange?.()

      const onMove = (moveE: MouseEvent) => {
        if (!mouseRef.current.dragging) return
        const m = modelRef.current
        if (!m) return
        // Колонка anchor'а как preferred: в gutter выделение не дёргается,
        // переход в соседнюю колонку — только когда X явно внутри неё.
        const anchorCol = m.lines[mouseRef.current.anchor!.line]?.column
        const focus = posFromPoint(m, moveE.clientX, moveE.clientY, anchorCol)
        if (!focus) return
        setLogicalSelection(m, mouseRef.current.anchor!, focus)
        callbacksRef.current.onSelectionChange?.()
      }

      const onUp = () => {
        mouseRef.current.dragging = false
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', onUp)
        callbacksRef.current.onMouseUp?.()
      }

      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
     }
 
     const onKeyDown = (e: KeyboardEvent) => {
      const sel = window.getSelection()

      if (e.key === 'Escape') {
        sel?.removeAllRanges()
        goalXRef.current = null
        callbacksRef.current.onSelectionCleared?.()
        return
      }

      // Goal column живёт только внутри серии Shift+↑/↓.
      const isVertical = e.key === 'ArrowUp' || e.key === 'ArrowDown'
      if (!(e.shiftKey && isVertical)) goalXRef.current = null

      type Action =
        | 'char-left'
        | 'char-right'
        | 'word-left'
        | 'word-right'
        | 'line-up'
        | 'line-down'
        | 'home'
        | 'end'
      let action: Action | null = null
      if (e.shiftKey && (e.ctrlKey || e.metaKey)) {
        if (e.key === 'ArrowLeft') action = 'word-left'
        else if (e.key === 'ArrowRight') action = 'word-right'
      } else if (e.shiftKey) {
        if (e.key === 'ArrowLeft') action = 'char-left'
        else if (e.key === 'ArrowRight') action = 'char-right'
        else if (e.key === 'ArrowUp') action = 'line-up'
        else if (e.key === 'ArrowDown') action = 'line-down'
        else if (e.key === 'Home') action = 'home'
        else if (e.key === 'End') action = 'end'
      }

      const model = modelRef.current
      if (!action || !model || !sel || sel.rangeCount === 0) return

      const { anchorNode, anchorOffset, focusNode, focusOffset } = sel
      if (
        !anchorNode ||
        !focusNode ||
        !container.contains(anchorNode) ||
        !container.contains(focusNode)
      ) {
        return
      }
      const anchor = domToPos(model, anchorNode, anchorOffset)
      const focus = domToPos(model, focusNode, focusOffset)
      if (!anchor || !focus) return

      e.preventDefault()

      let next: Pos = focus
      switch (action) {
        case 'char-right':
          next = toPos(model, nextBound(model.charBounds, toGlobal(model, focus)))
          break
        case 'char-left':
          next = toPos(model, prevBound(model.charBounds, toGlobal(model, focus)))
          break
        case 'word-right':
          next = toPos(model, nextBound(model.wordBounds, toGlobal(model, focus)))
          break
        case 'word-left':
          next = toPos(model, prevBound(model.wordBounds, toGlobal(model, focus)))
          break
        case 'home':
          next = { line: focus.line, offset: 0 }
          break
        case 'end':
          next = { line: focus.line, offset: model.lines[focus.line].text.length }
          break
        case 'line-up':
        case 'line-down': {
          const dir = action === 'line-down' ? 1 : -1
          const col = model.lines[focus.line].column
          // Шаг строго внутри своей колонки: строки упорядочены колонками,
          // поэтому ±1 по массиву на границе колонок прыгал бы в соседнюю.
          let targetLine = focus.line + dir
          while (
            targetLine >= 0 &&
            targetLine < model.lines.length &&
            model.lines[targetLine].column !== col
          ) {
            targetLine += dir
          }
          if (targetLine < 0 || targetLine >= model.lines.length) break
          if (goalXRef.current == null) {
            goalXRef.current = caretX(model, model.lines[focus.line], focus.offset)
          }
          const gx = goalXRef.current
          const line = model.lines[targetLine]
          let best = 0
          let bestDist = Infinity
          for (let o = 0; o <= line.text.length; o++) {
            const d = Math.abs(caretX(model, line, o) - gx)
            if (d < bestDist) {
              bestDist = d
              best = o
            }
          }
          next = { line: targetLine, offset: best }
          break
        }
      }

      const a = lineOffsetToDom(model.lines[anchor.line], anchor.offset)
      const f = lineOffsetToDom(model.lines[next.line], next.offset)
      if (!a || !f) return

      const range = document.createRange()
      if (comparePos(anchor, next) <= 0) {
        range.setStart(a.node, a.offset)
        range.setEnd(f.node, f.offset)
      } else {
        range.setStart(f.node, f.offset)
        range.setEnd(a.node, a.offset)
      }
      sel.removeAllRanges()
      sel.addRange(range)
      callbacksRef.current.onSelectionChange?.()
    }

    container.addEventListener('mousedown', onMouseDown)
    container.addEventListener('keydown', onKeyDown)
    return () => {
      container.removeEventListener('mousedown', onMouseDown)
      container.removeEventListener('keydown', onKeyDown)
    }
  }, [containerRef, tool])
}