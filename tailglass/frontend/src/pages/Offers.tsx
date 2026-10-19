import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { api, type ActionResult, type Offer } from '../lib/api'
import { fmt } from '../lib/format'
import { useAsync, useLocal } from '../lib/hooks'
import { PageHeader } from '../components/Shell'
import { DataGrid, type GridCol } from '../components/data/DataGrid'
import { OfferModal } from './Licenses'
import { Badge, Button, ErrorBox, InfoTip, Loading, Segmented, toast, Figure, Modal } from '../components/ui'

type Tab = 'tumu' | 'PENDING' | 'ACCEPTED' | 'REJECTED'

export default function OffersPage() {
  const res = useAsync(() => api.get<Offer[]>('/api/offers'), [])
  const [tab, setTab] = useLocal<Tab>('teklif.tab', 'tumu')
  const [yeni, setYeni] = useState(false)
  const [silinecek, setSilinecek] = useState<Offer | null>(null)
  const sil = async () => {
    if (!silinecek) return
    try {
      await api.del(`/api/offers/${silinecek.id}`)
      toast.ok('Teklif silindi.')
      res.reload()
    } catch (e) { toast.err(e instanceof Error ? e.message : 'Silinemedi.') }
    setSilinecek(null)
  }
  const list = res.data ?? []
  const rows = list.filter((o) => tab === 'tumu' || o.status === tab)
  const karar = list.filter((o) => o.status !== 'PENDING')
  const oran = karar.length ? (list.filter((o) => o.status === 'ACCEPTED').length / karar.length) * 100 : null
  const bekleyen = list.filter((o) => o.status === 'PENDING').reduce((s, o) => s + (o.currency === 'TRY' ? (o.offer_price || 0) * o.quantity : 0), 0)

  const durum = async (o: Offer, status: Offer['status']) => {
    try {
      const r = await api.post<ActionResult>(`/api/offers/${o.id}/status`, { status })
      toast.ok(r.message)
      res.reload()
    } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') }
  }

  const cols: GridCol<Offer & Record<string, unknown>>[] = [
    { key: '_sil', label: '', type: 'text', width: 64, sortable: false, render: (o) => (
      <button title="Sil" aria-label="Teklifi sil" onClick={async (e) => {
        e.stopPropagation()
        setSilinecek(o)
      }} className="rounded-[var(--radius-ctl)] p-1.5 text-muted hover:text-neg"><Trash2 className="size-4" /></button>
    ) },
    { key: 'offer_date', label: 'Tarih', type: 'date', width: 110 },
    { key: 'status', label: 'Durum', type: 'text', width: 220, render: (o) => (
      <span className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
        {(['PENDING', 'ACCEPTED', 'REJECTED'] as const).map((s) => (
          <button key={s} onClick={() => durum(o, s)} className={o.status === s ? '' : 'opacity-40 hover:opacity-100'}>
            <Badge tone={s === 'ACCEPTED' ? 'good' : s === 'REJECTED' ? 'critical' : 'neutral'}>{s === 'PENDING' ? 'Bekliyor' : s === 'ACCEPTED' ? 'Kabul' : 'Ret'}</Badge>
          </button>
        ))}
      </span>
    ) },
    { key: 'client_name', label: 'Müşteri', type: 'text', width: 260 },
    { key: 'product_name', label: 'Ürün', type: 'text', width: 300 },
    { key: 'quantity', label: 'Adet', type: 'num', width: 80 },
    { key: 'offer_price', label: 'Birim fiyat', type: 'num', width: 130, render: (o) => o.offer_price ? `${fmt(o.offer_price, 'num')} ${o.currency}` : '—' },
    { key: 'sales_rep', label: 'Temsilci', type: 'text', width: 140 },
    { key: 'notes', label: 'Not', type: 'text', hidden: true },
  ]

  return (
    <div>
      <PageHeader title="Teklifler" subtitle="Logo'ya düşmeyen, satış ekibinin verdiği teklifler. Kabul/ret durumu satıra tıklamadan güncellenir."
        actions={<Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setYeni(true)}>Yeni teklif</Button>} />
      {res.error && <ErrorBox message={res.error} onRetry={res.reload} />}
      {!res.data && res.loading && <Loading />}
      {res.data && (
        <div className="flex flex-col gap-5">
          <div className="panel grid grid-cols-1 divide-line max-md:divide-y md:grid-cols-3 md:divide-x">
            <div className="px-5 py-4"><p className="text-[12.5px] text-ink-2">Bekleyen teklif</p><p className="tnum text-[21px] font-semibold">{list.filter((o) => o.status === 'PENDING').length}</p></div>
            <div className="px-5 py-4"><p className="flex items-center gap-1.5 text-[12.5px] text-ink-2">Bekleyen tutar (TL)<InfoTip>Yalnızca TL teklifler toplanır.</InfoTip></p><div className="text-[21px] font-semibold"><Figure value={bekleyen} type="tl" /></div></div>
            <div className="px-5 py-4"><p className="flex items-center gap-1.5 text-[12.5px] text-ink-2">Kazanma oranı<InfoTip>Kabul edilen / karar verilmiş (kabul + ret) teklifler.</InfoTip></p><p className="tnum text-[21px] font-semibold">{oran === null ? '—' : fmt(oran, 'pct')}</p></div>
          </div>
          <div className="panel p-4">
            <DataGrid id="teklifler" pdfPeriod={false} columns={cols} rows={rows as (Offer & Record<string, unknown>)[]} rowKey={(o) => o.id}
              emptyText="Henüz teklif yok. Sağ üstteki düğmeyle ya da Lisanslar sayfasından yenileme teklifi ekleyebilirsiniz."
              toolbarLeft={<Segmented size="sm" value={tab} onChange={setTab} options={[
                { value: 'tumu', label: 'Tümü' }, { value: 'PENDING', label: 'Bekleyen' }, { value: 'ACCEPTED', label: 'Kabul' }, { value: 'REJECTED', label: 'Ret' },
              ]} />} />
          </div>
        </div>
      )}
      <OfferModal sale={yeni ? {} : null} onClose={() => setYeni(false)} onDone={res.reload} />
      <Modal open={!!silinecek} onClose={() => setSilinecek(null)} title="Teklif silinsin mi?"
        footer={<><Button onClick={() => setSilinecek(null)}>Vazgeç</Button><Button variant="danger" onClick={sil}>Teklifi sil</Button></>}>
        <p className="text-[13.5px] text-ink-2">{silinecek?.client_name} için verilen <b className="text-ink">{silinecek?.product_name}</b> teklifi kalıcı olarak silinir.</p>
      </Modal>
    </div>
  )
}
