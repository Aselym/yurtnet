import { useEffect, useMemo, useRef, useState } from 'react'
import { Download, GripVertical, ImageDown, Maximize2, MoveHorizontal, StickyNote, X } from 'lucide-react'
import { api, download, type QueryResult } from '../../lib/api'
import { fmt, fmtPeriodKey, fmtShort, fmtSpoken, isNum, rangeLabel } from '../../lib/format'
import { BarChart, LineChart, RankBars, SERIES } from '../charts/Charts'
import { cn } from '../ui'
import { DND_TIPI, ZAMAN_BOYUTLARI } from './bloklar'
import { dilimAraligi, istek, kartAraligi, kartBasligi, olcuBlok, type Kart, type KartVeri, type Pano } from './model'

export const KART_TIPI = 'application/x-tailglass-kart'

/** SVG grafigi PNG olarak indirir; CSS degiskenleriyle verilen renkler gercek renklere cevrilir. */
export function grafikPng(kap: HTMLElement | null, ad: string) {
  const svg = kap?.querySelector('svg')
  if (!svg) return
  const kopya = svg.cloneNode(true) as SVGSVGElement
  const kaynak = svg.querySelectorAll('*'), hedef = kopya.querySelectorAll('*')
  kaynak.forEach((el, i) => {
    const st = getComputedStyle(el)
    const h = hedef[i] as SVGElement
    for (const p of ['fill', 'stroke', 'opacity', 'font-size', 'font-family', 'font-weight']) h.style.setProperty(p, st.getPropertyValue(p))
  })
  const { width, height } = svg.getBoundingClientRect()
  kopya.setAttribute('width', String(width)); kopya.setAttribute('height', String(height))
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(kopya)], { type: 'image/svg+xml' }))
  const img = new Image()
  img.onload = () => {
    const c = document.createElement('canvas')
    c.width = width * 2; c.height = height * 2
    const ctx = c.getContext('2d')!
    ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--surface') || '#fff'
    ctx.fillRect(0, 0, c.width, c.height)
    ctx.scale(2, 2); ctx.drawImage(img, 0, 0)
    const a = document.createElement('a')
    a.download = `${ad}.png`; a.href = c.toDataURL('image/png'); a.click()
    URL.revokeObjectURL(url)
  }
  img.src = url
}

