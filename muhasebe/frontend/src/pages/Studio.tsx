import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { FilePlus2, FileSpreadsheet, FolderOpen, Presentation, Redo2, Save, Trash2, Undo2, X } from 'lucide-react'
import { api, download } from '../lib/api'
import { rangeLabel } from '../lib/format'
import { useWork } from '../lib/state'
import { yorumla } from '../lib/yorum'
import { blokBul } from '../components/studio/bloklar'
import { BosHucre, KartGorunum } from '../components/studio/Kart'
import { BlokPaleti, SagPanel, SolPanel, type AnalizParcasi } from '../components/studio/Paneller'
import { istek, kartAraligi, kartBasligi, olcuBlok, varsayilanPano, yeniKart, type Kart, type KartVeri, type Pano } from '../components/studio/model'
import { Button, Modal, Popover, cn, inputCls, toast } from '../components/ui'

const DEPO = 'tailglass.studyo'

function oku(): Pano {
  try {
    const p = JSON.parse(localStorage.getItem(DEPO) || '')
    if (p && Array.isArray(p.hucreler)) return p
  } catch { /* yok say */ }
  return varsayilanPano()
}

/** Izgarada her zaman en az bir bos satir kalsin (3'erli). */
function bosluklu(h: (Kart | null)[]): (Kart | null)[] {
  const dolu = h.filter(Boolean).length
  const n = Math.max(6, Math.ceil((dolu + 1) / 3) * 3)
  while (h.length > n && h[h.length - 1] === null) h = h.slice(0, -1)
  if (h.length < n) h = [...h, ...Array(n - h.length).fill(null)]
  if (!h.some((x) => x === null)) h = [...h, null, null, null]
  return h
}

