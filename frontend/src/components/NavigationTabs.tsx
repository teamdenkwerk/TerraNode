import React from 'react';
import { 
  UploadCloud, 
  Map as MapIcon, 
  Sparkles, 
  Split, 
  AlertCircle, 
  BarChart3, 
  FileText,
  MapPin,
  CheckCircle2,
  ArrowDown,
  X
} from 'lucide-react';
import { ActiveTab, Language, DatasetMeta } from '../types';
import { translations } from '../data/i18n';

interface NavigationTabsProps {
  activeTab: ActiveTab;
  onTabChange?: (tab: ActiveTab) => void;
  onChangeTab?: (tab: ActiveTab) => void;
  reviewCount?: number;
  reviewBadgeCount?: number;
  language: Language;
  activeDataset?: DatasetMeta;
  onClose?: () => void;
}

interface NavStep {
  id: ActiveTab;
  label: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: number;
}

export const NavigationTabs: React.FC<NavigationTabsProps> = ({
  activeTab,
  onTabChange,
  onChangeTab,
  reviewCount,
  reviewBadgeCount,
  language,
  activeDataset,
  onClose,
}) => {
  const count = reviewCount ?? reviewBadgeCount ?? 0;
  const t = translations[language] || translations.en;

  const handleSelect = (tab: ActiveTab) => {
    if (onTabChange) onTabChange(tab);
    if (onChangeTab) onChangeTab(tab);
  };

  // Canonical Navigation Flow without numbers
  const steps: NavStep[] = [
    { id: 'upload', label: t.tabUpload || 'Upload Documents', subtitle: t.tabUploadSub || 'Ingest Geo-Data', icon: UploadCloud },
    { id: 'gis', label: t.tabGis || 'GIS Explorer', subtitle: t.tabGisSub || 'Interactive Map', icon: MapIcon },
    { id: 'harmonization', label: t.tabHarmonization || 'Harmonization', subtitle: t.tabHarmonizationSub || 'Unified Boundaries', icon: Sparkles },
    { id: 'review', label: t.tabReview || 'Review & Verification', subtitle: t.tabReviewSub || 'Conflict Queue', icon: AlertCircle, badge: count },
    { id: 'validation', label: language === 'hi' ? 'परिवर्तन पहचान' : 'Change Detection', subtitle: language === 'hi' ? 'देखा गया स्थानिक परिवर्तन' : 'Observed Spatial Change', icon: Split },
    { id: 'analytics', label: t.tabAnalytics || 'Land Insights', subtitle: 'Land Data Insights', icon: BarChart3 },
    { id: 'reports', label: t.tabReports || 'Reports', subtitle: t.tabReportsSub || 'Audit & Certs', icon: FileText },
  ];

  // Normalize aliases
  const normalizedActive = 
    activeTab === 'data' ? 'upload' : 
    activeTab === 'map' ? 'gis' : 
    activeTab === 'dashboard' ? 'gis' :
    activeTab;

  return (
    <aside 
      aria-label="Workflow Stages" 
      className="w-64 sm:w-72 bg-[#FAF8F3] border-r border-[#E7DFD3] flex flex-col h-full shrink-0 select-none z-20 shadow-2xs"
    >
      {/* Sidebar Header */}
      <div className="p-4 border-b border-[#E7DFD3] flex items-center justify-between bg-[#F7F2EA]">
        <div>
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#A86236] block">
            {t.pipeline || 'WORKFLOW PIPELINE'}
          </span>
          <span className="text-xs font-bold text-[#241D16]">
            {t.stages || 'Reconciliation Stages'}
          </span>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#7D7063] hover:text-[#241D16] hover:bg-[#EAE2D5] transition cursor-pointer"
            title="Close Workflow Pipeline"
            aria-label="Close Workflow Pipeline"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Vertical Navigation Steps List */}
      <nav className="flex-1 overflow-y-auto no-scrollbar p-3 space-y-1">
        {steps.map((item) => {
          const Icon = item.icon;
          const isActive = normalizedActive === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => handleSelect(item.id)}
              className={`w-full group flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all duration-150 cursor-pointer border ${
                isActive
                  ? 'bg-white border-[#A86236]/30 shadow-xs'
                  : 'border-transparent text-[#7D7063] hover:text-[#241D16] hover:bg-[#F4EEE6]'
              }`}
              aria-current={isActive ? 'page' : undefined}
            >
              {/* Step Icon */}
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition ${
                isActive 
                  ? 'bg-[#FDF1EB] text-[#A86236]' 
                  : 'bg-[#EFE9DF]/60 text-[#7D7063] group-hover:bg-[#E5DDCF] group-hover:text-[#241D16]'
              }`}>
                <Icon className="w-4 h-4" />
              </div>

              {/* Step Label & Subtitle */}
              <div className="flex-1 min-w-0">
                <div className={`text-xs truncate tracking-tight ${
                  isActive ? 'font-bold text-[#241D16]' : 'font-semibold text-[#4A3E31]'
                }`}>
                  {item.label}
                </div>
                <div className="text-[10px] text-[#A39688] truncate">
                  {item.subtitle}
                </div>
              </div>

              {/* Review Queue Badge */}
              {item.badge !== undefined && item.badge > 0 && (
                <span className={`px-1.5 py-0.5 rounded-full font-mono text-[10px] font-bold border shrink-0 transition ${
                  isActive
                    ? 'bg-[#FDF1EB] text-[#C87958] border-[#F0CFC2]'
                    : 'bg-[#F0EBE2] text-[#7D7063] border-[#E7DFD3]'
                }`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Sidebar Footer / Active AOI Indicator */}
      <div className="p-3 border-t border-[#E7DFD3] bg-[#F7F2EA]">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-2 h-2 rounded-full bg-[#3F6452] animate-pulse" />
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#3F6452]">
            {t.online ? `${t.online.toUpperCase()} ENGINE` : 'ENGINE ONLINE'}
          </span>
        </div>
        {activeDataset && (
          <div className="text-[11px] font-mono text-[#7D7063] truncate">
            {activeDataset.city} · {activeDataset.aoi}
          </div>
        )}
      </div>
    </aside>
  );
};
