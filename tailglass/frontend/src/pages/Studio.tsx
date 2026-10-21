import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CalendarRange, ChevronDown, FilePlus2, FileSpreadsheet, FolderOpen, Presentation, Redo2, Save, Sparkles, Trash2, Undo2, X } from 'lucide-react'
import { api, download } from '../lib/api'
import { rangeLabel } from '../lib/format'
import { useWork } from '../lib/state'
import { yorumla } from '../lib/yorum'
import { blokBul } from '../components/studio/bloklar'
import { BosHucre, KartGorunum } from '../components/studio/Kart'
import { AralikSecici, BlokPaleti, SagPanel, SolPanel, type AnalizParcasi } from '../components/studio/Paneller'
import { TailglassLogo } from '../components/Brand'
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

  // Bos ekranda tek tikla baslatilan hazir sorular
  const HAZIR_SORULAR: { soru: string; kur: () => Kart }[] = [
    { soru: 'Satışlar aylara göre nasıl gitti?', kur: () => ({ ...yeniKart('satis'), boyut: 'month' }) },
    { soru: 'En çok kâr bırakan müşteriler kim?', kur: () => ({ ...yeniKart('kar'), boyut: 'client' }) },
    { soru: 'Lisans gelirleri hangi markadan?', kur: () => ({ ...yeniKart('satis'), boyut: 'brand', filtre: { kind: ['Süreli lisans'] } }) },
    { soru: 'Hangi kategoride kâr marjı yüksek?', kur: () => ({ ...yeniKart('marj'), boyut: 'category' }) },
  ]
  const hazirEkle = (k: Kart) => {
    const h = [...pano.hucreler]
    const i = h.findIndex((x) => x === null)
    if (i < 0) h.push(k); else h[i] = k
    setPano({ ...pano, hucreler: h }); setSecili(k.id)
  }
  const bosIndeks = pano.hucreler.findIndex((x) => x === null)

  return (
    <div ref={kok} className="-mx-6 -mt-6 -mb-16 flex h-dvh flex-col bg-canvas max-sm:-mx-3">
      {/* ------------------------------------------------ tek satir: ad, aralik, islemler, logo */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-line bg-surface px-4 py-2">
        <input value={pano.ad} onChange={(e) => setPano({ ...pano, ad: e.target.value }, true)} aria-label="Analizin adı"
          className="h-9 w-52 rounded-[var(--radius-ctl)] border border-transparent bg-transparent px-2 text-[16px] font-semibold text-ink hover:border-line focus:border-line-strong focus:outline-none" />
        <Popover width={330} trigger={(acik, t) => (
          <button onClick={t} className={cn('inline-flex h-9 items-center gap-2 rounded-[var(--radius-ctl)] border px-3 text-[13px]',
            acik ? 'border-ink' : 'border-line-strong hover:border-ink-2')}>
            <CalendarRange className="size-4 text-brand-ink" />
            <span className="font-medium text-ink">{rangeLabel(pano.aralik.from, pano.aralik.to)}</span>
            <ChevronDown className="size-3.5 text-muted" />
          </button>
        )}>
          {() => (
            <div className="p-3.5">
              <p className="mb-2.5 text-[12.5px] text-ink-2">Bütün kartlar bu tarih aralığını kullanır (kartın kendi aralığı yoksa).</p>
              <AralikSecici from={pano.aralik.from} to={pano.aralik.to} onDegis={(from, to) => setPano({ ...pano, aralik: { from, to } })} />
            </div>
          )}
        </Popover>
        <span className="mx-1 h-5 w-px bg-line" />
        <Simge ad="Geri al (Ctrl+Z)" ikon={Undo2} onClick={geriAl} disabled={!gecmis.length} />
        <Simge ad="Yinele (Ctrl+Y)" ikon={Redo2} onClick={yinele} disabled={!ileri.length} />
        <Simge ad="Yeni analiz" ikon={FilePlus2} onClick={() => { setPano(varsayilanPano()); setSecili(null) }} />
        <Popover width={300} trigger={(_, t) => <Simge ad="Kayıtlı analizi aç" ikon={FolderOpen} onClick={() => { panolar.yukle(); t() }} />}>
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
        <div className="ml-auto flex items-center gap-1.5">
          <Button size="sm" icon={<Save className="size-4" />} onClick={() => setKaydetAcik(true)}>Kaydet</Button>
          <Button size="sm" icon={<FileSpreadsheet className="size-4" />} onClick={panoyuExcel} disabled={!kartlar.length}>Excel</Button>
          <Button size="sm" variant="primary" icon={sunum ? <X className="size-4" /> : <Presentation className="size-4" />} onClick={sunumAc}>
            {sunum ? 'Sunumdan çık' : 'Sunum'}
          </Button>
          <a href="#/genel" className="ml-3 max-lg:hidden" aria-label="Tailglass Analytics"><TailglassLogo size={26} /></a>
        </div>
      </div>

      {/* ------------------------------------------------ bloklar */}
      {!sunum && <div className="border-b border-line bg-surface/70 px-4 backdrop-blur"><BlokPaleti onTikla={paletTik} /></div>}

      {/* ------------------------------------------------ calisma alani */}
      <div className="relative flex min-h-0 flex-1">
        {!sunum && seciliKart && (
          <aside className="scroll-thin absolute inset-y-0 left-0 z-20 w-[300px] overflow-y-auto border-r border-line bg-surface shadow-[8px_0_24px_rgba(11,15,14,.06)]">
            <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
              <span className="text-[13px] font-semibold text-ink">Kartı düzenle</span>
              <button onClick={() => setSecili(null)} aria-label="Kapat" className="text-muted hover:text-ink"><X className="size-4" /></button>
            </div>
            <SolPanel pano={pano} kart={seciliKart} etiket={etiket} onPano={(p) => setPano(p)}
              onKart={(k) => kartDegis(k, k.not !== seciliKart?.not)} />
          </aside>
        )}

        <section aria-label="Analiz ızgarası" className={cn('@container scroll-thin min-w-0 flex-1 overflow-y-auto p-5', !sunum && seciliKart && 'pl-[320px] max-md:pl-5')}
          onClick={(e) => { if (e.target === e.currentTarget) setSecili(null) }}>
          {!kartlar.length && !sunum && (
            <div className="mx-auto mt-[6vh] max-w-2xl text-center">
              <Sparkles className="mx-auto size-7 text-brand-ink" />
              <h2 className="display mt-3 text-[28px] leading-tight font-semibold text-ink">Ne merak ediyorsunuz?</h2>
              <p className="mt-2 text-[14.5px] text-ink-2">Yukarıdaki bloklardan birini aşağıdaki alana sürükleyin ya da bir soruyla başlayın.</p>
              <div className="mt-6 grid grid-cols-1 gap-2 text-left sm:grid-cols-2">
                {HAZIR_SORULAR.map((h) => (
                  <button key={h.soru} onClick={() => hazirEkle(h.kur())}
                    className="panel px-4 py-3 text-[14px] font-medium text-ink transition-colors hover:border-ink">{h.soru}</button>
                ))}
              </div>
            </div>
          )}
          <div data-izgara className={cn('grid grid-cols-1 gap-4 @2xl:grid-cols-2 @5xl:grid-cols-3', !kartlar.length && 'mx-auto mt-6 max-w-2xl @2xl:grid-cols-1 @5xl:grid-cols-1')}>
            {pano.hucreler.map((k, i) => k
              ? <KartGorunum key={k.id} k={k} p={pano} secili={secili === k.id} etiket={etiket}
                  onSec={() => setSecili(k.id)} onBlok={(b) => kartDegis(blokUygula(k, b))} onTasi={(id) => tasi(id, i)}
                  onSil={() => { setPano({ ...pano, hucreler: pano.hucreler.map((x) => (x?.id === k.id ? null : x)) }); if (secili === k.id) setSecili(null) }}
                  onDegis={(y) => kartDegis(y)} onVeri={(v) => setVeriler((s) => ({ ...s, [k.id]: v }))} />
              : !sunum && i === bosIndeks
                ? <BosHucre key={`bos-${i}`} ilk={!kartlar.length} onBlok={(b) => bosaBirak(i, b)} onTasi={(id) => tasi(id, i)} />
                : null)}
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

function Simge({ ad, ikon: I, onClick, disabled }: { ad: string; ikon: typeof Save; onClick: () => void; disabled?: boolean }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={ad} aria-label={ad}
      className="grid size-9 place-items-center rounded-[var(--radius-ctl)] text-ink-2 hover:bg-surface-2 hover:text-ink disabled:opacity-30">
      <I className="size-[18px]" />
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
