import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowDownUp, ArrowRight, Bookmark, Building2, Check, CheckCircle2, ChevronDown, CircleHelp,
  Clock3, GitCompareArrows, Heart, Home, Info, MapPin, MapPinned, Menu, Navigation,
  Search, SlidersHorizontal, Sparkles, TrainFront, X, Zap,
} from 'lucide-react'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import { api } from './api'
import { emptyCriteria, type Amenity, type Criteria, type Metadata, type Property, type SearchResponse } from './types'

const DEMO_QUERY = 'آپارتمان دو خوابه برای خرید در تهران تا ۱۵ میلیارد تومان، نزدیک مترو و دارای پارکینگ'
const FAVORITES_KEY = 'khoneyab:favorites:v1'
const SAVED_SEARCHES_KEY = 'khoneyab:saved-searches:v1'
const LAST_CRITERIA_KEY = 'khoneyab:last-criteria:v1'

type SavedSearch = { id: string; name: string; query: string; criteria: Criteria; savedAt: string }
type SortKey = 'relevance' | 'price_asc' | 'price_desc' | 'area_asc' | 'area_desc'

function readStored<T>(key: string, fallback: T): T {
  try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) as T : fallback } catch { return fallback }
}

function faNumber(value: number | string): string {
  return Number(value).toLocaleString('fa-IR', { maximumFractionDigits: 1 })
}

function compactMoney(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value >= 1_000_000_000) {
    const n = value / 1_000_000_000
    return `${new Intl.NumberFormat('fa-IR', { maximumFractionDigits: n % 1 ? 1 : 0 }).format(n)} میلیارد`
  }
  if (value >= 1_000_000) return `${new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 0 }).format(value / 1_000_000)} میلیون`
  return faNumber(value)
}