export default function StudioPage() {
  const { meta } = useWork()
  const [pano, setPanoHam] = useState<Pano>(oku)
  const [gecmis, setGecmis] = useState<Pano[]>([])
  const [ileri, setIleri] = useState<Pano[]>([])
  const [secili, setSecili] = useState<string | null>(null)
  const [veriler, setVeriler] = useState<Record<string, KartVeri | null>>({})
  const [sunum, setSunum] = useState(false)
  const [kaydetAcik, setKaydetAcik] = useState(false)
  const kok = useRef<HTMLDivElement>(null)

  const etiket = useCallback((d: string) => meta?.dimensions.find((x) => x.key === d)?.label ?? d, [meta])

  /** Degisiklik: gecmise yaz (geri alinabilir). sessiz=true not yazarken her harfte gecmis sismesin. */
  const panoRef = useRef(pano)
  panoRef.current = pano
  const setPano = useCallback((p: Pano, sessiz = false) => {
    if (!sessiz) { const once = panoRef.current; setGecmis((g) => [...g.slice(-49), once]); setIleri([]) }
    setPanoHam({ ...p, hucreler: bosluklu(p.hucreler) })
  }, [])
  useEffect(() => { try { localStorage.setItem(DEPO, JSON.stringify(pano)) } catch { /* yok say */ } }, [pano])

  const geriAl = () => { if (!gecmis.length) return; setIleri((f) => [pano, ...f]); setPanoHam(gecmis[gecmis.length - 1]); setGecmis((g) => g.slice(0, -1)) }
  const yinele = () => { if (!ileri.length) return; setGecmis((g) => [...g, pano]); setPanoHam(ileri[0]); setIleri((f) => f.slice(1)) }
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || (e.target as HTMLElement)?.closest('input,textarea,select')) return
      if (e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); geriAl() }
      if (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey)) { e.preventDefault(); yinele() }
    }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  })

  const kartlar = pano.hucreler.filter(Boolean) as Kart[]
  const seciliKart = kartlar.find((k) => k.id === secili) ?? null
  const kartDegis = (k: Kart, sessiz = false) => setPano({ ...pano, hucreler: pano.hucreler.map((x) => (x?.id === k.id ? k : x)) }, sessiz)

  /** Blogu bir karta uygula: olcu degistirir, boyut kirilim ekler, hazir secim filtreler. */
  const blokUygula = (k: Kart, blokId: string): Kart => {
    const b = blokBul(blokId)
    if (!b) return k
    if (b.tur === 'olcu') return { ...k, olcu: b.id }
    if (b.tur === 'hazir') return { ...k, filtre: { ...k.filtre, ...b.filtre } }
    if (!k.boyut) return { ...k, boyut: b.boyut, grafik: 'otomatik' }
    if (k.boyut === b.boyut) return k
    toast.ok(`${b.ad} ikinci kırılım olarak eklendi. Sol panelden kaldırabilirsiniz.`)
    return { ...k, seri: b.boyut }
  }
  const bosaBirak = (i: number, blokId: string) => {
    const b = blokBul(blokId)
    if (!b) return
    let k = yeniKart(b.tur === 'olcu' ? b.id : 'satis')
    if (b.tur !== 'olcu') k = blokUygula(k, blokId)
    const h = [...pano.hucreler]; h[i] = k
    setPano({ ...pano, hucreler: h }); setSecili(k.id)
  }
  const tasi = (kaynakId: string, hedef: number) => {
    const h = [...pano.hucreler]
    const i = h.findIndex((x) => x?.id === kaynakId)
    if (i < 0 || i === hedef) return
    ;[h[i], h[hedef]] = [h[hedef], h[i]]
    setPano({ ...pano, hucreler: h })
  }
  const paletTik = (blokId: string) => {
    if (seciliKart) { kartDegis(blokUygula(seciliKart, blokId)); return }
    const i = pano.hucreler.findIndex((x) => x === null)
    bosaBirak(i < 0 ? pano.hucreler.length : i, blokId)
  }

  // ------------------------------------------------------------ yorumlar
  const parcalar: AnalizParcasi[] = useMemo(() => kartlar.map((k) => {
    const v = veriler[k.id]
    const b = olcuBlok(k)
    const ar = kartAraligi(k, pano)
    const baslik = kartBasligi(k, etiket)
    if (!v) return { id: k.id, baslik, cumleler: [{ metin: 'Hesaplanıyor…', ton: 'notr' as const }] }
    return { id: k.id, baslik, cumleler: yorumla({
      olcuAdi: b.ad, tip: b.tip ?? 'num', mkey: `m_${b.olcu}`, boyut: k.boyut, boyutAdi: k.boyut ? etiket(k.boyut) : undefined,
      seri: k.seri, sonuc: v.sonuc, onceki: v.onceki, surucu: v.surucu, aralikAdi: rangeLabel(ar.from, ar.to),
      sonDonemSuruyor: ar.to >= new Date().toISOString().slice(0, 10),
    }) }
  }), [kartlar, veriler, pano, etiket])

  // ------------------------------------------------------------ arac cubugu
  const panolar = useAsyncPanolar()
  const panoyuExcel = () => download('/api/export/pano', {
    ad: pano.ad, not: pano.not, kartlar: kartlar.map((k) => ({
      baslik: kartBasligi(k, etiket), request: istek(k, pano), not: k.not,
      yorum: parcalar.find((p) => p.id === k.id)?.cumleler.map((c) => c.metin) ?? [],
    })),
  }).catch((e) => toast.err(e.message))
  const sunumAc = async () => {
    const yeni = !sunum
    setSunum(yeni)
    try {
      if (yeni && !document.fullscreenElement) await kok.current?.requestFullscreen()
      if (!yeni && document.fullscreenElement) await document.exitFullscreen()
    } catch { /* tam ekran izni yoksa yalnizca paneller gizlenir */ }
  }
  useEffect(() => {
    const k = () => { if (!document.fullscreenElement) setSunum(false) }
    document.addEventListener('fullscreenchange', k)
    return () => document.removeEventListener('fullscreenchange', k)
  }, [])

  return (
    <div ref={kok} className={cn('-mx-6 -mt-6 -mb-16 flex h-[calc(100dvh-73px)] flex-col bg-canvas max-sm:-mx-3', sunum && 'h-dvh')}>
      {/* ------------------------------------------------ arac cubugu */}
      <div className="flex flex-wrap items-center gap-1 border-b border-line bg-surface px-4 py-1.5">
        <input value={pano.ad} onChange={(e) => setPano({ ...pano, ad: e.target.value }, true)} aria-label="Analizin adı"
          className="mr-2 h-8 w-56 rounded-[var(--radius-ctl)] border border-transparent bg-transparent px-2 text-[15px] font-semibold text-ink hover:border-line focus:border-line-strong focus:outline-none" />
        <Arac ad="Yeni" ikon={FilePlus2} onClick={() => { setPano(varsayilanPano()); setSecili(null) }} />
        <Popover width={300} trigger={(_, t) => <Arac ad="Aç" ikon={FolderOpen} onClick={() => { panolar.yukle(); t() }} />}>
          {(kapat) => (
            <ul className="scroll-thin max-h-80 overflow-auto py-1.5">
              {!panolar.liste.length && <li className="px-3.5 py-2 text-[13px] text-muted">Kayıtlı analiz yok.</li>}
              {panolar.liste.map((v) => (
                <li key={v.id} className="group flex items-center">
                  <button onClick={() => { setPano(v.config); setSecili(null); kapat(); toast.ok(`"${v.name}" açıldı.`) }}
                    className="flex-1 truncate px-3.5 py-2 text-left text-[13px] hover:bg-surface-2">{v.name}</button>
                  <button onClick={async () => { await api.del(`/api/gorunumler/${v.id}`); panolar.yukle() }} aria-label="Sil"
                    className="px-2.5 text-muted opacity-0 group-hover:opacity-100 hover:text-neg"><Trash2 className="size-3.5" /></button>
                </li>
              ))}
            </ul>
          )}
        </Popover>
        <Arac ad="Kaydet" ikon={Save} onClick={() => setKaydetAcik(true)} />
        <span className="mx-1.5 h-5 w-px bg-line" />
        <Arac ad="Geri al" ikon={Undo2} onClick={geriAl} disabled={!gecmis.length} kisayol="Ctrl+Z" />
        <Arac ad="Yinele" ikon={Redo2} onClick={yinele} disabled={!ileri.length} kisayol="Ctrl+Y" />
        <span className="mx-1.5 h-5 w-px bg-line" />
        <Arac ad="Excel" ikon={FileSpreadsheet} onClick={panoyuExcel} disabled={!kartlar.length} />
        <Arac ad={sunum ? 'Sunumdan çık' : 'Sunum'} ikon={sunum ? X : Presentation} onClick={sunumAc} />
        <span className="ml-auto text-[12px] text-muted max-md:hidden">{rangeLabel(pano.aralik.from, pano.aralik.to)} · {kartlar.length} kart</span>
      </div>

      {/* ------------------------------------------------ blok paleti */}
      {!sunum && <div className="border-b border-line bg-surface/70 px-4 backdrop-blur"><BlokPaleti onTikla={paletTik} /></div>}

      {/* ------------------------------------------------ calisma alani */}
      <div className="flex min-h-0 flex-1">
        {!sunum && (
          <aside className="scroll-thin hidden w-[280px] shrink-0 overflow-y-auto border-r border-line bg-surface lg:block">
            <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
              <span className="text-[13px] font-semibold text-ink">{seciliKart ? 'Seçili kart' : 'Analiz'}</span>
              {seciliKart && <button onClick={() => setSecili(null)} className="text-[12px] text-ink-2 hover:text-ink">Seçimi bırak</button>}
            </div>
            <SolPanel pano={pano} kart={seciliKart} etiket={etiket} onPano={(p) => setPano(p)}
              onKart={(k) => kartDegis(k, k.not !== seciliKart?.not)} />
          </aside>
        )}

        <section aria-label="Analiz ızgarası" className="@container scroll-thin min-w-0 flex-1 overflow-y-auto p-4" onClick={(e) => { if (e.target === e.currentTarget) setSecili(null) }}>
          <div data-izgara className="grid grid-cols-1 gap-4 @2xl:grid-cols-2 @5xl:grid-cols-3">
            {pano.hucreler.map((k, i) => k
              ? <KartGorunum key={k.id} k={k} p={pano} secili={secili === k.id} etiket={etiket}
                  onSec={() => setSecili(k.id)} onBlok={(b) => kartDegis(blokUygula(k, b))} onTasi={(id) => tasi(id, i)}
                  onSil={() => { setPano({ ...pano, hucreler: pano.hucreler.map((x) => (x?.id === k.id ? null : x)) }); if (secili === k.id) setSecili(null) }}
                  onDegis={(y) => kartDegis(y)} onVeri={(v) => setVeriler((s) => ({ ...s, [k.id]: v }))} />
              : sunum ? null : <BosHucre key={`bos-${i}`} ilk={!kartlar.length && i === 0} onBlok={(b) => bosaBirak(i, b)} onTasi={(id) => tasi(id, i)} />)}
          </div>
        </section>

        <aside className={cn('hidden w-[340px] shrink-0 border-l border-line bg-surface xl:block', sunum && 'w-[400px]')}>
          <SagPanel parcalar={parcalar} seciliId={secili} pano={pano} kartlar={kartlar} etiket={etiket}
            onPano={(p) => setPano(p, true)} onKartNot={(id, not) => { const k = kartlar.find((x) => x.id === id); if (k) kartDegis({ ...k, not }, true) }}
            onSec={setSecili} />
        </aside>
      </div>

      <KaydetPenceresi acik={kaydetAcik} ad={pano.ad} onKapat={() => setKaydetAcik(false)} onKaydet={async (ad) => {
        const p = { ...pano, ad }
        await api.post('/api/gorunumler', { name: ad, page: 'studyo', config: p })
        setPano(p, true); setKaydetAcik(false); toast.ok(`"${ad}" kaydedildi.`)
      }} />
    </div>
  )
}

