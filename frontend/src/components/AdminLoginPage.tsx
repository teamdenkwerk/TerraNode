import React, { useState, useEffect } from 'react';
import { 
  ArrowRight, 
  Eye, 
  EyeOff, 
  HelpCircle, 
  Plus, 
  Minus, 
  UserCheck
} from 'lucide-react';
import indianUrbanAerialImage from '../assets/indian_urban_aerial.jpg';
import indianUrbanCadastralImage from '../assets/indian_urban_cadastral.jpg';
import './AdminLoginPage.css';

interface AdminLoginPageProps {
  onLoginSuccess: () => void;
}

export const AdminLoginPage: React.FC<AdminLoginPageProps> = ({ onLoginSuccess }) => {
  const [officerId, setOfficerId] = useState('admin');
  const [password, setPassword] = useState('••••••••');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberDevice, setRememberDevice] = useState(true);
  const [activeSlide, setActiveSlide] = useState(0);
  const [zoomScale, setZoomScale] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  const slides = [
    {
      image: indianUrbanAerialImage,
      kicker: 'Indian Urban Change & Cadastre',
      title: 'Selected Parcel: Survey No. 420 · Indian Urban',
      detail: 'Temporal urban change reconciled against municipal cadastre & high-res drone orthomosaic.',
      plot: {
        viewBox: '0 0 576 1024',
        boundaries: [
          'M 40 330 L 220 310 L 235 440 L 55 460 Z',
          'M 55 470 L 235 450 L 250 580 L 70 600 Z',
          'M 350 310 L 530 330 L 515 460 L 335 440 Z',
          'M 335 450 L 515 470 L 500 600 L 320 580 Z',
        ],
        selected: 'M 55 470 L 235 450 L 250 580 L 70 600 Z',
        marker: { x: 155, y: 520 },
        label: 'SURVEY NO. 420',
        labelAt: { x: 180, y: 495 },
      }
    },
    {
      image: indianUrbanCadastralImage,
      kicker: 'Indian Urban Change Detection',
      title: 'High-Resolution Drone Orthophoto (5cm GSD) · Indian Urban',
      detail: '5cm Ground Sample Distance orthomosaic verified against CORS RTK rover logs & property records.',
      plot: {
        viewBox: '0 0 576 1024',
        boundaries: [
          'M 130 260 L 285 250 L 300 390 L 145 400 Z',
          'M 310 250 L 465 240 L 480 380 L 325 390 Z',
          'M 140 420 L 295 410 L 310 560 L 155 570 Z',
          'M 320 410 L 475 400 L 490 550 L 335 560 Z',
        ],
        selected: 'M 140 420 L 295 410 L 310 560 L 155 570 Z',
        marker: { x: 225, y: 485 },
        label: 'CTS / TS-420',
        labelAt: { x: 250, y: 455 },
      }
    }
  ];

  // Auto-switch between the 2 Indian urban pictures every 3.0 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveSlide((prev) => (prev + 1) % slides.length);
    }, 3000);
    return () => clearInterval(timer);
  }, [slides.length]);

  const current = slides[activeSlide];

  const handleSignIn = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsSubmitting(true);
    setInfoMessage(null);

    // Save session in sessionStorage so fresh open starts on Login Page
    sessionStorage.setItem('terranode_admin_session', JSON.stringify({
      authenticated: true,
      officerId: officerId || 'admin',
      role: 'Administrator',
      timestamp: Date.now()
    }));
    try {
      localStorage.removeItem('terranode_admin_session');
    } catch {
      // ignore
    }

    setTimeout(() => {
      setIsSubmitting(false);
      onLoginSuccess();
    }, 450);
  };

  const handleQuickRole = (roleId: string, email: string) => {
    setOfficerId(email);
    setPassword('••••••••');
    localStorage.setItem('terranode_admin_session', JSON.stringify({
      authenticated: true,
      officerId: email,
      role: roleId,
      timestamp: Date.now()
    }));
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      onLoginSuccess();
    }, 400);
  };

  return (
    <div className="terranode-login-portal">
      
      {/* LEFT SIDE: City / Aerial Survey Visualizer */}
      <section className="portal-carousel-side">
        {/* Brand Top Left */}
        <div className="portal-brand-mark">
          <div className="w-11 h-11 rounded-full overflow-hidden bg-white border-2 border-white/60 shadow-md shrink-0">
            <img 
              src="/terranode_logo.png" 
              alt="TerraNode Logo" 
              className="w-full h-full object-cover rounded-full"
            />
          </div>
          <div>
            <div className="portal-brand-name">TERRANODE</div>
            <div className="portal-brand-sub">LAND RECORDS / FIELD INTELLIGENCE</div>
          </div>
        </div>

        {/* Cross-fading Indian Urban Survey Images */}
        {slides.map((slide, idx) => (
          <img
            key={idx}
            src={slide.image}
            alt={slide.title}
            className="portal-carousel-image"
            style={{
              opacity: activeSlide === idx ? 1 : 0,
              zIndex: activeSlide === idx ? 1 : 0,
              pointerEvents: 'none',
              transform: `scale(${zoomScale === 1 ? (activeSlide === idx ? 1.04 : 1.0) : 1.1})`,
              transition: 'opacity 0.7s ease-in-out, transform 3.0s cubic-bezier(0.25, 1, 0.5, 1)'
            }}
          />
        ))}

        {/* SVG Plot Overlay */}
        <svg
          key={activeSlide}
          className="portal-plot-overlay animate-fadeIn"
          viewBox={current.plot.viewBox}
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          {current.plot.boundaries.map((b, i) => (
            <path key={i} className="portal-plot-boundary" d={b} />
          ))}
          <path className="portal-plot-selected" d={current.plot.selected} />
          <path
            className="portal-plot-leader"
            d={`M ${current.plot.marker.x} ${current.plot.marker.y} L ${current.plot.labelAt.x} ${current.plot.labelAt.y}`}
          />
          <circle className="portal-plot-pin-halo" cx={current.plot.marker.x} cy={current.plot.marker.y} r="9" />
          <circle className="portal-plot-pin-core" cx={current.plot.marker.x} cy={current.plot.marker.y} r="3" />
          <g transform={`translate(${current.plot.labelAt.x} ${current.plot.labelAt.y})`}>
            <rect className="portal-plot-label-bg" x="0" y="-17" width="116" height="22" rx="4" />
            <text className="portal-plot-label" x="8" y="-3">{current.plot.label}</text>
          </g>
        </svg>

        {/* Floating Interactive Parcel Focus Callout Mini-Map */}
        <div
          className="portal-map-callout"
          style={{ transform: `rotate(1.5deg) scale(${zoomScale})` }}
          aria-label="Parcel focus map"
        >
          <div className="portal-parcel portal-parcel-a" />
          <div className="portal-parcel portal-parcel-b" />
          <div className="portal-parcel portal-parcel-c" />
          <div className="portal-parcel portal-parcel-d" />
          <div className="portal-parcel portal-parcel-selected" />
          <div className="portal-map-pin" aria-hidden="true" />
          <span className="portal-map-label">PARCEL FOCUS / 420</span>
          <span className="portal-map-scale">100 m</span>
          
          <div className="portal-map-tools">
            <button
              type="button"
              className="portal-map-tool"
              aria-label="Zoom in"
              onClick={() => setZoomScale(s => (s === 1 ? 1.06 : 1))}
            >
              <Plus size={13} strokeWidth={2.6} />
            </button>
            <button
              type="button"
              className="portal-map-tool"
              aria-label="Zoom out"
              onClick={() => setZoomScale(1)}
            >
              <Minus size={13} strokeWidth={2.6} />
            </button>
          </div>
        </div>

        {/* Caption at bottom-left */}
        <div key={activeSlide} className="portal-caption-wrap animate-fadeIn">
          <div className="portal-caption-kicker">{current.kicker}</div>
          <h2 className="portal-caption-title">{current.title}</h2>
          <p className="text-xs text-white/85 mt-2 max-w-md leading-relaxed">{current.detail}</p>
        </div>

        {/* Watermark */}
        <div className="portal-watermark">
          ONE PARCEL. ONE TRUSTED VIEW.
        </div>

        {/* Slide Indicator Dots with 3.0s timer badge */}
        <div className="absolute right-8 bottom-8 z-10 flex items-center gap-2">
          {slides.map((_, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setActiveSlide(idx)}
              className={`h-2 rounded-full transition-all duration-300 relative overflow-hidden ${
                activeSlide === idx ? 'w-10 bg-amber-400 shadow-sm shadow-amber-400/50' : 'w-2.5 bg-white/40 hover:bg-white/70'
              }`}
              aria-label={`Slide ${idx + 1}`}
            >
              {activeSlide === idx && (
                <div 
                  key={`${idx}-${activeSlide}`}
                  className="absolute inset-0 bg-white/60 origin-left animate-slide-progress" 
                  style={{ animationDuration: '3.0s' }}
                />
              )}
            </button>
          ))}
          <span className="text-[10px] font-mono tracking-wider font-semibold text-amber-300 ml-1.5 bg-black/60 px-2 py-0.5 rounded-full border border-amber-400/30 backdrop-blur-sm shadow-sm">
            3.0s
          </span>
        </div>
      </section>

      {/* RIGHT SIDE: Officer Access Form */}
      <main className="portal-login-side">
        <div className="portal-login-shell">
          
          {/* Header */}
          <header className="portal-login-header">
            <div className="portal-login-wordmark flex items-center gap-3">
              <div className="w-12 h-12 rounded-full overflow-hidden bg-white border border-[#E7DFD3] shadow-xs shrink-0">
                <img 
                  src="/terranode_logo.png" 
                  alt="TerraNode Logo" 
                  className="w-full h-full object-cover rounded-full"
                />
              </div>
              <div>
                <span className="portal-login-wordmark-text">TERRANODE</span>
                <span className="block text-[10px] text-[#7D7063] font-mono tracking-wider font-semibold">AI URBAN RECONCILIATION</span>
              </div>
            </div>
            
            <h1 className="portal-login-title">Welcome back.</h1>

            {/* Ministry of Rural Development Official Institutional Identity */}
            <div className="mt-3 mb-2 flex items-center justify-start">
              <img 
                src="/ministry_of_rural_development_clean.png" 
                onError={(e) => {
                  (e.target as HTMLImageElement).src = '/ministry_of_rural_development.png';
                }}
                alt="ग्रामीण विकास मंत्रालय / Ministry of Rural Development — Government of India" 
                className="h-14 sm:h-16 w-auto object-contain max-w-full drop-shadow-2xs"
              />
            </div>
          </header>

          {/* Form Card */}
          <form className="portal-login-card" onSubmit={handleSignIn} noValidate>
            
            {/* Officer ID / Email */}
            <div className="portal-field-group">
              <label className="portal-field-label" htmlFor="officer-id">
                Officer ID / Email
              </label>
              <input
                id="officer-id"
                name="officerId"
                type="text"
                className="portal-field-input"
                placeholder="Enter officer ID or email"
                value={officerId}
                onChange={(e) => setOfficerId(e.target.value)}
                autoComplete="username"
                required
              />
            </div>

            {/* Password */}
            <div className="portal-field-group">
              <label className="portal-field-label" htmlFor="password">
                Password
              </label>
              <div className="portal-password-wrap">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  className="portal-field-input"
                  placeholder="Enter password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="portal-password-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Options */}
            <div className="portal-form-options">
              <label className="portal-remember-label">
                <input
                  type="checkbox"
                  className="portal-remember-checkbox"
                  checked={rememberDevice}
                  onChange={(e) => setRememberDevice(e.target.checked)}
                />
                <span>Remember this device</span>
              </label>
              <button
                type="button"
                className="portal-forgot-link"
                onClick={() => setInfoMessage("Password reset request logged. Verification token dispatched to nodal administrator.")}
              >
                Forgot password?
              </button>
            </div>

            {infoMessage && (
              <div className="mb-4 p-3 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-lg animate-in fade-in">
                {infoMessage}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="portal-submit-button"
            >
              <span>{isSubmitting ? "Authenticating Node…" : "Sign In"}</span>
              <ArrowRight size={15} strokeWidth={2.4} />
            </button>

            {/* Demo User 1-Click Access Button */}
            <div className="portal-quick-access">
              <button
                type="button"
                onClick={() => handleQuickRole('Demo User', 'demo@terranode.gov.in')}
                className="portal-quick-header"
                title="1-Click Demo User Login"
              >
                <UserCheck size={14} className="text-[#a86236]" />
                <span>Demo User</span>
              </button>
            </div>

            {/* Help / Access Note */}
            <div className="portal-access-note">
              <HelpCircle size={14} />
              <span>Need access? Contact your department administrator.</span>
            </div>

          </form>

          {/* Footer */}
          <footer className="portal-login-footer">
            <div />
          </footer>

        </div>
      </main>

    </div>
  );
};

export default AdminLoginPage;
