import { Fragment, useMemo, useRef, useState, type ReactNode } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { ArrowDown, ArrowUp, ChevronRight, Columns3, FileDown } from 'lucide-react'
import type { ColType } from '../../lib/api'
import { fmt, fmtPeriodKey, isNum, rangeLabel } from '../../lib/format'
import { printTable } from '../../lib/print'
import { useWork } from '../../lib/state'
import { PAGE_TITLE } from '../Shell'
import { useRoute } from '../../lib/router'
import { useLocal } from '../../lib/hooks'
import { Popover, cn } from '../ui'

export interface GridCol<R = Record<string, unknown>> {
  key: string
  label: string
  type?: ColType
  dim?: string
  width?: number
  hidden?: boolean           // varsayilan olarak gizli (kolon secicide acilabilir)
  sortable?: boolean
  render?: (row: R) => ReactNode
  heat?: boolean             // sayisal kolonda sirali isi rengi (pivot)
  printValue?: (row: R) => string   // render'li kolonun PDF'teki metni
}

interface Props<R> {
  id: string                 // kolon tercihlerini hatirlamak icin
  columns: GridCol<R>[]
  rows: R[]
  rowKey: (r: R, i: number) => string | number
  sort?: { key: string; desc: boolean }
  onSort?: (s: { key: string; desc: boolean }) => void   // verilmezse istemci tarafi siralama
  totals?: Record<string, unknown> | null
  totalsLabel?: string
  expandable?: (r: R) => boolean
  renderExpanded?: (r: R) => ReactNode
  onRowClick?: (r: R) => void
  maxHeight?: number | string
  dense?: boolean
  emptyText?: string
  toolbarLeft?: ReactNode
  toolbarRight?: ReactNode
  highlightKey?: string | number | null
  pdfTitle?: string          // PDF basligi (yoksa sayfa adi)
  pdfPeriod?: boolean        // PDF'e secili donemi yaz (donemden bagimsiz sayfalarda false)
}

const SAG = new Set<ColType>(['tl', 'usd', 'num', 'pct'])