function Arac({ ad, ikon: I, onClick, disabled, kisayol }: { ad: string; ikon: typeof Save; onClick: () => void; disabled?: boolean; kisayol?: string }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={kisayol ? `${ad} (${kisayol})` : ad}
      className="inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-ctl)] px-2.5 text-[13px] text-ink-2 hover:bg-surface-2 hover:text-ink disabled:opacity-35">
      <I className="size-4" /><span className="max-md:hidden">{ad}</span>
    </button>
  )
}

function useAsyncPanolar() {
  const [liste, setListe] = useState<{ id: number; name: string; config: Pano }[]>([])
  const yukle = useCallback(() => { api.get<{ id: number; name: string; config: Pano }[]>('/api/gorunumler?page=studyo').then(setListe, () => {}) }, [])
  return { liste, yukle }
}

function KaydetPenceresi({ acik, ad, onKapat, onKaydet }: { acik: boolean; ad: string; onKapat: () => void; onKaydet: (ad: string) => Promise<void> }) {
  const [deger, setDeger] = useState(ad)
  const [mesgul, setMesgul] = useState(false)
  useEffect(() => { if (acik) setDeger(ad) }, [acik, ad])
  return (
    <Modal open={acik} onClose={onKapat} title="Analizi kaydet" footer={<>
      <Button onClick={onKapat}>Vazgeç</Button>
      <Button variant="primary" loading={mesgul} disabled={!deger.trim()} onClick={async () => {
        setMesgul(true)
        try { await onKaydet(deger.trim()) } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') } finally { setMesgul(false) }
      }}>Kaydet</Button>
    </>}>
      <label className="flex flex-col gap-1.5 text-[13px]">
        <span className="font-medium">Ad</span>
        <input autoFocus value={deger} onChange={(e) => setDeger(e.target.value)} className={inputCls} placeholder="Örn. Ekim yönetim toplantısı" />
      </label>
      <p className="mt-2 text-[12.5px] text-muted">Kartlar, aralıklar, seçimler ve notlar birlikte kaydedilir; "Aç" menüsünden geri yüklenir.</p>
    </Modal>
  )
}