export function KartGorunum({ k, p, secili, etiket, onSec, onBlok, onTasi, onSil, onDegis, onVeri, onOdak }: {
  k: Kart; p: Pano; secili: boolean; etiket: (d: string) => string
  onSec: () => void; onBlok: (blokId: string) => void; onTasi: (kaynakId: string) => void
  onSil: () => void; onDegis: (k: Kart) => void; onVeri: (v: KartVeri | null) => void; onOdak: () => void
}) {
  const [veri, setVeri] = useState<KartVeri | null>(null)
  const [hata, setHata] = useState<string | null>(null)
  const [yukleniyor, setYukleniyor] = useState(true)
  const [ust, setUst] = useState(false)
  const govde = useRef<HTMLDivElement>(null)
  const b = olcuBlok(k)
  const mkey = `m_${b.olcu}`
  const tip = b.tip ?? 'num'
  const zaman = !!k.boyut && ZAMAN_BOYUTLARI.has(k.boyut)
  const istekJson = JSON.stringify(istek(k, p))
  const baslik = kartBasligi(k, etiket)
  const ar = kartAraligi(k, p)

  useEffect(() => {
    let iptal = false
    setYukleniyor(true); setHata(null)
    ;(async () => {
      try {
        const [sonuc, onceki] = await Promise.all([
          api.post<QueryResult>('/api/analiz/sorgu', istek(k, p)),
          api.post<QueryResult>('/api/analiz/sorgu', { ...istek(k, p, true), group_by: [] }),
        ])
        let surucu: KartVeri['surucu']
        // Zaman serisinde zirve donemini kim tasidi? (yorum motoru "neden" cumlesi icin)
        if (zaman && !k.seri && tip !== 'pct' && sonuc.rows.length >= 3) {
          const zirve = [...sonuc.rows].sort((a, c) => Number(c[mkey]) - Number(a[mkey]))[0]
          const dilim = dilimAraligi(String(zirve.d0), k.boyut!)
          if (dilim) {
            const r = await api.post<QueryResult>('/api/analiz/sorgu', {
              ...istek(k, p), date_from: dilim[0], date_to: dilim[1], group_by: ['client'], limit: 3,
            })
            surucu = { donem: String(zirve.d0), toplam: Number(r.totals[mkey]) || 0,
              satirlar: r.rows.map((x) => ({ ad: String(x.d0), deger: Number(x[mkey]) || 0 })) }
          }
        }
        if (!iptal) { const v = { sonuc, onceki, surucu }; setVeri(v); onVeri(v) }
      } catch (e) {
        if (!iptal) { setHata(e instanceof Error ? e.message : 'Yüklenemedi'); onVeri(null) }
      } finally { if (!iptal) setYukleniyor(false) }
    })()
    return () => { iptal = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [istekJson])

  // ikinci kirilim varsa: x = d0, seriler = d1'in en buyuk 5 degeri + Diger
  const seriVeri = useMemo(() => {
    if (!veri || !k.seri) return null
    const toplamlar = new Map<string, number>()
    for (const r of veri.sonuc.rows) toplamlar.set(String(r.d1), (toplamlar.get(String(r.d1)) || 0) + (Number(r[mkey]) || 0))
    const ust5 = [...toplamlar.entries()].sort((a, c) => c[1] - a[1]).slice(0, 5).map(([x]) => x)
    const satir = new Map<string, Record<string, unknown>>()
    for (const r of veri.sonuc.rows) {
      const x = String(r.d0)
      const s = satir.get(x) ?? { d0: x }
      const anahtar = ust5.includes(String(r.d1)) ? `s::${r.d1}` : 's::Diğer'
      s[anahtar] = (Number(s[anahtar]) || 0) + (Number(r[mkey]) || 0)
      satir.set(x, s)
    }
    const seriler = [...ust5.map((x) => `s::${x}`), ...(toplamlar.size > 5 ? ['s::Diğer'] : [])]
    const satirlar = [...satir.values()]
    if (zaman) satirlar.sort((a, c) => String(a.d0).localeCompare(String(c.d0)))
    else satirlar.sort((a, c) => seriler.reduce((t, s) => t + (Number(c[s]) || 0), 0) - seriler.reduce((t, s) => t + (Number(a[s]) || 0), 0))
    return { satirlar: satirlar.slice(0, zaman ? undefined : k.ust), seriler: seriler.map((s, i) => ({ key: s, label: s === 's::Diğer' ? 'Diğer' : fmtPeriodKey(s.slice(3), k.seri), color: SERIES[i] })) }
  }, [veri, k.seri, k.ust, mkey, zaman])

  const grafik = k.grafik === 'otomatik' ? (!k.boyut ? 'sayi' : zaman ? 'cubuk' : 'cubuk') : k.grafik
  const toplam = veri?.sonuc.totals?.[mkey]
  const onceki = veri?.onceki?.totals?.[mkey]
  const degisim = isNum(toplam) && isNum(onceki) && onceki !== 0 ? (tip === 'pct' ? toplam - onceki : ((toplam - onceki) / Math.abs(onceki)) * 100) : null
  const satirlar = veri ? (zaman ? [...veri.sonuc.rows].sort((a, c) => String(a.d0).localeCompare(String(c.d0))) : veri.sonuc.rows.slice(0, k.ust)) : []
  const filtreSayisi = Object.values(k.filtre).reduce((a, v) => a + v.length, 0)

  return (
    <article
      onClick={onSec}
      onDragOver={(e) => { if (e.dataTransfer.types.includes(DND_TIPI) || e.dataTransfer.types.includes(KART_TIPI)) { e.preventDefault(); setUst(true) } }}
      onDragLeave={() => setUst(false)}
      onDrop={(e) => {
        e.preventDefault(); setUst(false)
        const blok = e.dataTransfer.getData(DND_TIPI), kart = e.dataTransfer.getData(KART_TIPI)
        if (blok) onBlok(blok)
        else if (kart && kart !== k.id) onTasi(kart)
      }}
      className={cn('@container panel group/kart relative flex min-h-[300px] flex-col overflow-hidden transition-shadow',
        k.genis === 2 && '@2xl:col-span-2', secili && 'ring-2 ring-brand', ust && 'ring-2 ring-brand ring-offset-2 ring-offset-canvas')}>
      <header className="flex items-start gap-2 border-b border-line px-3.5 py-2.5">
        <span draggable onDragStart={(e) => { e.dataTransfer.setData(KART_TIPI, k.id); e.dataTransfer.effectAllowed = 'move' }}
          title="Kartı başka bir hücreye sürükleyin" className="mt-0.5 cursor-grab text-muted hover:text-ink active:cursor-grabbing">
          <GripVertical className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[14px] font-semibold text-ink first-letter:uppercase">{baslik}</h3>
          <p className="mt-0.5 truncate text-[12px] text-muted">
            {rangeLabel(ar.from, ar.to)}{k.aralik.tur === 'ozel' && ' (kartın kendi aralığı)'}
            {filtreSayisi > 0 && <> · {Object.entries(k.filtre).filter(([, v]) => v.length).map(([d, v]) => `${etiket(d)}: ${v.length > 2 ? `${v.length} seçim` : v.join(', ')}`).join(' · ')}</>}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-0.5 opacity-60 transition-opacity group-hover/kart:opacity-100" onClick={(e) => e.stopPropagation()}>
          {k.not && <StickyNote className="mr-1 size-3.5 text-[var(--warning)]" aria-label="Not var" />}
          <Ikon ad="Excel olarak indir" onClick={() => download('/api/export/sorgu', { request: istek(k, p), title: baslik, filename: baslik }).catch(() => {})}><Download className="size-4" /></Ikon>
          {grafik !== 'sayi' && grafik !== 'tablo' && <Ikon ad="Grafiği görsel olarak indir" onClick={() => grafikPng(govde.current, baslik)}><ImageDown className="size-4" /></Ikon>}
          <Ikon ad={k.genis === 2 ? 'Panoda dar göster' : 'Panoda geniş göster'} onClick={() => onDegis({ ...k, genis: k.genis === 2 ? 1 : 2 })}><MoveHorizontal className="size-4" /></Ikon>
          <Ikon ad="Tam ekran ayrıntılı analiz" onClick={onOdak}><Maximize2 className="size-4" /></Ikon>
          <Ikon ad="Kartı kaldır" onClick={onSil}><X className="size-4" /></Ikon>
        </div>
      </header>

      <div ref={govde} className={cn('relative flex-1 px-3.5 py-3 transition-opacity', yukleniyor && 'opacity-50')}>
        {hata && <p className="py-8 text-center text-[13px] text-neg">{hata}</p>}
        {!hata && veri && grafik === 'sayi' && (
          <div className="flex h-full flex-col justify-center py-4">
            <p className="display tnum text-[26px] leading-none font-semibold text-ink @xs:text-[32px] @sm:text-[40px]">{fmt(toplam, tip)}</p>
            {tip !== 'pct' && tip !== 'num' && <p className="mt-1.5 text-[13px] text-ink-2">{fmtSpoken(toplam, tip)}</p>}
            {degisim !== null && (
              <p className={cn('mt-3 text-[13px] font-medium', degisim >= 0 ? 'text-pos' : 'text-neg')}>
                {degisim >= 0 ? '↑' : '↓'} {tip === 'pct' ? `${Math.abs(degisim).toLocaleString('tr-TR', { maximumFractionDigits: 1 })} puan` : `%${Math.abs(degisim).toLocaleString('tr-TR', { maximumFractionDigits: 1 })}`}
                <span className="font-normal text-muted"> önceki eşit döneme göre ({fmtShort(onceki, tip)})</span>
              </p>
            )}
            {!k.boyut && <p className="mt-5 text-[12.5px] text-muted">Kırılım için bu kartın üstüne "Müşteri", "Aylara göre" gibi bir blok bırakın.</p>}
          </div>
        )}
        {!hata && veri && grafik !== 'sayi' && k.boyut && satirlar.length === 0 && <p className="py-10 text-center text-[13px] text-muted">Bu aralıkta veri yok.</p>}
        {!hata && veri && grafik === 'tablo' && satirlar.length > 0 && (
          <div className="scroll-thin max-h-[300px] overflow-auto">
            <table className="w-full text-[13px]">
              <tbody className="divide-y divide-line">
                {satirlar.map((r, i) => (
                  <tr key={i}><td className="py-1.5 pr-3">{fmtPeriodKey(r.d0, k.boyut)}{k.seri ? ` / ${r.d1}` : ''}</td>
                    <td className="tnum py-1.5 text-right font-medium">{fmt(r[mkey], tip)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!hata && veri && (grafik === 'cubuk' || grafik === 'cizgi') && satirlar.length > 0 && (
          seriVeri
            ? (grafik === 'cizgi' && zaman
              ? <LineChart data={seriVeri.satirlar} xKey="d0" dim={k.boyut} type={tip} height={k.genis === 2 ? 260 : 220} series={seriVeri.seriler} />
              : <BarChart data={seriVeri.satirlar} xKey="d0" dim={k.boyut} type={tip} height={k.genis === 2 ? 260 : 220} series={seriVeri.seriler} />)
            : zaman
              ? (grafik === 'cizgi'
                ? <LineChart data={satirlar} xKey="d0" dim={k.boyut} type={tip} height={k.genis === 2 ? 260 : 220} series={[{ key: mkey, label: b.ad, color: 'var(--rev-product)' }]} />
                : <BarChart data={satirlar} xKey="d0" dim={k.boyut} type={tip} height={k.genis === 2 ? 260 : 220} series={[{ key: mkey, label: b.ad, color: 'var(--rev-product)' }]} />)
              : <div className="scroll-thin max-h-[300px] overflow-auto pr-1">
                  <RankBars rows={satirlar} labelKey="d0" valueKey={mkey} type={tip} color="var(--s1)" />
                </div>
        )}
        {seriVeri && grafik !== 'tablo' && grafik !== 'sayi' && (
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-ink-2">
            {seriVeri.seriler.map((s) => <span key={s.key} className="inline-flex items-center gap-1"><span className="size-2 rounded-[1px]" style={{ background: s.color }} />{s.label}</span>)}
          </div>
        )}
      </div>
    </article>
  )
}

function Ikon({ ad, onClick, children }: { ad: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" title={ad} aria-label={ad} onClick={onClick}
      className="grid size-7 place-items-center rounded-[var(--radius-ctl)] text-ink-2 hover:bg-surface-2 hover:text-ink">
      {children}
    </button>
  )
}

/** Bos hucre: blok birakilinca yeni kart olusur. */
export function BosHucre({ onBlok, onTasi, ilk }: { onBlok: (blokId: string) => void; onTasi: (kartId: string) => void; ilk?: boolean }) {
  const [ust, setUst] = useState(false)
  return (
    <div
      onDragOver={(e) => { if (e.dataTransfer.types.includes(DND_TIPI) || e.dataTransfer.types.includes(KART_TIPI)) { e.preventDefault(); setUst(true) } }}
      onDragLeave={() => setUst(false)}
      onDrop={(e) => {
        e.preventDefault(); setUst(false)
        const blok = e.dataTransfer.getData(DND_TIPI), kart = e.dataTransfer.getData(KART_TIPI)
        if (blok) onBlok(blok); else if (kart) onTasi(kart)
      }}
      className={cn('flex min-h-[300px] flex-col items-center justify-center rounded-[var(--radius-panel)] border border-dashed p-6 text-center transition-colors',
        ust ? 'border-brand bg-brand-soft' : 'border-line-strong bg-surface/40')}>
      <span className="text-[13.5px] font-medium text-ink-2">{ust ? 'Bırakın' : ilk ? 'Bir veri bloğunu buraya sürükleyin' : 'Boş hücre'}</span>
      {ilk && !ust && <span className="mt-1 max-w-[240px] text-[12.5px] text-muted">Örneğin önce "Satış"ı, sonra üstüne "Aylara göre"yi bırakın.</span>}
    </div>
  )
}