function fullMoney(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${faNumber(value)} تومان`
}

function priceLabel(property: Property): string {
  if (property.transaction_type === 'sale') return `${compactMoney(property.sale_price_toman)} تومان`
  return `${compactMoney(property.deposit_toman)} ودیعه · ${compactMoney(property.monthly_rent_toman)} تومان / ماه`
}

function transactionLabel(value?: string | null) { return value === 'rent' ? 'اجاره' : 'خرید' }
function typeLabel(value: string) { return value === 'house' ? 'خانه' : value === 'villa' ? 'ویلا' : 'آپارتمان' }
function amenityLabel(value: Amenity) { return value === 'parking' ? 'پارکینگ' : value === 'elevator' ? 'آسانسور' : 'انباری' }

function safeCriteria(input: Partial<Criteria>): Criteria {
  return {
    ...emptyCriteria(),
    ...input,
    must_have_amenities: input.must_have_amenities || [],
    preferred_amenities: input.preferred_amenities || [],
    emphasis: input.emphasis || [],
  }
}

function App() {
  const [favorites, setFavorites] = useState<string[]>(() => readStored(FAVORITES_KEY, []))
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>(() => readStored(SAVED_SEARCHES_KEY, []))

  useEffect(() => { localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites)) }, [favorites])
  useEffect(() => { localStorage.setItem(SAVED_SEARCHES_KEY, JSON.stringify(savedSearches)) }, [savedSearches])

  const toggleFavorite = useCallback((id: string) => {
    setFavorites(previous => previous.includes(id) ? previous.filter(item => item !== id) : [...previous, id])
  }, [])

  const saveSearch = useCallback((query: string, criteria: Criteria) => {
    setSavedSearches(previous => {
      const same = previous.findIndex(s => s.query === query && JSON.stringify(s.criteria) === JSON.stringify(criteria))
      if (same >= 0) return previous
      const name = query.trim() || `${transactionLabel(criteria.transaction_type)} · ${criteria.city || 'همه شهرها'}`
      return [{ id: `${Date.now()}`, name: name.slice(0, 72), query, criteria, savedAt: new Date().toISOString() }, ...previous].slice(0, 20)
    })
  }, [])

  return <Routes>
    <Route path="/" element={<SearchExperience favorites={favorites} toggleFavorite={toggleFavorite} savedSearches={savedSearches} saveSearch={saveSearch} setSavedSearches={setSavedSearches} />} />
    <Route path="/property/:propertyId" element={<PropertyPage favorites={favorites} toggleFavorite={toggleFavorite} />} />
    <Route path="*" element={<NotFound />} />
  </Routes>
}

function SiteHeader({ onSaved, savedCount }: { onSaved: () => void; savedCount: number }) {
  return <header className="site-header">
    <div className="header-inner">
      <Link to="/" className="brand" aria-label="خانه‌یاب، صفحه اول">
        <span className="brand-mark"><Home size={23} strokeWidth={2.4} /></span>
        <span className="brand-text"><strong>خانه‌یاب</strong><small>بهتر پیدا کن، آگاهانه انتخاب کن</small></span>
      </Link>
      <div className="header-actions">
        <span className="demo-pill"><span /> داده‌ی نمایشی</span>
        <button className="saved-nav" onClick={onSaved}><Bookmark size={17} /> ذخیره‌شده‌ها <span className="nav-count">{savedCount}</span></button>
      </div>
    </div>
  </header>
}

function SearchExperience({
  favorites, toggleFavorite, savedSearches, saveSearch, setSavedSearches,
}: {
  favorites: string[]; toggleFavorite: (id: string) => void; savedSearches: SavedSearch[];
  saveSearch: (query: string, criteria: Criteria) => void; setSavedSearches: (fn: (old: SavedSearch[]) => SavedSearch[]) => void;
}) {
  const navigate = useNavigate()
  const [metadata, setMetadata] = useState<Metadata | null>(null)
  const [query, setQuery] = useState(DEMO_QUERY)
  const [refineText, setRefineText] = useState('')
  const [criteria, setCriteria] = useState<Criteria>(emptyCriteria())
  const [response, setResponse] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [parsingSource, setParsingSource] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<SortKey>('relevance')
  const [view, setView] = useState<'list' | 'map'>('list')
  const [error, setError] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerTab, setDrawerTab] = useState<'favorites' | 'searches'>('favorites')
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [compareOpen, setCompareOpen] = useState(false)
  const [compareProperties, setCompareProperties] = useState<Property[]>([])
  const [compareLoading, setCompareLoading] = useState(false)
  const [toast, setToast] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(true)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(''), 2600) }

  const performSearch = useCallback(async (nextCriteria: Criteria, nextSort: SortKey = sortBy) => {
    setLoading(true); setError('')
    try {
      const data = await api.search(safeCriteria(nextCriteria), nextSort)
      setCriteria(safeCriteria(nextCriteria)); setResponse(data); sessionStorage.setItem(LAST_CRITERIA_KEY, JSON.stringify(safeCriteria(nextCriteria)))
    } catch (err) {
      setError('ارتباط با API برقرار نشد. اگر برنامه را محلی اجرا می‌کنی، مطمئن شو سرویس backend روشن است.')
      console.error(err)
    } finally { setLoading(false) }
  }, [sortBy])

  useEffect(() => {
    let cancelled = false
    async function init() {
      try {
        const meta = await api.metadata()
        if (cancelled) return
        setMetadata(meta)
        const parsed = await api.interpret(DEMO_QUERY, emptyCriteria())
        if (cancelled) return
        setParsingSource(parsed.parsed_by)
        setCriteria(parsed.criteria)
        sessionStorage.setItem(LAST_CRITERIA_KEY, JSON.stringify(safeCriteria(parsed.criteria)))
        const data = await api.search(parsed.criteria, 'relevance')
        if (!cancelled) setResponse(data)
      } catch (err) {
        if (!cancelled) setError('فعلاً به API دسترسی نداریم. در اجرای Docker، وضعیت سرویس backend را بررسی کن.')
        console.error(err)
      }
    }
    init()
    return () => { cancelled = true }
  }, [])

  const submitNaturalSearch = async (value = query, baseCriteria = criteria) => {
    if (!value.trim()) { await performSearch(baseCriteria); return }
    setLoading(true); setError('')
    try {
      const parsed = await api.interpret(value, baseCriteria)
      setParsingSource(parsed.parsed_by)
      setCriteria(safeCriteria(parsed.criteria))
      sessionStorage.setItem(LAST_CRITERIA_KEY, JSON.stringify(safeCriteria(parsed.criteria)))
      setQuery(value)
      const data = await api.search(safeCriteria(parsed.criteria), sortBy)
      setResponse(data)
    } catch (err) {
      setError('در تفسیر جست‌وجو مشکلی پیش آمد؛ فیلترهای فعلی همچنان قابل استفاده‌اند.')
      console.error(err)
    } finally { setLoading(false) }
  }

  const updateCriteria = (patch: Partial<Criteria>) => setCriteria(old => safeCriteria({ ...old, ...patch }))
  const updateNumber = (key: keyof Criteria, value: string) => updateCriteria({ [key]: value === '' ? null : Number(value) } as Partial<Criteria>)
  const toggleAmenity = (amenity: Amenity) => {
    const selected = criteria.must_have_amenities.includes(amenity)
    updateCriteria({ must_have_amenities: selected ? criteria.must_have_amenities.filter(a => a !== amenity) : [...criteria.must_have_amenities, amenity], preferred_amenities: criteria.preferred_amenities.filter(a => a !== amenity) })
  }

  const handleSort = async (next: SortKey) => { setSortBy(next); await performSearch(criteria, next) }

  const refineCurrentSearch = async (message = refineText) => {
    const cleanMessage = message.trim()
    if (!cleanMessage) return
    const normalized = cleanMessage.toLowerCase().replace(/[يى]/g, 'ی').replace(/\u200c/g, '')
    if (['ارزان تر', 'ارزون تر', 'قیمت کمتر', 'کم هزینه تر', 'ارزان‌تر', 'ارزون‌تر'].some(term => normalized.includes(term.replace(/\u200c/g, '')))) {
      setRefineText(''); setSortBy('price_asc'); await performSearch(criteria, 'price_asc'); notify('نتایج بر اساس قیمت از کم به زیاد مرتب شدند.'); return
    }
    if (['متراژ بیشتر', 'بزرگ تر', 'فضای بیشتر', 'خانه بزرگتر'].some(term => normalized.includes(term))) {
      setRefineText(''); setSortBy('area_desc'); await performSearch(criteria, 'area_desc'); notify('نتایج بر اساس متراژ مرتب شدند.'); return
    }
    setLoading(true); setError('')
    try {
      const refined = await api.refine(cleanMessage, criteria)
      const nextCriteria = safeCriteria(refined.criteria)
      setCriteria(nextCriteria); setParsingSource(refined.parsed_by); setQuery(old => old ? `${old} · ${cleanMessage}` : cleanMessage)
      sessionStorage.setItem(LAST_CRITERIA_KEY, JSON.stringify(nextCriteria))
      const data = await api.search(nextCriteria, sortBy)
      setResponse(data); setRefineText(''); notify('جست‌وجو با معیارهای جدید به‌روزرسانی شد.')
    } catch (err) { setError('اصلاح جست‌وجو انجام نشد؛ می‌توانی از فیلترهای معمول استفاده کنی.'); console.error(err) }
    finally { setLoading(false) }
  }

  const toggleCompare = (id: string) => {
    setCompareIds(current => {
      if (current.includes(id)) return current.filter(x => x !== id)
      if (current.length >= 3) { notify('حداکثر سه ملک را می‌توانی مقایسه کنی.'); return current }
      return [...current, id]
    })
  }

  const openCompare = async () => {
    if (compareIds.length < 2) { notify('برای مقایسه، حداقل دو ملک انتخاب کن.'); return }
    setCompareLoading(true)
    try {
      const data = await api.compare(compareIds)
      setCompareProperties(data.properties)
      setCompareOpen(true)
    } catch (err) { notify('دریافت اطلاعات مقایسه با خطا روبه‌رو شد.'); console.error(err) }
    finally { setCompareLoading(false) }
  }

  const loadSavedSearch = async (saved: SavedSearch) => {
    setQuery(saved.query); setDrawerOpen(false); setParsingSource(null)
    await performSearch(safeCriteria(saved.criteria))
  }

  const handleExample = async (example: string) => { setQuery(example); await submitNaturalSearch(example, criteria) }

  const resultList = response?.results || []
  const favoriteItems = useMemo(() => resultList.filter(p => favorites.includes(p.property_id)), [resultList, favorites])
  const activeChips = useMemo(() => criteriaChips(criteria), [criteria])

  return <div className="app-shell" dir="rtl">
    <SiteHeader onSaved={() => { setDrawerTab('favorites'); setDrawerOpen(true) }} savedCount={favorites.length + savedSearches.length} />
    <main className="main-content">
      <section className="hero-section">
        <div className="hero-copy">
          <div className="eyebrow"><Sparkles size={15} /> جست‌وجوی خانه با نگاه دقیق‌تر</div>
          <h1>خانه‌ی بعدی‌ات را<br /><span>هوشمندانه پیدا کن.</span></h1>
          <p>آگهی‌ها را فقط کنار هم نمی‌گذاریم؛ کمک می‌کنیم بفهمی کدام گزینه به نیازت نزدیک‌تر است و چه چیزی را در عوضش به دست می‌آوری.</p>
          <div className="hero-points"><span><CheckCircle2 size={15} /> مقایسه‌ی شفاف</span><span><CheckCircle2 size={15} /> رتبه‌بندی قابل توضیح</span><span><CheckCircle2 size={15} /> چند شهر، یک جست‌وجو</span></div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="art-sun" /><div className="art-building building-back"><i /><i /><i /><i /><i /><i /></div>
          <div className="art-building building-front"><i /><i /><i /><i /><i /><i /><i /><i /></div>
          <div className="art-ground" /><div className="art-pin"><MapPin size={18} fill="currentColor" /><span>اینجا می‌تونه خونه‌ی تو باشه</span></div>
          <div className="art-leaf leaf-one" /><div className="art-leaf leaf-two" />
        </div>
      </section>

      <section className="search-panel" aria-label="جست‌وجوی ملک">
        <div className="search-panel-top">
          <div><span className="section-mini-label">از اینجا شروع کن</span><h2>دنبال چه خونه‌ای می‌گردی؟</h2></div>
          <span className="private-badge"><Zap size={14} /> جست‌وجوی پایه بدون نیاز به AI</span>
        </div>
        <div className="transaction-tabs" role="tablist" aria-label="نوع معامله">
          <button className={criteria.transaction_type !== 'rent' ? 'active' : ''} onClick={() => { updateCriteria({ transaction_type: 'sale', max_deposit_toman: null, max_monthly_rent_toman: null }); setQuery('') }}><Building2 size={17} /> خرید خانه</button>
          <button className={criteria.transaction_type === 'rent' ? 'active' : ''} onClick={() => { updateCriteria({ transaction_type: 'rent', max_price_toman: null }); setQuery('') }}><Home size={17} /> اجاره خانه</button>
        </div>
        <form className="natural-search" onSubmit={e => { e.preventDefault(); void submitNaturalSearch() }}>
          <Search size={21} className="query-icon" />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="مثلاً آپارتمان دوخوابه در تهران تا ۱۵ میلیارد، نزدیک مترو..." aria-label="جست‌وجوی متنی" />
          {query && <button type="button" className="clear-query" aria-label="پاک کردن جست‌وجو" onClick={() => setQuery('')}><X size={17} /></button>}
          <button type="submit" className="search-submit" disabled={loading}><Search size={18} /> {loading ? 'در حال جست‌وجو…' : 'پیدا کن'}</button>
        </form>
        <div className="example-searches"><span>جست‌وجوهای پیشنهادی:</span>
          <button onClick={() => void handleExample('آپارتمان دو خوابه برای خرید در تهران تا ۱۵ میلیارد تومان، نزدیک مترو و دارای پارکینگ')}>تهران · دوخوابه · نزدیک مترو</button>
          <button onClick={() => void handleExample('خانه‌ی اجاره‌ای در مشهد، دو خوابه، با پارکینگ')}>اجاره در مشهد</button>
          <button onClick={() => void handleExample('ویلای سه خوابه برای خرید در شیراز تا ۱۰ میلیارد تومان')}>ویلا در شیراز</button>
        </div>
      </section>

      {error && <div className="error-banner"><Info size={18} /><span>{error}</span><button onClick={() => void performSearch(criteria)}>تلاش دوباره</button></div>}

      <div className="results-layout">
        <aside className={`filters-panel ${filtersOpen ? 'filters-visible' : 'filters-hidden'}`}>
          <div className="filters-head"><div><SlidersHorizontal size={18} /><h3>فیلترها</h3></div><button className="reset-filters" onClick={() => { const reset = emptyCriteria(); reset.transaction_type = criteria.transaction_type; setCriteria(reset); void performSearch(reset) }}>پاک‌کردن</button></div>
          <div className="filter-field">
            <label htmlFor="city">شهر</label>
            <div className="select-wrap"><MapPin size={16} /><select id="city" value={criteria.city || ''} onChange={e => updateCriteria({ city: e.target.value || null, neighborhood: null })}><option value="">همه‌ی شهرها</option>{metadata?.cities.map(city => <option key={city}>{city}</option>)}</select><ChevronDown size={15} /></div>
          </div>
          <div className="filter-field">
            <label htmlFor="neighborhood">محله</label>
            <div className="select-wrap"><MapPinned size={16} /><select id="neighborhood" value={criteria.neighborhood || ''} onChange={e => updateCriteria({ neighborhood: e.target.value || null })} disabled={!criteria.city}><option value="">همه‌ی محله‌ها</option>{(metadata?.neighborhoods[criteria.city || ''] || []).map(n => <option key={n}>{n}</option>)}</select><ChevronDown size={15} /></div>
          </div>
          <div className="filter-field">
            <label htmlFor="property-type">نوع ملک</label>
            <div className="select-wrap"><Building2 size={16} /><select id="property-type" value={criteria.property_type || ''} onChange={e => updateCriteria({ property_type: (e.target.value || null) as Criteria['property_type'] })}><option value="">همه‌ی انواع</option>{metadata?.property_types.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}</select><ChevronDown size={15} /></div>
          </div>
          <div className="filter-divider" />
          {criteria.transaction_type === 'rent' ? <>
            <NumberField label="حداکثر ودیعه (تومان)" value={criteria.max_deposit_toman} onChange={v => updateNumber('max_deposit_toman', v)} placeholder="مثلاً ۸۰۰۰۰۰۰۰۰" />
            <NumberField label="حداکثر اجاره ماهانه" value={criteria.max_monthly_rent_toman} onChange={v => updateNumber('max_monthly_rent_toman', v)} placeholder="مثلاً ۲۰۰۰۰۰۰۰" />
          </> : <NumberField label="حداکثر بودجه (تومان)" value={criteria.max_price_toman} onChange={v => updateNumber('max_price_toman', v)} placeholder="مثلاً ۱۵۰۰۰۰۰۰۰۰۰" />}
          <div className="filter-grid-two"><NumberField label="حداقل متراژ" value={criteria.min_area_sqm} onChange={v => updateNumber('min_area_sqm', v)} placeholder="متر" /><NumberField label="حداکثر متراژ" value={criteria.max_area_sqm} onChange={v => updateNumber('max_area_sqm', v)} placeholder="متر" /></div>
          <div className="filter-field"><label htmlFor="bedrooms">تعداد اتاق خواب</label><div className="select-wrap"><Home size={16} /><select id="bedrooms" value={criteria.bedrooms ?? ''} onChange={e => updateCriteria({ bedrooms: e.target.value === '' ? null : Number(e.target.value) })}><option value="">فرقی نمی‌کند</option><option value="0">بدون اتاق خواب</option><option value="1">۱ خواب</option><option value="2">۲ خواب</option><option value="3">۳ خواب</option><option value="4">۴ خواب</option></select><ChevronDown size={15} /></div></div>
          <div className="filter-field"><label>امکانات ضروری</label><div className="amenities-checks">{(['parking', 'elevator', 'storage'] as Amenity[]).map(a => <label key={a} className="check-row"><input type="checkbox" checked={criteria.must_have_amenities.includes(a)} onChange={() => toggleAmenity(a)} /><span className="fake-check"><Check size={12} /></span>{amenityLabel(a)}</label>)}</div></div>
          <NumberField label="حداکثر زمان پیاده تا حمل‌ونقل (دقیقه)" value={criteria.transit_max_minutes} onChange={v => updateNumber('transit_max_minutes', v)} placeholder="اختیاری" />
          <button className="apply-filters" onClick={() => void performSearch(criteria)}><SlidersHorizontal size={17} /> اعمال فیلترها</button>
          <p className="filter-note"><Info size={14} /> فیلترهای این بخش محدودیت قطعی‌اند؛ ترجیحات متنی در رتبه‌بندی اثر می‌گذارند.</p>
        </aside>

        <section className="results-main">
          <form className="refine-panel" onSubmit={e => { e.preventDefault(); void refineCurrentSearch() }}>
            <span className="refine-icon"><Sparkles size={17} /></span>
            <div className="refine-copy"><strong>نتایج را دقیق‌تر کن</strong><small>مثلاً «محله‌ی پونک رو هم بررسی کن» یا «بدون پارکینگ هم نشون بده»</small></div>
            <input value={refineText} onChange={e => setRefineText(e.target.value)} placeholder="یه تغییر دیگه می‌خوای؟" aria-label="اصلاح جست‌وجو" />
            <button type="submit" disabled={loading || !refineText.trim()}>اعمال <ArrowRight size={14} /></button>
          </form>
          <div className="results-heading">
            <div className="results-title-group"><button className="mobile-filter-button" onClick={() => setFiltersOpen(v => !v)}><SlidersHorizontal size={16} /> فیلترها</button><div><span className="section-mini-label">نتیجه‌ی جست‌وجوی تو</span><h2>{loading ? 'داریم گزینه‌ها را بررسی می‌کنیم…' : response?.total ? `${faNumber(response.total)} ملک پیدا شد` : 'هنوز گزینه‌ای پیدا نشده'}</h2></div></div>
            <div className="results-controls"><label className="sort-control"><ArrowDownUp size={15} /><select value={sortBy} onChange={e => void handleSort(e.target.value as SortKey)} aria-label="مرتب‌سازی"><option value="relevance">مرتبط‌ترین</option><option value="price_asc">ارزان‌ترین</option><option value="price_desc">گران‌ترین</option><option value="area_desc">بزرگ‌ترین متراژ</option><option value="area_asc">کوچک‌ترین متراژ</option></select><ChevronDown size={14} /></label><div className="view-toggle"><button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')} aria-label="نمای فهرست"><Menu size={17} /></button><button className={view === 'map' ? 'active' : ''} onClick={() => setView('map')} aria-label="نمای نقشه"><MapPinned size={17} /></button></div></div>
          </div>

          {activeChips.length > 0 && <div className="active-criteria"><span>معیارهای فعال</span>{activeChips.map((chip, i) => <span className={`criteria-chip ${chip.kind === 'preference' ? 'soft-chip' : ''}`} key={`${chip.label}-${i}`}>{chip.kind === 'preference' && <Sparkles size={11} />}{chip.label}</span>)}{parsingSource && <span className="parser-pill" title={parsingSource === 'ai' ? 'تفسیر با مدل زبانی' : 'تفسیر قاعده‌محور'}>{parsingSource === 'ai' ? <Sparkles size={12} /> : <Zap size={12} />}{parsingSource === 'ai' ? 'تفسیر AI' : 'تفسیر سریع'}</span>}</div>}

          {loading && <div className="loading-state"><span className="spinner" /><strong>در حال پیدا کردن بهترین تطبیق‌ها…</strong><small>فیلترها و رتبه‌بندی به‌صورت شفاف محاسبه می‌شوند.</small></div>}
          {!loading && view === 'map' && <MapResults results={resultList} onOpen={id => navigate(`/property/${id}`)} />}
          {!loading && view === 'list' && resultList.length > 0 && <div className="property-list">{resultList.map(property => <PropertyCard key={property.property_id} property={property} isFavorite={favorites.includes(property.property_id)} isCompared={compareIds.includes(property.property_id)} onFavorite={() => toggleFavorite(property.property_id)} onCompare={() => toggleCompare(property.property_id)} onOpen={() => navigate(`/property/${property.property_id}`)} />)}</div>}
          {!loading && response && resultList.length === 0 && <div className="empty-state"><div className="empty-icon"><Search size={26} /></div><h3>با این معیارها نتیجه‌ای پیدا نشد</h3><p>معیارهای ضروری را تغییر بده یا گزینه‌های نزدیک را بررسی کن. محدودیت‌ها بدون اطلاع تو حذف نمی‌شوند.</p><button onClick={() => { const relaxed = { ...criteria, must_have_amenities: [], transit_max_minutes: null, bedrooms: null, max_price_toman: null }; setCriteria(relaxed); void performSearch(relaxed) }}>کمی بازتر جست‌وجو کن</button></div>}

          {!loading && response && response.total === 0 && response.near_matches.length > 0 && <section className="near-section"><div className="near-header"><span className="near-icon"><Info size={18} /></span><div><h3>گزینه‌های نزدیک به خواسته‌ات</h3><p>این موارد همه‌ی شرایط ضروری را ندارند؛ موارد ناسازگار را برای هر ملک مشخص کرده‌ایم.</p></div></div><div className="property-list">{response.near_matches.map(property => <PropertyCard key={property.property_id} property={property} isFavorite={favorites.includes(property.property_id)} isCompared={compareIds.includes(property.property_id)} onFavorite={() => toggleFavorite(property.property_id)} onCompare={() => toggleCompare(property.property_id)} onOpen={() => navigate(`/property/${property.property_id}`)} nearMatch />)}</div></section>}

          {response && response.total > 0 && <div className="results-footer"><span>نمایش {faNumber(Math.min(response.total, resultList.length))} از {faNumber(response.total)} ملک یکتا</span><span><CheckCircle2 size={14} /> آگهی‌های مشابه گروه‌بندی شده‌اند</span></div>}
        </section>
      </div>

      <section className="how-it-works"><div><span className="section-mini-label">چطور تصمیم می‌گیریم؟</span><h2>فقط نتیجه نمی‌دهیم؛ دلیلش را هم می‌گوییم.</h2></div><div className="how-grid"><div><span className="how-number">۱</span><strong>معیارها را می‌فهمیم</strong><p>محدودیت‌های قطعی از ترجیح‌هایی که می‌شود درباره‌شان مصالحه کرد جدا می‌شوند.</p></div><div><span className="how-number">۲</span><strong>گزینه‌ها را مرتب می‌کنیم</strong><p>تطبیق بر اساس اطلاعات آگهی محاسبه می‌شود، نه یک پاسخ غیرقابل‌بررسی از مدل.</p></div><div><span className="how-number">۳</span><strong>تفاوت‌ها را روشن می‌کنیم</strong><p>می‌بینی هر ملک چه امتیازی دارد و کدام خواسته را پوشش نمی‌دهد.</p></div></div></section>
    </main>
    <footer className="site-footer"><div className="footer-brand"><span className="brand-mark small"><Home size={17} /></span><strong>خانه‌یاب</strong></div><span>نمونه‌ی نمایشی برای ارزیابی تجربه‌ی جست‌وجو · تمام آگهی‌ها و قیمت‌ها ساختگی‌اند.</span><a href="/docs" onClick={e => { e.preventDefault(); window.open('/api/health', '_blank', 'noopener,noreferrer') }}>وضعیت API <ArrowRight size={13} /></a></footer>

    {compareIds.length > 0 && <div className="compare-tray"><div><GitCompareArrows size={18} /><strong>{faNumber(compareIds.length)} ملک برای مقایسه</strong><span>حداکثر ۳ گزینه</span></div><div className="compare-tray-actions"><button className="tray-clear" onClick={() => setCompareIds([])}>پاک‌کردن</button><button className="tray-compare" onClick={() => void openCompare()} disabled={compareLoading || compareIds.length < 2}>{compareLoading ? 'در حال آماده‌سازی…' : 'مقایسه‌ی گزینه‌ها'} <ArrowRight size={15} /></button></div></div>}

    {drawerOpen && <SavedDrawer favorites={favorites} savedSearches={savedSearches} tab={drawerTab} setTab={setDrawerTab} onClose={() => setDrawerOpen(false)} onOpenSearch={loadSavedSearch} onToggleFavorite={toggleFavorite} onRemoveSearch={id => setSavedSearches(old => old.filter(s => s.id !== id))} />}
    {compareOpen && <CompareModal properties={compareProperties} onClose={() => setCompareOpen(false)} onOpenProperty={id => { setCompareOpen(false); navigate(`/property/${id}`) }} />}
    {toast && <div className="toast-message"><CheckCircle2 size={17} />{toast}</div>}
    <button className={`floating-save ${mobileMenuOpen ? 'expanded' : ''} ${compareIds.length ? 'above-compare' : ''}`} onClick={() => { setMobileMenuOpen(false); saveSearch(query, safeCriteria(criteria)); notify('جست‌وجو ذخیره شد.') }} title="ذخیره‌ی همین جست‌وجو"><Bookmark size={17} /><span>ذخیره‌ی جست‌وجو</span></button>
  </div>
}

function NumberField({ label, value, onChange, placeholder }: { label: string; value?: number | null; onChange: (value: string) => void; placeholder?: string }) {
  return <div className="filter-field"><label>{label}</label><input className="number-input" type="number" min="0" value={value ?? ''} onChange={e => onChange(e.target.value)} placeholder={placeholder} /></div>
}

function criteriaChips(criteria: Criteria): { label: string; kind: 'hard' | 'preference' }[] {
  const chips: { label: string; kind: 'hard' | 'preference' }[] = []
  if (criteria.transaction_type) chips.push({ label: transactionLabel(criteria.transaction_type), kind: 'hard' })
  if (criteria.city) chips.push({ label: criteria.city, kind: 'hard' })
  if (criteria.neighborhood) chips.push({ label: criteria.neighborhood, kind: 'hard' })
  if (criteria.property_type) chips.push({ label: typeLabel(criteria.property_type), kind: 'hard' })
  if (criteria.bedrooms != null) chips.push({ label: `${faNumber(criteria.bedrooms)} خواب`, kind: 'hard' })
  if (criteria.transaction_type === 'sale' && criteria.max_price_toman) chips.push({ label: `تا ${compactMoney(criteria.max_price_toman)} تومان`, kind: 'hard' })
  if (criteria.transaction_type === 'rent' && criteria.max_deposit_toman) chips.push({ label: `ودیعه تا ${compactMoney(criteria.max_deposit_toman)}`, kind: 'hard' })
  if (criteria.min_area_sqm) chips.push({ label: `از ${faNumber(criteria.min_area_sqm)} متر`, kind: 'hard' })
  if (criteria.max_area_sqm) chips.push({ label: `تا ${faNumber(criteria.max_area_sqm)} متر`, kind: 'hard' })
  criteria.must_have_amenities.forEach(a => chips.push({ label: `${amenityLabel(a)} ضروری`, kind: 'hard' }))
  criteria.preferred_amenities.forEach(a => chips.push({ label: `ترجیح: ${amenityLabel(a)}`, kind: 'preference' }))
  if (criteria.transit_max_minutes) chips.push({ label: `تا ${faNumber(criteria.transit_max_minutes)} دقیقه تا حمل‌ونقل`, kind: 'hard' })
  else if (criteria.transit_preference_minutes) chips.push({ label: `نزدیک حمل‌ونقل عمومی`, kind: 'preference' })
  return chips
}

function PropertyCard({ property, isFavorite, isCompared, onFavorite, onCompare, onOpen, nearMatch = false }: {
  property: Property; isFavorite: boolean; isCompared: boolean; onFavorite: () => void; onCompare: () => void; onOpen: () => void; nearMatch?: boolean;
}) {
  return <article className={`property-card ${nearMatch ? 'near-card' : ''}`}>
    <button className="property-image-button" onClick={onOpen} aria-label="مشاهده جزئیات ملک"><img className="property-image" src={property.images?.[0] || '/property-1.svg'} alt="تصویر نمایشی ملک" /><span className="image-demo-tag">تصویر نمونه</span>{property.advertisement_count > 1 && <span className="duplicate-tag"><GitCompareArrows size={12} /> {faNumber(property.advertisement_count)} آگهی مشابه</span>}</button>
    <div className="property-card-content">
      <div className="property-card-topline"><span className="property-type-label">{typeLabel(property.property_type)} · {transactionLabel(property.transaction_type)}</span><button className={`icon-button favorite-button ${isFavorite ? 'selected' : ''}`} onClick={e => { e.stopPropagation(); onFavorite() }} aria-label={isFavorite ? 'حذف از علاقه‌مندی‌ها' : 'افزودن به علاقه‌مندی‌ها'}><Heart size={18} fill={isFavorite ? 'currentColor' : 'none'} /></button></div>
      <button className="property-title" onClick={onOpen}>{property.title}</button>
      <div className="property-location"><MapPin size={14} /><span>{property.city}، {property.neighborhood}</span><span className="dot-separator" /> <span>{faNumber(property.building_age_years ?? 0)} سال ساخت</span></div>
      <div className="property-specs"><span><strong>{faNumber(property.area_sqm)}</strong> متر</span><span><strong>{faNumber(property.bedrooms)}</strong> خواب</span>{property.floor_number != null && <span>طبقه <strong>{faNumber(property.floor_number)}</strong></span>}<span className="transit-spec"><TrainFront size={14} /> {property.transit_walk_minutes != null ? `${faNumber(property.transit_walk_minutes)} دقیقه` : 'نامشخص'}</span></div>
      <div className="property-amenities">{property.parking && <span><Check size={12} /> پارکینگ</span>}{property.elevator && <span><Check size={12} /> آسانسور</span>}{property.storage && <span><Check size={12} /> انباری</span>}{!property.parking && !property.elevator && !property.storage && <span className="muted">امکانات ثبت نشده</span>}</div>
      {nearMatch && property.failed_constraints && <div className="failed-constraints"><span>ناسازگار با:</span>{property.failed_constraints.map(f => <em key={f}>{f}</em>)}</div>}
      <div className="property-explanation"><div className="score-block"><span className="score-value">{faNumber(property.match_score)}<small>/۱۰۰</small></span><span>تطبیق</span></div><div className="explanation-copy">{property.match_reasons.slice(0, 3).map(reason => <span key={reason}><CheckCircle2 size={12} />{reason}</span>)}{property.unmet_preferences.slice(0, 1).map(reason => <span className="unmet" key={reason}><Info size={12} />{reason}</span>)}</div></div>
      <div className="property-card-bottom"><div className="property-price">{property.transaction_type === 'rent' && <small>رهن و اجاره</small>}<strong>{priceLabel(property)}</strong>{property.transaction_type === 'sale' && property.price_per_sqm_toman && <small>{compactMoney(property.price_per_sqm_toman)} تومان / متر</small>}</div><div className="card-actions"><button className={`compare-card-button ${isCompared ? 'selected' : ''}`} onClick={onCompare}><GitCompareArrows size={15} /> {isCompared ? 'انتخاب شد' : 'مقایسه'}</button><button className="details-button" onClick={onOpen}>جزئیات <ArrowRight size={14} /></button></div></div>
    </div>
  </article>
}

function MapResults({ results, onOpen }: { results: Property[]; onOpen: (id: string) => void }) {
  const [tilesError, setTilesError] = useState(false)
  const center: [number, number] = results.length ? [results[0].latitude, results[0].longitude] : [35.7219, 51.3347]
  const markerIcon = useMemo(() => L.divIcon({ className: 'map-pin-shell', html: '<span class="map-pin-dot"></span>', iconSize: [22, 22], iconAnchor: [11, 11] }), [])
  if (!results.length) return <div className="empty-map"><MapPinned size={30} /><h3>ملکی برای نمایش روی نقشه نیست</h3><p>فیلترها را تغییر بده تا نتیجه‌های بیشتری ببینی.</p></div>
  return <div className="map-results-wrapper"><div className="map-note"><MapPin size={15} /> موقعیت‌ها تقریبی‌اند؛ برای حفظ حریم خصوصی به نقطه‌ی دقیق ملک اشاره نمی‌کنند.</div>{tilesError && <div className="map-warning">نقشه‌ی زمینه بارگذاری نشد؛ فهرست ملک‌ها همچنان قابل استفاده است.</div>}<div className="leaflet-shell"><MapContainer center={center} zoom={11} scrollWheelZoom={false} className="leaflet-map">
    <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" eventHandlers={{ tileerror: () => setTilesError(true) }} />
    {results.map(p => <Marker key={p.property_id} position={[p.latitude, p.longitude]} icon={markerIcon}><Popup><div className="map-popup"><strong>{p.title}</strong><span>{priceLabel(p)}</span><button onClick={() => onOpen(p.property_id)}>مشاهده جزئیات</button></div></Popup></Marker>)}
  </MapContainer></div><div className="map-results-list"><strong>{faNumber(results.length)} ملک روی نقشه</strong><div>{results.slice(0, 6).map(p => <button key={p.property_id} onClick={() => onOpen(p.property_id)}><span>{p.city}، {p.neighborhood}</span><strong>{priceLabel(p)}</strong></button>)}</div></div></div>
}

function SavedDrawer({ favorites, savedSearches, tab, setTab, onClose, onOpenSearch, onToggleFavorite, onRemoveSearch }: {
  favorites: string[]; savedSearches: SavedSearch[]; tab: 'favorites' | 'searches'; setTab: (t: 'favorites' | 'searches') => void; onClose: () => void;
  onOpenSearch: (s: SavedSearch) => void; onToggleFavorite: (id: string) => void; onRemoveSearch: (id: string) => void;
}) {
  const [favoriteProperties, setFavoriteProperties] = useState<Property[]>([])
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      const found = await Promise.all(favorites.map(id => api.property(id).catch(() => null)))
      if (!cancelled) { setFavoriteProperties(found.filter((x): x is Property => Boolean(x))); setLoading(false) }
    }
    void load()
    return () => { cancelled = true }
  }, [favorites])
  return <div className="modal-backdrop drawer-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}><aside className="saved-drawer" role="dialog" aria-modal="true" aria-label="ذخیره‌شده‌ها"><div className="drawer-heading"><div><span className="section-mini-label">برای بعد نگه‌دار</span><h2>ذخیره‌شده‌ها</h2></div><button className="icon-button" onClick={onClose} aria-label="بستن"><X size={20} /></button></div><div className="drawer-tabs"><button className={tab === 'favorites' ? 'active' : ''} onClick={() => setTab('favorites')}><Heart size={15} /> علاقه‌مندی‌ها <span>{faNumber(favorites.length)}</span></button><button className={tab === 'searches' ? 'active' : ''} onClick={() => setTab('searches')}><Bookmark size={15} /> جست‌وجوها <span>{faNumber(savedSearches.length)}</span></button></div>
    {tab === 'favorites' ? <div className="drawer-items">{loading && <div className="drawer-empty">در حال بارگذاری…</div>}{!loading && favoriteProperties.length === 0 && <div className="drawer-empty"><Heart size={22} /><strong>هنوز ملکی ذخیره نکرده‌ای</strong><span>با زدن قلب روی کارت‌ها، گزینه‌ها را اینجا نگه دار.</span></div>}{favoriteProperties.map(p => <div className="drawer-property" key={p.property_id}><img src={p.images?.[0] || '/property-1.svg'} alt="" /><div><Link to={`/property/${p.property_id}`} className="drawer-property-title">{p.title}</Link><span>{p.city}، {p.neighborhood}</span><b>{priceLabel(p)}</b></div><button className="icon-button selected" onClick={() => onToggleFavorite(p.property_id)} aria-label="حذف از علاقه‌مندی‌ها"><Heart size={17} fill="currentColor" /></button></div>)}</div> : <div className="drawer-items">{savedSearches.length === 0 && <div className="drawer-empty"><Bookmark size={22} /><strong>جست‌وجوی ذخیره‌شده‌ای نیست</strong><span>جست‌وجوی فعلی را از دکمه‌ی پایین صفحه ذخیره کن.</span></div>}{savedSearches.map(s => <div className="saved-search-item" key={s.id}><div className="saved-search-icon"><Search size={17} /></div><div className="saved-search-content"><strong>{s.name}</strong><span>{s.criteria.city || 'همه‌ی شهرها'} · {transactionLabel(s.criteria.transaction_type)}</span><button onClick={() => onOpenSearch(s)}>اجرای جست‌وجو <ArrowRight size={13} /></button></div><button className="icon-button" onClick={() => onRemoveSearch(s.id)} aria-label="حذف جست‌وجو"><X size={16} /></button></div>)}</div>}
    <div className="drawer-footer"><Info size={14} /> ذخیره‌ها فقط در همین مرورگر و بدون حساب کاربری نگه‌داری می‌شوند.</div></aside></div>
}

function CompareModal({ properties, onClose, onOpenProperty }: { properties: Property[]; onClose: () => void; onOpenProperty: (id: string) => void }) {
  const [summary, setSummary] = useState<string | null>(null)
  const [summaryBusy, setSummaryBusy] = useState(false)
  const [summaryMessage, setSummaryMessage] = useState('')
  const values: { label: string; value: (p: Property) => string }[] = [
    { label: 'قیمت', value: p => priceLabel(p) },
    { label: 'متراژ', value: p => `${faNumber(p.area_sqm)} متر مربع` },
    { label: 'اتاق خواب', value: p => `${faNumber(p.bedrooms)} خواب` },
    { label: 'شهر و محله', value: p => `${p.city}، ${p.neighborhood}` },
    { label: 'سن بنا', value: p => `${faNumber(p.building_age_years ?? 0)} سال` },
    { label: 'طبقه', value: p => p.floor_number == null ? '—' : `${faNumber(p.floor_number)} از ${faNumber(p.total_floors ?? 0)}` },
    { label: 'پارکینگ', value: p => p.parking ? 'دارد' : 'ندارد' },
    { label: 'آسانسور', value: p => p.elevator ? 'دارد' : 'ندارد' },
    { label: 'انباری', value: p => p.storage ? 'دارد' : 'ندارد' },
    { label: 'حمل‌ونقل عمومی', value: p => `${p.transit_station || p.transit_mode || 'نامشخص'} · ${p.transit_walk_minutes != null ? `${faNumber(p.transit_walk_minutes)} دقیقه پیاده` : 'نامشخص'}` },
    { label: 'قیمت هر متر', value: p => p.price_per_sqm_toman ? `${compactMoney(p.price_per_sqm_toman)} تومان` : 'برای اجاره محاسبه نمی‌شود' },
  ]
  const differing = (row: typeof values[number]) => new Set(properties.map(row.value)).size > 1
  const requestSummary = async () => {
    setSummaryBusy(true); setSummaryMessage('')
    try {
      const data = await api.synthesis(properties, 'Compare the properties for a person choosing a residential home. Explain trade-offs using only the given data.')
      if (data.summary) setSummary(data.summary)
      else setSummaryMessage('مدل پریمیوم تنظیم نشده است؛ تفاوت‌های جدول بالا بدون AI در دسترس‌اند.')
    } catch { setSummaryMessage('سرویس AI در دسترس نیست؛ برای مقایسه از جدول ویژگی‌ها استفاده کن.') }
    finally { setSummaryBusy(false) }
  }
  return <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}><section className="compare-modal" role="dialog" aria-modal="true" aria-label="مقایسه ملک‌ها"><div className="modal-heading"><div><span className="section-mini-label">کنار هم ببین</span><h2><GitCompareArrows size={21} /> مقایسه‌ی ملک‌ها</h2><p>ردیف‌های هایلایت‌شده تفاوت واقعی بین گزینه‌ها را نشان می‌دهند.</p></div><button className="icon-button" onClick={onClose} aria-label="بستن"><X size={21} /></button></div>
    <div className="compare-table-wrap"><table className="compare-table"><thead><tr><th>ویژگی</th>{properties.map(p => <th key={p.property_id}><img src={p.images?.[0] || '/property-1.svg'} alt="" /><strong>{p.city}، {p.neighborhood}</strong><button onClick={() => onOpenProperty(p.property_id)}>جزئیات ملک <ArrowRight size={12} /></button></th>)}</tr></thead><tbody>{values.map(row => <tr key={row.label} className={differing(row) ? 'diff-row' : ''}><th>{row.label}{differing(row) && <span className="diff-label">متفاوت</span>}</th>{properties.map(p => <td key={p.property_id}>{row.value(p)}</td>)}</tr>)}</tbody></table></div>
    <div className="comparison-ai"><div><Sparkles size={18} /><div><strong>خلاصه‌ی مقایسه با AI</strong><p>اختیاری است؛ جدول مقایسه بدون مدل زبانی هم کار می‌کند.</p></div></div><button onClick={() => void requestSummary()} disabled={summaryBusy}>{summaryBusy ? 'در حال بررسی…' : 'تهیه‌ی خلاصه'} <ArrowRight size={14} /></button></div>{summary && <div className="ai-summary"><Sparkles size={16} /><p>{summary}</p></div>}{summaryMessage && <p className="summary-unavailable"><Info size={14} />{summaryMessage}</p>}
    </section></div>
}

function PropertyPage({ favorites, toggleFavorite }: { favorites: string[]; toggleFavorite: (id: string) => void }) {
  const { propertyId = '' } = useParams()
  const navigate = useNavigate()
  const [property, setProperty] = useState<Property | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    setLoading(true); setError('')
    const criteriaFromSession = readStored<Criteria | null>(LAST_CRITERIA_KEY, null)
    api.property(propertyId, criteriaFromSession ? safeCriteria(criteriaFromSession) : undefined).then(p => { if (!cancelled) setProperty(p) }).catch(() => { if (!cancelled) setError('این ملک پیدا نشد یا API در دسترس نیست.') }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [propertyId])
  if (loading) return <div className="detail-page"><SiteHeader onSaved={() => navigate('/')} savedCount={favorites.length} /><div className="loading-state detail-loading"><span className="spinner" /><strong>در حال دریافت جزئیات ملک…</strong></div></div>
  if (!property) return <div className="detail-page"><SiteHeader onSaved={() => navigate('/')} savedCount={favorites.length} /><div className="empty-state detail-empty"><h2>{error || 'ملک پیدا نشد'}</h2><button onClick={() => navigate('/')}>بازگشت به جست‌وجو</button></div></div>
  const isFavorite = favorites.includes(property.property_id)
  return <div className="detail-page"><SiteHeader onSaved={() => navigate('/')} savedCount={favorites.length} /><main className="detail-container"><button className="back-link" onClick={() => navigate(-1)}><ArrowRight size={16} /> بازگشت به نتایج</button><div className="detail-title-row"><div><span className="property-type-label">{transactionLabel(property.transaction_type)} · {typeLabel(property.property_type)} · داده‌ی نمایشی</span><h1>{property.title}</h1><p><MapPin size={16} /> {property.city}، {property.neighborhood}</p></div><button className={`detail-favorite ${isFavorite ? 'selected' : ''}`} onClick={() => toggleFavorite(property.property_id)}><Heart size={18} fill={isFavorite ? 'currentColor' : 'none'} /> {isFavorite ? 'ذخیره شده' : 'ذخیره‌ی ملک'}</button></div>
    <div className="detail-layout"><div className="detail-main-column"><div className="detail-gallery"><img src={property.images?.[0] || '/property-1.svg'} alt="تصویر نمایشی ملک" /><span>تصویر نمونه — آگهی واقعی نیست</span></div><section className="detail-card"><div className="detail-section-heading"><h2>مشخصات ملک</h2><span><Building2 size={15} /> اطلاعات ساخت‌یافته</span></div><div className="detail-spec-grid"><DetailSpec label="متراژ" value={`${faNumber(property.area_sqm)} متر مربع`} /><DetailSpec label="اتاق خواب" value={`${faNumber(property.bedrooms)} خواب`} /><DetailSpec label="سن بنا" value={`${faNumber(property.building_age_years ?? 0)} سال`} /><DetailSpec label="طبقه" value={property.floor_number == null ? '—' : `${faNumber(property.floor_number)} از ${faNumber(property.total_floors ?? 0)}`} /><DetailSpec label="پارکینگ" value={property.parking ? 'دارد' : 'ندارد'} /><DetailSpec label="آسانسور" value={property.elevator ? 'دارد' : 'ندارد'} /><DetailSpec label="انباری" value={property.storage ? 'دارد' : 'ندارد'} /><DetailSpec label="قیمت هر متر" value={property.price_per_sqm_toman ? `${compactMoney(property.price_per_sqm_toman)} تومان` : '—'} /></div></section><section className="detail-card"><div className="detail-section-heading"><h2>درباره‌ی محله</h2><span><MapPin size={15} /> موقعیت تقریبی</span></div><p className="neighborhood-description">{property.neighborhood_info}</p><div className="transit-detail"><span className="transit-icon"><TrainFront size={19} /></span><div><strong>{property.transit_station || property.transit_mode || 'حمل‌ونقل عمومی'}</strong><small>{property.transit_distance_m != null ? `حدود ${faNumber(property.transit_distance_m)} متر فاصله` : 'فاصله نامشخص'} · {property.transit_walk_minutes != null ? `${faNumber(property.transit_walk_minutes)} دقیقه پیاده` : 'زمان نامشخص'}</small></div><span className="approx-tag">تقریبی</span></div><div className="detail-map-preview"><MapContainer center={[property.latitude, property.longitude]} zoom={13} scrollWheelZoom={false} className="detail-leaflet-map"><TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /><Marker position={[property.latitude, property.longitude]} icon={L.divIcon({ className: 'map-pin-shell', html: '<span class="map-pin-dot"></span>', iconSize: [22, 22], iconAnchor: [11, 11] })}><Popup>موقعیت تقریبی ملک</Popup></Marker></MapContainer></div></section><section className="detail-card"><div className="detail-section-heading"><h2>توضیحات آگهی</h2></div><p className="neighborhood-description">{property.description}</p><div className="synthetic-info"><Info size={15} /> این ملک و تمام اطلاعات آن ساختگی و صرفاً برای نمایش قابلیت‌های محصول است.</div></section></div>
    <aside className="detail-side-column"><div className="price-summary"><span className="section-mini-label">قیمت اعلام‌شده</span><strong>{priceLabel(property)}</strong>{property.transaction_type === 'rent' && <div className="rent-prices"><span>ودیعه <b>{fullMoney(property.deposit_toman)}</b></span><span>اجاره ماهانه <b>{fullMoney(property.monthly_rent_toman)}</b></span></div>}<div className="price-summary-divider" /><div className="detail-score"><div><strong>{faNumber(property.match_score)}</strong><small>/۱۰۰</small></div><span>امتیاز تطبیق با معیار فعلی</span></div><div className="detail-reasons">{property.match_reasons.map(r => <span key={r}><CheckCircle2 size={14} />{r}</span>)}{property.unmet_preferences.map(r => <span className="unmet" key={r}><Info size={14} />{r}</span>)}</div><button className={`detail-save-wide ${isFavorite ? 'selected' : ''}`} onClick={() => toggleFavorite(property.property_id)}><Heart size={17} fill={isFavorite ? 'currentColor' : 'none'} />{isFavorite ? 'در علاقه‌مندی‌هاست' : 'افزودن به علاقه‌مندی‌ها'}</button></div><div className="source-card"><div className="detail-section-heading"><h3>آگهی‌های گروه‌بندی‌شده</h3><span>{faNumber(property.advertisement_count)}</span></div><p>آگهی‌های زیر بر اساس اطلاعات مشابه در یک گروه نمایش داده شده‌اند.</p>{property.sources.map(source => <div className="source-row" key={source.id}><span className="source-dot" /><div><strong>{source.source_name}</strong><small>{source.title}</small></div><span className="source-demo">نمونه</span></div>)}<div className="synthetic-info compact"><Info size={14} /> لینک منبع واقعی عمداً نمایش داده نمی‌شود.</div></div></aside></div></main></div>
}

function DetailSpec({ label, value }: { label: string; value: string }) { return <div className="detail-spec"><span>{label}</span><strong>{value}</strong></div> }

function NotFound() { return <div className="not-found"><Home size={28} /><h2>این صفحه پیدا نشد</h2><Link to="/">بازگشت به خانه‌یاب</Link></div> }

export default App
