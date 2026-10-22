import { useEffect, useMemo, useRef, useState } from 'react'
import { BarChart3, Bot, CalendarRange, Layers, MessageSquareText, NotebookPen, Plus, Search, Send, Sparkles, X } from 'lucide-react'
import { api } from '../../lib/api'
import { useAsync, useDebounced } from '../../lib/hooks'
import { iso, today, useWork } from '../../lib/state'
import { rangeLabel } from '../../lib/format'
import type { Cumle } from '../../lib/yorum'
import { Popover, cn, inputCls } from '../ui'
import { BOYUTLAR, DND_TIPI, HAZIRLAR, OLCULER, type Blok } from './bloklar'
import type { Grafik, Kart, Pano } from './model'

// ------------------------------------------------------------------ blok paleti
const BLOK_STIL: Record<Blok['tur'], string> = {
  olcu: 'bg-[#0f8f82] text-white border-[#0b7268]',
  boyut: 'bg-[#1c2624] text-white border-[#0b0f0e] dark:bg-[#dbe5e3] dark:text-[#0b0f0e] dark:border-white',
  hazir: 'bg-[#bd7a1f] text-white border-[#9c6418]',
}

function BlokCip({ b, onTikla }: { b: Blok; onTikla: (id: string) => void }) {
  return (
    <button type="button" draggable title={`${b.aciklama}. Izgaraya ya da bir kartın üstüne sürükleyin, ya da tıklayın.`}
      onDragStart={(e) => { e.dataTransfer.setData(DND_TIPI, b.id); e.dataTransfer.effectAllowed = 'copy' }}
      onClick={() => onTikla(b.id)}
      className={cn('blok relative inline-flex h-8 shrink-0 cursor-grab items-center gap-1.5 border-b-2 pr-3 pl-2.5 text-[12.5px] font-semibold whitespace-nowrap select-none active:cursor-grabbing', BLOK_STIL[b.tur])}>
      {b.ad}
    </button>
  )
}

// En cok kullanilan bloklar gorunur; digerleri "Daha fazla" menusunde (sade gorunum)
const TEMEL = new Set(['satis', 'kar', 'marj', 'adet', 'alis', 'ay', 'musteri', 'urun', 'marka', 'kategori', 'temsilci', 'lisanslar', 'tekrar'])

export function BlokPaleti({ onTikla }: { onTikla: (id: string) => void }) {
  const tum = [...OLCULER, ...BOYUTLAR, ...HAZIRLAR]
  const diger = tum.filter((b) => !TEMEL.has(b.id))
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 py-2">
      {([['Ne?', OLCULER], ['Neye göre?', BOYUTLAR], ['Sadece', HAZIRLAR]] as const).map(([ad, liste]) => (
        <div key={ad} className="flex flex-wrap items-center gap-1.5">
          <span className="mr-0.5 text-[12px] font-medium text-muted">{ad}</span>
          {liste.filter((b) => TEMEL.has(b.id)).map((b) => <BlokCip key={b.id} b={b} onTikla={onTikla} />)}
        </div>
      ))}
      <Popover width={360} trigger={(acik, t) => (
        <button onClick={t} className={cn('inline-flex h-8 items-center gap-1 rounded-[var(--radius-ctl)] border border-dashed px-2.5 text-[12.5px]',
          acik ? 'border-ink text-ink' : 'border-line-strong text-ink-2 hover:text-ink')}>
          <Plus className="size-3.5" /> Daha fazla
        </button>
      )}>
        {() => (
          <div className="flex flex-wrap gap-1.5 p-3">
            {diger.map((b) => <BlokCip key={b.id} b={b} onTikla={onTikla} />)}
          </div>
        )}
      </Popover>
    </div>
  )
}

// ------------------------------------------------------------------ aralik secimi
function hazirAraliklar(ilk?: string | null): { ad: string; from: string; to: string }[] {
  const t = new Date(), y = t.getFullYear(), m = t.getMonth()
  return [
    { ad: 'Bu ay', from: iso(new Date(y, m, 1)), to: today() },
    { ad: 'Son 3 ay', from: iso(new Date(y, m - 2, 1)), to: today() },
    { ad: 'Son 6 ay', from: iso(new Date(y, m - 5, 1)), to: today() },
    { ad: 'Son 12 ay', from: iso(new Date(y, m - 11, 1)), to: today() },
    { ad: 'Bu yıl', from: `${y}-01-01`, to: today() },
    { ad: 'Geçen yıl', from: `${y - 1}-01-01`, to: `${y - 1}-12-31` },
    { ad: 'Tüm veri', from: ilk || `${y - 10}-01-01`, to: today() },
  ]
}

