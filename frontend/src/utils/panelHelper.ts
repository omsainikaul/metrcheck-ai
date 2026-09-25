/**
 * MetrCheck AI - Panel Localization & Identification Helper
 *
 * Normalizes package panel labels across multilingual inputs (e.g. Hindi "सामने", Marathi "समोर",
 * Bengali "সামने", Gujarati "આગળ", canonical "Front", etc.) and maps them to the active UI language.
 */

export type CanonicalPanelType = 'front' | 'back' | 'side1' | 'side2' | 'other';

const FRONT_ALIASES = new Set([
  'front',
  'front panel',
  'front_panel',
  'front_label',
  'सामने',
  'समोर',
  'সামনে',
  'આગળ',
  'முன்பக்கம்',
  'ಮುಂಭಾಗ',
  'ముందు',
  'മുൻഭാഗം',
  'ਅੱਗੇ'
]);

const BACK_ALIASES = new Set([
  'back',
  'back panel',
  'back_panel',
  'back_label',
  'पीछे',
  'मागे',
  'পেছনে',
  'પાછળ',
  'பின்பக்கம்',
  'ಹಿಂಭಾಗ',
  'వెనుక',
  'പിൻഭാഗം',
  'ਪਿੱਛੇ'
]);

const SIDE1_ALIASES = new Set([
  'side 1',
  'side1',
  'side_1',
  'side 1 panel',
  'साइड 1',
  'बाजू 1',
  'সাইড ১',
  'બાજુ ૧',
  'பக்கவாட்டு 1',
  'ಬದಿ 1',
  'సైడ్ 1',
  'വശം 1',
  'ਪਾਸਾ 1'
]);

const SIDE2_ALIASES = new Set([
  'side 2',
  'side2',
  'side_2',
  'side 2 panel',
  'साइड 2',
  'बाजू 2',
  'সাইড ২',
  'બાજુ ૨',
  'பக்கவாட்டு 2',
  'ಬದಿ 2',
  'సైడ్ 2',
  'വശം 2',
  'ਪਾਸਾ 2'
]);

/**
 * Resolves a raw panel label string to a canonical panel type ('front' | 'back' | 'side1' | 'side2' | 'other').
 */
export function getCanonicalPanelType(label: string | null | undefined, index = 0): CanonicalPanelType {
  if (!label || label.trim() === '') {
    if (index === 0) return 'front';
    if (index === 1) return 'back';
    if (index === 2) return 'side1';
    if (index === 3) return 'side2';
    return 'other';
  }

  const clean = label.trim().toLowerCase();

  if (FRONT_ALIASES.has(clean)) return 'front';
  if (BACK_ALIASES.has(clean)) return 'back';
  if (SIDE1_ALIASES.has(clean)) return 'side1';
  if (SIDE2_ALIASES.has(clean)) return 'side2';

  // Substring checks
  for (const alias of FRONT_ALIASES) {
    if (clean.includes(alias)) return 'front';
  }
  for (const alias of BACK_ALIASES) {
    if (clean.includes(alias)) return 'back';
  }
  for (const alias of SIDE1_ALIASES) {
    if (clean.includes(alias)) return 'side1';
  }
  for (const alias of SIDE2_ALIASES) {
    if (clean.includes(alias)) return 'side2';
  }

  if (clean.startsWith('side') || clean.startsWith('साइड') || clean.startsWith('बाजू') || clean.startsWith('সাইড') || clean.startsWith('બાજુ')) {
    if (clean.includes('2') || clean.includes('२') || clean.includes('২')) return 'side2';
    return 'side1';
  }

  if (index === 0 && !clean.includes('back') && !clean.includes('side') && !clean.includes('पीछे') && !clean.includes('मागे')) {
    return 'front';
  }

  return 'other';
}

/**
 * Returns true if the panel corresponds to the Front view (Principal Display Panel).
 */
export function isFrontPanel(label: string | null | undefined, index = 0): boolean {
  return getCanonicalPanelType(label, index) === 'front';
}

/**
 * Formats and localizes any panel label according to the active translation function `t`.
 */
export function getLocalizedPanelName(
  label: string | null | undefined,
  index: number,
  t: (key: string, options?: any) => string
): string {
  const panelType = getCanonicalPanelType(label, index);

  switch (panelType) {
    case 'front':
      return t('analysis.slots.front_label', { defaultValue: 'Front' });
    case 'back':
      return t('analysis.slots.back_label', { defaultValue: 'Back' });
    case 'side1':
      return t('analysis.slots.side1_label', { defaultValue: 'Side 1' });
    case 'side2':
      return t('analysis.slots.side2_label', { defaultValue: 'Side 2' });
    default: {
      const trimmed = (label || '').trim();
      if (!trimmed) {
        return `${t('common.panel', { defaultValue: 'Panel' })} ${index + 1}`;
      }

      // Check for "Panel X" pattern
      const panelMatch = trimmed.match(/^(?:Panel|Image|Face)\s*(\d+)$/i);
      if (panelMatch) {
        return `${t('common.panel', { defaultValue: 'Panel' })} ${panelMatch[1]}`;
      }

      return trimmed;
    }
  }
}
