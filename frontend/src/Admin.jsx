import { useEffect, useState } from 'react'
import { Package, FileText, FileUp, Trash2, MessageSquare, LogOut, Laptop } from 'lucide-react'
import api, { errorMessage } from './api'
import { useAuth } from './auth'

const PRODUCT_FIELDS = [
  ['product_name', 'Product name', 'text'],
  ['brand', 'Brand', 'text'],
  ['processor', 'Processor', 'text'],
  ['ram', 'RAM (GB)', 'number'],
  ['storage', 'Storage (GB)', 'number'],
  ['display_size', 'Display (inch)', 'number'],
  ['battery_life', 'Battery (hours)', 'number'],
  ['weight', 'Weight (kg)', 'number'],
  ['operating_system', 'Operating system', 'text'],
  ['price', 'Price (₹)', 'number'],
  ['warranty', 'Warranty', 'text'],
]

const EMPTY_PRODUCT = {
  product_name: '', brand: '', processor: '', ram: '16', storage: '512', display_size: '15.6',
  battery_life: '8', weight: '1.6', operating_system: 'Windows 11', price: '',
  warranty: '1 year manufacturer warranty', stock_status: 'IN_STOCK', description: '',
}

function ProductsTab({ notify }) {
  const [items, setItems] = useState([])
  const [form, setForm] = useState(EMPTY_PRODUCT)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    try {
      const { data } = await api.get('/products')
      setItems(data)
    } catch (err) {
      notify('error', errorMessage(err, 'Could not load products.'))
    }
  }
  useEffect(() => { load() }, [])

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api.post('/admin/products', {
        ...form,
        ram: Number(form.ram),
        storage: Number(form.storage),
        display_size: Number(form.display_size),
        battery_life: Number(form.battery_life),
        weight: Number(form.weight),
        price: Number(form.price),
      })
      setForm(EMPTY_PRODUCT)
      notify('ok', 'Product added.')
      load()
    } catch (err) {
      notify('error', errorMessage(err, 'Could not add product.'))
    } finally {
      setSaving(false)
    }
  }

  const toggleStock = async (p) => {
    const next = p.stock_status === 'IN_STOCK' ? 'OUT_OF_STOCK' : 'IN_STOCK'
    try {
      await api.patch(`/admin/products/${p.product_id}`, { stock_status: next })
      load()
    } catch (err) {
      notify('error', errorMessage(err, 'Could not update product.'))
    }
  }

  const remove = async (p) => {
    if (!window.confirm(`Delete "${p.product_name}"?`)) return
    try {
      await api.delete(`/admin/products/${p.product_id}`)
      notify('ok', 'Product deleted.')
      load()
    } catch (err) {
      notify('error', errorMessage(err, 'Could not delete product.'))
    }
  }

  return (
    <>
      <form className="panel" onSubmit={submit}>
        <h3>Add a product</h3>
        <div className="form-grid">
          {PRODUCT_FIELDS.map(([key, label, type]) => (
            <label className="field" key={key}>{label}
              <input type={type} step={type === 'number' ? 'any' : undefined} value={form[key]}
                onChange={set(key)} required />
            </label>
          ))}
          <label className="field">Stock status
            <select value={form.stock_status} onChange={set('stock_status')}>
              <option value="IN_STOCK">In stock</option>
              <option value="OUT_OF_STOCK">Out of stock</option>
            </select>
          </label>
          <label className="field wide">Description
            <input value={form.description} onChange={set('description')} />
          </label>
        </div>
        <button className="primary-btn inline" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Add product'}</button>
      </form>

      <div className="panel">
        <h3>Catalog ({items.length})</h3>
        <div className="table-scroll">
          <table className="admin-table">
            <thead><tr><th>Name</th><th>Brand</th><th>Price</th><th>RAM</th><th>Stock</th><th /></tr></thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.product_id}>
                  <td>{p.product_name}</td>
                  <td>{p.brand}</td>
                  <td>₹{Number(p.price).toLocaleString('en-IN')}</td>
                  <td>{p.ram} GB</td>
                  <td>
                    <button className={`pill ${p.stock_status === 'IN_STOCK' ? 'on' : 'off'}`} onClick={() => toggleStock(p)}>
                      {p.stock_status === 'IN_STOCK' ? 'In stock' : 'Out of stock'}
                    </button>
                  </td>
                  <td><button className="icon-btn danger" onClick={() => remove(p)} aria-label="Delete"><Trash2 size={16} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {items.length >= 100 && <p className="hint">Showing the first 100 products (the products endpoint is capped at 100).</p>}
      </div>
    </>
  )
}

