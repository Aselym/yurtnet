import { useMemo, useState } from 'react'
import { Download, Link2, Search } from 'lucide-react'
import { api, download, type QueryResult, type Sale, type Subscription } from '../lib/api'
import { fmt, fmtDate } from '../lib/format'
import { useAsync, useDebounced, useLocal } from '../lib/hooks'
import { useWork } from '../lib/state'
import { PageHeader } from '../components/Shell'
import { FilterBar } from '../components/FilterBar'
import { DataGrid, type GridCol } from '../components/data/DataGrid'
import { BarChart, RankBars } from '../components/charts/Charts'
import { Badge, Button, Drawer, ErrorBox, Loading, Segmented, cn, inputCls, toast, Figure } from '../components/ui'

export default function CustomersPage() {
  const { base, currency } = useWork()
  const [dim, setDim] = useLocal<'client' | 'client_group'>('musteri.boyut', 'client')
  const [q, setQ] = useState('')
  const dq = useDebounced(q, 300)
  const [open, setOpen] = useState<string | null>(null)
  const money = currency === 'USD' ? ['net_usd', 'profit_usd', 'margin_usd'] : currency === 'TL' ? ['net_tl', 'profit_tl', 'margin'] : ['net_tl', 'net_usd', 'profit_tl', 'margin']
  const measures = [...money, 'invoices', 'items', 'qty']
  const req = { ...base, direction: 'SATIS_NET', group_by: [dim, 'city'], measures, search: dq }
  const res = useAsync(() => api.post<QueryResult>('/api/analiz/sorgu', req), [JSON.stringify(req)])

  // ilk/son alim tarihleri (donemden bagimsiz musteri gecmisi)
  const hayat = useAsync(() => api.post<QueryResult>('/api/analiz/sorgu', {
    date_from: '1900-01-01', date_to: base.date_to, direction: 'SATIS_NET', group_by: [dim, 'year'], measures: ['net_tl'],
  }), [dim, base.date_to])
  const ilkSon = useMemo(() => {
    const m = new Map<string, { ilk: string; son: string }>()
    hayat.data?.rows.forEach((r) => {
      const k = String(r.d0), y = String(r.d1)
      const c = m.get(k)
      m.set(k, { ilk: c && c.ilk < y ? c.ilk : y, son: c && c.son > y ? c.son : y })
    })
    return m
  }, [hayat.data])

  const cols: GridCol[] = (res.data?.columns ?? []).map((c) => ({
    key: c.key, label: c.key === 'd1' ? 'Şehir' : c.label, type: c.type, width: c.key === 'd0' ? 360 : c.key === 'd1' ? 120 : undefined,
  }))
  cols.push({ key: '_ilk', label: 'İlk alım yılı', type: 'text', width: 110, render: (r) => ilkSon.get(String(r.d0))?.ilk ?? '—' })
  cols.push({ key: '_son', label: 'Son alım yılı', type: 'text', width: 110, render: (r) => ilkSon.get(String(r.d0))?.son ?? '—' })

  return (
    <div>
      <PageHeader title="Müşteriler" subtitle="Seçili dönemde kim ne kadar aldı, ne kadar kâr bıraktı. Bir müşteriye tıklayınca tüm geçmişi açılır."
        actions={<Button icon={<Download className="size-4" />} onClick={() =>
          download('/api/export/sorgu', { request: req, title: 'Müşteriler', filename: 'Müşteriler' }).catch((e) => toast.err(e.message))}>Excel'e aktar</Button>}>
        <FilterBar />
      </PageHeader>
      <div className="panel p-4">
        {res.error && <ErrorBox message={res.error} onRetry={res.reload} />}
        {!res.data && res.loading && <Loading />}
        {res.data && (
          <div className={cn(res.loading && 'opacity-60')}>
            <DataGrid id={`musteri.${dim}`} columns={cols} rows={res.data.rows} rowKey={(r) => `${r.d0}|${r.d1}`}
              totals={res.data.totals} onRowClick={(r) => setOpen(String(r.d0))}
              toolbarLeft={<>
                <Segmented value={dim} onChange={setDim} options={[
                  { value: 'client', label: 'Firma bazında' }, { value: 'client_group', label: 'Firma grubu bazında' },
                ]} />
                <label className="relative">
                  <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted" />
                  <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Müşteri ara" className={cn(inputCls, 'h-8 w-56 pl-8 text-[13px]')} />
                </label>
              </>}
              toolbarRight={<span className="text-[12.5px] text-muted">{res.data.row_count.toLocaleString('tr-TR')} müşteri</span>} />
          </div>
        )}
      </div>
      <CustomerDrawer name={open} dim={dim} onClose={() => setOpen(null)} />
    </div>
  )
}

export function CustomerDrawer({ name, dim = 'client', onClose }: { name: string | null; dim?: 'client' | 'client_group'; onClose: () => void }) {
  const { base } = useWork()
  const f = name ? { [dim]: [name] } : {}
  const tum = useAsync(() => name ? api.post<QueryResult>('/api/analiz/sorgu', {
    date_from: '1900-01-01', date_to: base.date_to, filters: f, direction: 'SATIS_NET', group_by: ['month'],
    measures: ['net_tl', 'profit_tl', 'invoices'],
  }) : Promise.resolve(null), [name, dim, base.date_to])
  const kirilim = useAsync(() => name ? Promise.all(['category', 'brand', 'item'].map((g) => api.post<QueryResult>('/api/analiz/sorgu', {
    date_from: '1900-01-01', date_to: base.date_to, filters: f, direction: 'SATIS_NET', group_by: [g], measures: ['net_tl', 'qty'], limit: 8,
  }))) : Promise.resolve(null), [name, dim, base.date_to])
  const lisans = useAsync(() => name ? api.get<Sale[]>('/api/sales') : Promise.resolve([] as Sale[]), [name])
  const abone = useAsync(() => name ? api.get<Subscription[]>('/api/subscriptions') : Promise.resolve([] as Subscription[]), [name])
  const gruplar = useAsync(() => api.get<{ client_name: string; group_name: string }[]>('/api/firma-gruplari'), [name])

  const toplam = tum.data?.totals
  const aylar = useMemo(() => [...(tum.data?.rows ?? [])].sort((a, b) => String(a.d0).localeCompare(String(b.d0))), [tum.data])
  const lisanslar = (lisans.data ?? []).filter((s) => s.client_name === name)
  const abonelikler = (abone.data ?? []).filter((s) => s.client_name === name)
  const grup = gruplar.data?.find((g) => g.client_name === name)?.group_name

  return (
    <Drawer open={!!name} onClose={onClose} title={name ?? ''} width={860}
      subtitle={aylar.length ? <>İlk alım {fmtDate(String(aylar[0].d0) + '-01').slice(3)}, son alım {fmtDate(String(aylar[aylar.length - 1].d0) + '-01').slice(3)}{grup && <>, firma grubu: {grup}</>}</> : undefined}>
      {tum.loading && <Loading />}
      {toplam && (
        <dl className="mb-6 grid grid-cols-3 gap-4 border-b border-line pb-5">
          <div><dt className="text-[12.5px] text-ink-2">Toplam satış (tüm zamanlar)</dt><dd className="text-[20px] font-semibold"><Figure value={toplam.m_net_tl} type="tl" /></dd></div>
          <div><dt className="text-[12.5px] text-ink-2">Brüt kâr</dt><dd className="text-[20px] font-semibold"><Figure value={toplam.m_profit_tl} type="tl" /></dd></div>
          <div><dt className="text-[12.5px] text-ink-2">Fatura</dt><dd className="tnum text-[20px] font-semibold">{fmt(toplam.m_invoices, 'num')}</dd></div>
        </dl>
      )}
      {aylar.length > 0 && (
        <section className="mb-6">
          <h3 className="mb-2 text-[14px] font-semibold">Aylık alımları</h3>
          <BarChart data={aylar.slice(-48)} xKey="d0" dim="month" type="tl" height={190} series={[{ key: 'm_net_tl', label: 'Satış' }]} />
        </section>
      )}
      {kirilim.data && (
        <section className="mb-6 grid grid-cols-1 gap-6 md:grid-cols-3">
          {(['Kategoriler', 'Markalar', 'En çok aldığı ürünler'] as const).map((t, i) => (
            <div key={t}>
              <h3 className="mb-2.5 text-[14px] font-semibold">{t}</h3>
              <RankBars rows={kirilim.data![i].rows} labelKey="d0" valueKey="m_net_tl" type="tl" color={i === 1 ? 'var(--s3)' : 'var(--s1)'} />
            </div>
          ))}
        </section>
      )}
      <section className="mb-6">
        <h3 className="mb-2 text-[14px] font-semibold">Lisansları ({lisanslar.length})</h3>
        {lisanslar.length === 0 ? <p className="text-[13px] text-muted">Takip edilen lisans yok.</p> : (
          <ul className="divide-y divide-line rounded-xl border border-line">
            {lisanslar.slice(0, 30).map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 px-3.5 py-2 text-[13px]">
                <span className="min-w-0 truncate">{s.product_name}</span>
                <span className="flex shrink-0 items-center gap-2"><span className="tnum text-ink-2">{fmtDate(s.expiration_date)}</span><LicenseBadge s={s} /></span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {abonelikler.length > 0 && (
        <section className="mb-6">
          <h3 className="mb-2 text-[14px] font-semibold">Abonelikleri</h3>
          <ul className="divide-y divide-line rounded-xl border border-line">
            {abonelikler.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 px-3.5 py-2 text-[13px]">
                <span className="min-w-0 truncate">{s.product_name}</span>
                <span className="text-ink-2">son fatura {s.days_since_last} gün önce</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {name && dim === 'client' && <GroupLink name={name} current={grup} groups={[...new Set((gruplar.data ?? []).map((g) => g.group_name))]} onDone={gruplar.reload} />}
    </Drawer>
  )
}

export function LicenseBadge({ s }: { s: Sale }) {
  if (s.status === 'RENEWED') return <Badge tone="good">Yenilendi</Badge>
  if (s.status === 'EXPIRED') return <Badge tone="critical">Süresi doldu</Badge>
  if (s.status === 'NEEDS_DURATION') return <Badge tone="neutral">Süre girilmeli</Badge>
  if (s.days_left <= 30) return <Badge tone="serious">{s.days_left} gün kaldı</Badge>
  if (s.days_left <= 90) return <Badge tone="warning">{s.days_left} gün kaldı</Badge>
  return <Badge tone="neutral">{s.days_left} gün kaldı</Badge>
}

function GroupLink({ name, current, groups, onDone }: { name: string; current?: string; groups: string[]; onDone: () => void }) {
  const [g, setG] = useState(current || name.split(' ')[0] + ' GRUBU')
  const [busy, setBusy] = useState(false)
  return (
    <section className="rounded-xl border border-dashed border-line-strong p-4">
      <h3 className="flex items-center gap-1.5 text-[14px] font-semibold"><Link2 className="size-4" /> Firma grubu</h3>
      <p className="mt-1 text-[13px] text-ink-2">
        Bu firmanın yan/kardeş firmaları varsa aynı gruba ekleyin. Gruptaki firmalar analizlerde birlikte görülebilir ve abonelik
        faturası yan firmaya kesildiğinde abonelik "riskli" görünmez.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input list="gruplar" value={g} onChange={(e) => setG(e.target.value)} className={cn(inputCls, 'w-72')} />
        <datalist id="gruplar">{groups.map((x) => <option key={x} value={x} />)}</datalist>
        <Button variant="primary" loading={busy} disabled={!g.trim()} onClick={async () => {
          setBusy(true)
          try {
            const r = await api.post<{ message: string }>('/api/firma-gruplari', { client_names: [name], group_name: g.trim() })
            toast.ok(r.message)
            onDone()
          } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') } finally { setBusy(false) }
        }}>{current ? 'Grubu değiştir' : 'Gruba ekle'}</Button>
        {current && <Button variant="ghost" onClick={async () => {
          await api.del(`/api/firma-gruplari/${encodeURIComponent(name)}`)
          toast.ok('Firma gruptan çıkarıldı.')
          onDone()
        }}>Gruptan çıkar</Button>}
      </div>
    </section>
  )
}
