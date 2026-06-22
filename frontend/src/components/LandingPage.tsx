import React, { useState, useEffect } from 'react';
import { Sparkles, CheckCircle, ArrowRight } from 'lucide-react';

interface LandingPageProps {
  onStartChat: (initialQuery?: string) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onStartChat }) => {
  // Calculator States
  const [loanAmount, setLoanAmount] = useState<number>(5000000); // 50 Lakhs default
  const [interestRate, setInterestRate] = useState<number>(8.5); // 8.5% default
  const [tenure, setTenure] = useState<number>(20); // 20 years default

  const [emi, setEmi] = useState<number>(0);
  const [totalInterest, setTotalInterest] = useState<number>(0);
  const [totalPayable, setTotalPayable] = useState<number>(0);

  // Calculate EMI
  useEffect(() => {
    const P = loanAmount;
    const R = interestRate;
    const Y = tenure;
    
    const monthlyRate = R / 12 / 100;
    const numberOfMonths = Y * 12;

    if (monthlyRate === 0) {
      setEmi(P / numberOfMonths);
      setTotalPayable(P);
      setTotalInterest(0);
      return;
    }

    const calculatedEmi = (P * monthlyRate * Math.pow(1 + monthlyRate, numberOfMonths)) / 
                         (Math.pow(1 + monthlyRate, numberOfMonths) - 1);
    
    const calculatedTotalPayable = calculatedEmi * numberOfMonths;
    const calculatedTotalInterest = calculatedTotalPayable - P;

    setEmi(calculatedEmi);
    setTotalPayable(calculatedTotalPayable);
    setTotalInterest(calculatedTotalInterest);
  }, [loanAmount, interestRate, tenure]);

  // Format functions
  const formatEmi = (val: number) => {
    return `₹${Math.round(val).toLocaleString('en-IN')}`;
  };

  const formatLakhsCrores = (val: number) => {
    if (val >= 10000000) {
      return `₹${(val / 10000000).toFixed(1)} Cr`;
    }
    return `₹${(val / 100000).toFixed(1)} L`;
  };

  const formatAmountSlider = (val: number) => {
    if (val >= 10000000) {
      return `₹${(val / 10000000).toFixed(1)} Cr`;
    }
    return `₹${(val / 100000).toFixed(1)} L`;
  };

  return (
    <div className="min-h-screen bg-[#fafbfc] text-gray-800 font-sans overflow-x-hidden relative">
      {/* Decorative Blur Backgrounds */}
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-blue-100/30 rounded-full blur-3xl pointer-events-none -z-10" />
      <div className="absolute top-[30%] right-[-10%] w-[600px] h-[600px] bg-indigo-100/30 rounded-full blur-3xl pointer-events-none -z-10" />

      {/* Header */}
      <header className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between border-b border-gray-100 bg-white/70 backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#3b82f6] flex items-center justify-center shadow-md shadow-blue-500/10">
            <span className="text-white font-black text-lg">N</span>
          </div>
          <div>
            <p className="text-base font-extrabold text-gray-900 tracking-tight leading-none mb-1">National Bank</p>
            <p className="text-xs font-semibold text-gray-400">BankWise AI</p>
          </div>
        </div>
        <button 
          onClick={() => onStartChat()}
          className="bg-[#1e3a6e] hover:bg-[#152950] text-white px-5 py-2.5 rounded-full text-sm font-bold flex items-center gap-2 transition-all shadow-md shadow-blue-900/10 active:scale-95"
        >
          Talk to BankWise AI <ArrowRight className="w-4 h-4" />
        </button>
      </header>

      {/* Hero Section */}
      <section className="max-w-4xl mx-auto px-6 pt-16 pb-20 text-center flex flex-col items-center">
        <h1 className="text-5xl md:text-6xl font-extrabold text-gray-900 tracking-tight leading-[1.15] mb-6">
          Banking, but <span className="font-serif italic font-normal text-[#1e3a6e]">finally</span> intelligent.
        </h1>
        
        <p className="text-lg md:text-xl text-gray-500 max-w-2xl leading-relaxed mb-10 font-medium">
          Get pre-approved for a home loan — chat with BankWise AI, upload your documents, and walk into your new home without paperwork battles.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 mb-12">
          <button 
            onClick={() => onStartChat("Apply for a loan")}
            className="bg-[#1e3a6e] hover:bg-[#152950] text-white px-8 py-4 rounded-full text-base font-bold flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-900/15 active:scale-98"
          >
            Start with BankWise AI <ArrowRight className="w-5 h-5" />
          </button>
          <a 
            href="#calculator"
            className="bg-white border border-gray-200 hover:border-gray-300 text-gray-700 px-8 py-4 rounded-full text-base font-bold flex items-center justify-center gap-2 transition-all shadow-sm active:scale-98"
          >
            Calculate EMI 
            <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </a>
        </div>

        {/* Security/Features Row */}
        <div className="flex flex-wrap items-center justify-center gap-8 text-sm text-gray-500 font-semibold border-t border-gray-100 pt-8 w-full max-w-xl">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-500" />
            <span>256-bit secure</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-500" />
            <span>Zero hidden fees</span>
          </div>
        </div>
      </section>

      {/* Loan Products Section */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="mb-12">
          <p className="text-[#b28741] text-xs font-black tracking-widest uppercase mb-2">Loan Products</p>
          <h2 className="text-3xl font-extrabold text-gray-900 leading-tight">
            The right loan, <span className="font-serif italic font-normal text-[#1e3a6e]">tailored.</span>
          </h2>
          <p className="text-gray-500 font-medium max-w-xl mt-3 text-sm leading-relaxed">
            From dream homes to business growth, our AI matches you to the most competitive offer in the country — in real time.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Home Loan Card */}
          <div className="bg-white border border-gray-100 rounded-3xl p-8 hover:shadow-xl hover:border-gray-250 transition-all duration-300 group flex flex-col justify-between">
            <div>
              <div className="w-12 h-12 rounded-2xl bg-[#1e3a6e]/5 flex items-center justify-center mb-6">
                <svg className="w-6 h-6 text-[#1e3a6e]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Home Loan</h3>
              <p className="text-gray-500 text-sm font-medium leading-relaxed mb-8">
                Buy, build, renovate. 30-year tenure with flexible part-payment options tailored for your needs.
              </p>
            </div>
            
            <div>
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-[#fafbfc] p-4 rounded-2xl">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Starting</p>
                  <p className="text-lg font-black text-gray-900">7.95%</p>
                </div>
                <div className="bg-[#fafbfc] p-4 rounded-2xl">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Up To</p>
                  <p className="text-lg font-black text-gray-900">₹10 Cr</p>
                </div>
              </div>
              <button 
                onClick={() => onStartChat("Tell me about Home Loans")}
                className="text-[#1e3a6e] font-extrabold text-sm flex items-center gap-1 group-hover:gap-2 transition-all"
              >
                Explore <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Loan Against Property Card */}
          <div className="bg-white border border-gray-100 rounded-3xl p-8 hover:shadow-xl hover:border-gray-250 transition-all duration-300 group flex flex-col justify-between">
            <div>
              <div className="w-12 h-12 rounded-2xl bg-[#1e3a6e]/5 flex items-center justify-center mb-6">
                <svg className="w-6 h-6 text-[#1e3a6e]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Loan Against Property</h3>
              <p className="text-gray-500 text-sm font-medium leading-relaxed mb-8">
                Unlock your property value for business expansion, education, wedding, or high-value financial requirements.
              </p>
            </div>

            <div>
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-[#fafbfc] p-4 rounded-2xl">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Starting</p>
                  <p className="text-lg font-black text-gray-900">9.25%</p>
                </div>
                <div className="bg-[#fafbfc] p-4 rounded-2xl">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Up To</p>
                  <p className="text-lg font-black text-gray-900">₹15 Cr</p>
                </div>
              </div>
              <button 
                onClick={() => onStartChat("Tell me about Loan Against Property (LAP)")}
                className="text-[#1e3a6e] font-extrabold text-sm flex items-center gap-1 group-hover:gap-2 transition-all"
              >
                Explore <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Try Before You Ask & EMI Calculator Section */}
      <section id="calculator" className="max-w-6xl mx-auto px-6 py-20 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        {/* Left explanation column */}
        <div className="lg:col-span-5">
          <p className="text-[#b28741] text-xs font-black tracking-widest uppercase mb-2">Try Before You Ask</p>
          <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 leading-tight mb-6">
            Know exactly what you'll pay — <span className="font-serif italic font-normal text-[#1e3a6e]">upfront.</span>
          </h2>
          <p className="text-gray-500 font-medium text-sm leading-relaxed mb-8">
            No hidden surprises. Slide the dials, see real numbers, and when you're ready, hand it over to our AI to lock the offer.
          </p>

          <ul className="space-y-4">
            {[
              "Pre-approved offers based on verified details",
              "Real-time interest rate calculations",
              "Compare different loan products side-by-side"
            ].map((bullet, idx) => (
              <li key={idx} className="flex items-center gap-3 text-sm font-semibold text-gray-700">
                <div className="w-5 h-5 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                </div>
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Right calculator column */}
        <div className="lg:col-span-7 bg-white border border-gray-150 rounded-3xl p-8 shadow-xl shadow-gray-100/50">
          <div className="flex items-center gap-2 mb-6">
            <Sparkles className="w-5 h-5 text-[#b28741] fill-[#b28741]/10" />
            <p className="text-xs font-black text-gray-400 uppercase tracking-widest">Instant Calculator</p>
          </div>

          <h3 className="text-2xl font-extrabold text-gray-900 mb-8">
            Plan your EMI <span className="font-serif italic font-normal text-[#1e3a6e]">in seconds.</span>
          </h3>

          <div className="space-y-8">
            {/* Amount Slider */}
            <div>
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs font-bold text-gray-400 uppercase">Loan Amount</span>
                <span className="text-sm font-black text-gray-900">{formatAmountSlider(loanAmount)}</span>
              </div>
              <input 
                type="range"
                min={1000000} // 10 L
                max={100000000} // 10 Cr
                step={500000}
                value={loanAmount}
                onChange={(e) => setLoanAmount(Number(e.target.value))}
                className="w-full h-1.5 bg-gray-100 rounded-lg appearance-none cursor-pointer accent-[#1e3a6e]"
              />
            </div>

            {/* Interest Slider */}
            <div>
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs font-bold text-gray-400 uppercase">Interest Rate</span>
                <span className="text-sm font-black text-gray-900">{interestRate.toFixed(2)} %</span>
              </div>
              <input 
                type="range"
                min={5.0}
                max={15.0}
                step={0.05}
                value={interestRate}
                onChange={(e) => setInterestRate(Number(e.target.value))}
                className="w-full h-1.5 bg-gray-100 rounded-lg appearance-none cursor-pointer accent-[#1e3a6e]"
              />
            </div>

            {/* Tenure Slider */}
            <div>
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs font-bold text-gray-400 uppercase">Tenure</span>
                <span className="text-sm font-black text-gray-900">{tenure} years</span>
              </div>
              <input 
                type="range"
                min={1}
                max={30}
                step={1}
                value={tenure}
                onChange={(e) => setTenure(Number(e.target.value))}
                className="w-full h-1.5 bg-gray-100 rounded-lg appearance-none cursor-pointer accent-[#1e3a6e]"
              />
            </div>
          </div>

          <div className="border-t border-dashed border-gray-200 my-8 pt-8 grid grid-cols-3 gap-4">
            <div>
              <p className="text-[10px] font-bold text-gray-400 uppercase mb-1">Monthly EMI</p>
              <p className="text-lg font-black text-gray-900 truncate">{formatEmi(emi)}</p>
            </div>
            <div>
              <p className="text-[10px] font-bold text-gray-400 uppercase mb-1">Total Interest</p>
              <p className="text-lg font-black text-gray-900 truncate">{formatLakhsCrores(totalInterest)}</p>
            </div>
            <div>
              <p className="text-[10px] font-bold text-gray-400 uppercase mb-1">Total Payable</p>
              <p className="text-lg font-black text-gray-900 truncate">{formatLakhsCrores(totalPayable)}</p>
            </div>
          </div>

          <button 
            onClick={() => onStartChat(`Check eligibility for a Home Loan of ${formatAmountSlider(loanAmount)} at ${interestRate}% for ${tenure} years`)}
            className="w-full py-4 rounded-xl bg-gradient-to-tr from-[#1e3a6e] to-[#254f96] hover:brightness-110 text-white font-bold text-sm shadow-md transition-all active:scale-[0.98]"
          >
            Apply Now
          </button>
        </div>
      </section>

      {/* Footer copyright */}
      <footer className="text-center py-10 border-t border-gray-100 text-xs text-gray-400 font-medium">
        <p>© 2026 National Bank. All rights reserved. Demo Project.</p>
      </footer>
    </div>
  );
};
