import { useMemo, useState } from 'react'
import { ArrowDownRight, ArrowUpRight, CheckCheck, ChevronRight, Clock, Hourglass, PackageX, Repeat } from 'lucide-react'
import { api, type QueryResult } from '../lib/api'
import { delta, fmt, fmtShort, fmtSpoken, isNum, rangeLabel } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { navigate } from '../lib/router'
import { iso, useWork, type Compare } from '../lib/state'
import { PageHeader } from '../components/Shell'
import { FilterBar } from '../components/FilterBar'
import { BarChart, Legend, LineChart, RankBars } from '../components/charts/Charts'
import { ErrorBox, Figure, InfoTip, Loading, Panel, Select, cn } from '../components/ui'

interface Totals { [k: string]: number | null }
interface Overview {
  date_from: string; date_to: string; compare_from: string; compare_to: string; compare: Compare
  current: { sales: Totals; by_revenue_type: Record<string, Totals>; purchases: Totals }
  previous: { sales: Totals; by_revenue_type: Record<string, Totals>; purchases: Totals } | null
  granularity: string
  series_sales: QueryResult; series_purchases: QueryResult
  top_brands: Record<string, unknown>[]; top_categories: Record<string, unknown>[]
  top_customers: Record<string, unknown>[]; top_salesmen: Record<string, unknown>[]
}

const GRAN = [
  { value: 'auto', label: 'Otomatik' }, { value: 'day', label: 'Gün' }, { value: 'week', label: 'Hafta' },
  { value: 'month', label: 'Ay' }, { value: 'quarter', label: 'Çeyrek' }, { value: 'year', label: 'Yıl' },
]

