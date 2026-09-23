import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  RotateCcw,
  AlertTriangle,
  Info,
  ShieldCheck,
  Building2,
  Scale,
  Tag,
  Phone,
  Loader2,
  Calculator,
  Apple,
  Package,
  Calendar,
  Layers,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';
import { api } from '../services/api';
import Card from '../components/ui/Card';
import { type ManualProductCheckPayload } from '../types';
import { useLanguage } from '../context/LanguageContext';

type ProductClassification = 'FOOD' | 'NON_FOOD';

interface FormState {
  productType: ProductClassification;
  productName: string;
  brand: string;
  genericName: string;
  category: string;
  netQuantity: string;
  mrp: string;
  unitSalePrice: string;
  manufactureDate: string;
  expiryDate: string;
  bestBefore: string;
  batchNumber: string;
  countryOfOrigin: string;
  manufacturerName: string;
  manufacturerAddress: string;
  packerName: string;
  packerAddress: string;
  consumerCarePhone: string;
  consumerCareEmail: string;
  consumerCareAddress: string;
  fssaiLicense: string;
  ingredients: string;
  allergenInfo: string;
  nutritionalInfo: string;
}

const INITIAL_FORM: FormState = {
  productType: 'FOOD',
  productName: '',
  brand: '',
  genericName: '',
  category: '',
  netQuantity: '',
  mrp: '',
  unitSalePrice: '',
  manufactureDate: '',
  expiryDate: '',
  bestBefore: '',
  batchNumber: '',
  countryOfOrigin: 'India',
  manufacturerName: '',
  manufacturerAddress: '',
  packerName: '',
  packerAddress: '',
  consumerCarePhone: '',
  consumerCareEmail: '',
  consumerCareAddress: '',
  fssaiLicense: '',
  ingredients: '',
  allergenInfo: '',
  nutritionalInfo: '',
};

const DEMO_SAMPLE_PACKAGE: FormState = {
  productType: 'FOOD',
  productName: 'CrunchKart Salted Potato Chips',
  brand: 'CrunchKart',
  genericName: 'Potato Chips',
  category: 'Snack Food',
  netQuantity: '100 g',
  mrp: '₹50 (Incl. of all taxes)',
  unitSalePrice: '₹0.50 / g',
  manufactureDate: '09/2026',
  expiryDate: '',
  bestBefore: '6 Months from manufacture',
  batchNumber: 'CK-260921',
  countryOfOrigin: 'India',
  manufacturerName: 'CrunchKart Foods Pvt. Ltd.',
  manufacturerAddress: 'Plot 42, GIDC Industrial Estate, Surat, Gujarat 395001',
  packerName: '',
  packerAddress: '',
  consumerCarePhone: '1800-000-5678',
  consumerCareEmail: 'care@crunchkart.in',
  consumerCareAddress: 'Plot 42, GIDC Industrial Estate, Surat, Gujarat 395001',
  fssaiLicense: '10000000000001',
  ingredients: 'Potatoes, Edible Vegetable Oil (Palmolein), Salt (1.5%)',
  allergenInfo: 'Manufactured in a facility that also processes peanuts and dairy.',
  nutritionalInfo: 'Energy: 540 kcal, Protein: 6.5g, Carbohydrates: 52g, Total Fat: 34g, Sodium: 600mg per 100g',
};

