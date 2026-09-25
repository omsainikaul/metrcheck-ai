import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  Save, 
  Building2, 
  Tag, 
  Barcode, 
  ShieldCheck, 
  Scale, 
  Globe, 
  AlertCircle,
  AlertTriangle,
  FileCheck
} from 'lucide-react';
import { api } from '../services/api';
import { type ProductCreateInput, type Product } from '../types';
import { useLanguage } from '../context/LanguageContext';

export default function ProductNew() {
  const navigate = useNavigate();
  const { t } = useLanguage();

  const [formData, setFormData] = useState<ProductCreateInput>({
    product_name: '',
    brand_name: '',
    category: 'GENERAL',
    gtin_barcode: '',
    fssai_license: '',
    legal_metrology_license: '',
    net_quantity_declared: '',
    mrp_declared: 0.0,
    unit_sale_price_declared: '',
    manufacturer_name: '',
    country_of_origin: 'India',
  });

  const [existingProducts, setExistingProducts] = useState<Product[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    api.getProducts({ limit: 200, status: 'ACTIVE' }).then(res => {
      if (isMounted && res?.products) {
        setExistingProducts(res.products);
      }
    }).catch(() => {});
    return () => { isMounted = false; };
  }, []);

  const isDuplicateGtin = useMemo(() => {
    const norm = (formData.gtin_barcode || '').trim().toLowerCase();
    if (!norm) return false;
    return existingProducts.some(p => (p.gtin_barcode || '').trim().toLowerCase() === norm);
  }, [formData.gtin_barcode, existingProducts]);

  const handleChange = (field: keyof ProductCreateInput, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.product_name.trim()) {
      setError(t('merchant.product_new.validation_name_required'));
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const created = await api.createProduct({
        ...formData,
        mrp_declared: Number(formData.mrp_declared) || 0.0
      });
      navigate(`/products/${created.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to register product SKU.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/products')}
            className="p-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
              {t('merchant.product_new.title')}
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-0.5">
              {t('merchant.product_new.subtitle')}
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section 1: Core Product Identity */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <Tag className="w-4 h-4 text-sky-600 dark:text-sky-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              {t('merchant.product_new.sec_identity')}
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_name')} <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Organic Almond Milk 1L Tetra Pak"
                value={formData.product_name}
                onChange={(e) => handleChange('product_name', e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_brand')}
              </label>
              <input
                type="text"
                placeholder="e.g. NutriFarm"
                value={formData.brand_name}
                onChange={(e) => handleChange('brand_name', e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_category')}
              </label>
              <select
                value={formData.category}
                onChange={(e) => handleChange('category', e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all cursor-pointer"
              >
                <option value="GENERAL">{t('merchant.categories.GENERAL')}</option>
                <option value="FOOD_BEVERAGES">{t('merchant.categories.FOOD_BEVERAGES')}</option>
                <option value="COSMETICS">{t('merchant.categories.COSMETICS')}</option>
                <option value="ELECTRONICS">{t('merchant.categories.ELECTRONICS')}</option>
                <option value="PHARMACEUTICALS">{t('merchant.categories.PHARMACEUTICALS')}</option>
                <option value="HOUSEHOLD">{t('merchant.categories.HOUSEHOLD')}</option>
                <option value="APPAREL">{t('merchant.categories.APPAREL')}</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_gtin')}
              </label>
              <div className="relative">
                <Barcode className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="text"
                  placeholder="e.g. 8901234567890"
                  value={formData.gtin_barcode}
                  onChange={(e) => handleChange('gtin_barcode', e.target.value)}
                  className="w-full pl-9 pr-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-mono text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
                />
              </div>
              {isDuplicateGtin && (
                <div className="mt-1.5 flex items-start gap-1.5 text-xs text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                  <p>{t('sku_workflow.gtin_duplicate_warning')}</p>
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_origin')}
              </label>
              <div className="relative">
                <Globe className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="text"
                  placeholder="e.g. India"
                  value={formData.country_of_origin}
                  onChange={(e) => handleChange('country_of_origin', e.target.value)}
                  className="w-full pl-9 pr-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Statutory Metrology Declarations */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <Scale className="w-4 h-4 text-sky-600 dark:text-sky-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              {t('merchant.product_new.sec_declarations')}
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_net_qty')}
              </label>
              <input
                type="text"
                placeholder="e.g. 1 L or 500 g"
                value={formData.net_quantity_declared}
                onChange={(e) => handleChange('net_quantity_declared', e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
              />
              <p className="text-[10px] text-slate-400 mt-1">{t('merchant.product_new.hint_si_units')}</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_mrp')}
              </label>
              <div className="relative">
                <span className="text-slate-400 font-bold absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none text-sm">₹</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0.00"
                  value={formData.mrp_declared || ''}
                  onChange={(e) => handleChange('mrp_declared', parseFloat(e.target.value) || 0)}
                  className="w-full pl-8 pr-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-mono text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
                />
              </div>
              <p className="text-[10px] text-slate-400 mt-1">{t('merchant.product_new.hint_incl_taxes')}</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_usp')}
              </label>
              <input
                type="text"
                placeholder="e.g. ₹0.25 / ml"
                value={formData.unit_sale_price_declared}
                onChange={(e) => handleChange('unit_sale_price_declared', e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
              />
              <p className="text-[10px] text-slate-400 mt-1">{t('merchant.product_new.hint_per_unit')}</p>
            </div>
          </div>
        </div>

        {/* Section 3: Manufacturer & Regulatory Licenses */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <Building2 className="w-4 h-4 text-sky-600 dark:text-sky-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              {t('merchant.product_new.sec_licensure')}
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_mfg_address')}
              </label>
              <textarea
                rows={2}
                placeholder="e.g. NutriFarm Foods Pvt. Ltd., Plot 12, Industrial Area, Phase II, Pune, Maharashtra - 411001"
                value={formData.manufacturer_name}
                onChange={(e) => handleChange('manufacturer_name', e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_fssai')}
              </label>
              <div className="relative">
                <ShieldCheck className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="text"
                  maxLength={14}
                  placeholder="14-digit FSSAI Number"
                  value={formData.fssai_license}
                  onChange={(e) => handleChange('fssai_license', e.target.value)}
                  className="w-full pl-9 pr-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-mono text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                {t('merchant.product_new.field_lm_license')}
              </label>
              <div className="relative">
                <FileCheck className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="text"
                  placeholder="e.g. LM/MH/PACKER/2024/0981"
                  value={formData.legal_metrology_license}
                  onChange={(e) => handleChange('legal_metrology_license', e.target.value)}
                  className="w-full pl-9 pr-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-mono text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={() => navigate('/products')}
            className="px-5 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
          >
            {t('common.cancel') || 'Cancel'}
          </button>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-6 py-2.5 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition-all shadow-sm hover:shadow-md cursor-pointer"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? t('merchant.product_new.btn_registering') : t('merchant.product_new.btn_save')}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