export function DataGrid<R extends Record<string, unknown>>(p: Props<R>) {
  const [hiddenPref, setHiddenPref] = useLocal<Record<string, boolean>>(`grid.${p.id}.cols`, {})
  const [localSort, setLocalSort] = useState<{ key: string; desc: boolean } | null>(null)
  const [open, setOpen] = useState<Set<string | number>>(new Set())
  const scrollRef = useRef<HTMLDivElement>(null)
  const { base, meta } = useWork()
  const { page } = useRoute()

  const visible = p.columns.filter((c) => !(hiddenPref[c.key] ?? c.hidden))
  const sort = p.sort ?? localSort

  const rows = useMemo(() => {
    if (p.onSort || !sort) return p.rows
    const k = sort.key
    const out = [...p.rows].sort((a, b) => {
      const x = a[k], y = b[k]
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      const c = isNum(x) && isNum(y) ? x - y : String(x).localeCompare(String(y), 'tr')
      return sort.desc ? -c : c
    })
    return out
  }, [p.rows, sort, p.onSort])

  const heatMax = useMemo(() => {
    const m: Record<string, number> = {}
    visible.filter((c) => c.heat).forEach((c) => {
      m[c.key] = Math.max(0, ...rows.map((r) => (isNum(r[c.key]) ? Math.abs(r[c.key] as number) : 0)))
    })
    return m
  }, [visible, rows])

  const hasExpand = !!p.renderExpanded
  const virt = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => (p.dense ? 34 : 40),
    overscan: 12,
    enabled: !hasExpand && rows.length > 150,
  })
  const useVirt = !hasExpand && rows.length > 150

  const clickSort = (c: GridCol<R>) => {
    if (c.sortable === false) return
    const next = { key: c.key, desc: sort?.key === c.key ? !sort.desc : !(c.type === 'text' || c.type === 'dim' || c.type === 'date') }
    if (c.type === 'date' && sort?.key !== c.key) next.desc = true
    p.onSort ? p.onSort(next) : setLocalSort(next)
  }

  const metin = (c: GridCol<R>, r: R): string => {
    if (c.printValue) return c.printValue(r)
    const v = r[c.key]
    if (c.type === 'dim') return String(fmtPeriodKey(v, c.dim) ?? '')
    return v == null ? '' : String(fmt(v, c.type ?? 'text'))
  }
  const pdf = () => {
    const kolonlar = visible.filter((c) => !c.key.startsWith('_'))
    const satirlar: string[] = []
    if (p.pdfPeriod !== false) satirlar.push(`Dönem: ${rangeLabel(base.date_from, base.date_to)}`)
    const ad = (k: string) => meta?.dimensions.find((d) => d.key === k)?.label ?? k
    for (const [k, v] of Object.entries(base.filters)) {
      const deg = Array.isArray(v) ? v : v.values
      if (deg.length) satirlar.push(`${ad(k)}${!Array.isArray(v) && v.not ? ' (hariç)' : ''}: ${deg.join(', ')}`)
    }
    printTable({
      title: p.pdfTitle ?? PAGE_TITLE[page] ?? 'Tablo', company: meta?.settings?.company_name ?? undefined, lines: satirlar,
      cols: kolonlar.map((c) => ({ label: c.label, right: SAG.has(c.type ?? 'text') })),
      rows: rows.map((r) => kolonlar.map((c) => metin(c, r))),
      totals: p.totals ? kolonlar.map((c, j) => (j === 0 ? (p.totalsLabel ?? 'Toplam') : p.totals![c.key] !== undefined ? String(fmt(p.totals![c.key], c.type ?? 'text')) : '')) : null,
    })
  }

  const cell = (c: GridCol<R>, r: R) => {
    if (c.render) return c.render(r)
    const v = r[c.key]
    if (c.type === 'dim') return fmtPeriodKey(v, c.dim)
    return fmt(v, c.type ?? 'text')
  }

  const heatBg = (c: GridCol<R>, v: unknown) => {
    if (!c.heat || !isNum(v) || !heatMax[c.key]) return undefined
    const t = Math.min(1, Math.abs(v) / heatMax[c.key])
    return `color-mix(in oklab, var(--s1) ${Math.round(4 + t * 30)}%, transparent)`
  }

  const pad = p.dense ? 'px-3 py-1.5' : 'px-3.5 py-2.5'
  // Sabit kolon genislikleri + en sonda esnek bosluk: uzun bir musteri adi
  // tabloyu yana itmez, genis ekranda kalan alan sondaki bosluga gider.
  // Sayisal kolonlar en uzun degere (toplam dahil) gore genisler: milyarlik tutarlar kesilmez.
  const numW = (c: GridCol<R>) => {
    let n = fmt(p.totals?.[c.key], c.type ?? 'num').length
    for (const r of rows.slice(0, 500)) {
      const v = (r as Record<string, unknown>)[c.key]
      if (v != null) n = Math.max(n, fmt(v, c.type ?? 'num').length)
    }
    const baslik = String(c.label ?? '').length * 7.4 + 40      // basliga gore de genisle (12.5px yazi)
    return Math.min(260, Math.max(132, n * 8 + 34, baslik))
  }
  const widths = visible.map((c) => c.width ?? (SAG.has(c.type ?? 'text') ? numW(c) : c.type === 'date' ? 110 : 240))
  const totalW = widths.reduce((a, b) => a + b, 0) + (hasExpand ? 32 : 0)
  const gridCols = (hasExpand ? '32px ' : '') + widths.map((w) => `${w}px`).join(' ') + ' minmax(0,1fr)'

  const Row = ({ r, i, style }: { r: R; i: number; style?: React.CSSProperties }) => {
    const k = p.rowKey(r, i)
    const canOpen = hasExpand && (p.expandable ? p.expandable(r) : true)
    const isOpen = open.has(k)
    return (
      <div style={style}>
        <div
          role="row"
          onClick={() => {
            if (canOpen) setOpen((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n })
            else p.onRowClick?.(r)
          }}
          className={cn('grid items-center border-b border-line text-[13px] transition-colors',
            (canOpen || p.onRowClick) && 'cursor-pointer hover:bg-surface-2',
            isOpen && 'bg-surface-2', p.highlightKey === k && 'bg-brand-soft')}
          style={{ gridTemplateColumns: gridCols }}
        >
          {hasExpand && (
            <span className="flex justify-center">
              {canOpen && <ChevronRight className={cn('size-4 text-muted transition-transform', isOpen && 'rotate-90 text-ink')} />}
            </span>
          )}
          {visible.map((c) => (
            <div key={c.key} role="cell" title={typeof r[c.key] === 'string' ? (r[c.key] as string) : undefined} style={{ background: heatBg(c, r[c.key]) }}
              className={cn(pad, 'min-w-0 truncate', SAG.has(c.type ?? 'text') && 'tnum text-right',
                isNum(r[c.key]) && (r[c.key] as number) < 0 && SAG.has(c.type ?? 'text') && 'text-neg')}>
              {cell(c, r)}
            </div>
          ))}
          <span />
        </div>
        {isOpen && p.renderExpanded && (
          <div className="border-b border-line bg-surface-2/60 px-4 py-3">{p.renderExpanded(r)}</div>
        )}
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-2 px-1 pb-2.5">
        <div className="flex flex-wrap items-center gap-2">{p.toolbarLeft}</div>
        <div className="flex flex-wrap items-center gap-2">
          {p.toolbarRight}
          <button onClick={pdf} title="Bu tabloyu yazdır ya da PDF olarak kaydet" disabled={!rows.length}
            className="inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-ctl)] border border-line-strong bg-surface px-2.5 text-[13px] text-ink-2 hover:text-ink disabled:opacity-50">
            <FileDown className="size-4" /> PDF
          </button>
          <Popover align="right" width={260} trigger={(_, toggle) => (
            <button onClick={toggle} title="Kolonları seç"
              className="inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-ctl)] border border-line-strong bg-surface px-2.5 text-[13px] text-ink-2 hover:text-ink">
              <Columns3 className="size-4" /> Kolonlar
            </button>
          )}>
            {() => (
              <ul className="scroll-thin max-h-80 overflow-auto py-1.5">
                {p.columns.map((c) => {
                  const on = !(hiddenPref[c.key] ?? c.hidden)
                  return (
                    <li key={c.key}>
                      <label className="flex cursor-pointer items-center gap-2.5 px-3.5 py-1.5 text-[13px] hover:bg-surface-2">
                        <input type="checkbox" checked={on} className="accent-[var(--brand)]"
                          onChange={() => setHiddenPref({ ...hiddenPref, [c.key]: on })} />
                        {c.label}
                      </label>
                    </li>
                  )
                })}
              </ul>
            )}
          </Popover>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <div ref={scrollRef} className="scroll-thin overflow-auto" style={{ maxHeight: p.maxHeight ?? 620 }} role="table">
          <div style={{ minWidth: totalW }}>
            <div role="row" className="sticky top-0 z-10 grid border-b border-line-strong bg-surface-2 text-[12.5px] font-medium text-ink-2"
              style={{ gridTemplateColumns: gridCols }}>
              {hasExpand && <span />}
              {visible.map((c) => {
                const s = sort?.key === c.key
                return (
                  <button key={c.key} role="columnheader" onClick={() => clickSort(c)}
                    aria-sort={s ? (sort!.desc ? 'descending' : 'ascending') : 'none'}
                    className={cn(pad, 'flex items-center gap-1 text-left whitespace-nowrap hover:text-ink',
                      SAG.has(c.type ?? 'text') && 'justify-end text-right', s && 'text-ink')}>
                    {c.label}
                    {s && (sort!.desc ? <ArrowDown className="size-3.5" /> : <ArrowUp className="size-3.5" />)}
                  </button>
                )
              })}
              <span />
            </div>



            {useVirt ? (
              <div style={{ height: virt.getTotalSize(), position: 'relative' }}>
                {virt.getVirtualItems().map((vi) => (
                  <Row key={p.rowKey(rows[vi.index], vi.index)} r={rows[vi.index]} i={vi.index}
                    style={{ position: 'absolute', top: 0, left: 0, right: 0, transform: `translateY(${vi.start}px)` }} />
                ))}
              </div>
            ) : (
              rows.map((r, i) => <Fragment key={p.rowKey(r, i)}><Row r={r} i={i} /></Fragment>)
            )}

            {p.totals && rows.length > 0 && (
              <div role="row" className="sticky bottom-0 z-10 grid border-t border-line-strong bg-surface text-[13px] font-semibold"
                style={{ gridTemplateColumns: gridCols }}>
                {hasExpand && <span />}
                {visible.map((c, j) => (
                  <div key={c.key} className={cn(pad, 'truncate', SAG.has(c.type ?? 'text') && 'tnum text-right')}>
                    {j === 0 ? (p.totalsLabel ?? 'Toplam') : (p.totals![c.key] !== undefined ? fmt(p.totals![c.key], c.type ?? 'text') : '')}
                  </div>
                ))}
                <span />
              </div>
            )}
          </div>
        </div>
        {rows.length === 0 && (
          <div className="px-4 py-12 text-center text-[13.5px] text-ink-2">{p.emptyText || 'Bu seçimde kayıt yok.'}</div>
        )}
      </div>
    </div>
  )
}
