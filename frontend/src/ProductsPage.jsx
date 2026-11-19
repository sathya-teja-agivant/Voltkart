import { useState, useEffect, useMemo } from 'react'
import {
  Laptop, Search, SlidersHorizontal, ArrowUpDown, Sparkles,
  Bot, Shield, LogOut, Check, X, Info, Layers, Cpu,
  HardDrive, Battery, Scale, RefreshCw, ChevronRight, Tag
} from 'lucide-react'
import api, { errorMessage } from './api'
import { useAuth } from './auth'
import logo from './assets/logo.png'

// High-quality showcase catalog used if backend is connecting or has 0 products
const DEMO_PRODUCTS = [
  {
    product_id: 101,
    product_name: 'Dell XPS 13 Plus (9320)',
    brand: 'Dell',
    processor: 'Intel Core i7-1360P (12-Core, up to 5.0GHz)',
    ram: 16,
    storage: 512,
    display_size: 13.4,
    battery_life: 11,
    weight: 1.24,
    operating_system: 'Windows 11 Home',
    price: 139990,
    warranty: '2 Year Dell On-site Premium Support',
    stock_status: 'IN_STOCK',
    description: 'Ultra-thin, zero-lattice keyboard, OLED 3.5K touch display and whisper-quiet dual fans.'
  },
  {
    product_id: 102,
    product_name: 'Apple MacBook Air 15" M3',
    brand: 'Apple',
    processor: 'Apple M3 Chip (8-Core CPU, 10-Core GPU)',
    ram: 16,
    storage: 512,
    display_size: 15.3,
    battery_life: 18,
    weight: 1.51,
    operating_system: 'macOS Sonoma',
    price: 144900,
    warranty: '1 Year Apple International Warranty',
    stock_status: 'IN_STOCK',
    description: 'Liquid Retina display with True Tone, fanless silent operation, 1080p FaceTime HD camera.'
  },
  {
    product_id: 103,
    product_name: 'Lenovo ThinkPad X1 Carbon Gen 11',
    brand: 'Lenovo',
    processor: 'Intel Core i7-1365U vPro (10-Core)',
    ram: 32,
    storage: 1000,
    display_size: 14.0,
    battery_life: 14,
    weight: 1.12,
    operating_system: 'Windows 11 Pro',
    price: 174990,
    warranty: '3 Year Lenovo Premier Support',
    stock_status: 'IN_STOCK',
    description: 'Legendary military-grade durability, carbon fiber chassis, TrackPoint, privacy webcam shutter.'
  },
  {
    product_id: 104,
    product_name: 'ASUS ROG Zephyrus G14 (2024)',
    brand: 'ASUS',
    processor: 'AMD Ryzen 9 8945HS (8-Core, 16-Threads)',
    ram: 32,
    storage: 1000,
    display_size: 14.0,
    battery_life: 9,
    weight: 1.50,
    operating_system: 'Windows 11 Home',
    price: 164990,
    warranty: '1 Year ASUS Global Warranty',
    stock_status: 'IN_STOCK',
    description: 'NVIDIA RTX 4070 8GB GPU, 3K 120Hz OLED display, CNC aluminum chassis, Slash Lighting.'
  },
  {
    product_id: 105,
    product_name: 'HP Pavilion 15 (Aerospace Edition)',
    brand: 'HP',
    processor: 'Intel Core i5-1335U (10-Core, up to 4.6GHz)',
    ram: 16,
    storage: 512,
    display_size: 15.6,
    battery_life: 8,
    weight: 1.75,
    operating_system: 'Windows 11 Home',
    price: 58990,
    warranty: '1 Year HP On-site Warranty',
    stock_status: 'IN_STOCK',
    description: 'Micro-edge FHD display, Bang & Olufsen audio tuning, HP Fast Charge (50% in 45 mins).'
  },
  {
    product_id: 106,
    product_name: 'Acer Swift Go 14 AI OLED',
    brand: 'Acer',
    processor: 'Intel Core Ultra 7 155H with Intel AI Boost NPU',
    ram: 16,
    storage: 1000,
    display_size: 14.0,
    battery_life: 12,
    weight: 1.32,
    operating_system: 'Windows 11 Home',
    price: 84990,
    warranty: '1 Year International Travelers Warranty',
    stock_status: 'IN_STOCK',
    description: '2.8K 90Hz OLED 100% DCI-P3, dedicated Copilot hardware key, dual USB4 Type-C ports.'
  },
  {
    product_id: 107,
    product_name: 'Dell Inspiron 14 5430',
    brand: 'Dell',
    processor: 'Intel Core i5-1335U (13th Gen)',
    ram: 16,
    storage: 512,
    display_size: 14.0,
    battery_life: 9,
    weight: 1.53,
    operating_system: 'Windows 11 Home',
    price: 63990,
    warranty: '1 Year Onsite Hardware Service',
    stock_status: 'IN_STOCK',
    description: '16:10 aspect ratio FHD+ display, Waves MaxxAudio Pro speakers, backlit spill-resistant keyboard.'
  },
  {
    product_id: 108,
    product_name: 'ASUS Vivobook 15 Pro OLED',
    brand: 'ASUS',
    processor: 'AMD Ryzen 7 7735HS (8-Core, 16-Thread)',
    ram: 16,
    storage: 512,
    display_size: 15.6,
    battery_life: 7,
    weight: 1.80,
    operating_system: 'Windows 11 Home',
    price: 72990,
    warranty: '1 Year Manufacturer Warranty',
    stock_status: 'OUT_OF_STOCK',
    description: 'NVIDIA GeForce RTX 3050 4GB GPU, Pantone validated 2.8K 120Hz display, ice-blade thermal tech.'
  }
]