export default function ManualProductCheck() {
  const navigate = useNavigate();
  const { t } = useLanguage();

  const [formData, setFormData] = useState<FormState>(INITIAL_FORM);
  const [loading, setLoading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [calculatedUspNote, setCalculatedUspNote] = useState<string | null>(null);
  const [sampleLoadedNotice, setSampleLoadedNotice] = useState<string | null>(null);

  const updateField = <K extends keyof FormState>(field: K, value: FormState[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (validationError) setValidationError(null);
    if (apiError) setApiError(null);
  };

  const handleClassificationChange = (type: ProductClassification) => {
    setFormData((prev) => ({ ...prev, productType: type }));
    if (validationError) setValidationError(null);
  };

  const handleLoadSample = () => {
    setFormData(DEMO_SAMPLE_PACKAGE);
    setValidationError(null);
    setApiError(null);
    setCalculatedUspNote(t('manual_check.usp_demo_loaded'));
    setSampleLoadedNotice(t('manual_check.sample_loaded_msg'));
  };

  // Optional convenience helper to calculate Unit Sale Price
  const handleCalculateUSP = () => {
    const rawQty = formData.netQuantity.trim();
    const rawMrp = formData.mrp.replace(/[^0-9.]/g, '');

    const matchQty = rawQty.match(/^([\d.]+)\s*([a-zA-Z]+)?$/);
    const numQty = matchQty ? parseFloat(matchQty[1]) : parseFloat(rawQty);
    const unit = matchQty && matchQty[2] ? matchQty[2].toLowerCase() : 'g';
    const numMrp = parseFloat(rawMrp);

    if (isNaN(numQty) || numQty <= 0 || isNaN(numMrp) || numMrp <= 0) {
      setValidationError(t('manual_check.validation_usp_calc'));
      return;
    }

    let calculated = '';
    if (unit === 'g' || unit === 'gm' || unit === 'gms') {
      if (numQty >= 1000) {
        const kg = numQty / 1000;
        calculated = `₹ ${(numMrp / kg).toFixed(2)} / kg`;
      } else {
        const ratePerKg = ((numMrp / numQty) * 1000).toFixed(2);
        const ratePerG = (numMrp / numQty).toFixed(2);
        calculated = `₹ ${ratePerKg} / kg (₹ ${ratePerG} / g)`;
      }
    } else if (unit === 'kg') {
      calculated = `₹ ${(numMrp / numQty).toFixed(2)} / kg`;
    } else if (unit === 'ml') {
      if (numQty >= 1000) {
        const l = numQty / 1000;
        calculated = `₹ ${(numMrp / l).toFixed(2)} / L`;
      } else {
        const ratePerL = ((numMrp / numQty) * 1000).toFixed(2);
        const ratePerMl = (numMrp / numQty).toFixed(2);
        calculated = `₹ ${ratePerL} / L (₹ ${ratePerMl} / ml)`;
      }
    } else if (unit === 'l' || unit === 'ltr' || unit === 'liter') {
      calculated = `₹ ${(numMrp / numQty).toFixed(2)} / L`;
    } else {
      calculated = `₹ ${(numMrp / numQty).toFixed(2)} / ${unit || 'unit'}`;
    }

    updateField('unitSalePrice', calculated);
    setCalculatedUspNote(t('manual_check.usp_helper_calculated'));
    setValidationError(null);
  };

  const handleReset = () => {
    setFormData(INITIAL_FORM);
    setValidationError(null);
    setApiError(null);
    setCalculatedUspNote(null);
    setSampleLoadedNotice(null);
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    if (!formData.productName.trim()) {
      setValidationError(t('manual_check.validation_enter_name'));
      return;
    }

    setValidationError(null);
    setApiError(null);
    setLoading(true);

    const payload: ManualProductCheckPayload = {
      product_type: formData.productType,
      product_name: formData.productName.trim(),
      brand: formData.brand.trim() || undefined,
      generic_name: formData.genericName.trim() || undefined,
      category: formData.category.trim() || undefined,
      net_quantity: formData.netQuantity.trim() || undefined,
      mrp: formData.mrp.trim() || undefined,
      unit_sale_price: formData.unitSalePrice.trim() || undefined,
      manufacture_date: formData.manufactureDate.trim() || undefined,
      expiry_date: formData.expiryDate.trim() || undefined,
      best_before: formData.bestBefore.trim() || undefined,
      batch_number: formData.batchNumber.trim() || undefined,
      country_of_origin: formData.countryOfOrigin.trim() || undefined,
      manufacturer_name: formData.manufacturerName.trim() || undefined,
      manufacturer_address: formData.manufacturerAddress.trim() || undefined,
      packer_name: formData.packerName.trim() || undefined,
      packer_address: formData.packerAddress.trim() || undefined,
      consumer_care_phone: formData.consumerCarePhone.trim() || undefined,
      consumer_care_email: formData.consumerCareEmail.trim() || undefined,
      consumer_care_address: formData.consumerCareAddress.trim() || undefined,
      fssai_license: formData.productType === 'FOOD' ? (formData.fssaiLicense.trim() || undefined) : undefined,
      ingredients: formData.productType === 'FOOD' ? (formData.ingredients.trim() || undefined) : undefined,
      allergen_info: formData.productType === 'FOOD' ? (formData.allergenInfo.trim() || undefined) : undefined,
      nutritional_info: formData.productType === 'FOOD' ? (formData.nutritionalInfo.trim() || undefined) : undefined,
    };

    try {
      const result = await api.analyzeManual(payload);
      navigate(`/results/${result.id}`, { state: { analysisData: result } });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t('manual_check.api_error_fallback');
      setApiError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/10 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
              <FileText className="w-5 h-5" />
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {t('manual_check.title')}
            </h1>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            {t('manual_check.subtitle')}
          </p>
        </div>
      </div>

      {/* Informational Disclaimer Notice */}
      <div className="p-4 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 flex items-start gap-3 text-slate-700 dark:text-slate-300">
        <Info className="w-5 h-5 text-indigo-500 shrink-0 mt-0.5" />
        <div className="text-xs sm:text-sm space-y-1">
          <p className="font-semibold text-slate-900 dark:text-slate-100">
            {t('manual_check.disclaimer_title')}
          </p>
          <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
            {t('manual_check.disclaimer_desc')}
          </p>
        </div>
      </div>

      {/* Demo Sample Package Loader (Judge & Testing Helper) */}
      <Card className="p-4 sm:p-5 bg-gradient-to-r from-amber-500/5 via-indigo-500/5 to-purple-500/5 border border-amber-200 dark:border-amber-900/40">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-500/20 text-amber-800 dark:text-amber-300 border border-amber-500/30 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-amber-500" />
                {t('manual_check.demo_badge')}
              </span>
              <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                {t('manual_check.demo_title')}
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t('manual_check.demo_desc')}
            </p>
            <p className="text-[11px] text-amber-700 dark:text-amber-400 font-medium">
              {t('manual_check.demo_warning')}
            </p>
          </div>
          <div className="shrink-0 pt-1 sm:pt-0">
            <button
              type="button"
              onClick={handleLoadSample}
              className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white font-bold text-xs shadow-xs hover:shadow-md transition-all cursor-pointer flex items-center justify-center gap-2"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {t('manual_check.demo_btn')}
            </button>
          </div>
        </div>

        {sampleLoadedNotice && (
          <div className="mt-3 pt-3 border-t border-amber-200/60 dark:border-amber-900/40 flex items-center gap-2 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />
            <span>{sampleLoadedNotice}</span>
          </div>
        )}
      </Card>

      {/* Product Classification Toggle */}
      <Card className="p-4 sm:p-5">
        <div className="space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-indigo-500" />
            {t('manual_check.classification_label')}
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => handleClassificationChange('FOOD')}
              className={`flex items-center gap-3 p-3.5 rounded-xl border transition-all text-left cursor-pointer ${
                formData.productType === 'FOOD'
                  ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-950 dark:text-emerald-100 ring-2 ring-emerald-500/20'
                  : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:border-slate-300'
              }`}
            >
              <div className={`p-2 rounded-lg ${formData.productType === 'FOOD' ? 'bg-emerald-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}`}>
                <Apple className="w-5 h-5" />
              </div>
              <div>
                <div className="font-bold text-sm">{t('manual_check.food_product')}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400">{t('manual_check.food_desc')}</div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => handleClassificationChange('NON_FOOD')}
              className={`flex items-center gap-3 p-3.5 rounded-xl border transition-all text-left cursor-pointer ${
                formData.productType === 'NON_FOOD'
                  ? 'bg-indigo-500/10 border-indigo-500/40 text-indigo-950 dark:text-indigo-100 ring-2 ring-indigo-500/20'
                  : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:border-slate-300'
              }`}
            >
              <div className={`p-2 rounded-lg ${formData.productType === 'NON_FOOD' ? 'bg-indigo-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}`}>
                <Package className="w-5 h-5" />
              </div>
              <div>
                <div className="font-bold text-sm">{t('manual_check.non_food_commodity')}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400">{t('manual_check.non_food_desc')}</div>
              </div>
            </button>
          </div>
        </div>
      </Card>

      {/* Main Declaration Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* GROUP 1: Product Information */}
        <Card className="p-5 space-y-4">
          <div className="border-b border-slate-200 dark:border-slate-800 pb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider flex items-center gap-2">
              <Tag className="w-4 h-4 text-indigo-500" />
              {t('manual_check.group_1')}
            </h2>
            <span className="text-[11px] font-semibold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 rounded border border-amber-200/50 dark:border-amber-800/50">
              {t('manual_check.required_field')}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5 md:col-span-2">
              <label htmlFor="productName" className="block text-xs font-bold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_product_name')} <span className="text-red-500">*</span>
              </label>
              <input
                id="productName"
                type="text"
                value={formData.productName}
                onChange={(e) => updateField('productName', e.target.value)}
                placeholder="e.g. High Protein Crunchy Peanut Butter"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
                required
              />
              <p className="text-[11px] text-slate-500">{t('manual_check.product_name_hint')}</p>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="brand" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_brand')}
              </label>
              <input
                id="brand"
                type="text"
                value={formData.brand}
                onChange={(e) => updateField('brand', e.target.value)}
                placeholder="e.g. Alpino"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="genericName" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_generic_name')}
              </label>
              <input
                id="genericName"
                type="text"
                value={formData.genericName}
                onChange={(e) => updateField('genericName', e.target.value)}
                placeholder="e.g. Roasted Peanut Spread"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>

            <div className="space-y-1.5 md:col-span-2">
              <label htmlFor="category" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_category')}
              </label>
              <input
                id="category"
                type="text"
                value={formData.category}
                onChange={(e) => updateField('category', e.target.value)}
                placeholder="e.g. Food & Grocery / Spreads"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>
          </div>
        </Card>

        {/* GROUP 2: Quantity & Pricing */}
        <Card className="p-5 space-y-4">
          <div className="border-b border-slate-200 dark:border-slate-800 pb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider flex items-center gap-2">
              <Scale className="w-4 h-4 text-indigo-500" />
              {t('manual_check.group_2')}
            </h2>
            <button
              type="button"
              onClick={handleCalculateUSP}
              className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 flex items-center gap-1.5 cursor-pointer"
            >
              <Calculator className="w-3.5 h-3.5" />
              {t('manual_check.auto_calc_usp')}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="netQuantity" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_net_quantity')}
              </label>
              <input
                id="netQuantity"
                type="text"
                value={formData.netQuantity}
                onChange={(e) => updateField('netQuantity', e.target.value)}
                placeholder="e.g. 500 g, 1 kg, 250 ml"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
              <p className="text-[11px] text-slate-500">{t('manual_check.net_quantity_hint')}</p>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="mrp" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_mrp')}
              </label>
              <input
                id="mrp"
                type="text"
                value={formData.mrp}
                onChange={(e) => updateField('mrp', e.target.value)}
                placeholder="e.g. ₹ 499.00 or 499"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
              <p className="text-[11px] text-slate-500">{t('manual_check.mrp_hint')}</p>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="unitSalePrice" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_unit_sale_price')}
              </label>
              <input
                id="unitSalePrice"
                type="text"
                value={formData.unitSalePrice}
                onChange={(e) => {
                  updateField('unitSalePrice', e.target.value);
                  setCalculatedUspNote(null);
                }}
                placeholder="e.g. ₹ 0.50 / g or ₹ 500 / kg"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
              {calculatedUspNote ? (
                <p className="text-[11px] text-indigo-600 dark:text-indigo-400 font-medium">{calculatedUspNote}</p>
              ) : (
                <p className="text-[11px] text-slate-500">{t('manual_check.usp_hint')}</p>
              )}
            </div>
          </div>
        </Card>

        {/* GROUP 3: Dates */}
        <Card className="p-5 space-y-4">
          <div className="border-b border-slate-200 dark:border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider flex items-center gap-2">
              <Calendar className="w-4 h-4 text-indigo-500" />
              {t('manual_check.group_3')}
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="manufactureDate" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_mfg_date')}
              </label>
              <input
                id="manufactureDate"
                type="text"
                value={formData.manufactureDate}
                onChange={(e) => updateField('manufactureDate', e.target.value)}
                placeholder="e.g. 15/01/2026 or Jan 2026"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
              <p className="text-[11px] text-slate-500">{t('manual_check.mfg_date_hint')}</p>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="expiryDate" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_expiry_date')}
              </label>
              <input
                id="expiryDate"
                type="text"
                value={formData.expiryDate}
                onChange={(e) => updateField('expiryDate', e.target.value)}
                placeholder="e.g. 15/01/2027"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="bestBefore" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_best_before')}
              </label>
              <input
                id="bestBefore"
                type="text"
                value={formData.bestBefore}
                onChange={(e) => updateField('bestBefore', e.target.value)}
                placeholder="e.g. 12 months from packing"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>
          </div>
        </Card>

        {/* GROUP 4: Manufacturer / Packer */}
        <Card className="p-5 space-y-4">
          <div className="border-b border-slate-200 dark:border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider flex items-center gap-2">
              <Building2 className="w-4 h-4 text-indigo-500" />
              {t('manual_check.group_4')}
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="manufacturerName" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_manufacturer_name')}
              </label>
              <input
                id="manufacturerName"
                type="text"
                value={formData.manufacturerName}
                onChange={(e) => updateField('manufacturerName', e.target.value)}
                placeholder="e.g. Alpino Health Foods Pvt Ltd"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="manufacturerAddress" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_manufacturer_address')}
              </label>
              <input
                id="manufacturerAddress"
                type="text"
                value={formData.manufacturerAddress}
                onChange={(e) => updateField('manufacturerAddress', e.target.value)}
                placeholder="e.g. Plot No 12, GIDC, Surat, Gujarat - 395007"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>
          </div>
        </Card>

        {/* GROUP 5: Other Declarations */}
        <Card className="p-5 space-y-4">
          <div className="border-b border-slate-200 dark:border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider flex items-center gap-2">
              <Phone className="w-4 h-4 text-indigo-500" />
              {t('manual_check.group_5')}
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="batchNumber" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_batch_no')}
              </label>
              <input
                id="batchNumber"
                type="text"
                value={formData.batchNumber}
                onChange={(e) => updateField('batchNumber', e.target.value)}
                placeholder="e.g. BATCH-2026-04"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="countryOfOrigin" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_country_of_origin')}
              </label>
              <input
                id="countryOfOrigin"
                type="text"
                value={formData.countryOfOrigin}
                onChange={(e) => updateField('countryOfOrigin', e.target.value)}
                placeholder="e.g. India"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="consumerCarePhone" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_helpline_phone')}
              </label>
              <input
                id="consumerCarePhone"
                type="text"
                value={formData.consumerCarePhone}
                onChange={(e) => updateField('consumerCarePhone', e.target.value)}
                placeholder="e.g. 1800-123-4567"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>

            <div className="space-y-1.5 md:col-span-3">
              <label htmlFor="consumerCareEmail" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('manual_check.field_helpline_email')}
              </label>
              <input
                id="consumerCareEmail"
                type="text"
                value={formData.consumerCareEmail}
                onChange={(e) => updateField('consumerCareEmail', e.target.value)}
                placeholder="e.g. care@alpino.in or same as manufacturer address"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>
          </div>
        </Card>

        {/* GROUP 6: Food Information (Only if Food Product) */}
        {formData.productType === 'FOOD' && (
          <Card className="p-5 space-y-4 border-emerald-500/30 dark:border-emerald-500/20 bg-emerald-50/20 dark:bg-emerald-950/10">
            <div className="border-b border-emerald-200/60 dark:border-emerald-800/40 pb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold text-emerald-950 dark:text-emerald-200 uppercase tracking-wider flex items-center gap-2">
                <Apple className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                {t('manual_check.group_6')}
              </h2>
              <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-900/40 px-2 py-0.5 rounded">
                {t('manual_check.food_only_badge')}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5 md:col-span-2">
                <label htmlFor="fssaiLicense" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {t('manual_check.field_fssai_license')}
                </label>
                <input
                  id="fssaiLicense"
                  type="text"
                  value={formData.fssaiLicense}
                  onChange={(e) => updateField('fssaiLicense', e.target.value)}
                  placeholder="e.g. 10019021004567"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
                />
              </div>

              <div className="space-y-1.5 md:col-span-2">
                <label htmlFor="ingredients" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {t('manual_check.field_ingredients')}
                </label>
                <textarea
                  id="ingredients"
                  rows={2}
                  value={formData.ingredients}
                  onChange={(e) => updateField('ingredients', e.target.value)}
                  placeholder="e.g. Roasted Peanuts (100%), Salt"
                  className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 resize-y"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="allergenInfo" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {t('manual_check.field_allergen_info')}
                </label>
                <input
                  id="allergenInfo"
                  type="text"
                  value={formData.allergenInfo}
                  onChange={(e) => updateField('allergenInfo', e.target.value)}
                  placeholder="e.g. Contains Peanuts. May contain tree nuts."
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="nutritionalInfo" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {t('manual_check.field_nutritional_info')}
                </label>
                <input
                  id="nutritionalInfo"
                  type="text"
                  value={formData.nutritionalInfo}
                  onChange={(e) => updateField('nutritionalInfo', e.target.value)}
                  placeholder="e.g. Energy: 588 kcal, Protein: 30g, Carbs: 20g"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
                />
              </div>
            </div>
          </Card>
        )}

        {/* Error Messages */}
        {validationError && (
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-900 dark:text-amber-200 text-xs sm:text-sm flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        {apiError && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-900 dark:text-red-200 text-xs sm:text-sm flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-red-500 shrink-0" />
            <span>{apiError}</span>
          </div>
        )}

        {/* Actions Bar */}
        <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleReset}
            disabled={loading}
            className="w-full sm:w-auto px-5 py-3 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold text-sm transition-colors cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <RotateCcw className="w-4 h-4" />
            {t('manual_check.clear_form')}
          </button>

          <button
            type="submit"
            disabled={loading}
            className="w-full sm:w-auto px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-bold text-sm shadow-md shadow-indigo-600/30 transition-all cursor-pointer flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {t('manual_check.screening_btn')}
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4" />
                {t('manual_check.run_check')}
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