function PoliciesTab({ notify }) {
  const [items, setItems] = useState([])
  const [file, setFile] = useState(null)
  const [pdfTitle, setPdfTitle] = useState('')
  const [pdfCategory, setPdfCategory] = useState('')
  const [replace, setReplace] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [manual, setManual] = useState({ title: '', category: '', content: '' })

  const load = async () => {
    try {
      const { data } = await api.get('/admin/policies')
      setItems(data)
    } catch (err) {
      notify('error', errorMessage(err, 'Could not load policies.'))
    }
  }
  useEffect(() => { load() }, [])

  const upload = async (e) => {
    e.preventDefault()
    if (!file) return
    setUploading(true)
    try {
      const body = new FormData()
      body.append('file', file)
      body.append('title', pdfTitle)
      body.append('category', pdfCategory)
      body.append('replace_existing', String(replace))
      const { data } = await api.post('/admin/policies/upload-pdf', body)
      notify('ok', `PDF processed: ${data.chunks_created} section(s) created, ${data.replaced_existing_rows} replaced.`)
      setFile(null)
      setPdfTitle('')
      setPdfCategory('')
      e.target.reset()
      load()
    } catch (err) {
      notify('error', errorMessage(err, 'PDF upload failed.'))
    } finally {
      setUploading(false)
    }
  }

  const addManual = async (e) => {
    e.preventDefault()
    try {
      await api.post('/admin/policies', manual)
      setManual({ title: '', category: '', content: '' })
      notify('ok', 'Policy added.')
      load()
    } catch (err) {
      notify('error', errorMessage(err, 'Could not add policy.'))
    }
  }

  const toggleActive = async (p) => {
    try {
      await api.patch(`/admin/policies/${p.policy_id}`, { is_active: !p.is_active })
      load()
    } catch (err) {
      notify('error', errorMessage(err, 'Could not update policy.'))
    }
  }

  const remove = async (p) => {
    if (!window.confirm(`Delete "${p.title}"?`)) return
    try {
      await api.delete(`/admin/policies/${p.policy_id}`)
      load()
    } catch (err) {
      notify('error', errorMessage(err, 'Could not delete policy.'))
    }
  }

  return (
    <>
      <form className="panel" onSubmit={upload}>
        <h3>Upload a policy PDF</h3>
        <p className="hint">The text is extracted and split into sections the assistant can search. Scanned (image-only) PDFs are not supported.</p>
        <div className="form-grid">
          <label className="field wide">PDF file
            <input type="file" accept="application/pdf" required onChange={(e) => setFile(e.target.files[0] || null)} />
          </label>
          <label className="field">Title
            <input value={pdfTitle} onChange={(e) => setPdfTitle(e.target.value)} required maxLength={150} placeholder="e.g. EMI and Offers" />
          </label>
          <label className="field">Category
            <input value={pdfCategory} onChange={(e) => setPdfCategory(e.target.value)} required maxLength={80} placeholder="e.g. payment" />
          </label>
          <label className="check wide">
            <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
            Replace existing entries that have the same title
          </label>
        </div>
        <button className="primary-btn inline" type="submit" disabled={uploading || !file}>
          <FileUp size={16} /> {uploading ? 'Processing…' : 'Upload and process'}
        </button>
      </form>

      <form className="panel" onSubmit={addManual}>
        <h3>Add policy text manually</h3>
        <div className="form-grid">
          <label className="field">Title
            <input value={manual.title} onChange={(e) => setManual({ ...manual, title: e.target.value })} required />
          </label>
          <label className="field">Category
            <input value={manual.category} onChange={(e) => setManual({ ...manual, category: e.target.value })} required />
          </label>
          <label className="field wide">Content
            <textarea rows={4} value={manual.content} onChange={(e) => setManual({ ...manual, content: e.target.value })} required maxLength={20000} />
          </label>
        </div>
        <button className="primary-btn inline" type="submit">Add policy</button>
      </form>

      <div className="panel">
        <h3>Policies ({items.length})</h3>
        {items.map((p) => (
          <div className="policy-row" key={p.policy_id}>
            <div className="policy-text">
              <strong>{p.title}</strong> <span className="tag">{p.category}</span>
              <p>{p.content.length > 180 ? p.content.slice(0, 180) + '…' : p.content}</p>
            </div>
            <button className={`pill ${p.is_active ? 'on' : 'off'}`} onClick={() => toggleActive(p)}>{p.is_active ? 'Active' : 'Inactive'}</button>
            <button className="icon-btn danger" onClick={() => remove(p)} aria-label="Delete"><Trash2 size={16} /></button>
          </div>
        ))}
      </div>
    </>
  )
}

export default function Admin({ onOpenChat }) {
  const { user, logout } = useAuth()
  const [tab, setTab] = useState('products')
  const [notice, setNotice] = useState(null)

  const notify = (type, text) => {
    setNotice({ type, text })
    setTimeout(() => setNotice(null), 5000)
  }

  return (
    <div className="admin-shell">
      <header className="admin-top">
        <div className="brand dark"><div className="brand-icon"><Laptop size={21} /></div><span>VoltKart Admin</span></div>
        <div className="admin-actions">
          <span className="admin-user">{user.email}</span>
          <button className="ghost-btn" onClick={onOpenChat}><MessageSquare size={15} /> Open chat</button>
          <button className="ghost-btn" onClick={logout}><LogOut size={15} /> Sign out</button>
        </div>
      </header>

      <div className="admin-body">
        <div className="tabs">
          <button className={tab === 'products' ? 'active' : ''} onClick={() => setTab('products')}><Package size={15} /> Products</button>
          <button className={tab === 'policies' ? 'active' : ''} onClick={() => setTab('policies')}><FileText size={15} /> Policies</button>
        </div>
        {notice && <div className={notice.type === 'ok' ? 'ok-banner' : 'error-banner'}>{notice.text}</div>}
        {tab === 'products' ? <ProductsTab notify={notify} /> : <PoliciesTab notify={notify} />}
      </div>
    </div>
  )
}