export default function ProductsPage({ onOpenChat, onOpenAdmin, onAskAboutProduct, onCompareProducts }) {
  const { user, logout } = useAuth()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [isUsingDemo, setIsUsingDemo] = useState(false)
  const [search, setSearch] = useState('')
  const [brandFilter, setBrandFilter] = useState('ALL')
  const [ramFilter, setRamFilter] = useState('ALL')
  const [stockOnly, setStockOnly] = useState(false)
  const [priceRange, setPriceRange] = useState('ALL')
  const [sortBy, setSortBy] = useState('FEATURED')
  const [selectedForCompare, setSelectedForCompare] = useState([])
  const [quickViewProduct, setQuickViewProduct] = useState(null)
  const [showPolicies, setShowPolicies] = useState(false)
  const [comparisonModal, setComparisonModal] = useState(false)

  // Fetch products from backend
  const loadProducts = async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/products')
      if (Array.isArray(data) && data.length > 0) {
        setProducts(data)
        setIsUsingDemo(false)
      } else {
        setProducts(DEMO_PRODUCTS)
        setIsUsingDemo(true)
      }
    } catch {
      // Gracefully fall back to rich showcase items when backend is starting
      setProducts(DEMO_PRODUCTS)
      setIsUsingDemo(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProducts()
  }, [])

  // Derive unique brands
  const brands = useMemo(() => {
    const list = Array.from(new Set(products.map((p) => p.brand).filter(Boolean)))
    return ['ALL', ...list]
  }, [products])

  // Filter & sort products
  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      // Search text
      if (search.trim()) {
        const q = search.toLowerCase()
        const matchName = (p.product_name || '').toLowerCase().includes(q)
        const matchBrand = (p.brand || '').toLowerCase().includes(q)
        const matchProc = (p.processor || '').toLowerCase().includes(q)
        const matchDesc = (p.description || '').toLowerCase().includes(q)
        if (!matchName && !matchBrand && !matchProc && !matchDesc) return false
      }

      // Brand filter
      if (brandFilter !== 'ALL' && p.brand !== brandFilter) return false

      // RAM filter
      const ramVal = Number(p.ram_gb || p.ram || 0)
      if (ramFilter === '16+' && ramVal < 16) return false
      if (ramFilter === '32+' && ramVal < 32) return false
      if (ramFilter === '8' && ramVal !== 8) return false

      // Stock status
      if (stockOnly && p.stock_status !== 'IN_STOCK') return false

      // Price filter
      const priceVal = Number(p.price_inr || p.price || 0)
      if (priceRange === 'UNDER_60K' && priceVal > 60000) return false
      if (priceRange === '60K_100K' && (priceVal < 60000 || priceVal > 100000)) return false
      if (priceRange === 'ABOVE_100K' && priceVal < 100000) return false

      return true
    }).sort((a, b) => {
      const priceA = Number(a.price_inr || a.price || 0)
      const priceB = Number(b.price_inr || b.price || 0)
      const ramA = Number(a.ram_gb || a.ram || 0)
      const ramB = Number(b.ram_gb || b.ram || 0)
      const batA = Number(a.battery_life_hours || a.battery_life || 0)
      const batB = Number(b.battery_life_hours || b.battery_life || 0)

      if (sortBy === 'PRICE_ASC') return priceA - priceB
      if (sortBy === 'PRICE_DESC') return priceB - priceA
      if (sortBy === 'RAM_DESC') return ramB - ramA
      if (sortBy === 'BATTERY_DESC') return batB - batA
      return 0 // Default featured
    })
  }, [products, search, brandFilter, ramFilter, stockOnly, priceRange, sortBy])

  // Compare selection toggles
  const toggleCompare = (prod) => {
    const id = prod.product_id
    if (selectedForCompare.some((p) => p.product_id === id)) {
      setSelectedForCompare(selectedForCompare.filter((p) => p.product_id !== id))
    } else {
      if (selectedForCompare.length >= 4) {
        alert('You can compare up to 4 laptops at once.')
        return
      }
      setSelectedForCompare([...selectedForCompare, prod])
    }
  }

  const handleAskAIAboutProduct = (product) => {
    const prompt = `Tell me more about the ${product.brand} ${product.product_name}. What are its main pros and cons, and is it good value for money?`
    if (onAskAboutProduct) {
      onAskAboutProduct(prompt)
    } else if (onOpenChat) {
      onOpenChat(prompt)
    }
  }

  const handleAskAIToCompare = () => {
    if (selectedForCompare.length < 2) return
    const names = selectedForCompare.map((p) => `${p.brand} ${p.product_name}`).join(' vs ')
    const prompt = `Compare these laptops side-by-side and tell me which one is the better buy: ${names}`
    if (onCompareProducts) {
      onCompareProducts(prompt)
    } else if (onOpenChat) {
      onOpenChat(prompt)
    }
  }

  const resetFilters = () => {
    setSearch('')
    setBrandFilter('ALL')
    setRamFilter('ALL')
    setStockOnly(false)
    setPriceRange('ALL')
    setSortBy('FEATURED')
  }

  const hasActiveFilters = search || brandFilter !== 'ALL' || ramFilter !== 'ALL' || stockOnly || priceRange !== 'ALL' || sortBy !== 'FEATURED'

  return (
    <div className="saas-store">
      {/* SaaS Top Navigation */}
      <header className="saas-navbar">
        <div className="nav-container">
          <div className="nav-brand">
            <img src={logo} alt="VoltKart" className="nav-logo" />
            <div className="brand-meta">
              <span className="brand-title">VoltKart</span>
              <span className="brand-badge">SaaS Store</span>
            </div>
          </div>

          <div className="nav-search-bar">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              placeholder="Search laptops by model, brand, processor, specs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button className="clear-btn" onClick={() => setSearch('')}>
                <X size={14} />
              </button>
            )}
          </div>

          <div className="nav-actions">
            <button className="nav-link-btn" onClick={() => setShowPolicies(true)}>
              <Info size={15} />
              <span>Policies</span>
            </button>

            {onOpenAdmin && (
              <button className="nav-link-btn admin-link" onClick={onOpenAdmin}>
                <Shield size={15} />
                <span>Admin Console</span>
              </button>
            )}

            <button className="nav-assistant-pill" onClick={() => onOpenChat && onOpenChat()}>
              <span className="pulse-dot" />
              <Bot size={16} />
              <span>Chat Assistant</span>
            </button>

            <div className="user-profile-menu">
              <div className="user-avatar" title={user?.full_name || 'User'}>
                {(user?.full_name || 'U').charAt(0).toUpperCase()}
              </div>
              <div className="user-text">
                <span className="user-name">{user?.full_name}</span>
                <span className="user-role">{user?.role || 'CUSTOMER'}</span>
              </div>
              <button className="logout-icon-btn" onClick={logout} title="Sign Out">
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="store-content">
        {/* Hero Section */}
        <section className="store-hero">
          <div className="hero-badge">
            <Sparkles size={14} />
            <span>AI-Assisted Laptop Marketplace</span>
          </div>
          <h1 className="hero-headline">
            Explore Next-Generation Laptops.<br />
            <span>Precision Specs & Instant AI Guidance.</span>
          </h1>
          <p className="hero-description">
            Browse verified laptops from leading brands. Compare hardware specifications in real-time
            or summon the VoltKart AI Shopping Assistant at any moment.
          </p>

          <div className="hero-highlights">
            <div className="highlight-item">
              <span className="hl-bullet" />
              <span>Catalog specs verified</span>
            </div>
            <div className="highlight-item">
              <span className="hl-bullet" />
              <span>Side-by-side comparison</span>
            </div>
            <div className="highlight-item">
              <span className="hl-bullet" />
              <span>Official brand warranties</span>
            </div>
            <div className="highlight-item">
              <span className="hl-bullet" />
              <span>Real-time AI shopping expert</span>
            </div>
          </div>
        </section>

        {/* Filter Toolbar */}
        <section className="catalog-toolbar">
          <div className="toolbar-top">
            <div className="brand-tabs">
              {brands.map((b) => (
                <button
                  key={b}
                  className={`tab-btn ${brandFilter === b ? 'active' : ''}`}
                  onClick={() => setBrandFilter(b)}
                >
                  {b === 'ALL' ? 'All Brands' : b}
                </button>
              ))}
            </div>

            <div className="sort-box">
              <ArrowUpDown size={15} />
              <label htmlFor="sort-select">Sort:</label>
              <select
                id="sort-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
              >
                <option value="FEATURED">Featured Specs</option>
                <option value="PRICE_ASC">Price: Low to High</option>
                <option value="PRICE_DESC">Price: High to Low</option>
                <option value="RAM_DESC">Highest RAM</option>
                <option value="BATTERY_DESC">Longest Battery</option>
              </select>
            </div>
          </div>

          <div className="toolbar-filters">
            <div className="filter-group">
              <span className="filter-label"><SlidersHorizontal size={14} /> Price:</span>
              <button
                className={`chip ${priceRange === 'ALL' ? 'selected' : ''}`}
                onClick={() => setPriceRange('ALL')}
              >
                All
              </button>
              <button
                className={`chip ${priceRange === 'UNDER_60K' ? 'selected' : ''}`}
                onClick={() => setPriceRange('UNDER_60K')}
              >
                Under ₹60k
              </button>
              <button
                className={`chip ${priceRange === '60K_100K' ? 'selected' : ''}`}
                onClick={() => setPriceRange('60K_100K')}
              >
                ₹60k - ₹1.0L
              </button>
              <button
                className={`chip ${priceRange === 'ABOVE_100K' ? 'selected' : ''}`}
                onClick={() => setPriceRange('ABOVE_100K')}
              >
                ₹1.0L+
              </button>
            </div>

            <div className="filter-group">
              <span className="filter-label">RAM:</span>
              <button
                className={`chip ${ramFilter === 'ALL' ? 'selected' : ''}`}
                onClick={() => setRamFilter('ALL')}
              >
                Any
              </button>
              <button
                className={`chip ${ramFilter === '16+' ? 'selected' : ''}`}
                onClick={() => setRamFilter('16+')}
              >
                16GB+
              </button>
              <button
                className={`chip ${ramFilter === '32+' ? 'selected' : ''}`}
                onClick={() => setRamFilter('32+')}
              >
                32GB
              </button>
            </div>

            <label className="stock-toggle">
              <input
                type="checkbox"
                checked={stockOnly}
                onChange={(e) => setStockOnly(e.target.checked)}
              />
              <span>In stock only</span>
            </label>

            {hasActiveFilters && (
              <button className="reset-filter-btn" onClick={resetFilters}>
                <RefreshCw size={13} />
                <span>Reset filters</span>
              </button>
            )}

            <div className="catalog-count">
              Showing <strong>{filteredProducts.length}</strong> of {products.length} laptops
            </div>
          </div>
        </section>

        {isUsingDemo && (
          <div className="demo-notice">
            <span className="dot" />
            <span>Displaying featured showcase catalog. Real-time updates automatically sync when FastAPI backend is active.</span>
          </div>
        )}

        {/* Products Grid */}
        <section className="products-grid-section">
          {loading ? (
            <div className="loading-grid">
              <div className="spinner" />
              <p>Loading catalog items...</p>
            </div>
          ) : filteredProducts.length === 0 ? (
            <div className="empty-catalog">
              <Laptop size={48} />
              <h3>No laptops match your criteria</h3>
              <p>Try clearing some filters or searching with different terms.</p>
              <button className="primary-btn inline" onClick={resetFilters}>
                Clear all filters
              </button>
            </div>
          ) : (
            <div className="products-grid">
              {filteredProducts.map((p) => {
                const isSelected = selectedForCompare.some((item) => item.product_id === p.product_id)
                const inStock = p.stock_status === 'IN_STOCK'
                const priceNum = Number(p.price_inr || p.price || 0)
                const ramVal = p.ram_gb || p.ram
                const storageVal = p.storage_gb || p.storage
                const weightVal = p.weight_kg || p.weight
                const batteryVal = p.battery_life_hours || p.battery_life

                return (
                  <article key={p.product_id} className={`saas-product-card ${!inStock ? 'out-of-stock' : ''}`}>
                    {/* Top Row: Brand & Stock Badge */}
                    <div className="card-top">
                      <span className="brand-chip">{p.brand}</span>
                      <span className={`stock-badge ${inStock ? 'in' : 'out'}`}>
                        <span className="status-indicator" />
                        {inStock ? 'In Stock' : 'Out of Stock'}
                      </span>
                    </div>

                    {/* Card Media Preview */}
                    <div className="card-media">
                      <div className="laptop-preview-icon">
                        <Laptop size={46} strokeWidth={1.4} />
                      </div>
                      <button
                        className={`compare-checkbox ${isSelected ? 'checked' : ''}`}
                        onClick={() => toggleCompare(p)}
                        title="Add to comparison"
                      >
                        {isSelected ? <Check size={13} /> : null}
                        <span>{isSelected ? 'Compared' : '+ Compare'}</span>
                      </button>
                    </div>

                    {/* Product Title & Processor */}
                    <div className="card-info">
                      <h3 className="card-title" title={p.product_name}>
                        {p.product_name}
                      </h3>
                      <div className="card-processor" title={p.processor}>
                        <Cpu size={14} />
                        <span>{p.processor}</span>
                      </div>
                    </div>

                    {/* Key Specs Pill Grid */}
                    <div className="card-specs">
                      <div className="spec-pill" title="System Memory">
                        <span className="spec-name">RAM</span>
                        <span className="spec-value">{ramVal}GB</span>
                      </div>
                      <div className="spec-pill" title="Solid State Drive">
                        <span className="spec-name">SSD</span>
                        <span className="spec-value">
                          {Number(storageVal) >= 1000 ? `${Number(storageVal) / 1000}TB` : `${storageVal}GB`}
                        </span>
                      </div>
                      <div className="spec-pill" title="Screen Size">
                        <span className="spec-name">Display</span>
                        <span className="spec-value">{p.display_size}"</span>
                      </div>
                      <div className="spec-pill" title="Battery Life">
                        <span className="spec-name">Battery</span>
                        <span className="spec-value">{batteryVal}h</span>
                      </div>
                      <div className="spec-pill" title="Device Weight">
                        <span className="spec-name">Weight</span>
                        <span className="spec-value">{weightVal}kg</span>
                      </div>
                    </div>

                    {/* Price & Primary CTAs */}
                    <div className="card-bottom">
                      <div className="price-block">
                        <span className="price-currency">₹</span>
                        <span className="price-amount">{priceNum.toLocaleString('en-IN')}</span>
                        <span className="price-sub">Free Delivery</span>
                      </div>

                      <div className="card-actions">
                        <button
                          className="quick-view-btn"
                          onClick={() => setQuickViewProduct(p)}
                          title="Full Specifications"
                        >
                          Specs
                        </button>
                        <button
                          className="ask-ai-btn"
                          onClick={() => handleAskAIAboutProduct(p)}
                          title="Ask AI Shopping Assistant about this laptop"
                        >
                          <Sparkles size={14} />
                          <span>Ask AI</span>
                        </button>
                      </div>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>
      </main>

      {/* Floating Comparison Tray (Appears when >= 1 laptop is selected) */}
      {selectedForCompare.length > 0 && (
        <aside className="compare-dock">
          <div className="dock-container">
            <div className="dock-left">
              <span className="dock-title">
                <Layers size={17} />
                <span>Comparing {selectedForCompare.length} {selectedForCompare.length === 1 ? 'laptop' : 'laptops'}</span>
              </span>
              <div className="dock-thumbnails">
                {selectedForCompare.map((item) => (
                  <div key={item.product_id} className="thumb-item">
                    <span>{item.brand} {item.product_name.substring(0, 16)}...</span>
                    <button onClick={() => toggleCompare(item)}>
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="dock-right">
              <button className="dock-clear-btn" onClick={() => setSelectedForCompare([])}>
                Clear
              </button>
              <button
                className="dock-view-btn"
                onClick={() => setComparisonModal(true)}
              >
                Compare Table
              </button>
              {selectedForCompare.length >= 2 && (
                <button
                  className="dock-ai-btn"
                  onClick={handleAskAIToCompare}
                >
                  <Sparkles size={15} />
                  <span>Ask AI to Compare</span>
                </button>
              )}
            </div>
          </div>
        </aside>
      )}

      {/* Quick Specs Modal */}
      {quickViewProduct && (
        <div className="modal-overlay" onClick={() => setQuickViewProduct(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-box">
                <span className="brand-chip">{quickViewProduct.brand}</span>
                <h2>{quickViewProduct.product_name}</h2>
              </div>
              <button className="close-btn" onClick={() => setQuickViewProduct(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {quickViewProduct.description && (
                <div className="product-desc-box">
                  <p>{quickViewProduct.description}</p>
                </div>
              )}

              <h4 className="specs-section-title">Technical Specifications</h4>
              <div className="specs-detail-grid">
                <div className="spec-row">
                  <span className="label"><Cpu size={14} /> Processor</span>
                  <span className="val">{quickViewProduct.processor}</span>
                </div>
                <div className="spec-row">
                  <span className="label"><Layers size={14} /> RAM</span>
                  <span className="val">{quickViewProduct.ram_gb || quickViewProduct.ram} GB</span>
                </div>
                <div className="spec-row">
                  <span className="label"><HardDrive size={14} /> Storage</span>
                  <span className="val">{quickViewProduct.storage_gb || quickViewProduct.storage} GB SSD</span>
                </div>
                <div className="spec-row">
                  <span className="label"><Laptop size={14} /> Display</span>
                  <span className="val">{quickViewProduct.display_size} inches</span>
                </div>
                <div className="spec-row">
                  <span className="label"><Battery size={14} /> Battery</span>
                  <span className="val">{quickViewProduct.battery_life_hours || quickViewProduct.battery_life} hours</span>
                </div>
                <div className="spec-row">
                  <span className="label"><Scale size={14} /> Weight</span>
                  <span className="val">{quickViewProduct.weight_kg || quickViewProduct.weight} kg</span>
                </div>
                <div className="spec-row">
                  <span className="label"><Tag size={14} /> Operating System</span>
                  <span className="val">{quickViewProduct.operating_system}</span>
                </div>
                <div className="spec-row">
                  <span className="label"><Shield size={14} /> Warranty</span>
                  <span className="val">{quickViewProduct.warranty}</span>
                </div>
              </div>

              <div className="modal-footer">
                <div className="modal-price">
                  <span className="amount">
                    ₹{Number(quickViewProduct.price_inr || quickViewProduct.price).toLocaleString('en-IN')}
                  </span>
                  <span className="tax-tag">Taxes Included</span>
                </div>

                <div className="modal-actions">
                  <button
                    className={`compare-toggle-btn ${selectedForCompare.some((x) => x.product_id === quickViewProduct.product_id) ? 'active' : ''}`}
                    onClick={() => toggleCompare(quickViewProduct)}
                  >
                    {selectedForCompare.some((x) => x.product_id === quickViewProduct.product_id) ? 'Selected for Compare' : '+ Add to Compare'}
                  </button>
                  <button
                    className="primary-btn inline"
                    onClick={() => {
                      setQuickViewProduct(null)
                      handleAskAIAboutProduct(quickViewProduct)
                    }}
                  >
                    <Sparkles size={15} />
                    <span>Ask AI About This Laptop</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Side-by-Side Comparison Modal */}
      {comparisonModal && selectedForCompare.length > 0 && (
        <div className="modal-overlay" onClick={() => setComparisonModal(false)}>
          <div className="modal-card wide-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-box">
                <Layers size={20} />
                <h2>Direct Specification Comparison</h2>
              </div>
              <button className="close-btn" onClick={() => setComparisonModal(false)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <div className="compare-scroll">
                <table className="direct-compare-table">
                  <thead>
                    <tr>
                      <th>Specification</th>
                      {selectedForCompare.map((item) => (
                        <th key={item.product_id}>
                          <div className="th-product">
                            <span className="th-brand">{item.brand}</span>
                            <strong>{item.product_name}</strong>
                            <span className="th-price">
                              ₹{Number(item.price_inr || item.price).toLocaleString('en-IN')}
                            </span>
                            <button
                              className="th-remove-btn"
                              onClick={() => toggleCompare(item)}
                            >
                              Remove
                            </button>
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="row-key">Processor</td>
                      {selectedForCompare.map((p) => <td key={p.product_id}>{p.processor}</td>)}
                    </tr>
                    <tr>
                      <td className="row-key">RAM (GB)</td>
                      {selectedForCompare.map((p) => <td key={p.product_id}>{p.ram_gb || p.ram} GB</td>)}
                    </tr>
                    <tr>
                      <td className="row-key">Storage (SSD)</td>
                      {selectedForCompare.map((p) => <td key={p.product_id}>{p.storage_gb || p.storage} GB</td>)}
                    </tr>
                    <tr>
                      <td className="row-key">Display</td>
                      {selectedForCompare.map((p) => <td key={p.product_id}>{p.display_size}"</td>)}
                    </tr>
                    <tr>
                      <td className="row-key">Battery</td>
                      {selectedForCompare.map((p) => <td key={p.product_id}>{p.battery_life_hours || p.battery_life} hours</td>)}
                    </tr>
                    <tr>
                      <td className="row-key">Weight</td>
                      {selectedForCompare.map((p) => <td key={p.product_id}>{p.weight_kg || p.weight} kg</td>)}
                    </tr>
                    <tr>
                      <td className="row-key">Operating System</td>
                      {selectedForCompare.map((p) => <td key={p.product_id}>{p.operating_system}</td>)}
                    </tr>
                    <tr>
                      <td className="row-key">Warranty</td>
                      {selectedForCompare.map((p) => <td key={p.product_id}>{p.warranty}</td>)}
                    </tr>
                    <tr>
                      <td className="row-key">Stock Status</td>
                      {selectedForCompare.map((p) => (
                        <td key={p.product_id}>
                          <span className={`stock-badge ${p.stock_status === 'IN_STOCK' ? 'in' : 'out'}`}>
                            {p.stock_status === 'IN_STOCK' ? 'In Stock' : 'Out of Stock'}
                          </span>
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="compare-modal-footer">
                <button className="link-btn" onClick={() => setSelectedForCompare([])}>
                  Clear all
                </button>
                <button
                  className="primary-btn inline"
                  onClick={() => {
                    setComparisonModal(false)
                    handleAskAIToCompare()
                  }}
                >
                  <Sparkles size={16} />
                  <span>Ask AI to Recommend Best Pick</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Policies Modal */}
      {showPolicies && (
        <div className="modal-overlay" onClick={() => setShowPolicies(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-box">
                <Shield size={20} />
                <h2>VoltKart Store Policies & Guarantees</h2>
              </div>
              <button className="close-btn" onClick={() => setShowPolicies(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body policies-body">
              <div className="policy-card">
                <h4>🔄 14-Day Return & Replacement Policy</h4>
                <p>
                  Any brand new laptop purchased on VoltKart can be returned or replaced within 14 days of delivery
                  if there are hardware defects, transit damage, or specification mismatch. The original packaging,
                  serial numbers, and accessories must be intact.
                </p>
              </div>
              <div className="policy-card">
                <h4>🛡️ Brand Manufacturer Warranty</h4>
                <p>
                  Every laptop carries genuine official manufacturer warranty honored at authorized service centers
                  nationwide. Dell, Apple, Lenovo, HP, ASUS, and Acer support channels are directly linked.
                </p>
              </div>
              <div className="policy-card">
                <h4>🚚 Insured Express Shipping</h4>
                <p>
                  All shipments are 100% transit-insured with real-time tracking and tamper-proof security seals.
                  Dispatches occur within 24 hours of order confirmation.
                </p>
              </div>
              <div className="modal-footer">
                <button
                  className="primary-btn inline"
                  onClick={() => {
                    setShowPolicies(false)
                    if (onOpenChat) onOpenChat('What are your detailed store return and warranty policies?')
                  }}
                >
                  <Bot size={15} />
                  <span>Ask AI Policy Questions</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
