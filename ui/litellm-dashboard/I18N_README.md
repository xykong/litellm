# Internationalization (i18n) Support - Proof of Concept

This PR introduces internationalization (i18n) support for the LiteLLM Dashboard UI. This is a **proof of concept** implementation to demonstrate the architecture and gather feedback from maintainers.

## Background

Many users have requested multi-language support for the LiteLLM Dashboard. This is especially important for:
- Non-English speaking users who prefer their native language
- Enterprises deploying LiteLLM in different regions
- Better accessibility and user experience

## Architecture Overview

### Technology Stack

We chose **react-i18next** for the following reasons:
1. **Industry Standard**: Most popular i18n solution for React applications
2. **React Integration**: Excellent hooks-based API (`useTranslation`)
3. **Language Detection**: Built-in browser language detection
4. **Performance**: Supports lazy loading of translations
5. **TypeScript Support**: Full TypeScript support

### Implementation Structure

```
src/
├── i18n/
│   └── config.ts              # i18n configuration
├── components/
│   └── LanguageSwitcher.tsx   # Language switcher component
└── [pages and components with translations]
```

### Key Components

1. **i18n/config.ts**: Configuration file that:
   - Sets up i18next with react-i18next
   - Configures language detection (localStorage + browser)
   - Defines translation resources
   - Sets fallback language to English

2. **LanguageSwitcher.tsx**: UI component that:
   - Displays current language
   - Allows users to switch languages
   - Persists choice to localStorage

3. **useTranslation Hook**: Used in components to:
   - Access translation functions
   - Display translated text via `t('key.path')`

## Usage Example

### In Components

```tsx
import { useTranslation } from "react-i18next";
import "@/i18n/config";

function MyComponent() {
  const { t } = useTranslation();
  
  return (
    <div>
      <h1>{t("navigation.usage")}</h1>
      <button>{t("common.save")}</button>
    </div>
  );
}
```

### Adding New Translations

Add translation keys to the `resources` object in `i18n/config.ts`:

```typescript
const resources = {
  en: {
    translation: {
      newKey: "English Text",
    },
  },
  "zh-CN": {
    translation: {
      newKey: "中文文本",
    },
  },
};
```

## Current Implementation

This POC includes:
- ✅ i18n framework setup (react-i18next)
- ✅ Language detection and persistence
- ✅ Language switcher component
- ✅ Example translations for navigation and common terms
- ✅ Support for English (en) and Simplified Chinese (zh-CN)

## Future Work (If Accepted)

If this architecture is approved, we would:

1. **Move translations to JSON files**:
   ```
   src/
   └── locales/
       ├── en/
       │   └── common.json
       └── zh-CN/
           └── common.json
   ```

2. **Complete translations for all UI pages**:
   - Usage page
   - Keys/Virtual Keys page
   - Teams page
   - Users page
   - Models page
   - Logs page
   - Settings pages
   - And more...

3. **Add more languages**:
   - Japanese (ja)
   - Korean (ko)
   - Spanish (es)
   - French (fr)
   - German (de)

4. **Add translation management**:
   - Pluralization support
   - Date/number formatting
   - RTL (right-to-left) language support

## Questions for Maintainers

1. **Do you approve of this architecture?**
   - Using react-i18next as the i18n solution
   - Storing translations inline vs external JSON files
   - Current translation key naming convention

2. **Would you like us to complete all translations?**
   - We can systematically translate all UI pages
   - This would be ~3000+ text strings across 700+ components

3. **Any concerns or suggestions?**
   - We welcome feedback on the approach
   - Happy to adjust the architecture based on your preferences

## Testing

To test this implementation:
1. Build the UI: `npm run build`
2. Start the proxy server
3. Open the dashboard in a browser
4. You should see a language switcher in the navbar
5. Click to switch between English and 简体中文

## Breaking Changes

**None**. This implementation is fully backwards compatible:
- Default language is English (existing behavior)
- No existing functionality is affected
- Translation keys are added incrementally

## Dependencies Added

```json
{
  "i18next": "^23.7.6",
  "i18next-browser-languagedetector": "^7.2.0",
  "react-i18next": "^14.0.0"
}
```

These are well-maintained, widely-used packages with minimal bundle size impact.

---

We're excited to contribute this feature to LiteLLM and look forward to your feedback! If this architecture is approved, we're ready to complete the full translation work.