export function AralikSecici({ from, to, onDegis }: { from: string; to: string; onDegis: (f: string, t: string) => void }) {
  const { meta } = useWork()
  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        {hazirAraliklar(meta?.data.first).map((h) => (
          <button key={h.ad} onClick={() => onDegis(h.from, h.to)}
            className={cn('h-7 border px-2.5 text-[12.5px]', 'rounded-[var(--radius-ctl)]',
              h.from === from && h.to === to ? 'border-ink bg-ink text-surface' : 'border-line-strong bg-surface text-ink-2 hover:text-ink')}>
            {h.ad}
          </button>
        ))}
      </div>
      <div className="mt-2.5 flex items-center gap-1.5">
        <input type="date" value={from} max={to} onChange={(e) => e.target.value && onDegis(e.target.value, to)} className={cn(inputCls, 'h-8 px-2 text-[12.5px]')} aria-label="Başlangıç" />
        <span className="text-muted">–</span>
        <input type="date" value={to} min={from} onChange={(e) => e.target.value && onDegis(from, e.target.value)} className={cn(inputCls, 'h-8 px-2 text-[12.5px]')} aria-label="Bitiş" />
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ deger secimi (musteri, urun, lisans...)
const ARAMALI = new Set(['client', 'item', 'client_group', 'item_code'])
const SECILEBILIR = ['client', 'client_group', 'item', 'brand', 'category', 'kind', 'revenue_type', 'salesman', 'city']

function DegerSecici({ dim, secili, aralik, onDegis }: { dim: string; secili: string[]; aralik: { from: string; to: string }; onDegis: (v: string[]) => void }) {
  const [q, setQ] = useState('')
  const dq = useDebounced(q, 250)
  const ops = useAsync<{ v: string; n: number }[]>(async () => {
    if (ARAMALI.has(dim)) return api.get(`/api/ara?boyut=${dim}&q=${encodeURIComponent(dq)}&limit=30`)
    const r = await api.post<Record<string, { v: string; n: number }[]>>('/api/analiz/secenekler', { date_from: aralik.from, date_to: aralik.to })
    return (r[dim] || []).filter((x) => !dq || String(x.v).toLocaleLowerCase('tr').includes(dq.toLocaleLowerCase('tr')))
  }, [dim, dq, aralik.from, aralik.to])
  return (
    <div className="border border-line bg-surface rounded-[var(--radius-ctl)]">
      <label className="flex items-center gap-2 border-b border-line px-2.5">
        <Search className="size-3.5 text-muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={ARAMALI.has(dim) ? 'Aramak için yazın…' : 'Süz…'}
          className="h-8 w-full bg-transparent text-[12.5px] outline-none" />
      </label>
      <ul className="scroll-thin max-h-48 overflow-auto py-1">
        {(ops.data || []).slice(0, 60).map((o) => {
          const on = secili.includes(String(o.v))
          return (
            <li key={String(o.v)}>
              <label className="flex cursor-pointer items-center gap-2 px-2.5 py-1 text-[12.5px] hover:bg-surface-2">
                <input type="checkbox" checked={on} className="accent-[var(--brand)]"
                  onChange={() => onDegis(on ? secili.filter((x) => x !== String(o.v)) : [...secili, String(o.v)])} />
                <span className="min-w-0 flex-1 truncate">{String(o.v)}</span>
              </label>
            </li>
          )
        })}
        {ops.data && !ops.data.length && <li className="px-2.5 py-2 text-[12px] text-muted">{ARAMALI.has(dim) && !dq ? 'Aramak için yazın' : 'Sonuç yok'}</li>}
      </ul>
    </div>
  )
}

function Bolum({ baslik, children, ikon: I }: { baslik: string; children: React.ReactNode; ikon?: typeof Layers }) {
  return (
    <section className="border-b border-line px-4 py-3.5 last:border-b-0">
      <h4 className="mb-2.5 flex items-center gap-1.5 text-[12.5px] font-semibold text-ink">{I && <I className="size-3.5 text-muted" />}{baslik}</h4>
      {children}
    </section>
  )
}

export function SolPanel({ pano, kart, etiket, onPano, onKart }: {
  pano: Pano; kart: Kart | null; etiket: (d: string) => string
  onPano: (p: Pano) => void; onKart: (k: Kart) => void
}) {
  const [eklenecek, setEklenecek] = useState('')
  if (!kart) {
    return (
      <div>
        <Bolum baslik="Analizin tarih aralığı" ikon={CalendarRange}>
          <AralikSecici from={pano.aralik.from} to={pano.aralik.to} onDegis={(from, to) => onPano({ ...pano, aralik: { from, to } })} />
          <p className="mt-2 text-[12px] text-muted">Kendi aralığı olmayan bütün kartlar bu aralığı kullanır.</p>
        </Bolum>
        <Bolum baslik="Nasıl kullanılır?" ikon={Sparkles}>
          <ol className="list-decimal space-y-1.5 pl-4 text-[12.5px] text-ink-2">
            <li><b className="font-semibold text-ink">Satış</b> gibi bir ölçü bloğunu ortadaki boş hücreye sürükleyin.</li>
            <li>Üstüne <b className="font-semibold text-ink">Aylara göre</b>, <b className="font-semibold text-ink">Müşteri</b> gibi bir blok bırakın.</li>
            <li>Kartı seçip burada aralığı, müşteriyi, ürünü daraltın.</li>
            <li>Sağda analiz kendiliğinden yazılır.</li>
          </ol>
        </Bolum>
      </div>
    )
  }
  const ar = kart.aralik.tur === 'pano' ? pano.aralik : { from: kart.aralik.from, to: kart.aralik.to }
  const filtreler = Object.entries(kart.filtre)
  return (
    <div>
      <Bolum baslik="Tarih aralığı" ikon={CalendarRange}>
        <div className="mb-2.5 flex border border-line-strong p-0.5 text-[12.5px] rounded-[var(--radius-ctl)]">
          {(['pano', 'ozel'] as const).map((t) => (
            <button key={t} onClick={() => onKart({ ...kart, aralik: t === 'pano' ? { tur: 'pano', from: '', to: '' } : { tur: 'ozel', ...pano.aralik } })}
              className={cn('h-7 flex-1 rounded-[var(--radius-ctl)]', kart.aralik.tur === t ? 'bg-ink font-medium text-surface' : 'text-ink-2 hover:text-ink')}>
              {t === 'pano' ? 'Analizin aralığı' : 'Bu karta özel'}
            </button>
          ))}
        </div>
        {kart.aralik.tur === 'ozel'
          ? <AralikSecici from={ar.from} to={ar.to} onDegis={(from, to) => onKart({ ...kart, aralik: { tur: 'ozel', from, to } })} />
          : <p className="text-[12.5px] text-ink-2">{rangeLabel(ar.from, ar.to)}</p>}
      </Bolum>

      <Bolum baslik="Neleri kapsasın?" ikon={Layers}>
        {filtreler.map(([d, v]) => (
          <div key={d} className="mb-3">
            <div className="mb-1.5 flex items-center justify-between text-[12.5px]">
              <span className="font-medium text-ink">{etiket(d)}{v.length ? ` (${v.length})` : ''}</span>
              <button onClick={() => { const f = { ...kart.filtre }; delete f[d]; onKart({ ...kart, filtre: f }) }} className="text-muted hover:text-neg" aria-label="Filtreyi kaldır"><X className="size-3.5" /></button>
            </div>
            <DegerSecici dim={d} secili={v} aralik={ar} onDegis={(yeni) => onKart({ ...kart, filtre: { ...kart.filtre, [d]: yeni } })} />
          </div>
        ))}
        <div className="flex gap-1.5">
          <select value={eklenecek} onChange={(e) => setEklenecek(e.target.value)} className={cn(inputCls, 'h-8 flex-1 py-0 text-[12.5px]')}>
            <option value="">Seçim ekle: müşteri, ürün, marka…</option>
            {SECILEBILIR.filter((d) => !(d in kart.filtre)).map((d) => <option key={d} value={d}>{etiket(d)}</option>)}
          </select>
          <button disabled={!eklenecek} onClick={() => { onKart({ ...kart, filtre: { ...kart.filtre, [eklenecek]: [] } }); setEklenecek('') }}
            className="grid size-8 place-items-center border border-line-strong text-ink-2 hover:text-ink disabled:opacity-40 rounded-[var(--radius-ctl)]" aria-label="Seçim ekle"><Plus className="size-4" /></button>
        </div>
      </Bolum>

      <Bolum baslik="Görünüm" ikon={BarChart3}>
        <div className="flex flex-wrap gap-1 text-[12px]">
          {([['otomatik', 'Otomatik'], ['sayi', 'Sayı'], ['cubuk', 'Çubuk'], ['cizgi', 'Çizgi'], ['tablo', 'Tablo']] as [Grafik, string][]).map(([g, ad]) => (
            <button key={g} onClick={() => onKart({ ...kart, grafik: g })}
              className={cn('h-7 rounded-[var(--radius-ctl)] border px-2.5', kart.grafik === g ? 'border-ink bg-ink font-medium text-surface' : 'border-line-strong text-ink-2 hover:text-ink')}>{ad}</button>
          ))}
        </div>
        {kart.boyut && (
          <label className="mt-3 flex items-center justify-between text-[12.5px] text-ink-2">Gösterilecek kalem
            <select value={kart.ust} onChange={(e) => onKart({ ...kart, ust: Number(e.target.value) })} className={cn(inputCls, 'h-8 w-24 py-0 text-[12.5px]')}>
              {[5, 10, 20, 50].map((n) => <option key={n} value={n}>İlk {n}</option>)}
            </select>
          </label>
        )}
        {(kart.boyut || kart.seri) && (
          <div className="mt-3 flex flex-wrap gap-1.5 text-[12px]">
            {kart.boyut && <Etiket ad={`Kırılım: ${etiket(kart.boyut)}`} onSil={() => onKart({ ...kart, boyut: kart.seri, seri: undefined })} />}
            {kart.seri && <Etiket ad={`İkinci kırılım: ${etiket(kart.seri)}`} onSil={() => onKart({ ...kart, seri: undefined })} />}
          </div>
        )}
      </Bolum>

      <Bolum baslik="Bu kartın notu" ikon={NotebookPen}>
        <textarea value={kart.not} onChange={(e) => onKart({ ...kart, not: e.target.value })} rows={3}
          placeholder="Sunumda söyleyeceğiniz ya da sonra bakılacak şeyler…" className={cn(inputCls, 'h-auto py-2 text-[12.5px]')} />
      </Bolum>
    </div>
  )
}

function Etiket({ ad, onSil }: { ad: string; onSil: () => void }) {
  return (
    <span className="inline-flex h-6 items-center gap-1 border border-line-strong bg-surface-2 pr-1 pl-2 rounded-[var(--radius-ctl)]">{ad}
      <button onClick={onSil} className="text-muted hover:text-neg" aria-label={`${ad} kaldır`}><X className="size-3" /></button>
    </span>
  )
}

// ------------------------------------------------------------------ sag panel: analiz, notlar, sohbet
export interface AnalizParcasi { id: string; baslik: string; cumleler: Cumle[] }

const TON: Record<Cumle['ton'], string> = {
  notr: 'border-line-strong', iyi: 'border-[var(--pos)]', kotu: 'border-[var(--neg)]', dikkat: 'border-[var(--warning)]',
}

/** Metni harf harf yazar; yalnizca yeni gelen cumlelerde (sunumda "anlatiyor" hissi). */
function Yazan({ metin }: { metin: string }) {
  const [n, setN] = useState(0)
  useEffect(() => {
    setN(0)
    const azalt = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (azalt) { setN(metin.length); return }
    const t = setInterval(() => setN((x) => (x >= metin.length ? (clearInterval(t), x) : x + 3)), 16)
    return () => clearInterval(t)
  }, [metin])
  return <>{metin.slice(0, n)}{n < metin.length && <span className="ml-px inline-block h-3.5 w-1.5 animate-pulse bg-brand align-middle" />}</>
}

export function SagPanel({ parcalar, baglam, seciliId, pano, kartlar, etiket, onPano, onKartNot, onSec }: {
  parcalar: AnalizParcasi[]; baglam: string; seciliId: string | null; pano: Pano; kartlar: Kart[]; etiket: (d: string) => string
  onPano: (p: Pano) => void; onKartNot: (id: string, not: string) => void; onSec: (id: string) => void
}) {
  const [sekme, setSekme] = useState<'analiz' | 'not' | 'sohbet'>('analiz')
  const kutu = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!seciliId) return
    kutu.current?.querySelector(`[data-parca="${seciliId}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [seciliId])
  const sirali = useMemo(() => parcalar, [parcalar])
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div role="tablist" className="flex border-b border-line text-[12.5px]">
        {([['analiz', 'Analiz', Sparkles], ['not', 'Notlar', NotebookPen], ['sohbet', 'Sohbet', MessageSquareText]] as const).map(([k, ad, I]) => (
          <button key={k} role="tab" aria-selected={sekme === k} onClick={() => setSekme(k)}
            className={cn('-mb-px flex flex-1 items-center justify-center gap-1.5 border-b-2 py-2.5', sekme === k ? 'border-ink font-semibold text-ink' : 'border-transparent text-ink-2 hover:text-ink')}>
            <I className="size-3.5" />{ad}
          </button>
        ))}
      </div>

      {sekme === 'analiz' && (
        <div ref={kutu} className="scroll-thin flex-1 overflow-y-auto px-4 py-4">
          {!sirali.length && <p className="text-[13px] text-muted">Izgaraya bir kart eklediğinizde analizi burada yazılır.</p>}
          {sirali.map((p) => (
            <article key={p.id} data-parca={p.id} onClick={() => onSec(p.id)}
              className={cn('mb-5 cursor-pointer transition-opacity', seciliId && seciliId !== p.id && 'opacity-55 hover:opacity-100')}>
              <h5 className="mb-2 text-[13px] font-semibold text-ink first-letter:uppercase">{p.baslik}</h5>
              <div className="space-y-2">
                {p.cumleler.map((c, i) => (
                  <p key={i + c.metin} className={cn('border-l-2 pl-2.5 text-[13px] leading-relaxed text-ink-2', TON[c.ton])}><Yazan metin={c.metin} /></p>
                ))}
              </div>
            </article>
          ))}
          {!!sirali.length && <p className="mt-2 border-t border-line pt-3 text-[11.5px] text-muted">Bu yorumlar verideki zirve, eğilim, olağandışı dönem ve yoğunlaşma kurallarıyla üretildi. Yapay zekâ bağlandığında daha ayrıntılı anlatım burada görünecek.</p>}
        </div>
      )}

      {sekme === 'not' && (
        <div className="scroll-thin flex-1 overflow-y-auto px-4 py-4">
          <label className="block text-[12.5px] font-semibold text-ink">Analiz notu</label>
          <textarea value={pano.not} onChange={(e) => onPano({ ...pano, not: e.target.value })} rows={5}
            placeholder="Toplantıda konuşulanlar, kararlar, sonra bakılacaklar…" className={cn(inputCls, 'mt-1.5 h-auto py-2 text-[13px]')} />
          {kartlar.map((k) => (
            <div key={k.id} className="mt-4">
              <label className="block truncate text-[12.5px] font-medium text-ink-2 first-letter:uppercase">{etiketBaslik(k, etiket)}</label>
              <textarea value={k.not} onChange={(e) => onKartNot(k.id, e.target.value)} rows={2}
                className={cn(inputCls, 'mt-1 h-auto py-1.5 text-[12.5px]')} placeholder="Bu kart için not…" />
            </div>
          ))}
        </div>
      )}

      {sekme === 'sohbet' && <Sohbet baglam={baglam} />}
    </div>
  )
}

function etiketBaslik(k: Kart, etiket: (d: string) => string) {
  const ad = OLCULER.find((o) => o.id === k.olcu)?.ad ?? 'Kart'
  return k.boyut ? `${etiket(k.boyut)} bazında ${ad.toLocaleLowerCase('tr')}` : ad
}

// ------------------------------------------------------------------ yapay zeka sohbeti
interface Mesaj { rol: 'kullanici' | 'asistan'; metin: string; hata?: boolean }
const ORNEK_SORULAR = ['Bu dönemdeki düşüşün nedeni ne olabilir?', 'Hangi müşteriye odaklanmalıyız?', 'Bu panoyu yöneticiye üç maddede özetle.']

function Sohbet({ baglam }: { baglam: string }) {
  const durum = useAsync(() => api.get<{ acik: boolean; ad?: string; model?: string; eksik?: string | null }>('/api/ai/durum'), [])
  const [mesajlar, setMesajlar] = useState<Mesaj[]>([])
  const [yazi, setYazi] = useState('')
  const [bekliyor, setBekliyor] = useState(false)
  const alt = useRef<HTMLDivElement>(null)
  useEffect(() => { alt.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [mesajlar, bekliyor])

  const gonder = async (soru: string) => {
    const metin = soru.trim()
    if (!metin || bekliyor) return
    const yeni: Mesaj[] = [...mesajlar.filter((m) => !m.hata), { rol: 'kullanici', metin }]
    setMesajlar(yeni); setYazi(''); setBekliyor(true)
    try {
      const r = await api.post<{ success: boolean; yanit?: string; message?: string }>('/api/ai/sohbet', {
        mesajlar: yeni.map(({ rol, metin }) => ({ rol, metin })), baglam,
      })
      setMesajlar([...yeni, r.success ? { rol: 'asistan', metin: (r.yanit || '(boş yanıt)').replace(/\*\*(.+?)\*\*/g, '$1').replace(/^#{1,6}\s+/gm, '') } : { rol: 'asistan', metin: r.message || 'Yanıt alınamadı.', hata: true }])
    } catch (e) {
      setMesajlar([...yeni, { rol: 'asistan', metin: e instanceof Error ? e.message : 'Yanıt alınamadı.', hata: true }])
    } finally { setBekliyor(false) }
  }

  if (durum.data && !durum.data.acik) {
    return (
      <div className="flex-1 px-4 py-4 text-[13px] text-ink-2">
        <div className="flex items-start gap-2.5">
          <span className="grid size-7 shrink-0 place-items-center bg-ink text-surface rounded-[var(--radius-ctl)]"><Bot className="size-4" /></span>
          <p>{durum.data.eksik ?? 'Yapay zekâ kapalı.'} Ayarlar &gt; Yapay zekâ bölümünden bir sağlayıcı seçin. Groq'un ücretsiz katmanıyla başlayabilirsiniz. Asistan yalnızca ekrandaki kartların özetini ve notlarınızı görür, ham faturaları görmez.</p>
        </div>
        <a href="#/ayarlar" onClick={() => { try { localStorage.setItem('ayar.bolum', JSON.stringify('ai')) } catch { /* yok */ } }}
          className="mt-4 inline-flex h-9 items-center border border-line-strong px-3 text-[13px] font-medium text-ink hover:bg-surface-2 rounded-[var(--radius-ctl)]">Ayarlara git</a>
      </div>
    )
  }
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="scroll-thin flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
        {!mesajlar.length && (
          <>
            <p className="text-[13px] text-ink-2">Panodaki kartlar hakkında soru sorun.{durum.data?.ad && <span className="text-muted"> ({durum.data.ad} · {durum.data.model})</span>}</p>
            <div className="space-y-1.5">
              {ORNEK_SORULAR.map((q) => (
                <button key={q} onClick={() => gonder(q)} className="block w-full border border-line px-3 py-2 text-left text-[12.5px] text-ink-2 hover:border-line-strong hover:text-ink rounded-[var(--radius-ctl)]">{q}</button>
              ))}
            </div>
          </>
        )}
        {mesajlar.map((m, i) => (
          <div key={i} className={cn('text-[13px] leading-relaxed', m.rol === 'kullanici' ? 'ml-6 bg-surface-2 px-3 py-2 text-ink rounded-[var(--radius-ctl)]' : 'whitespace-pre-wrap text-ink-2', m.hata && 'border-l-2 border-[var(--neg)] pl-2.5 text-[var(--neg)]')}>
            {m.metin}
          </div>
        ))}
        {bekliyor && <p className="text-[12.5px] text-muted">Yanıt yazılıyor…</p>}
        <div ref={alt} />
      </div>
      <form className="flex items-center gap-2 border-t border-line px-4 py-3" onSubmit={(e) => { e.preventDefault(); gonder(yazi) }}>
        <input value={yazi} onChange={(e) => setYazi(e.target.value)} placeholder="Soru yazın…" aria-label="Soru" className={cn(inputCls, 'h-9 flex-1 text-[13px]')} />
        <button type="submit" disabled={!yazi.trim() || bekliyor} className="grid size-9 place-items-center bg-ink text-surface disabled:opacity-40 rounded-[var(--radius-ctl)]" aria-label="Gönder"><Send className="size-4" /></button>
      </form>
    </div>
  )
}
