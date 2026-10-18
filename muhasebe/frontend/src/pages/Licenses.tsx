import { useEffect, useMemo, useState } from 'react'
import { Check, Clock, FileText, Mail, Search, X } from 'lucide-react'
import { api, type ActionResult, type Sale } from '../lib/api'
import { fmt, fmtDate } from '../lib/format'
import { useAsync, useLocal } from '../lib/hooks'
import { useWork } from '../lib/state'
import { PageHeader } from '../components/Shell'
import { DataGrid, type GridCol } from '../components/data/DataGrid'
import { LicenseBadge } from './Customers'
import { Button, ErrorBox, InfoTip, Loading, Modal, Panel, Segmented, Select, cn, inputCls, toast, Figure } from '../components/ui'

type Tab = 'yaklasan' | 'aktif' | 'sure' | 'kayip' | 'yenilendi' | 'tumu'

interface Renewal {
  eski_id: number; musteri: string; eski_urun: string; eski_satis: string; eski_bitis: string
  yeni_id: number; yeni_urun: string; yeni_satis: string; yeni_bitis: string
}

export default function LicensesPage({ params }: { params: URLSearchParams }) {
  const { meta } = useWork()
  const sales = useAsync(() => api.get<Sale[]>('/api/sales'), [])
  const renewals = useAsync(() => api.get<Renewal[]>('/api/renewals'), [])
  const varsayilanGun = meta?.settings?.expiring_soon_days ?? '90'
  const [tab, setTab] = useLocal<Tab>('lisans.tab', 'yaklasan')
  const [gun, setGun] = useLocal('lisans.gun', varsayilanGun)
  const [q, setQ] = useState('')
  const [rep, setRep] = useState('')
  const [mailFor, setMailFor] = useState<Sale | null>(null)
  const [durFor, setDurFor] = useState<Sale | null>(null)
  const [offerFor, setOfferFor] = useState<Sale | null>(null)
  const hedef = Number(params.get('id')) || null

  useEffect(() => {
    if (hedef) setTab('tumu')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hedef])

  const list = sales.data ?? []
  const gunN = Number(gun)
  const sayac = useMemo(() => ({
    yaklasan: list.filter((s) => isActive(s) && s.days_left >= 0 && s.days_left <= gunN).length,
    aktif: list.filter(isActive).length,
    sure: list.filter((s) => s.status === 'NEEDS_DURATION').length,
    kayip: list.filter((s) => s.status === 'EXPIRED' && s.renewal_state !== 'SUSPECT').length,
    yenilendi: list.filter((s) => s.status === 'RENEWED').length,
    tumu: list.length,
  }), [list, gunN])
  const beklenen = list.filter((s) => isActive(s) && s.days_left >= 0 && s.days_left <= gunN).reduce((a, s) => a + (s.price || 0), 0)
  const temsilciler = [...new Set(list.map((s) => s.sales_rep).filter(Boolean))].sort() as string[]

  const rows = useMemo(() => {
    let r = list
    if (tab === 'yaklasan') r = r.filter((s) => isActive(s) && s.days_left >= 0 && s.days_left <= gunN)
    if (tab === 'aktif') r = r.filter(isActive)
    if (tab === 'sure') r = r.filter((s) => s.status === 'NEEDS_DURATION')
    if (tab === 'kayip') r = r.filter((s) => s.status === 'EXPIRED' && s.renewal_state !== 'SUSPECT')
    if (tab === 'yenilendi') r = r.filter((s) => s.status === 'RENEWED')
    if (rep) r = r.filter((s) => s.sales_rep === rep)
    if (q.trim()) {
      const k = q.toLocaleLowerCase('tr')
      r = r.filter((s) => `${s.client_name} ${s.product_name} ${s.license_key ?? ''}`.toLocaleLowerCase('tr').includes(k))
    }
    return [...r].sort((a, b) => tab === 'kayip' || tab === 'yenilendi' ? b.expiration_date.localeCompare(a.expiration_date) : a.days_left - b.days_left)
  }, [list, tab, gunN, q, rep])

  const byId = useMemo(() => new Map(list.map((s) => [s.id, s])), [list])
  const cols: GridCol<Sale & Record<string, unknown>>[] = [
    { key: '_actions', label: '', type: 'text', width: 84, sortable: false, render: (s) => (
      <span className="flex gap-0.5" onClick={(e) => e.stopPropagation()}>
        {s.status === 'NEEDS_DURATION'
          ? <IconBtn title="Süre girin" onClick={() => setDurFor(s)}><Clock className="size-4" /></IconBtn>
          : <IconBtn title="Hatırlatma gönder" onClick={() => setMailFor(s)}><Mail className="size-4" /></IconBtn>}
        <IconBtn title="Yenileme teklifi oluştur" onClick={() => setOfferFor(s)}><FileText className="size-4" /></IconBtn>
      </span>
    ) },
    { key: 'client_name', label: 'Müşteri', type: 'text', width: 280 },
    { key: 'product_name', label: 'Ürün', type: 'text', width: 340 },
    { key: 'sales_rep', label: 'Temsilci', type: 'text', width: 140 },
    { key: 'sale_date', label: 'Satış', type: 'date', width: 105 },
    { key: 'expiration_date', label: 'Bitiş', type: 'date', width: 105 },
    { key: 'status', label: 'Durum', type: 'text', width: 140, render: (s) => (
      <span title={s.status === 'RENEWED' && s.renewed_by ? `Yeni lisans: ${byId.get(s.renewed_by)?.product_name ?? ''} (${fmtDate(byId.get(s.renewed_by)?.expiration_date)})` : undefined}>
        <LicenseBadge s={s} />
      </span>
    ) },
    { key: 'price', label: 'Tutar', type: 'tl', width: 120 },
    { key: 'reminders_sent_count', label: 'Hatırlatma', type: 'num', width: 100, hidden: true },
    { key: 'client_phone', label: 'Telefon', type: 'text', hidden: true },
    { key: 'client_city', label: 'Şehir', type: 'text', hidden: true },
    { key: 'license_key', label: 'Ürün kodu', type: 'text', hidden: true },
  ]

  const tabs: { value: Tab; label: string }[] = [
    { value: 'yaklasan', label: `Yaklaşan (${sayac.yaklasan})` }, { value: 'aktif', label: `Aktif (${sayac.aktif})` },
    { value: 'sure', label: `Süre girilmeli (${sayac.sure})` }, { value: 'kayip', label: `Yenilenmemiş (${sayac.kayip})` },
    { value: 'yenilendi', label: `Yenilendi (${sayac.yenilendi})` }, { value: 'tumu', label: `Tümü (${sayac.tumu})` },
  ]

  return (
    <div>
      <PageHeader title="Lisanslar"
        subtitle="Süreli lisanslar (WatchGuard, FortiGate, ESET…). Bu sayfa seçili dönemden bağımsızdır; listeyi bitiş tarihine göre gösterir."
      />
      {sales.error && <ErrorBox message={sales.error} onRetry={sales.reload} />}
      {!sales.data && sales.loading && <Loading />}
      {sales.data && (
        <div className="flex flex-col gap-5">
          <div className="panel grid grid-cols-2 divide-line max-md:divide-y md:grid-cols-4 md:divide-x">
            {[
              [`${gun} gün içinde dolacak`, fmt(sayac.yaklasan, 'num'), null],
              ['Beklenen yenileme geliri', <Figure value={beklenen} type="tl" />, `Önümüzdeki ${gun} günde süresi dolacak aktif lisansların ilk satış tutarlarının toplamı. Tahmindir; yenileme fiyatı farklı olabilir.`],
              ['Süre girilmeli', fmt(sayac.sure, 'num'), 'Ürün adından süresi anlaşılamayan lisanslar. Süre girilene kadar hatırlatma üretmezler.'],
              ['Yenilenmemiş', fmt(sayac.kayip, 'num'), 'Süresi dolmuş ve yenilendiğine dair kayıt bulunamamış lisanslar.'],
            ].map(([l, v, h]) => (
              <div key={l as string} className="px-5 py-4">
                <p className="flex items-center gap-1.5 text-[12.5px] text-ink-2">{l}{h && <InfoTip>{h}</InfoTip>}</p>
                <div className="tnum mt-0.5 text-[21px] font-semibold">{v}</div>
              </div>
            ))}
          </div>

          {(renewals.data?.length ?? 0) > 0 && <RenewalPanel items={renewals.data!} onDone={() => { renewals.reload(); sales.reload() }} />}

          <div className="panel p-4">
            <DataGrid id="lisanslar" columns={cols} rows={rows as (Sale & Record<string, unknown>)[]} rowKey={(s) => s.id}
              highlightKey={hedef} maxHeight={640}
              onRowClick={(s) => (s.status === 'NEEDS_DURATION' ? setDurFor(s) : setMailFor(s))}
              toolbarLeft={<>
                <Segmented value={tab} onChange={setTab} options={tabs} size="sm" />
              </>}
              toolbarRight={<>
                {tab === 'yaklasan' && <Select label="Süre:" value={gun} onChange={setGun} options={[
                  { value: '7', label: '7 gün' }, { value: '30', label: '30 gün' }, { value: '60', label: '60 gün' }, { value: '90', label: '90 gün' },
                  { value: '180', label: '180 gün' }, { value: '365', label: '1 yıl' },
                ]} />}
                <Select value={rep} onChange={setRep} options={[{ value: '', label: 'Tüm temsilciler' }, ...temsilciler.map((t) => ({ value: t, label: t }))]} />
                <label className="relative">
                  <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted" />
                  <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Müşteri ya da ürün" className={cn(inputCls, 'h-8 w-52 pl-8 text-[13px]')} />
                </label>
              </>} />
          </div>
        </div>
      )}
      <ReminderModal sale={mailFor} onClose={() => setMailFor(null)} />
      <DurationModal sale={durFor} onClose={() => setDurFor(null)} onDone={sales.reload} />
      <OfferModal sale={offerFor} onClose={() => setOfferFor(null)} />
    </div>
  )
}

