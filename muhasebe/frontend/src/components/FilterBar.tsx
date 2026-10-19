import { useMemo, useState } from 'react'
import { ArrowLeft, Plus, SlidersHorizontal, X } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync, useDebounced } from '../lib/hooks'
import { filterValues, isExclude, useWork } from '../lib/state'
import { OptionList, Popover, Segmented, cn, type Opt } from './ui'

// Kullanicinin secebildigi tum filtreler. Musteri ve urun gibi binlerce
// degeri olanlar sunucuda aranir; digerleri donemdeki kayit sayisiyla listelenir.
const ARAMALI = new Set(['client', 'item', 'client_group'])
const SIRA = ['brand', 'category', 'client', 'client_group', 'item', 'salesman', 'city', 'kind', 'revenue_type',
  'aging_bucket', 'year', 'month', 'direction']

export function FilterBar({ exclude = [] }: { exclude?: string[] }) {
  const { filters, setFilter, clearFilters, meta } = useWork()
  const label = (k: string) => meta?.dimensions.find((d) => d.key === k)?.label ?? k
  const active = Object.entries(filters).filter(([k]) => !exclude.includes(k))

  return (
    <div className="flex flex-wrap items-center gap-2">
      <SlidersHorizontal className="size-4 text-muted" />
      {active.length === 0 && <span className="text-[13px] text-muted">Filtre yok — tüm kayıtlar</span>}
      {active.map(([k, v]) => {
        const vals = filterValues(v)
        const not = isExclude(v)
        return (
          <FilterPopover key={k} dim={k} trigger={(toggle) => (
            <span className={cn('inline-flex h-8 items-center gap-1 rounded-full border pr-1 pl-3 text-[13px]',
              not ? 'border-neg/40 bg-neg/5' : 'border-brand/40 bg-brand-soft')}>
              <button onClick={toggle} className="flex items-center gap-1">
                <span className="text-ink-2">{label(k)}{not ? ' hariç' : ''}:</span>
                <span className="max-w-[220px] truncate font-medium text-ink">
                  {vals.length <= 2 ? vals.join(', ') : `${vals[0]} +${vals.length - 1}`}
                </span>
              </button>
              <button onClick={() => setFilter(k, null)} aria-label={`${label(k)} filtresini kaldır`}
                className="flex size-6 items-center justify-center rounded-full text-ink-2 hover:bg-surface hover:text-ink">
                <X className="size-3.5" />
              </button>
            </span>
          )} />
        )
      })}
      <AddFilter exclude={exclude} />
      {active.length > 1 && (
        <button onClick={clearFilters} className="text-[13px] text-ink-2 underline-offset-2 hover:text-ink hover:underline">
          Tümünü temizle
        </button>
      )}
    </div>
  )
}

function AddFilter({ exclude }: { exclude: string[] }) {
  const { meta, filters } = useWork()
  const [dim, setDim] = useState<string | null>(null)
  const dims = SIRA.filter((k) => !exclude.includes(k) && !filters[k] && meta?.dimensions.some((d) => d.key === k))
  return (
    <Popover width={330} onOpenChange={(o) => { if (!o) setDim(null) }}
      trigger={(open, toggle) => (
        <button onClick={toggle} className={cn('inline-flex h-8 items-center gap-1 rounded-full border border-dashed px-3 text-[13px] font-medium',
          open ? 'border-brand text-brand-ink' : 'border-line-strong text-ink-2 hover:border-ink-2 hover:text-ink')}>
          <Plus className="size-3.5" /> Filtre ekle
        </button>
      )}>
      {(close) => dim
        ? <ValuePicker dim={dim} onBack={() => setDim(null)} onDone={close} />
        : (
          <ul className="py-1.5">
            {dims.map((k) => (
              <li key={k}>
                <button onClick={() => setDim(k)} className="w-full px-3.5 py-2 text-left text-[13.5px] hover:bg-surface-2">
                  {meta?.dimensions.find((d) => d.key === k)?.label}
                </button>
              </li>
            ))}
          </ul>
        )}
    </Popover>
  )
}

