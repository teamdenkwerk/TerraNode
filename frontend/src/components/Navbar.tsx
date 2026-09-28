import React from 'react';
import { 
  Layers, 
  ChevronDown, 
  ShieldCheck, 
  LogOut,
  FolderOpen
} from 'lucide-react';
import { Language, DatasetMeta } from '../types';
import { translations } from '../data/i18n';

interface NavbarProps {
  currentZone?: string;
  onZoneChange?: (zone: string) => void;
  datasets?: DatasetMeta[];
  activeDatasetId?: string;
  onSelectDataset?: (datasetId: string) => void;
  language: Language;
  onLanguageChange?: (lang: Language) => void;
  onToggleLanguage?: () => void;
  isOnline?: boolean;
  onToggleOnline?: () => void;
  onLogout?: () => void;
  onOpenUpload?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  datasets = [],
  activeDatasetId,
  onSelectDataset,
  language,
  onToggleLanguage,
  isOnline = true,
  onLogout,
  onOpenUpload,
}) => {
  const currentDataset = datasets.find(d => d.id === activeDatasetId) || datasets[0];
  const t = translations[language] || translations.en;

  return (
    <header className="w-full bg-[#FAF8F3] border-b border-[#E7DFD3] sticky top-0 z-40 select-none shadow-2xs">
      <div className="w-full px-4 sm:px-6 flex items-center justify-between h-16 gap-3">
        
        {/* ============================================================== */}
        {/* LEFT SECTION: BRAND (Starts directly from left edge, no gap)    */}
        {/* ============================================================== */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Circular TerraNode Official Logo */}
          <div className="w-9 h-9 rounded-full overflow-hidden bg-white border border-[#E7DFD3] shadow-xs flex items-center justify-center shrink-0">
            <img 
              src="/terranode_logo.png" 
              alt="TerraNode Logo" 
              className="w-full h-full object-cover rounded-full"
            />
          </div>

          <div className="flex flex-col">
            <div className="flex items-baseline leading-none">
              <span className="font-extrabold text-base tracking-tight text-[#241D16] font-sans">
                TERRA<span className="text-[#A86236]">NODE</span>
              </span>
            </div>
            <span className="text-[8.5px] uppercase tracking-wider text-[#7D7063] font-semibold font-mono mt-0.5 leading-none">
              {t.subTitle || 'GEOSPATIAL RECONCILIATION & FIELD INTELLIGENCE'}
            </span>
          </div>
        </div>

        {/* ============================================================== */}
        {/* RIGHT SECTION: DATASET SELECTOR, LOCALE, STATUS, ADMIN, LOGOUT */}
        {/* ============================================================== */}
        <div className="flex items-center gap-2 shrink-0">
          
          {/* Dataset / AOI Selector */}
          <div className="relative flex items-center bg-[#F4EEE6] hover:bg-[#EFE7DC] border border-[#E7DFD3] rounded-lg px-2.5 py-1.5 transition text-xs">
            <Layers className="w-3.5 h-3.5 text-[#A86236] mr-1.5 shrink-0" />
            {datasets && datasets.length > 1 && onSelectDataset ? (
              <>
                <select 
                  aria-label="Dataset / AOI"
                  value={activeDatasetId || datasets[0].id}
                  onChange={(e) => onSelectDataset(e.target.value)}
                  className="bg-transparent font-semibold text-[#241D16] focus:outline-none cursor-pointer pr-4 text-xs font-mono max-w-[210px] sm:max-w-none truncate"
                >
                  {datasets.map((ds) => (
                    <option key={ds.id} className="bg-[#FAF8F3] text-[#241D16]" value={ds.id}>
                      {ds.city} — {ds.aoi}
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-3 h-3 text-[#7D7063] absolute right-2 pointer-events-none" />
              </>
            ) : (
              <span className="font-semibold text-[#241D16] font-mono text-xs pr-1">
                {currentDataset ? `${currentDataset.city} — ${currentDataset.aoi}` : 'Indian Urban'}
              </span>
            )}
          </div>

          {/* Change Area / Import Folder Button */}
          {onOpenUpload && (
            <button
              type="button"
              onClick={onOpenUpload}
              className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold font-mono rounded-lg border border-[#A86236]/30 bg-[#F4EEE6] hover:bg-[#EFE7DC] text-[#A86236] transition cursor-pointer shadow-2xs"
              title="Import New City / Manage Active Workspace"
            >
              <FolderOpen className="w-3.5 h-3.5 text-[#A86236]" />
              <span>{t.importAoi || 'IMPORT / AOI'}</span>
            </button>
          )}

          {/* Language Toggle (EN / HI) */}
          <button
            type="button"
            onClick={onToggleLanguage}
            className="px-2 py-1 text-xs font-bold font-mono rounded-lg border border-[#E7DFD3] bg-[#F4EEE6] hover:bg-[#EFE7DC] text-[#241D16] transition cursor-pointer"
            title={language === 'en' ? 'हिन्दी में बदलें (Switch to Hindi)' : 'Switch to English'}
          >
            {language === 'en' ? 'EN' : 'हि'}
          </button>

          {/* Online Indicator (Green only for Online status) */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-[#CBE0D3] bg-[#F2F7F4] text-[#3F6452] text-xs font-semibold font-mono shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-[#3F6452] animate-pulse" />
            <span className="hidden sm:inline">{t.online || 'Online'}</span>
          </div>

          {/* Administrator Role Badge */}
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-[#EAD9B8] bg-[#FDF8F3] text-[#A86236] text-[11px] font-mono font-bold shrink-0">
            <ShieldCheck className="w-3.5 h-3.5 text-[#A86236]" />
            <span className="hidden sm:inline">{t.adminRole || 'ADMIN'}</span>
          </div>

          {/* Logout Icon Button */}
          {onLogout && (
            <button
              type="button"
              onClick={onLogout}
              className="p-1.5 rounded-lg text-[#7D7063] hover:text-[#241D16] hover:bg-[#F4EEE6] transition cursor-pointer"
              title={t.signOut || 'Sign Out of Session'}
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}

        </div>

      </div>
    </header>
  );
};