function isActive(s: Sale) {
  return !['EXPIRED', 'NEEDS_DURATION', 'RENEWED'].includes(s.status)
}

function IconBtn({ title, onClick, children }: { title: string; onClick: () => void; children: React.ReactNode }) {
  return <button title={title} aria-label={title} onClick={onClick} className="rounded-md p-1.5 text-ink-2 hover:bg-brand-soft hover:text-brand-ink">{children}</button>
}

function RenewalPanel({ items, onDone }: { items: Renewal[]; onDone: () => void }) {
  const karar = async (id: number, k: 'CONFIRMED' | 'REJECTED') => {
    try {
      const r = await api.post<ActionResult>(`/api/sales/${id}/renewal`, { karar: k })
      toast.ok(r.message)
      onDone()
    } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') }
  }
  return (
    <Panel title={`Yenileme adayları (${items.length})`}
      hint="Süresi dolmuş bir lisansla aynı müşteriye aynı marka/model ailesinden daha yeni bir satış bulundu ama ürün adı birebir aynı değil. Gerçekten yenileme mi, siz karar verin. Birebir aynı ürün tekrar satıldıysa sistem bunu zaten otomatik 'yenilendi' sayar."
      bodyClass="divide-y divide-line">
      {items.map((r) => (
        <div key={r.eski_id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-[13px]">
          <div className="min-w-0">
            <p className="font-medium">{r.musteri}</p>
            <p className="text-ink-2"><span className="line-through decoration-muted">{r.eski_urun}</span> <span className="text-muted">({fmtDate(r.eski_bitis)} bitti)</span></p>
            <p className="text-ink">{r.yeni_urun} <span className="text-muted">({fmtDate(r.yeni_satis)} satıldı)</span></p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" icon={<Check className="size-4" />} onClick={() => karar(r.eski_id, 'CONFIRMED')}>Yenilendi</Button>
            <Button size="sm" variant="ghost" icon={<X className="size-4" />} onClick={() => karar(r.eski_id, 'REJECTED')}>Değil</Button>
          </div>
        </div>
      ))}
    </Panel>
  )
}

function ReminderModal({ sale, onClose }: { sale: Sale | null; onClose: () => void }) {
  const [busy, setBusy] = useState(false)
  const { meta } = useWork()
  if (!sale) return null
  return (
    <Modal open onClose={onClose} title="Hatırlatma gönder" footer={<>
      <Button variant="ghost" onClick={onClose}>Vazgeç</Button>
      <Button variant="primary" loading={busy} onClick={async () => {
        setBusy(true)
        try {
          const r = await api.post<ActionResult>(`/api/sales/${sale.id}/send-reminder`, { stage: sale.days_left <= 5 ? 'FINAL_REMINDER' : 'FIRST_REMINDER' })
          r.success ? toast.ok(r.message) : toast.err(r.message)
          if (r.success) onClose()
        } catch (e) { toast.err(e instanceof Error ? e.message : 'Gönderilemedi.') } finally { setBusy(false) }
      }}>Gönder</Button>
    </>}>
      <p className="text-[13.5px]"><b>{sale.client_name}</b> — {sale.product_name}</p>
      <p className="mt-1 text-[13px] text-ink-2">Bitiş {fmtDate(sale.expiration_date)} ({sale.days_left >= 0 ? `${sale.days_left} gün kaldı` : 'süresi doldu'})</p>
      <p className="mt-3 text-[13px] text-ink-2">Mail, Ayarlar &gt; E-posta'daki iç alıcılara gider (müşteriye değil). Otomatik hatırlatma günleri: {meta?.settings?.reminder_days ?? '10,5,1'}.</p>
    </Modal>
  )
}

function DurationModal({ sale, onClose, onDone }: { sale: Sale | null; onClose: () => void; onDone: () => void }) {
  const [ay, setAy] = useState(12)
  const [busy, setBusy] = useState(false)
  if (!sale) return null
  return (
    <Modal open onClose={onClose} title="Lisans süresini girin" footer={<>
      <Button variant="ghost" onClick={onClose}>Vazgeç</Button>
      <Button variant="primary" loading={busy} disabled={ay <= 0} onClick={async () => {
        setBusy(true)
        try {
          const r = await api.post<ActionResult>(`/api/sales/${sale.id}/set-duration`, { duration_months: ay })
          toast.ok(r.message)
          onDone()
          onClose()
        } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') } finally { setBusy(false) }
      }}>Kaydet</Button>
    </>}>
      <p className="text-[13.5px]"><b>{sale.client_name}</b> — {sale.product_name}</p>
      <p className="mt-1 text-[13px] text-ink-2">Satış tarihi {fmtDate(sale.sale_date)}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {[12, 24, 36, 60].map((m) => (
          <button key={m} onClick={() => setAy(m)} className={cn('h-9 rounded-[var(--radius-ctl)] border px-3.5 text-[13px]',
            ay === m ? 'border-brand bg-brand-soft font-semibold text-brand-ink' : 'border-line-strong')}>{m / 12} yıl</button>
        ))}
        <label className="flex items-center gap-2 whitespace-nowrap text-[13px]">ya da
          <input type="number" min={1} value={ay} onChange={(e) => setAy(Number(e.target.value))} className={cn(inputCls, 'w-20')} /> ay
        </label>
      </div>
    </Modal>
  )
}

export function OfferModal({ sale, onClose, onDone }: { sale: Partial<Sale> | null; onClose: () => void; onDone?: () => void }) {
  const [f, setF] = useState({ product_name: '', client_name: '', quantity: 1, offer_price: '', currency: 'TRY', notes: '', sales_rep: '' })
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (sale) setF({
      product_name: sale.product_name ?? '', client_name: sale.client_name ?? '', quantity: 1, offer_price: '', currency: 'TRY',
      notes: sale.expiration_date ? `Yenileme teklifi — eski bitiş ${fmtDate(sale.expiration_date)}` : '', sales_rep: sale.sales_rep ?? '',
    })
  }, [sale])
  if (!sale) return null
  return (
    <Modal open onClose={onClose} title="Teklif kaydet" width={520} footer={<>
      <Button variant="ghost" onClick={onClose}>Vazgeç</Button>
      <Button variant="primary" loading={busy} disabled={!f.product_name || !f.client_name} onClick={async () => {
        setBusy(true)
        try {
          const r = await api.post<ActionResult>('/api/offers', { ...f, offer_price: Number(f.offer_price) || 0 })
          toast.ok(r.message)
          onDone?.()
          onClose()
        } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') } finally { setBusy(false) }
      }}>Teklifi kaydet</Button>
    </>}>
      <div className="grid grid-cols-2 gap-3">
        <label className="col-span-2 flex flex-col gap-1 text-[13px]">Müşteri<input value={f.client_name} onChange={(e) => setF({ ...f, client_name: e.target.value })} className={inputCls} /></label>
        <label className="col-span-2 flex flex-col gap-1 text-[13px]">Ürün<input value={f.product_name} onChange={(e) => setF({ ...f, product_name: e.target.value })} className={inputCls} /></label>
        <label className="flex flex-col gap-1 text-[13px]">Adet<input type="number" min={1} value={f.quantity} onChange={(e) => setF({ ...f, quantity: Number(e.target.value) })} className={inputCls} /></label>
        <label className="flex flex-col gap-1 text-[13px]">Fiyat
          <span className="flex gap-1.5">
            <input type="number" value={f.offer_price} onChange={(e) => setF({ ...f, offer_price: e.target.value })} className={inputCls} />
            <select value={f.currency} onChange={(e) => setF({ ...f, currency: e.target.value })} className={cn(inputCls, 'w-24')}>
              <option>TRY</option><option>USD</option><option>EUR</option>
            </select>
          </span>
        </label>
        <label className="col-span-2 flex flex-col gap-1 text-[13px]">Temsilci<input value={f.sales_rep} onChange={(e) => setF({ ...f, sales_rep: e.target.value })} className={inputCls} /></label>
        <label className="col-span-2 flex flex-col gap-1 text-[13px]">Not<textarea rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} className={cn(inputCls, 'h-auto py-2')} /></label>
      </div>
    </Modal>
  )
}