function FilterPopover({ dim, trigger }: { dim: string; trigger: (toggle: () => void) => React.ReactNode }) {
  return (
    <Popover width={330} trigger={(_, toggle) => trigger(toggle)}>
      {(close) => <ValuePicker dim={dim} onDone={close} />}
    </Popover>
  )
}

function ValuePicker({ dim, onBack, onDone }: { dim: string; onBack?: () => void; onDone: () => void }) {
  const { filters, setFilter, base, meta } = useWork()
  const cur = filters[dim]
  const [selected, setSelected] = useState<string[]>(filterValues(cur))
  const [not, setNot] = useState(isExclude(cur))
  const [q, setQ] = useState('')
  const dq = useDebounced(q, 250)

  const opts = useAsync<Opt[]>(async () => {
    if (ARAMALI.has(dim)) {
      const r = await api.get<{ v: string; n: number }[]>(`/api/ara?boyut=${dim}&q=${encodeURIComponent(dq)}&limit=60`)
      return r.map((x) => ({ value: x.v, count: x.n }))
    }
    if (['brand', 'category', 'kind', 'revenue_type', 'salesman', 'city', 'year'].includes(dim)) {
      const r = await api.post<Record<string, { v: string; n: number }[]>>('/api/analiz/secenekler',
        { ...base, filters: Object.fromEntries(Object.entries(base.filters).filter(([k]) => k !== dim)) })
      return (r[dim] || []).map((x) => ({ value: String(x.v), count: x.n }))
    }
    const r = await api.post<{ rows: Record<string, unknown>[] }>('/api/analiz/sorgu',
      { ...base, direction: 'TUMU', group_by: [dim], measures: ['lines'], filters: {} })
    return r.rows.map((x) => ({ value: String(x.d0), count: Number(x.m_lines) }))
  }, [dim, ARAMALI.has(dim) ? dq : '', base.date_from, base.date_to])

  const shown = useMemo(() => {
    const list = opts.data || []
    const filt = ARAMALI.has(dim) || !q ? list : list.filter((o) => o.value.toLocaleLowerCase('tr').includes(q.toLocaleLowerCase('tr')))
    const missing = selected.filter((s) => !filt.some((o) => o.value === s)).map((s) => ({ value: s }))
    return [...missing, ...filt]
  }, [opts.data, q, selected, dim])

  return (
    <div>
      <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div className="flex items-center gap-1.5">
          {onBack && <button onClick={onBack} aria-label="Geri" className="text-muted hover:text-ink"><ArrowLeft className="size-4" /></button>}
          <span className="text-[13px] font-semibold">{meta?.dimensions.find((d) => d.key === dim)?.label}</span>
        </div>
        <Segmented size="sm" value={not ? 'not' : 'in'} onChange={(v) => setNot(v === 'not')}
          options={[{ value: 'in', label: 'Dahil' }, { value: 'not', label: 'Hariç' }]} />
      </div>
      <OptionList options={shown} selected={selected} loading={opts.loading} search={q} onSearch={setQ}
        onToggle={(v) => setSelected((p) => (p.includes(v) ? p.filter((x) => x !== v) : [...p, v]))}
        emptyText={ARAMALI.has(dim) && !q ? 'Aramak için yazın' : undefined} />
      <div className="flex items-center justify-between border-t border-line px-3 py-2">
        <button onClick={() => setSelected([])} className="text-[13px] text-ink-2 hover:text-ink">Seçimi temizle</button>
        <button onClick={() => { setFilter(dim, selected.length ? (not ? { not: true, values: selected } : selected) : null); onDone() }}
          className="h-8 rounded-[var(--radius-ctl)] bg-brand px-3 text-[13px] font-semibold text-on-brand">
          Uygula{selected.length ? ` (${selected.length})` : ''}
        </button>
      </div>
    </div>
  )
}