export default function OverviewPage() {
  const { base, currency, compare, setCompare, setFilter, setPeriod } = useWork()
  const [gran, setGran] = useState('auto')
  const usd = currency === 'USD'
  const m = usd ? 'net_usd' : 'net_tl'
  const t = usd ? 'usd' : 'tl'

  const ov = useAsync(() => api.post<Overview>('/api/genel-bakis', {
    ...base, compare, measure: m, granularity: gran === 'auto' ? undefined : gran,
  }), [JSON.stringify(base), compare, m, gran])

  const alerts = useAsync(async () => {
    const [sales, renewals, subs, stok] = await Promise.all([
      api.get<{ status: string; days_left: number; price: number | null }[]>('/api/sales'),
      api.get<unknown[]>('/api/renewals'),
      api.get<{ status: string }[]>('/api/subscriptions'),
      api.post<{ totals: { dead_items: number; dead_value_tl: number } }>('/api/stok', { limit: 1 }),
    ])
    const aktif = sales.filter((x) => !['EXPIRED', 'NEEDS_DURATION', 'RENEWED'].includes(x.status) && x.days_left >= 0)
    const ay = aktif.filter((x) => x.days_left <= 30)
    return {
      expiring30: ay.length, expiring30Value: ay.reduce((t, x) => t + (x.price || 0), 0),
      expiring90: aktif.filter((x) => x.days_left <= 90).length,
      candidates: renewals.length,
      needsDuration: sales.filter((x) => x.status === 'NEEDS_DURATION').length,
      risky: subs.filter((x) => x.status === 'AT_RISK').length,
      dead: stok.totals,
    }
  }, [])

  const g = ov.data
  const seriler = useMemo(() => {
    if (!g) return null
    const rows = [...g.series_sales.rows].sort((a, b) => String(a.d0).localeCompare(String(b.d0)))
    const alis = new Map(g.series_purchases.rows.map((r) => [String(r.d0), Number(r[`m_${m}`]) || 0]))
    const birlesik = rows.map((r) => ({
      d0: r.d0,
      urun: Number(r['p::Ürün']) || 0,
      tekrar: Number(r['p::Tekrarlayan']) || 0,
      satis: (Number(r['p::Ürün']) || 0) + (Number(r['p::Tekrarlayan']) || 0),
      alis: alis.get(String(r.d0)) ?? 0,
    }))
    alis.forEach((v, k) => { if (!birlesik.some((x) => x.d0 === k)) birlesik.push({ d0: k, urun: 0, tekrar: 0, satis: 0, alis: v }) })
    birlesik.sort((a, b) => String(a.d0).localeCompare(String(b.d0)))
    return birlesik
  }, [g, m])

  // Bir zaman dilimine tiklayinca: donemi o dilime daralt + gelir tipini filtrele, Satislar'a git
  const drill = (key: string, revenue?: string) => {
    const r = bucketRange(key, g?.granularity || 'month')
    if (r) setPeriod(r[0], r[1])
    if (revenue) setFilter('revenue_type', [revenue])
    navigate('satislar')
  }

  return (
    <div>
      <PageHeader
        title="Genel bakış"
        subtitle={g ? <>Seçili dönem {rangeLabel(g.date_from, g.date_to)}{g.previous && <>, karşılaştırma {rangeLabel(g.compare_from, g.compare_to)}</>}</> : ' '}
        actions={(
          <Select<Compare> label="Karşılaştır" value={compare} onChange={setCompare} options={[
            { value: 'previous', label: 'Önceki dönemle' }, { value: 'year', label: 'Geçen yılın aynı dönemiyle' },
            { value: 'none', label: 'Karşılaştırma yok' },
          ]} />
        )}
      >
        <FilterBar />
      </PageHeader>

      {ov.loading && !g && <Loading />}
      {ov.error && <ErrorBox message={ov.error} onRetry={ov.reload} />}

      {g && (
        <div className={cn('flex flex-col gap-5 transition-opacity', ov.loading && 'opacity-60')}>
          <Statement g={g} m={m} t={t} currency={currency} onRevenue={(r) => { setFilter('revenue_type', [r]); navigate('satislar') }} />

          {alerts.data && <Alerts a={alerts.data} />}

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <Panel title="Ürün satışları" hint="Fiziksel ürün satışları (iadeler düşülmüş). Bir çubuğa tıklarsanız o dönemin satış satırları açılır."
              actions={<Select value={gran} onChange={setGran} options={GRAN} />}>
              <BarChart data={seriler ?? []} xKey="d0" dim={g.granularity} type={t}
                series={[{ key: 'urun', label: 'Ürün', color: 'var(--rev-product)' }]}
                onBarClick={(r) => drill(String(r.d0), 'Ürün')} />
            </Panel>
            <Panel title="Tekrarlayan gelir" hint="Süreli lisanslar ve aylık abonelikler (Microsoft vb.). Kullanıcı Ayarlar > Sınıflandırma'dan hangi ürünlerin tekrarlayan sayılacağını değiştirebilir.">
              <BarChart data={seriler ?? []} xKey="d0" dim={g.granularity} type={t}
                series={[{ key: 'tekrar', label: 'Tekrarlayan', color: 'var(--rev-recurring)' }]}
                onBarClick={(r) => drill(String(r.d0), 'Tekrarlayan')} />
            </Panel>
          </div>

          <Panel title="Alış ve satış" hint="Aynı dönemde yapılan alışlar ile satışlar. İkisi aynı birimde olduğu için tek eksende gösterilir.">
            <div className="mb-3"><Legend series={[{ key: 'satis', label: 'Satış', color: 'var(--rev-product)' }, { key: 'alis', label: 'Alış', color: 'var(--s2)' }]} /></div>
            <LineChart data={seriler ?? []} xKey="d0" dim={g.granularity} type={t}
              series={[{ key: 'satis', label: 'Satış', color: 'var(--rev-product)' }, { key: 'alis', label: 'Alış', color: 'var(--s2)' }]} />
          </Panel>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 2xl:grid-cols-4">
            {([
              ['Markalar', g.top_brands, 'brand'], ['Kategoriler', g.top_categories, 'category'],
              ['Müşteriler', g.top_customers, 'client_group'], ['Temsilciler', g.top_salesmen, 'salesman'],
            ] as const).map(([title, rows, dim]) => (
              <Panel key={title} title={title} hint="Bir satıra tıklarsanız tüm sayfalara filtre olarak eklenir.">
                <RankBars rows={rows} labelKey="d0" valueKey={`m_${m}`} type={t}
                  sub={(r) => { const mk = usd ? 'm_margin_usd' : 'm_margin'; return isNum(r[mk]) ? `Marj ${fmt(r[mk], 'pct')}` : null }}
                  onClick={(r) => setFilter(dim, [String(r.d0)])} />
              </Panel>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Statement({ g, m, t, currency, onRevenue }: { g: Overview; m: string; t: 'tl' | 'usd'; currency: string; onRevenue: (r: string) => void }) {
  const s = g.current.sales, p = g.previous?.sales
  const a = g.current.purchases, pa = g.previous?.purchases
  const urun = Number(g.current.by_revenue_type['Ürün']?.[`m_${m}`]) || 0
  const tekrar = Number(g.current.by_revenue_type['Tekrarlayan']?.[`m_${m}`]) || 0
  const toplam = urun + tekrar
  const profitKey = t === 'usd' ? 'm_profit_usd' : 'm_profit_tl'
  const marginKey = t === 'usd' ? 'm_margin_usd' : 'm_margin'
  const items: { label: string; value: string; raw?: unknown; d: number | null; hint?: string; neutral?: boolean; go: string }[] = [
    { label: 'Alış', value: fmt(a[`m_${m}`], t), raw: a[`m_${m}`], d: delta(a[`m_${m}`], pa?.[`m_${m}`]), neutral: true, go: 'alislar',
      hint: 'Dönemdeki alış faturaları (iadeler düşülmüş). Artış ya da azalış tek başına iyi/kötü sayılmaz, o yüzden nötr renkte gösterilir.' },
    { label: 'Brüt kâr', value: fmt(s[profitKey], t), raw: s[profitKey], d: delta(s[profitKey], p?.[profitKey]), go: 'analiz',
      hint: 'Satış tutarından, satılan ürünlerin FIFO yöntemiyle tahmin edilen alış maliyeti düşülerek bulunur. Alış kaydı veri başlangıcından önce olan satışlar hesaba katılmaz.' },
    { label: 'Kâr marjı', value: fmt(s[marginKey], 'pct'), d: isNum(s[marginKey]) && isNum(p?.[marginKey]) ? (s[marginKey] as number) - (p![marginKey] as number) : null, go: 'analiz',
      hint: 'Brüt kârın, maliyeti bilinen satışlara oranı. Karşılaştırmadaki değişim yüzde puan olarak gösterilir.' },
    { label: 'Fatura', value: fmt(s.m_invoices, 'num'), d: delta(s.m_invoices, p?.m_invoices), go: 'satislar' },
    { label: 'Müşteri', value: fmt(s.m_clients, 'num'), d: delta(s.m_clients, p?.m_clients), go: 'musteriler' },
    { label: 'Satılan ürün çeşidi', value: fmt(s.m_items, 'num'), d: delta(s.m_items, p?.m_items), go: 'stok' },
  ]
  const d = delta(s[`m_${m}`], p?.[`m_${m}`])
  return (
    <section className="panel ledger-in grid grid-cols-1 overflow-hidden xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <div className="border-b border-line p-6 xl:border-r xl:border-b-0">
        <p className="text-[13px] font-medium text-ink-2">Satış (iadeler düşülmüş)</p>
        <p className="display tnum mt-1 text-[44px] leading-none font-semibold text-ink max-sm:text-[34px]">{fmt(s[`m_${m}`], t)}</p>
        <p className="mt-1.5 text-[13px] text-ink-2">{fmtSpoken(s[`m_${m}`], t)}</p>
        <div className="mt-2.5 flex flex-wrap items-center gap-3 text-[13px]">
          <DeltaTag d={d} />
          {currency === 'BOTH' && <span className="tnum text-ink-2">{fmt(s.m_net_usd, 'usd')}</span>}
          {g.previous && <span className="text-muted">önceki dönem: {fmtShort(p?.[`m_${m}`], t)}</span>}
        </div>
        <div className="mt-6">
          <div className="flex h-2.5 w-full gap-[2px] overflow-hidden rounded-full bg-surface-3">
            <div className="h-full bg-[var(--rev-product)]" style={{ width: `${toplam ? (urun / toplam) * 100 : 0}%` }} />
            <div className="h-full bg-[var(--rev-recurring)]" style={{ width: `${toplam ? (tekrar / toplam) * 100 : 0}%` }} />
          </div>
          <div className="mt-2.5 grid grid-cols-1 gap-4 sm:grid-cols-2 text-[13px]">
            <div role="button" tabIndex={0} onClick={() => onRevenue('Ürün')} onKeyDown={(e) => e.key === 'Enter' && onRevenue('Ürün')}
              title="Bu gelirin satış satırlarını aç" className="-m-2 cursor-pointer rounded-lg p-2 transition-colors hover:bg-surface-2">
              <span className="inline-flex items-center gap-1.5 text-ink-2"><span className="size-2.5 rounded-[2px] bg-[var(--rev-product)]" />Ürün</span>
              <Figure value={urun} type={t} className="mt-0.5 text-[17px] font-semibold" />
              <p className="text-[12px] text-muted">%{toplam ? Math.round((urun / toplam) * 100) : 0} pay</p>
            </div>
            <div role="button" tabIndex={0} onClick={() => onRevenue('Tekrarlayan')} onKeyDown={(e) => e.key === 'Enter' && onRevenue('Tekrarlayan')}
              title="Bu gelirin satış satırlarını aç" className="-m-2 cursor-pointer rounded-lg p-2 transition-colors hover:bg-surface-2">
              <span className="inline-flex items-center gap-1.5 text-ink-2"><span className="size-2.5 rounded-[2px] bg-[var(--rev-recurring)]" />Tekrarlayan
                <InfoTip>Süreli lisanslar ve abonelikler: düzenli yenilenen, tekrar eden gelir.</InfoTip></span>
              <Figure value={tekrar} type={t} className="mt-0.5 text-[17px] font-semibold" />
              <p className="text-[12px] text-muted">%{toplam ? Math.round((tekrar / toplam) * 100) : 0} pay</p>
            </div>
          </div>
        </div>
      </div>
      <dl className="grid grid-cols-1 min-[420px]:grid-cols-2 sm:grid-cols-3 xl:grid-cols-2 2xl:grid-cols-3">
        {items.map((it) => (
          <a key={it.label} href={`#/${it.go}`} className="group relative block border-b border-line p-5 transition-colors hover:bg-surface-2 min-[420px]:even:border-l sm:[&:not(:nth-child(3n+1))]:border-l sm:[&:nth-child(3n+1)]:border-l-0 xl:[&:nth-child(odd)]:border-l-0 xl:[&:nth-child(even)]:border-l 2xl:[&:nth-child(even)]:border-l-0 2xl:[&:not(:nth-child(3n+1))]:border-l">
            <dt className="flex items-center gap-1.5 text-[13px] text-ink-2">{it.label}{it.hint && <InfoTip>{it.hint}</InfoTip>}</dt>
            <dd className="mt-1 text-[20px] font-semibold text-ink">
              {it.raw !== undefined ? <Figure value={it.raw} type={t} /> : <span className="tnum">{it.value}</span>}
            </dd>
            <dd className="mt-1 text-[12.5px]"><DeltaTag d={it.d} neutral={it.neutral} unit={it.label === 'Kâr marjı' ? 'puan' : '%'} /></dd>
            <ChevronRight aria-hidden className="absolute top-5 right-4 size-4 text-muted opacity-0 transition group-hover:opacity-100" />
          </a>
        ))}
      </dl>
    </section>
  )
}

function DeltaTag({ d, unit = '%', neutral }: { d: number | null; unit?: '%' | 'puan'; neutral?: boolean }) {
  if (d === null || !Number.isFinite(d)) return <span className="text-muted">karşılaştırma yok</span>
  const up = d >= 0
  const v = Math.abs(d).toLocaleString('tr-TR', { maximumFractionDigits: 1 })
  return (
    <span className={cn('inline-flex items-center gap-0.5 font-medium', neutral ? 'text-ink-2' : up ? 'text-pos' : 'text-neg')}>
      {up ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}
      {unit === '%' ? `%${v}` : `${v} puan`}
      <span className="sr-only">{up ? 'artış' : 'azalış'}</span>
    </span>
  )
}

type AlertData = {
  expiring30: number; expiring30Value: number; expiring90: number; candidates: number; needsDuration: number
  risky: number; dead: { dead_items: number; dead_value_tl: number }
}

/** "Dikkat isteyenler": donemden bagimsiz yapilacak isler. Her kutu ilgili listeyi filtreli acar. */
function Alerts({ a }: { a: AlertData }) {
  const items = [
    { icon: Clock, tone: 'var(--warning)', n: a.expiring30, label: '30 gün içinde biten lisans',
      sub: a.expiring30 ? `${fmtShort(a.expiring30Value, 'tl')} yenileme, 90 günde ${a.expiring90}` : `90 gün içinde ${a.expiring90}`,
      go: 'lisanslar?tab=yaklasan&gun=30' },
    { icon: CheckCheck, tone: 'var(--s2)', n: a.candidates, label: 'Onay bekleyen yenileme', sub: 'Yenilendi mi, değil mi?', go: 'lisanslar?tab=aday' },
    { icon: Hourglass, tone: 'var(--serious)', n: a.needsDuration, label: 'Süresi girilmeli', sub: 'Girilene kadar hatırlatma gitmez', go: 'lisanslar?tab=sure' },
    { icon: Repeat, tone: 'var(--critical)', n: a.risky, label: 'Faturası geciken abonelik', sub: 'Olağan aralığın dışında', go: 'abonelikler' },
    { icon: PackageX, tone: 'var(--muted)', n: a.dead.dead_items, label: 'Hareketsiz stok kalemi',
      sub: `${fmtShort(a.dead.dead_value_tl, 'tl')}, 180 günden uzun`, go: 'stok' },
  ]
  return (
    <section aria-labelledby="dikkat" className="ledger-in">
      <h2 id="dikkat" className="display mb-2.5 text-[15px] font-semibold text-ink">Dikkat isteyenler</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {items.map((it) => (
          <a key={it.label} href={`#/${it.go}`}
            className={cn('panel group relative flex flex-col overflow-hidden px-4 pt-3.5 pb-3.5 transition-colors hover:border-line-strong', it.n === 0 && 'opacity-55')}>
            <span aria-hidden className="absolute inset-x-0 top-0 h-[2px]" style={{ background: it.n ? it.tone : 'var(--line)' }} />
            <span className="flex items-center justify-between text-[12.5px] text-ink-2">
              <span className="inline-flex items-center gap-1.5"><it.icon className="size-[15px] text-muted" strokeWidth={1.8} />{it.label}</span>
              <ChevronRight aria-hidden className="size-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-ink" />
            </span>
            <span className="display tnum mt-2 text-[24px] leading-none font-semibold text-ink">{it.n === 0 ? '—' : fmt(it.n, 'num')}</span>
            <span className="mt-1.5 truncate text-[12px] text-muted">{it.n === 0 ? 'Bekleyen iş yok' : it.sub}</span>
          </a>
        ))}
      </div>
    </section>
  )
}

function bucketRange(key: string, gran: string): [string, string] | null {
  if (gran === 'month' && /^\d{4}-\d{2}$/.test(key)) {
    const [y, m] = key.split('-').map(Number)
    return [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))]
  }
  if (gran === 'year') return [`${key}-01-01`, `${key}-12-31`]
  if (gran === 'day') return [key, key]
  if (gran === 'quarter') {
    const [y, q] = key.split('-Ç').map(Number)
    return [iso(new Date(y, (q - 1) * 3, 1)), iso(new Date(y, q * 3, 0))]
  }
  return null
}
